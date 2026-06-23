"""
Batch AI Cleaning — continuous loop until all chunks done.
"""
import os, sys, time
import pymysql
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.config import DB_CONFIG as DB, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL  # noqa: E402

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

PROMPT = "Perbaiki teks OCR rusak dari dokumen pemerintah Indonesia. Output HANYA teks bersih, tanpa kata pembuka.\n\nATURAN:\n1. Perbaiki error OCR umum: PRTORTTAS->PRIORITAS, ldeoIogi->Ideologi, Demolqasi->Demokrasi, PRES!DEN->PRESIDEN, REPU BLIK->REPUBLIK, INOONESIA->INDONESIA, FRESIDEN->PRESIDEN, FEPUBLTK->REPUBLIK\n2. PERTAHANKAN SEMUA angka, kode (01.01.01), jumlah Rp, persentase APA ADANYA\n3. JANGAN tambah, kurang, ringkas, atau ubah struktur teks\n4. JANGAN beri kata pembuka seperti Tentu, Berikut, Baik, atau penjelasan apapun\n\nTeks: {text}\n\nTeks bersih:"

def clean(text):
    try:
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": PROMPT.format(text=text[:6000])}],
            temperature=0.1, max_tokens=4000
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        return None

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    
    batch_size = 8
    total_done = 0
    
    while True:
        cur.execute("SELECT c.id, c.text FROM deepseek_policy_chunks c WHERE c.clean_text_ai IS NULL AND c.token_estimate > 50 ORDER BY CASE c.level_hint WHEN 'PN' THEN 1 WHEN 'PP' THEN 2 WHEN 'KP' THEN 3 ELSE 4 END, c.id LIMIT " + str(batch_size))
        chunks = cur.fetchall()
        
        if not chunks:
            print("ALL CLEANED!")
            break
        
        ok = 0
        for chunk_id, text in chunks:
            cleaned = clean(text)
            if cleaned:
                cur.execute("UPDATE deepseek_policy_chunks SET clean_text_ai=%s, oc_text=1, model_used='deepseek-chat', cleaned_at=NOW() WHERE id=%s", (cleaned, chunk_id))
                conn.commit()
                ok += 1
        
        total_done += ok
        cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NULL AND token_estimate > 50")
        remaining = cur.fetchone()[0]
        print("[total=%d, remaining=%d] batch: %d/%d" % (total_done, remaining, ok, len(chunks)))
        
        if remaining == 0:
            break
    
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NOT NULL")
    print("FINAL: %d chunks cleaned" % cur.fetchone()[0])
    conn.close()

if __name__ == "__main__":
    main()
