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
import json, requests, time, sys

from common.config import TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS
from common.db import get_connection
from common.verdict import parse_verdict
from common.kl_context import get_kl_mandate_context

# === CONFIG ===
MODEL        = "oss120b"
TREASURY_URL = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
TREASURY_KEY = TREASURAI_API_KEY
LIMIT_WEAK   = int(sys.argv[1]) if len(sys.argv) > 1 else 50

SYSTEM_PROMPT = """Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. \
Analisis hasil deteksi anomali alignment DIPA vs RPJMN/RKP.

Untuk setiap item:
1. Jelaskan kenapa alignment rendah
2. Tentukan: anomali valid, false positive, atau perlu review manual
3. Beri rekomendasi 1 kalimat

Jawaban maksimal 4 kalimat, Bahasa Indonesia formal."""

conn = get_connection()
cur  = conn.cursor()

# Ambil: semua policy_orphan (prioritas utama) + weak_alignment top-N by review_priority
# Keduanya harus llm_reasoning IS NULL
cur.execute("""
    SELECT a.id, a.anomaly_type, a.kementerian_kode, a.kementerian_uraian,
           a.alignment_score, a.review_priority,
           (SELECT p.alignment_text FROM ddac_pagu_akun_2026 p WHERE p.id = a.pagu_id) AS txt,
           a.best_match_name, a.top3_matches
    FROM ddac_anomaly_2026 a
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

for i, (aid, atype, kl, kl_name, score, prio, txt, best_kp, top3_json) in enumerate(items):
    top3       = json.loads(top3_json) if top3_json else []
    type_label = "Policy Orphan" if atype == "policy_orphan" else "Weak Alignment"

    # Bangun prompt — konteks berbeda untuk orphan vs weak
    top3_lines = "".join(
        "- %s: %s (skor %s)\n" % (t.get("code",""), t.get("name","")[:100], t.get("score",""))
        for t in top3[:3]
    )

    # Konteks mandat K/L dari knowledge graph RPJMN/RKP
    mandate_ctx = get_kl_mandate_context(cur, kl)
    mandate_section = ("\n%s\n" % mandate_ctx) if mandate_ctx else ""

    if atype == "policy_orphan":
        question = (
            "Item ini tidak memiliki KP RPJMN/RKP yang cukup relevan (skor < 45 dan rank < P15). "
            "Berdasarkan mandat K/L di atas, apakah ini anomali valid "
            "(program di luar cakupan prioritas nasional) atau false positive "
            "akibat perbedaan nomenklatur DIPA vs RPJMN?"
        )
    else:
        question = (
            "Item ini memiliki alignment lemah (rank < P15, skor ≥ 45). "
            "Berdasarkan mandat K/L di atas, apakah ada penjelasan mengapa similaritynya rendah? "
            "Misalnya: perbedaan nomenklatur DIPA vs RPJMN, program lintas sektor, "
            "atau memang tidak ada payung prioritas nasionalnya?"
        )

    prompt = (
        "[%s] Item DIPA:\n"
        "K/L     : %s - %s\n"
        "Prog/Keg/Out: %s\n\n"
        "KP RPJMN/RKP terdekat (skor %.0f/100):\n%s\n\n"
        "Top-3 semantic match:\n%s"
        "%s\n"
        "%s"
    ) % (type_label, kl, kl_name or "", (txt or "")[:300],
         score, (best_kp or "")[:250], top3_lines,
         mandate_section, question)

    print("[%d/%d] %s [%s] prio=%.1f — %s..." % (
        i+1, len(items), kl, atype, prio, (txt or "")[:60]))

    try:
        r = requests.post(
            TREASURY_URL,
            json={
                "prompt": prompt, "session_id": None,
                "system_prompt": SYSTEM_PROMPT,
                "temperature": 0.1, "max_tokens": 1200,
            },
            headers={"Content-Type": "application/json", "X-API-Key": TREASURY_KEY},
            timeout=30,
        )
        if r.status_code == 200:
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
                "UPDATE ddac_anomaly_2026 "
                "SET llm_reasoning=%s, llm_model=%s, treasurai_verdict=%s, review_status=%s "
                "WHERE id=%s",
                (reasoning, MODEL, verdict, review_status, aid),
            )
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:180]))
        else:
            print("  HTTP %d: %s\n" % (r.status_code, r.text[:200]))
    except Exception as e:
        print("  ERR: %s\n" % str(e)[:200])

    time.sleep(0.3)

# Summary
print("=" * 60)
print("FINAL STATUS ddac_anomaly_2026")
print("=" * 60)
cur.execute("""
    SELECT anomaly_type,
           COUNT(*) AS total,
           SUM(CASE WHEN llm_reasoning IS NOT NULL THEN 1 ELSE 0 END) AS has_reasoning,
           SUM(CASE WHEN llm_model = %s THEN 1 ELSE 0 END) AS oss120b_count
    FROM ddac_anomaly_2026
    WHERE anomaly_type IN ('policy_orphan', 'weak_alignment')
    GROUP BY anomaly_type
""", (MODEL,))
for row in cur.fetchall():
    print("  %-20s: %s total | %d reasoning | %d oss120b" % (
        row[0], format(row[1], ","), row[2], row[3]))

conn.close()
