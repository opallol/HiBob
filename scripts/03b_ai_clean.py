"""
Phase 3b: AI OCR Cleaning via DeepSeek API
"""
import os, sys, argparse
from pathlib import Path
import pymysql
from openai import OpenAI

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

DB_CONFIG = {"host": "172.16.2.153", "user": "ddac26", "password": "p4ssw0rd!", "database": "ddac2026", "port": 3306, "charset": "utf8mb4"}

api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if not api_key:
    print("ERROR: DEEPSEEK_API_KEY not set"); sys.exit(1)

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

PROMPT = "Perbaiki teks OCR rusak dari dokumen pemerintah Indonesia. Output HANYA teks bersih, tanpa kata pembuka.\n\nATURAN:\n1. Perbaiki error OCR umum: PRTORTTAS->PRIORITAS, ldeoIogi->Ideologi, Demolqasi->Demokrasi, PRES!DEN->PRESIDEN, REPU BLIK->REPUBLIK, INOONESIA->INDONESIA\n2. PERTAHANKAN SEMUA angka, kode (01.01.01), jumlah Rp, persentase APA ADANYA\n3. JANGAN tambah, kurang, ringkas, atau ubah struktur teks\n4. JANGAN beri kata pembuka seperti Tentu, Berikut, Baik, atau penjelasan apapun\n\nTeks: {text}\n\nTeks bersih:"

def clean_chunk(text):
    try:
        text_in = text[:6000] if len(text) > 6000 else text
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": PROMPT.format(text=text_in)}],
            temperature=0.1, max_tokens=4000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("  API error: %s" % str(e)[:200])
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-id", type=int)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    if args.doc_id:
        where = "WHERE c.document_id = %d" % args.doc_id
    else:
        where = """WHERE c.document_id IN (SELECT id FROM deepseek_policy_documents WHERE attachment LIKE '%%Lampiran II%%' OR attachment LIKE '%%Lampiran I%%')"""
    
    query = """SELECT c.id, c.document_id, c.chunk_index, c.text, c.token_estimate, d.doc_family, d.attachment, c.level_hint
        FROM deepseek_policy_chunks c
        JOIN deepseek_policy_documents d ON c.document_id = d.id
        %s AND c.clean_text_ai IS NULL AND c.token_estimate > 50
        ORDER BY CASE c.level_hint WHEN 'PN' THEN 1 WHEN 'PP' THEN 2 WHEN 'KP' THEN 3 ELSE 4 END, c.document_id, c.chunk_index
        LIMIT %d""" % (where, args.limit)
    
    cur.execute(query)
    chunks = cur.fetchall()
    print("Chunks to clean: %d" % len(chunks))
    
    if args.dry_run:
        for c in chunks:
            print("  [%d] %s %s hint=%s tokens=%d" % (c[0], c[5], c[6], c[7], c[4]))
        conn.close(); return
    
    ok = 0
    for i, (chunk_id, doc_id, chunk_idx, text, tokens, family, attach, hint) in enumerate(chunks):
        print("[%d/%d] Chunk %d (%s %s, %d tokens)..." % (i+1, len(chunks), chunk_id, family, attach, tokens))
        cleaned = clean_chunk(text)
        if cleaned:
            cur.execute("UPDATE deepseek_policy_chunks SET clean_text_ai=%s, oc_text=1, model_used='deepseek-chat', cleaned_at=NOW() WHERE id=%s", (cleaned, chunk_id))
            conn.commit()
            ok += 1
            before = text.replace('\n', ' ')[:70]
            after = cleaned.replace('\n', ' ')[:70]
            print("  OK: %s -> %s" % (before, after))
        else:
            print("  FAIL")
    
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NOT NULL")
    total = cur.fetchone()[0]
    print("\nCleaned this run: %d | Total in DB: %d" % (ok, total))
    conn.close()

if __name__ == "__main__":
    main()
