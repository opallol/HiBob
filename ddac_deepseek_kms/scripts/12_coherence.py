"""
Internal Coherence Detection Pipeline
Deteksi anomali struktur internal DIPA: hierarki + jenis komponen + komposisi akun
Output: ddac_coherence_<year> (lihat BUDGET_YEAR di common/config.py)
"""
import time

from common.db import get_connection
from common.config import TABLE_PAGU_AKUN, TABLE_COHERENCE, TABLE_KMPNEN

T_PAGU     = TABLE_PAGU_AKUN
T_COH      = TABLE_COHERENCE
T_KMPNEN   = TABLE_KMPNEN


def main():
    conn = get_connection()
    cur = conn.cursor()
    t0 = time.time()
    
    # ============================================================
    # STEP 1: Create coherence table (dari pagu + join kmpnen)
    # ============================================================
    print("=== STEP 1: Creating table ===")
    cur.execute(f"DROP TABLE IF EXISTS {T_COH}")
    cur.execute(f"""
        CREATE TABLE {T_COH} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pagu_id INT NOT NULL,
            kementerian_kode CHAR(3) DEFAULT '',
            kementerian_uraian TEXT,
            program_kode CHAR(2) DEFAULT '',
            program_uraian TEXT,
            kegiatan_kode CHAR(4) DEFAULT '',
            kegiatan_uraian TEXT,
            outputkro_kode CHAR(3) DEFAULT '',
            outputkro_uraian VARCHAR(250) DEFAULT '',
            komponen_kode VARCHAR(10) DEFAULT '',
            komponen_uraian TEXT,
            jenis_komponen VARCHAR(20) DEFAULT '',
            total_pagu DECIMAL(65,2) DEFAULT 0,
            prog_keg_coherence DECIMAL(5,2) DEFAULT NULL,
            keg_out_coherence DECIMAL(5,2) DEFAULT NULL,
            out_komp_coherence DECIMAL(5,2) DEFAULT NULL,
            akun_komposisi_score DECIMAL(5,2) DEFAULT NULL,
            akun_detail JSON,
            jenis_anomaly VARCHAR(50) DEFAULT '',
            jenis_anomaly_score DECIMAL(5,2) DEFAULT 0,
            coherence_score DECIMAL(5,2) DEFAULT 0,
            anomaly_flags JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_pagu (pagu_id), INDEX idx_kl (kementerian_kode),
            INDEX idx_coherence (coherence_score), INDEX idx_jenis (jenis_anomaly)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    print("[%.0fs] Table created" % (time.time()-t0))

    # Build a small, indexed jenis_komponen lookup map first.
    # The full index on {T_KMPNEN} is (kddept, kdunit, kdprogram, ...), but the
    # pagu table has no kdunit, so a direct join breaks the index prefix and is
    # catastrophically slow over 1.5M rows. Pre-aggregating to a tiny PK-indexed
    # map keyed on the columns we actually join makes the lookup fast and correct.
    print("[%.0fs] Building jenis_komponen lookup map..." % (time.time()-t0))
    cur.execute("DROP TABLE IF EXISTS tmp_kmpnen_map")
    cur.execute("""
        CREATE TABLE tmp_kmpnen_map (
            kddept VARCHAR(3) NOT NULL,
            kdprogram VARCHAR(2) NOT NULL,
            kdgiat VARCHAR(4) NOT NULL,
            kdoutput VARCHAR(3) NOT NULL,
            kdkmpnen VARCHAR(20) NOT NULL,
            jenis_komponen VARCHAR(20) NOT NULL,
            PRIMARY KEY (kddept, kdprogram, kdgiat, kdoutput, kdkmpnen)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute(f"""
        INSERT INTO tmp_kmpnen_map
        SELECT kddept, kdprogram, kdgiat, kdoutput, kdkmpnen,
               MAX(CASE WHEN TRIM(jenis_komponen) = 'Utama' THEN 'Utama'
                        WHEN TRIM(jenis_komponen) = 'Pendukung' THEN 'Pendukung'
                   END)
        FROM {T_KMPNEN}
        WHERE TRIM(jenis_komponen) IN ('Utama', 'Pendukung')
        GROUP BY kddept, kdprogram, kdgiat, kdoutput, kdkmpnen
    """)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM tmp_kmpnen_map")
    print("[%.0fs] Map has %s rows" % (time.time()-t0, format(cur.fetchone()[0], ',')))

    # Populate {T_COH} from pagu, joining the small indexed map
    print(f"[%.0fs] Populating from {T_PAGU} + map..." % (time.time()-t0))
    cur.execute(f"""
        INSERT INTO {T_COH} (
            pagu_id, kementerian_kode, kementerian_uraian,
            program_kode, program_uraian,
            kegiatan_kode, kegiatan_uraian,
            outputkro_kode, outputkro_uraian,
            komponen_kode, komponen_uraian,
            jenis_komponen, total_pagu
        )
        SELECT 
            p.id, p.kementerian_kode, p.kementerian_uraian,
            p.program_kode, p.program_uraian,
            p.kegiatan_kode, p.kegiatan_uraian,
            p.outputkro_kode, p.outputkro_uraian,
            p.komponen_kode, p.komponen_uraian,
            COALESCE(m.jenis_komponen, 'none'),
            p.total_pagu
        FROM {T_PAGU} p
        LEFT JOIN tmp_kmpnen_map m 
            ON p.kementerian_kode = m.kddept 
            AND p.program_kode = m.kdprogram 
            AND p.kegiatan_kode = m.kdgiat 
            AND p.outputkro_kode = m.kdoutput
            AND p.komponen_kode = m.kdkmpnen
        WHERE p.total_pagu > 0
    """)
    conn.commit()
    cur.execute("DROP TABLE IF EXISTS tmp_kmpnen_map")
    conn.commit()
    
    cur.execute(f"SELECT COUNT(*) FROM {T_COH}")
    n = cur.fetchone()[0]
    print("[%.0fs] %s rows inserted" % (time.time()-t0, format(n, ',')))
    
    # ============================================================
    # STEP 2: Jenis Komponen Anomaly (rule-based)
    # Merujuk field jenis_komponen yang sudah dibersihkan ke 3 nilai
    # (Utama / Pendukung / none). 'none' tidak bisa dianalisis.
    # ============================================================
    print("\n=== STEP 2: Jenis Komponen Anomaly ===")
    
    # Count jenis_komponen
    cur.execute(f"SELECT jenis_komponen, COUNT(*) FROM {T_COH} GROUP BY jenis_komponen")
    for row in cur.fetchall():
        print("  %-15s: %s" % (row[0] or '(blank)', format(row[1], ',')))

    # Index dipakai oleh UPDATE klasifikasi (join per KL/program/output/jenis).
    cur.execute(f"""ALTER TABLE {T_COH}
        ADD INDEX idx_grp (kementerian_kode, program_kode, outputkro_kode, jenis_komponen)""")
    conn.commit()

    # 'none' = jenis_komponen tidak terdefinisi di sumber -> tak bisa dianalisis.
    cur.execute(f"""
        UPDATE {T_COH}
        SET jenis_anomaly = 'unclassified',
            jenis_anomaly_score = 20,
            coherence_score = 20
        WHERE jenis_komponen = 'none'
    """)
    conn.commit()
    print("[%.0fs] 'none' -> unclassified" % (time.time()-t0))

    # Total pagu per (KL, program, output) untuk komponen Utama+Pendukung.
    # Tabel kecil ber-PK supaya join klasifikasi cepat.
    cur.execute("DROP TABLE IF EXISTS tmp_out_total")
    cur.execute(f"""
        CREATE TABLE tmp_out_total (
            kementerian_kode CHAR(3), program_kode CHAR(2), outputkro_kode CHAR(3),
            total_pagu DECIMAL(65,2),
            PRIMARY KEY (kementerian_kode, program_kode, outputkro_kode)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        SELECT kementerian_kode, program_kode, outputkro_kode,
               SUM(total_pagu) AS total_pagu
        FROM {T_COH}
        WHERE jenis_komponen IN ('Utama', 'Pendukung')
        GROUP BY kementerian_kode, program_kode, outputkro_kode
    """)

    # Label per (KL, program, output, jenis) berdasar share pagu.
    cur.execute("DROP TABLE IF EXISTS tmp_flag")
    cur.execute(f"""
        CREATE TABLE tmp_flag (
            kementerian_kode CHAR(3), program_kode CHAR(2), outputkro_kode CHAR(3),
            jenis_komponen VARCHAR(20), label VARCHAR(50), score DECIMAL(5,2),
            PRIMARY KEY (kementerian_kode, program_kode, outputkro_kode, jenis_komponen)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        SELECT s.kementerian_kode, s.program_kode, s.outputkro_kode, s.jenis_komponen,
            CASE
                WHEN s.jenis_komponen='Pendukung' AND s.jenis_pagu/t.total_pagu > 0.5 THEN 'pendukung_dominan'
                WHEN s.jenis_komponen='Utama'     AND s.jenis_pagu/t.total_pagu < 0.1 THEN 'utama_kecil'
                ELSE 'normal'
            END AS label,
            CASE
                WHEN s.jenis_komponen='Pendukung' AND s.jenis_pagu/t.total_pagu > 0.5 THEN 85
                WHEN s.jenis_komponen='Utama'     AND s.jenis_pagu/t.total_pagu < 0.1 THEN 50
                ELSE 0
            END AS score
        FROM (
            SELECT kementerian_kode, program_kode, outputkro_kode, jenis_komponen,
                   SUM(total_pagu) AS jenis_pagu
            FROM {T_COH}
            WHERE jenis_komponen IN ('Utama', 'Pendukung')
            GROUP BY kementerian_kode, program_kode, outputkro_kode, jenis_komponen
        ) s
        JOIN tmp_out_total t
          ON s.kementerian_kode = t.kementerian_kode
         AND s.program_kode = t.program_kode
         AND s.outputkro_kode = t.outputkro_kode
    """)
    conn.commit()
    print("[%.0fs] Classification map built" % (time.time()-t0))

    # Satu UPDATE ber-index melabeli SEMUA baris Utama/Pendukung sekaligus
    # (normal / pendukung_dominan / utama_kecil). Tidak ada sisa blank.
    cur.execute(f"""
        UPDATE {T_COH} c
        JOIN tmp_flag f
          ON c.kementerian_kode = f.kementerian_kode
         AND c.program_kode = f.program_kode
         AND c.outputkro_kode = f.outputkro_kode
         AND c.jenis_komponen = f.jenis_komponen
        SET c.jenis_anomaly = f.label,
            c.jenis_anomaly_score = f.score,
            c.coherence_score = f.score
    """)
    conn.commit()
    cur.execute("DROP TABLE IF EXISTS tmp_flag")
    cur.execute("DROP TABLE IF EXISTS tmp_out_total")
    conn.commit()
    print("[%.0fs] Anomaly labels applied" % (time.time()-t0))
    
    # ============================================================
    # STEP 3: Results
    # ============================================================
    print("\n" + "=" * 60)
    print("RESULTS: JENIS KOMPONEN ANOMALY")
    print("=" * 60)
    
    cur.execute(f"""
        SELECT jenis_anomaly, COUNT(*) as cnt,
               CAST(SUM(total_pagu) AS DOUBLE) as tp
        FROM {T_COH}
        GROUP BY jenis_anomaly ORDER BY
            CASE jenis_anomaly
                WHEN 'pendukung_dominan' THEN 1
                WHEN 'utama_kecil' THEN 2
                WHEN 'unclassified' THEN 3
                ELSE 4 END
    """)
    for row in cur.fetchall():
        print("  %-20s: %8s | Rp %.1f T" % (row[0], format(row[1], ','), float(row[2])/1e12 if row[2] else 0))
    
    # Top pendukung_dominan
    print("\n=== TOP 10: PENDUDUKUNG DOMINAN ===")
    cur.execute(f"""
        SELECT kementerian_kode, LEFT(kementerian_uraian,25),
               program_kode, LEFT(program_uraian,30),
               outputkro_kode, LEFT(outputkro_uraian,25),
               LEFT(komponen_uraian,40), total_pagu
        FROM {T_COH}
        WHERE jenis_anomaly = 'pendukung_dominan'
        ORDER BY total_pagu DESC LIMIT 10
    """)
    for row in cur.fetchall():
        print("  %s %s" % (row[0], row[1]))
        print("    Prog:%s %s | Out:%s %s" % (row[2], row[3], row[4], row[5]))
        print("    Komp: %s | Rp %.0f M" % (row[6][:35], float(row[7])/1e6))
    
    # Top utama_kecil
    print("\n=== TOP 10: UTAMA KECIL ===")
    cur.execute(f"""
        SELECT kementerian_kode, LEFT(kementerian_uraian,25),
               program_kode, LEFT(program_uraian,30),
               outputkro_kode, LEFT(outputkro_uraian,25),
               LEFT(komponen_uraian,40), total_pagu
        FROM {T_COH}
        WHERE jenis_anomaly = 'utama_kecil'
        ORDER BY total_pagu DESC LIMIT 10
    """)
    for row in cur.fetchall():
        print("  %s %s" % (row[0], row[1]))
        print("    Prog:%s %s | Out:%s %s" % (row[2], row[3], row[4], row[5]))
        print("    Komp: %s | Rp %.0f M" % (row[6][:35], float(row[7])/1e6))
    
    print("\n[%.0fs] Pipeline complete!" % (time.time()-t0))
    print(f"Table: {T_COH}")
    conn.close()

if __name__ == "__main__":
    main()
