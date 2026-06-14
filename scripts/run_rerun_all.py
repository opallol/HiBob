"""
run_rerun_all.py — Orkestrator re-run reasoning pasca-audit (D1-D6), PARALEL.
Menjalankan reason_parallel.py (alignment lalu coherence) sampai TUNTAS.
Resume-safe; loop sampai 0 pending (menangkap item yang sempat ke-skip).

Reasoning HANYA via TreasurAI oss120b. Tidak ada DeepSeek.

Usage: python scripts/run_rerun_all.py [workers]
"""
import subprocess, sys, time
sys.path.insert(0, "scripts")
from common.config import DB_CONFIG
import pymysql

PY = sys.executable
WORKERS = sys.argv[1] if len(sys.argv) > 1 else "10"


def q1(sql):
    c = pymysql.connect(**DB_CONFIG); cur = c.cursor()
    cur.execute(sql); n = cur.fetchone()[0]; c.close(); return n


def align_remaining():
    return q1("""SELECT COUNT(*) FROM ddac_anomaly_2026
        WHERE anomaly_type IN ('weak_alignment','policy_orphan') AND llm_reasoning IS NULL""")


def coh_remaining():
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
          ) t2) AS total""")


def run(mode):
    subprocess.run([PY, "-u", "scripts/reason_parallel.py", mode, WORKERS], cwd=".")


def main():
    t0 = time.time()
    print("=== FASE 1: alignment (paralel x%s) ===" % WORKERS, flush=True)
    for _ in range(8):
        if align_remaining() == 0:
            break
        run("align")
    print("[align] selesai sisa=%d (%.0f min)" % (align_remaining(), (time.time()-t0)/60), flush=True)

    print("\n=== FASE 2: coherence (paralel x%s) ===" % WORKERS, flush=True)
    c = pymysql.connect(**DB_CONFIG); cur = c.cursor()
    cur.execute("""UPDATE ddac_coherence_2026
        SET llm_reasoning=NULL, treasurai_verdict=NULL, review_status_coherence='pending'
        WHERE llm_reasoning IS NOT NULL""")
    c.commit(); print("[coh] cleared %d rows" % cur.rowcount, flush=True); c.close()

    for _ in range(8):
        if coh_remaining() == 0:
            break
        run("coh")
    print("[coh] selesai sisa=%d" % coh_remaining(), flush=True)

    print("\n=== ORKESTRATOR SELESAI (%.0f menit) ===" % ((time.time()-t0)/60), flush=True)
    with open("rerun_done.flag", "w") as f:
        f.write("done %.0f min\n" % ((time.time()-t0)/60))


if __name__ == "__main__":
    main()
