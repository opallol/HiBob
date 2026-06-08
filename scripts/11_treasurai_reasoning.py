"""
TreasuryAI Reasoning Script
Run dari laptop yg terkoneksi network Kemenkeu.
Kirim top policy orphans ke TreasuryAI OSS 120B untuk reasoning.
Menyimpan reasoning bebas + verdict terstruktur (valid/false_positive/manual_review).
"""
import json, requests, time, sys

from common.config import TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS
from common.db import get_connection
from common.verdict import parse_verdict

# === CONFIG ===
MODEL = "oss120b"
TREASURY_URL = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
TREASURY_KEY = TREASURAI_API_KEY
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 15

SYSTEM_PROMPT = """Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. Analisis hasil deteksi anomali alignment DIPA vs RPJMN/RKP.

Untuk setiap item:
1. Jelaskan kenapa alignment rendah 
2. Tentukan: anomali valid, false positive, atau perlu review manual
3. Beri rekomendasi 1 kalimat

Jawaban maksimal 4 kalimat, Bahasa Indonesia formal."""

conn = get_connection()
cur = conn.cursor()

cur.execute("""
    SELECT a.id, a.kementerian_kode, a.kementerian_uraian, a.alignment_score,
           (SELECT alignment_text FROM ddac_pagu_akun_2026 WHERE id=a.pagu_id) as txt,
           a.best_match_name, a.top3_matches
    FROM ddac_anomaly_2026 a
    WHERE a.anomaly_type = 'policy_orphan' AND a.llm_reasoning IS NULL
    ORDER BY a.review_priority DESC LIMIT %d
""" % LIMIT)
orphans = cur.fetchall()
print("Found %d orphans needing reasoning\n" % len(orphans))

for i, (aid, kl, kl_name, score, txt, best_kp, top3_json) in enumerate(orphans):
    top3 = json.loads(top3_json) if top3_json else []
    
    prompt = f"Item DIPA:\nK/L: {kl} - {kl_name}\nProgram/Kegiatan: {txt[:300]}\n\nKP RKP terdekat (skor {score:.0f}/100):\n{best_kp[:250]}\n\nTop-3 semantic match:\n"
    for t in top3[:3]:
        prompt += f"- {t['code']}: {t['name'][:100]} (skor {t['score']})\n"
    prompt += "\nKenapa alignment rendah? Anomali valid atau false positive?"

    print("[%d/%d] %s — %s..." % (i+1, len(orphans), kl, txt[:60]))
    
    try:
        r = requests.post(TREASURY_URL, json={
            "prompt": prompt, "session_id": None,
            "system_prompt": SYSTEM_PROMPT,
            "temperature": 0.1, "max_tokens": 1200
        }, headers={"Content-Type": "application/json", "X-API-Key": TREASURY_KEY}, timeout=30)
        
        if r.status_code == 200:
            data = r.json()
            reasoning = data.get("response") or data.get("text") or data.get("content") or str(data)[:500]
            verdict = parse_verdict(reasoning)
            review_status = {"false_positive": "dismissed", "valid": "confirmed",
                             "manual_review": "needs_review"}.get(verdict, "pending")
            cur.execute(
                "UPDATE ddac_anomaly_2026 SET llm_reasoning=%s, llm_model=%s, "
                "treasurai_verdict=%s, review_status=%s WHERE id=%s",
                (reasoning[:2000], MODEL, verdict, review_status, aid))
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:180]))
        else:
            print("  HTTP %d: %s\n" % (r.status_code, r.text[:200]))
    except Exception as e:
        print("  ERR: %s\n" % str(e)[:200])
    time.sleep(0.3)

cur.execute("SELECT COUNT(*) FROM ddac_anomaly_2026 WHERE llm_reasoning IS NOT NULL")
print("Total with reasoning: %d" % cur.fetchone()[0])
conn.close()
