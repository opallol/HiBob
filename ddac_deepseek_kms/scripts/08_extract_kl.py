"""
08_extract_kl.py - Ekstraksi penugasan KP -> K/L pelaksana dari chunk KL_MATRIX.

Matriks Lampiran III RPJMN/RKP memasangkan tiap kode KP/PP (mis. 01.03.01) dengan
K/L pelaksana yang ditulis "<kddept> - <nama>" (mis. "129 - Kementerian Koordinator
Bidang Politik dan Keamanan"). Teks tabel hasil OCR berantakan, sehingga DeepSeek
dipakai untuk mengurai tiap chunk menjadi tuple terstruktur (code, kl_kode, kl_nama).
Kode lalu di-link ke node KP/PP dan K/L dinormalisasi terhadap ddac_pagu_akun_<year>.

Pemakaian:
  python 08_extract_kl.py --limit 3            # uji kecil (3 chunk)
  python 08_extract_kl.py --reset              # bangun ulang penuh (hapus dulu)
  python 08_extract_kl.py --doc-id 13 --limit 5
"""
import argparse
import json
import re
import time

from openai import OpenAI

from common.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, TABLE_PAGU_AKUN
from common.db import get_connection

T_PAGU = TABLE_PAGU_AKUN

SYSTEM_PROMPT = (
    "Anda mengekstrak data terstruktur dari matriks perencanaan pembangunan "
    "pemerintah Indonesia (Lampiran III RPJMN/RKP). Jawab HANYA dengan JSON valid, "
    "tanpa teks pembuka atau penjelasan."
)

USER_PROMPT = """Dari teks matriks berikut, ekstrak setiap baris yang memasangkan KODE Prioritas (PP/KP) dengan K/L pelaksana.

ATURAN:
- "code" = kode hierarki: PP (format NN.NN) atau KP (format NN.NN.NN). Pertahankan apa adanya.
- "kl_kode" = kode K/L (3 digit, mis. 059, 129). Ambil dari kolom UNIT/SATKER/PELAKSANA.
- "kl_nama" = nama K/L persis seperti tertulis.
- Satu code bisa punya >1 K/L -> buat baris terpisah untuk tiap K/L.
- Lewati baris tanpa kode atau tanpa K/L.
- Output HANYA array JSON: [{{"code":"01.03.01","kl_kode":"129","kl_nama":"Kementerian Koordinator Bidang Politik dan Keamanan"}}]
- Jika tidak ada pasangan, output: []

Teks matriks:
{text}

JSON:"""

CODE_RE = re.compile(r"^\d{2}\.\d{2}(\.\d{2})?$")


def parse_json_array(raw):
    """Robustly pull a JSON array out of an LLM response."""
    if not raw:
        return []
    s = raw.strip()
    # strip code fences
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    # isolate the outermost [...]
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(s[start:end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def extract_tuples(client, text):
    text_in = text[:6000]
    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(text=text_in)},
            ],
            temperature=0.0,
            max_tokens=4000,
        )
        return parse_json_array(resp.choices[0].message.content)
    except Exception as e:
        print("  API error: %s" % str(e)[:200])
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 = semua chunk KL_MATRIX")
    parser.add_argument("--doc-id", type=int)
    parser.add_argument("--reset", action="store_true", help="hapus kl_assignments dulu")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY:
        print("ERROR: DEEPSEEK_API_KEY belum di-set di .env")
        return

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    conn = get_connection()
    cur = conn.cursor()

    # --- Referensi K/L: kddept(3 digit) -> nama ---
    cur.execute(f"SELECT DISTINCT kementerian_kode, kementerian_uraian FROM {T_PAGU}")
    kl_ref = {}
    for kode, nama in cur.fetchall():
        if kode:
            kl_ref[str(kode).strip().zfill(3)] = nama
    print("K/L reference: %d entri" % len(kl_ref))

    # --- Node KP/PP: node_code -> (node_id, document_id) ---
    cur.execute("SELECT id, node_code, document_id FROM deepseek_policy_nodes WHERE node_type IN ('KP','PP')")
    node_map = {}
    for nid, code, doc in cur.fetchall():
        if code:
            node_map[code.strip()] = (nid, doc)
    print("Node KP/PP: %d" % len(node_map))

    # --- Chunk KL_MATRIX ---
    where = "WHERE level_hint='KL_MATRIX' AND clean_text_ai IS NOT NULL AND clean_text_ai != ''"
    if args.doc_id:
        where += " AND document_id = %d" % args.doc_id
    q = ("SELECT id, document_id, page_start, clean_text_ai FROM deepseek_policy_chunks "
         + where + " ORDER BY document_id, chunk_index")
    if args.limit:
        q += " LIMIT %d" % args.limit
    cur.execute(q)
    chunks = cur.fetchall()
    print("Chunk KL_MATRIX: %d\n" % len(chunks))

    if args.dry_run:
        for c in chunks:
            print("  chunk %d doc=%d page=%d" % (c[0], c[1], c[2]))
        conn.close()
        return

    if args.reset:
        cur.execute("DELETE FROM deepseek_policy_kl_assignments")
        conn.commit()
        print("kl_assignments dikosongkan.\n")

    stat = {"tuples": 0, "linked": 0, "kl_matched": 0, "no_node": 0, "inserted": 0}
    seen = set()  # (node_id, kddept) dedup

    for i, (cid, doc_id, page, text) in enumerate(chunks):
        tuples = extract_tuples(client, text)
        if tuples is None:
            print("[%d/%d] chunk %d: API FAIL" % (i + 1, len(chunks), cid))
            continue
        rows = []
        for t in tuples:
            if not isinstance(t, dict):
                continue
            code = str(t.get("code", "")).strip()
            kl_kode = re.sub(r"\D", "", str(t.get("kl_kode", "")))[:3].zfill(3) if t.get("kl_kode") else ""
            kl_nama = str(t.get("kl_nama", "")).strip()
            if not CODE_RE.match(code) or not (kl_kode != "000" and kl_kode):
                continue
            stat["tuples"] += 1

            node = node_map.get(code)
            if not node:
                stat["no_node"] += 1
                continue
            node_id, node_doc = node
            stat["linked"] += 1

            nm_norm = kl_ref.get(kl_kode)
            if nm_norm:
                stat["kl_matched"] += 1
            confidence = 0.9 if nm_norm else 0.6

            key = (node_id, kl_kode)
            if key in seen:
                continue
            seen.add(key)

            rows.append((doc_id, node_id, kl_kode, kl_nama, nm_norm or kl_nama,
                         "pelaksana", confidence, page,
                         ("KP/PP %s -> %s %s" % (code, kl_kode, kl_nama))[:500]))

        if rows:
            cur.executemany(
                """INSERT INTO deepseek_policy_kl_assignments
                   (document_id, node_id, kddept, nmdept_original, nmdept_normalized,
                    role, confidence, source_page, evidence)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
            conn.commit()
            stat["inserted"] += len(rows)
        print("[%d/%d] chunk %d doc=%d: %d tuple -> %d insert"
              % (i + 1, len(chunks), cid, doc_id, len(tuples), len(rows)))
        time.sleep(0.3)

    print("\n" + "=" * 50)
    print("SELESAI")
    print("  tuple valid     : %d" % stat["tuples"])
    print("  ter-link node   : %d" % stat["linked"])
    print("  K/L ter-normal  : %d" % stat["kl_matched"])
    print("  code tanpa node : %d" % stat["no_node"])
    print("  baris di-insert : %d" % stat["inserted"])
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_kl_assignments")
    print("  total di DB     : %d" % cur.fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
