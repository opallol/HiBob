"""
run_rerun_all.py — Orkestrator re-run reasoning pasca-audit (D1–D6).
Menjalankan ulang reasoning alignment (script 11) lalu coherence (script 15)
sampai TUNTAS, tahan terhadap stall/rate-limit TreasurAI (resume-safe).

Reasoning HANYA via TreasurAI oss120b (lihat script 11/15). Tidak ada DeepSeek.

Catatan: clear reasoning coherence dilakukan SEKALI di awal fase 2 agar
prompt/taksonomi baru (D2) diterapkan ke seluruh output.

Usage: python scripts/run_rerun_all.py
"""
import subprocess, sys, time
sys.path.insert(0, "scripts")
from common.config import DB_CONFIG
import pymysql

PY = sys.executable


def q1(sql):
    c = pymysql.connect(**DB_CONFIG); cur = c.cursor()
    cur.execute(sql); n = cur.fetchone()[0]; c.close(); return n


def align_remaining():
    return q1("""SELECT COUNT(*) FROM ddac_anomaly_2026
        WHERE anomaly_type IN ('weak_alignment','policy_orphan') AND llm_reasoning IS NULL""")


def coh_remaining():
    # L3 in-scope (akun_score>=40) + L1/L2 flagged, yang reasoning-nya NULL
    return q1("""
        SELECT
          (SELECT COUNT(*) FROM (
             SELECT 1 FROM ddac_coherence_akun_2026 ca
             JOIN ddac_coherence_2026 c
               ON c.kementerian_kode=ca.kementerian_kode AND c.program_kode=ca.program_kode
              AND c.kegiatan_kode=ca.kegiatan_kode AND c.outputkro_kode=ca.outputkro_kode
             WHERE ca.akun_komposisi_score>=40 AND c.llm_reasoning IS NULL
             GROUP BY ca.kementerian_kode, ca.program_kode, ca.kegiatan_kode, ca.outputkro_kode
          ) t1)
        +
          (SELECT COUNT(*) FROM (
             SELECT 1 FROM ddac_coherence_2026
             WHERE (JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level1_program_kegiatan_lemah'))
                 OR JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level2_kegiatan_output_lemah')))
               AND llm_reasoning IS NULL
             GROUP BY kementerian_kode, program_kode, kegiatan_kode, anomaly_flags
          ) t2) AS total
    """)


def run(cmd):
    print(">>> RUN:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=".")


def main():
    t0 = time.time()
    # ── FASE 1: ALIGNMENT ────────────────────────────────────────────────
    print("=== FASE 1: alignment reasoning ===", flush=True)
    last = -1
    for attempt in range(40):
        rem = align_remaining()
        print("[align] sisa NULL: %d (attempt %d)" % (rem, attempt), flush=True)
        if rem == 0:
            break
        if rem == last:
            # tidak ada kemajuan di pass sebelumnya — beri cooldown lalu lanjut
            time.sleep(20)
        last = rem
        run([PY, "-u", "scripts/11_treasurai_reasoning.py", "2000"])
    print("[align] SELESAI sisa=%d (%.0f menit)" % (align_remaining(), (time.time()-t0)/60), flush=True)

    # ── FASE 2: COHERENCE ────────────────────────────────────────────────
    print("\n=== FASE 2: coherence reasoning ===", flush=True)
    # Clear sekali agar taksonomi baru (D2) diterapkan menyeluruh
    c = pymysql.connect(**DB_CONFIG); cur = c.cursor()
    cur.execute("""UPDATE ddac_coherence_2026
        SET llm_reasoning=NULL, treasurai_verdict=NULL, review_status_coherence='pending'
        WHERE llm_reasoning IS NOT NULL""")
    c.commit(); print("[coh] cleared %d rows" % cur.rowcount, flush=True); c.close()

    last = -1
    for attempt in range(60):
        rem = coh_remaining()
        print("[coh] sisa in-scope NULL: %d (attempt %d)" % (rem, attempt), flush=True)
        if rem == 0:
            break
        if rem == last:
            time.sleep(20)
        last = rem
        run([PY, "-u", "scripts/15_coherence_reasoning.py", "1200", "500"])
    print("[coh] SELESAI sisa=%d" % coh_remaining(), flush=True)

    print("\n=== ORKESTRATOR SELESAI (%.0f menit) ===" % ((time.time()-t0)/60), flush=True)
    # Tulis penanda selesai
    with open("rerun_done.flag", "w") as f:
        f.write("done %.0f min\n" % ((time.time()-t0)/60))


if __name__ == "__main__":
    main()
