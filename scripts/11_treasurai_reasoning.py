"""
TreasurAI Reasoning — Policy Alignment Anomalies
Run dari laptop yang terkoneksi network Kemenkeu.

Scope:
  - policy_orphan : semua item (tanpa reasoning)
  - weak_alignment: top-N by review_priority (tanpa reasoning)

Model: oss120b

Usage:
  python scripts/11_treasurai_reasoning.py           # default top-50 weak + semua orphan
  python scripts/11_treasurai_reasoning.py 100       # top-100 weak_alignment
"""
import json, requests, time, sys, os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jeda antar-call (detik). Default 4s untuk menghindari burst-throttle TreasurAI.
PACE = float(os.environ.get("TREASURAI_PACE", "4"))

# Paksa UTF-8 untuk console Windows (karakter Unicode dari TreasurAI)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from common.config import TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS, TABLE_ANOMALY, TABLE_PAGU_AKUN
from common.db import get_connection

T_ANOMALY = TABLE_ANOMALY
T_PAGU    = TABLE_PAGU_AKUN
from common.verdict import parse_verdict
from common.kl_context import get_kl_mandate_context
from common.treasurai_call import call_with_timeout

# === CONFIG ===
MODEL        = "oss120b"
TREASURY_URL = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
TREASURY_KEY = TREASURAI_API_KEY
LIMIT_WEAK   = int(sys.argv[1]) if len(sys.argv) > 1 else 50

SYSTEM_PROMPT = """Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. \
Tugasmu menilai apakah satu item belanja DIPA selaras dengan mandat prioritas nasional \
(RPJMN/RKP) yang diberikan kepada K/L tersebut.

PENTING — skor kemiripan rendah BUKAN otomatis berarti tidak selaras. Skor bisa rendah \
hanya karena nomenklatur DIPA berbeda dari nama Kegiatan Prioritas, atau karena ini \
mekanisme pembiayaan (mis. jaminan/subsidi) yang melaksanakan suatu KP secara tidak langsung.

CATATAN PENTING soal daftar mandat:
- Daftar "Mandat K/L" yang diberikan BISA TIDAK LENGKAP. Lampiran III RPJMN ditulis \
sebelum reorganisasi kementerian Oktober 2024, sehingga sebagian K/L baru hasil pemekaran \
(mis. Kemendikdasmen, Kemendikti, Kemenbud, Kementerian Imigrasi) mewarisi tugas yang di \
RPJMN masih tercatat pada kementerian lama. Karena itu JANGAN simpulkan "valid" hanya karena \
sebuah belanja tidak tercantum di daftar mandat — pertimbangkan juga domain/tupoksi K/L \
tersebut dan KP terdekat secara substansi.

Tentukan SATU verdict (bersikap KONSERVATIF — hindari tuduhan keliru):
- false_positive : belanja secara substansi mendukung/melaksanakan suatu prioritas nasional \
di domain K/L ini (baik tercantum di mandat maupun wajar berdasarkan tupoksi), skor rendah \
hanya akibat beda nomenklatur atau karena ini mekanisme pembiayaan → bukan masalah.
- valid          : belanja JELAS di luar seluruh prioritas nasional DAN di luar domain/tupoksi \
inti K/L (tidak ada KP manapun yang relevan secara substansi) → perlu ditindaklanjuti.
- manual_review  : ada indikasi keterkaitan namun tidak cukup bukti untuk memutuskan, ATAU \
mandat K/L tampak tidak lengkap akibat reorganisasi → serahkan ke penilai manusia.

Format jawaban (Bahasa Indonesia formal, maksimal 4 kalimat):
1. Penjelasan singkat penyebab skor rendah dan kaitannya dengan mandat/domain K/L.
2. Rekomendasi 1 kalimat.
Lalu BARIS TERAKHIR wajib persis: VERDICT: valid | VERDICT: false_positive | VERDICT: manual_review"""

conn = get_connection()
cur  = conn.cursor()

# Ambil: semua policy_orphan (prioritas utama) + weak_alignment top-N by review_priority
# Keduanya harus llm_reasoning IS NULL
cur.execute(f"""
    SELECT a.id, a.anomaly_type, a.kementerian_kode, a.kementerian_uraian,
           a.alignment_score, a.review_priority,
           (SELECT p.alignment_text FROM {T_PAGU} p WHERE p.id = a.pagu_id) AS txt,
           a.best_match_name, a.top3_matches,
           a.mandate_match_code, a.mandate_match_name, a.mandate_match_score,
           a.anchored_on_mandate
    FROM {T_ANOMALY} a
    WHERE a.anomaly_type IN ('policy_orphan', 'weak_alignment')
      AND a.llm_reasoning IS NULL
    ORDER BY
        CASE a.anomaly_type WHEN 'policy_orphan' THEN 0 ELSE 1 END,
        a.review_priority DESC
    LIMIT %s
""", (LIMIT_WEAK,))
items = cur.fetchall()

print("Model   : %s" % MODEL)
print("Items   : %d (policy_orphan diprioritaskan, lalu weak_alignment by review_priority)" % len(items))
print("Limit   : %d weak_alignment\n" % LIMIT_WEAK)

for i, (aid, atype, kl, kl_name, score, prio, txt, best_kp, top3_json,
        mand_code, mand_name, mand_score, anchored) in enumerate(items):
    top3       = json.loads(top3_json) if top3_json else []
    type_label = "Policy Orphan" if atype == "policy_orphan" else "Weak Alignment"

    # Tetangga semantik lintas SEMUA K/L (informasi tambahan, bukan acuan utama)
    top3_lines = "".join(
        "- %s: %s (skor %s)\n" % (t.get("code",""), t.get("name","")[:100], t.get("score",""))
        for t in top3[:3]
    )

    # Konteks mandat K/L dari knowledge graph RPJMN/RKP — ACUAN UTAMA penilaian
    mandate_ctx = get_kl_mandate_context(cur, kl)
    mandate_section = (mandate_ctx + "\n") if mandate_ctx else \
        "Mandat K/L %s: TIDAK ADA penugasan KP eksplisit di RPJMN/RKP Lampiran III.\n" % kl

    # KP mandat terdekat = KP yang ditugaskan ke K/L ini yang paling mirip dgn belanja
    if mand_code:
        mandate_match_line = (
            "KP mandat K/L ini yang paling dekat dengan belanja ini: "
            "%s — %s (skor %.0f/100)\n" % (mand_code, (mand_name or "")[:120], float(mand_score or 0))
        )
    else:
        mandate_match_line = ""

    question = (
        "Nilai: apakah belanja DIPA ini termasuk dalam mandat RPJMN/RKP K/L tersebut? "
        "Jika ada KP mandat yang secara substansi mencakup/ dilaksanakan oleh belanja ini "
        "(meski beda nomenklatur atau berupa mekanisme pembiayaan) → false_positive. "
        "Jika benar-benar tidak ada KP mandat yang relevan → valid. "
        "Jika ragu → manual_review."
    )

    prompt = (
        "[%s] Item belanja DIPA:\n"
        "K/L          : %s - %s\n"
        "Prog/Keg/Out : %s\n"
        "Skor kemiripan tertinggi ke prioritas nasional manapun: %.0f/100\n\n"
        "=== MANDAT RPJMN/RKP K/L INI (acuan utama) ===\n"
        "%s"
        "%s\n"
        "=== Tetangga semantik lintas semua K/L (informasi tambahan) ===\n"
        "%s\n"
        "%s"
    ) % (type_label, kl, kl_name or "", (txt or "")[:300],
         score, mandate_section, mandate_match_line, top3_lines, question)

    print("[%d/%d] %s [%s] prio=%.1f — %s..." % (
        i+1, len(items), kl, atype, prio, (txt or "")[:60]))

    # Resilient: hard wall-clock timeout per call (tahan hang/throttle).
    # Item gagal tetap NULL → diambil lagi saat script di-run ulang (resume-safe).
    r, err = call_with_timeout(
        TREASURY_URL,
        {"prompt": prompt, "session_id": None,
         "system_prompt": SYSTEM_PROMPT, "temperature": 0.1, "max_tokens": 700},
        {"Content-Type": "application/json", "X-API-Key": TREASURY_KEY},
    )
    try:
        if r is not None and r.status_code == 200:
            data     = r.json()
            reasoning = (data.get("response") or data.get("text")
                         or data.get("content") or str(data))[:2000]
            verdict      = parse_verdict(reasoning)
            review_status = {
                "false_positive": "dismissed",
                "valid":          "confirmed",
                "manual_review":  "needs_review",
            }.get(verdict, "pending")
            cur.execute(
                f"UPDATE {T_ANOMALY} "
                "SET llm_reasoning=%s, llm_model=%s, treasurai_verdict=%s, review_status=%s "
                "WHERE id=%s",
                (reasoning, MODEL, verdict, review_status, aid),
            )
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:500]))
        elif r is not None:
            print("  HTTP %d: %s\n" % (r.status_code, r.text[:200]))
        else:
            print("  SKIP (%s, akan diulang di run berikutnya)\n" % err)
    except Exception as e:
        print("  ERR: %s\n" % str(e)[:200])

    time.sleep(PACE)   # jeda antar-call agar tidak memicu burst-throttle TreasurAI

# Summary
print("=" * 60)
print(f"FINAL STATUS {T_ANOMALY}")
print("=" * 60)
cur.execute(f"""
    SELECT anomaly_type,
           COUNT(*) AS total,
           SUM(CASE WHEN llm_reasoning IS NOT NULL THEN 1 ELSE 0 END) AS has_reasoning,
           SUM(CASE WHEN llm_model = %s THEN 1 ELSE 0 END) AS oss120b_count
    FROM {T_ANOMALY}
    WHERE anomaly_type IN ('policy_orphan', 'weak_alignment')
    GROUP BY anomaly_type
""", (MODEL,))
for row in cur.fetchall():
    print("  %-20s: %s total | %d reasoning | %d oss120b" % (
        row[0], format(row[1], ","), row[2], row[3]))

conn.close()
