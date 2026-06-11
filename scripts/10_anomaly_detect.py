"""
Anomaly Detection Pipeline
Embeds pagu texts -> cosine similarity vs KP nodes -> classify anomalies.

Model: LazarusNLP/all-indo-e5-small (query: prefix)
Menghasilkan distribusi skor lebih lebar (std ~10-15) dibanding bge-m3 (std ~2.5),
sehingga threshold percentile lebih bermakna. KP vectors di-embed ulang saat runtime
agar vector space konsisten dengan pagu texts.

Perubahan dari versi sebelumnya:
  - Fix 1A: ganti bge-m3 -> e5-small, re-embed KP at runtime (bukan dari DB)
  - Fix 1B: K/L 999 (BAUN) dikategorikan treasury_crosscutting, bukan policy_orphan;
            tambah absolute score floor (< ABS_FLOOR) sebagai syarat kedua policy_orphan
  - Fix 1C: pre-fetch semua K/L info sebelum loop (hapus N+1 query)
  - Fix 1D: ganti ROUTINE_KEYWORDS (text mining) -> kode resmi DIPA:
            outputkro_kode LIKE 'EB%' ATAU program_uraian LIKE '%Dukungan Manajemen%'.
            Verifikasi: 2,738 item (49% routine_support) salah label karena keyword
            broad seperti 'pembinaan', 'pengelolaan', 'koordinasi'; 68% di antaranya
            sebenarnya aligned ke KP (moderate/strong).
"""
import json
import time

import numpy as np
from sentence_transformers import SentenceTransformer

from common.db import get_connection

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
MODEL_NAME    = "LazarusNLP/all-indo-e5-small"
QUERY_PREFIX  = "query: "

# Percentile cut-offs (rank dalam distribusi skor aktual).
PCT = {"strong": 85, "moderate": 50, "weak": 15}

# Absolute floor: item hanya bisa jadi policy_orphan jika skor JUGA di bawah
# nilai ini. Mencegah item dengan skor cukup tinggi tapi kebetulan rank rendah
# karena distribusi terkompres.
# Fix D1 (2026-06-11): Turun dari 50 → 45 setelah verifikasi menunjukkan semua
# 20 orphan saat ini memiliki skor 45-50 dan sebenarnya adalah false positive:
# - Rp 4.21T "Wajib Belajar 13 Tahun" (Kemendikdasmen) → nomenklatur DIPA ≠ nama KP RPJMN,
#   tapi semantik jelas pendidikan (→ KP 04.01.01, skor 47). Harusnya weak_alignment.
# - Rp 1.5T "Modernisasi Alutsista" (Kemhan) → borderline ke PN 02 (skor 48-49).
# Verifikasi: tidak ada item dengan skor < 45 yang memenuhi kondisi orphan,
# sehingga menurunkan floor ke 45 tidak menghilangkan orphan sejati.
ABS_FLOOR = 45.0

# K/L yang berfungsi sebagai bendahara negara / cross-cutting treasury —
# fungsi ini tidak memetakan ke KP prioritas spesifik RPJMN/RKP.
TREASURY_KL = {"999"}

# Klasifikasi spending_nature menggunakan kode resmi DIPA, bukan keyword text mining.
# Verifikasi DB (2026-06-11): 2,738 item (49% dari routine_support) salah klasifikasi
# hanya karena keyword — 68% di antaranya sebenarnya moderate/strong alignment.
# EB* = kode resmi Kemenkeu untuk output dukungan internal (EBA/EBB/EBC/EBD).
ROUTINE_EB_PREFIX = "EB"
ROUTINE_PROGRAM_PATTERN = "dukungan manajemen"


def _ensure_verdict_column(cur):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=DATABASE() AND table_name='ddac_anomaly_2026'
             AND column_name='treasurai_verdict'""")
    if cur.fetchone()[0] == 0:
        cur.execute("ALTER TABLE ddac_anomaly_2026 "
                    "ADD COLUMN treasurai_verdict VARCHAR(20) NULL AFTER llm_model")


def main():
    conn = get_connection()
    cur  = conn.cursor()
    t0   = time.time()

    # ------------------------------------------------------------------
    # STEP 1: Load model + embed KP nodes at runtime
    # ------------------------------------------------------------------
    print("=== STEP 1: Loading %s ===" % MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)
    print("[%.0fs] model ready" % (time.time() - t0))

    cur.execute("""
        SELECT n.id, n.node_type, n.node_code,
               COALESCE(n.clean_node_name_ai, n.node_name) AS display_name,
               n.source_type
        FROM deepseek_policy_nodes n
        WHERE n.node_type = 'KP'
    """)
    kp_rows = cur.fetchall()
    print("Embedding %d KP nodes with %s ..." % (len(kp_rows), MODEL_NAME))

    kp_texts = [QUERY_PREFIX + r[3] for r in kp_rows]
    kp_vecs  = model.encode(kp_texts, normalize_embeddings=True,
                            batch_size=64, show_progress_bar=False,
                            convert_to_numpy=True).astype(np.float32)
    kp_info  = [{"id": r[0], "type": r[1], "code": r[2],
                 "name": r[3], "source": r[4]} for r in kp_rows]
    print("[%.0fs] KP vectors ready (%d)" % (time.time() - t0, len(kp_rows)))

    # ------------------------------------------------------------------
    # STEP 2: Unique alignment texts + embed
    # ------------------------------------------------------------------
    print("\n=== STEP 2: Embedding unique pagu texts ===")
    cur.execute("""
        SELECT alignment_text, COUNT(*) AS cnt,
               SUM(total_pagu) AS total_pagu, MIN(id) AS sample_id
        FROM ddac_pagu_akun_2026
        WHERE alignment_text != '' AND alignment_text IS NOT NULL
        GROUP BY alignment_text
    """)
    texts     = cur.fetchall()
    print("%d unique texts to embed" % len(texts))

    unique_texts = [t[0] for t in texts]
    text_info    = [{"text": t[0], "count": t[1],
                     "total_pagu": float(t[2]), "sample_id": t[3]}
                    for t in texts]

    prefixed    = [QUERY_PREFIX + t for t in unique_texts]
    pagu_vecs   = model.encode(prefixed, normalize_embeddings=True,
                               batch_size=64, show_progress_bar=True,
                               convert_to_numpy=True).astype(np.float32)
    print("[%.0fs] Embedded %d texts" % (time.time() - t0, len(pagu_vecs)))

    # ------------------------------------------------------------------
    # Fix 1C: Pre-fetch semua K/L info sekaligus (hapus N+1 query)
    # ------------------------------------------------------------------
    sample_ids = [ti["sample_id"] for ti in text_info]
    ph = ",".join(["%s"] * len(sample_ids))
    cur.execute(
        "SELECT id, kementerian_kode, kementerian_uraian, "
        "program_kode, kegiatan_kode, total_pagu, "
        "outputkro_kode, program_uraian "
        "FROM ddac_pagu_akun_2026 WHERE id IN (%s)" % ph,
        sample_ids)
    kl_lookup = {r[0]: r for r in cur.fetchall()}
    print("[%.0fs] K/L lookup pre-fetched (%d rows)" % (time.time() - t0, len(kl_lookup)))

    # ------------------------------------------------------------------
    # STEP 3: Cosine similarity
    # ------------------------------------------------------------------
    print("\n=== STEP 3: Computing cosine similarity ===")
    sim_matrix   = np.dot(pagu_vecs, kp_vecs.T)          # (N_texts, N_kp)
    top3_indices = np.argsort(-sim_matrix, axis=1)[:, :3]
    top3_scores  = np.take_along_axis(sim_matrix, top3_indices, axis=1)
    print("[%.0fs] Similarity computed" % (time.time() - t0))

    best_scores = top3_scores[:, 0].astype(np.float64) * 100
    sorted_bs   = np.sort(best_scores)
    n_bs        = len(sorted_bs)
    thr = {k: float(np.percentile(best_scores, p)) for k, p in PCT.items()}
    print("Score distribution: min=%.1f  p15=%.1f  p50=%.1f  p85=%.1f  max=%.1f  std=%.2f"
          % (best_scores.min(), thr["weak"], thr["moderate"], thr["strong"],
             best_scores.max(), best_scores.std()))
    print("Percentile thresholds: strong>=%.1f  moderate>=%.1f  weak>=%.1f  abs_floor=%.1f"
          % (thr["strong"], thr["moderate"], thr["weak"], ABS_FLOOR))

    def pct_rank(score):
        return float(np.searchsorted(sorted_bs, score, side="right")) / n_bs * 100

    # ------------------------------------------------------------------
    # STEP 4: Preserve existing TreasurAI reasoning
    # ------------------------------------------------------------------
    print("\n=== STEP 4: Classifying & inserting anomalies ===")
    _ensure_verdict_column(cur)
    conn.commit()
    cur.execute(
        """SELECT p.alignment_text, a.llm_reasoning, a.llm_model,
                  a.treasurai_verdict, a.review_status
           FROM ddac_anomaly_2026 a
           JOIN ddac_pagu_akun_2026 p ON a.pagu_id = p.id
           WHERE a.llm_reasoning IS NOT NULL""")
    preserved = cur.fetchall()
    print("Preserving %d existing reasonings" % len(preserved))

    cur.execute("DELETE FROM ddac_anomaly_2026")

    batch        = []
    total_ins    = 0
    batch_size   = 500
    max_pagu     = max((ti["total_pagu"] for ti in text_info), default=1)
    max_pagu     = max(max_pagu, 1)

    for i, ti in enumerate(text_info):
        scores  = [float(s * 100) for s in top3_scores[i]]
        indices = [int(idx) for idx in top3_indices[i]]

        best_score = scores[0]
        best_kp    = kp_info[indices[0]]
        rank       = pct_rank(best_score)

        # Alignment strength (relative)
        if rank >= PCT["strong"]:
            strength = "strong"
        elif rank >= PCT["moderate"]:
            strength = "moderate"
        elif rank >= PCT["weak"]:
            strength = "weak"
        else:
            strength = "none"

        # Spending nature: gunakan kode resmi DIPA bukan keyword text mining.
        # outputkro_kode EB* = output internal by definition (EBA/EBB/EBC/EBD).
        # "Program Dukungan Manajemen" = program overhead resmi di setiap K/L.
        kl_row         = kl_lookup.get(ti["sample_id"])
        kl_kode        = kl_row[1] if kl_row else ""
        outputkro_kode = (kl_row[6] or "") if kl_row else ""
        program_uraian = (kl_row[7] or "") if kl_row else ""

        if kl_kode in TREASURY_KL:
            nature = "treasury_crosscutting"
        elif (outputkro_kode.upper().startswith(ROUTINE_EB_PREFIX) or
              ROUTINE_PROGRAM_PATTERN in program_uraian.lower()):
            nature = "routine_support"
        else:
            nature = "substantive"

        # Anomaly type — Fix 1B: absolute floor untuk policy_orphan
        if nature in ("routine_support", "treasury_crosscutting"):
            atype = "routine"
        elif strength == "none" and best_score < ABS_FLOOR:
            # Rendah secara relatif DAN absolut → orphan sejati
            atype = "policy_orphan"
        elif strength == "none" or strength == "weak":
            # Rendah relatif tapi skor masih di atas floor → lemah bukan orphan
            atype = "weak_alignment"
        else:
            atype = "aligned"

        # Scores
        materiality    = np.log(ti["total_pagu"] + 1) / np.log(max_pagu + 1) * 100
        ascore         = 0.0 if nature in ("routine_support", "treasury_crosscutting") \
                         else (100.0 - rank)
        review_priority = ascore * materiality / 100

        top3_json = json.dumps([
            {"code": kp_info[indices[j]]["code"],
             "name": kp_info[indices[j]]["name"][:100],
             "score": round(scores[j], 2),
             "source": kp_info[indices[j]]["source"]}
            for j in range(3)
        ])

        if not kl_row:
            continue

        batch.append((
            ti["sample_id"], kl_row[1], kl_row[2], kl_row[3], kl_row[4], kl_row[5],
            round(best_score, 2), strength, None, None,
            best_kp["source"], best_kp["code"], best_kp["name"][:300], round(best_score, 2),
            top3_json,
            nature, atype, round(ascore, 2), round(materiality, 2), round(review_priority, 2),
        ))

        if len(batch) >= batch_size:
            cur.executemany("""
                INSERT INTO ddac_anomaly_2026
                (pagu_id, kementerian_kode, kementerian_uraian, program_kode,
                 kegiatan_kode, total_pagu,
                 alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
                 best_match_type, best_match_code, best_match_name, best_match_score,
                 top3_matches, spending_nature, anomaly_type,
                 anomaly_score, materiality_score, review_priority)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, batch)
            conn.commit()
            total_ins += len(batch)
            batch = []

        if (i + 1) % 1000 == 0:
            print("  %d/%d (%.0f%%) | %.0fs"
                  % (i + 1, len(text_info), (i + 1) / len(text_info) * 100, time.time() - t0))

    if batch:
        cur.executemany("""
            INSERT INTO ddac_anomaly_2026
            (pagu_id, kementerian_kode, kementerian_uraian, program_kode,
             kegiatan_kode, total_pagu,
             alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
             best_match_type, best_match_code, best_match_name, best_match_score,
             top3_matches, spending_nature, anomaly_type,
             anomaly_score, materiality_score, review_priority)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, batch)
        conn.commit()
        total_ins += len(batch)

    if preserved:
        cur.executemany(
            """UPDATE ddac_anomaly_2026 a
               JOIN ddac_pagu_akun_2026 p ON a.pagu_id = p.id
               SET a.llm_reasoning=%s, a.llm_model=%s,
                   a.treasurai_verdict=%s, a.review_status=%s
               WHERE p.alignment_text=%s""",
            [(r[1], r[2], r[3], r[4], r[0]) for r in preserved])
        conn.commit()
        print("Restored reasoning for %d items" % len(preserved))

    elapsed = time.time() - t0

    # ------------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("ANOMALY DETECTION COMPLETE")
    print("=" * 60)
    print("Model   : %s" % MODEL_NAME)
    print("Time    : %.0f seconds" % elapsed)
    print("Rows    : %d unique texts -> %d anomaly records" % (len(text_info), total_ins))

    cur.execute("""
        SELECT anomaly_type, COUNT(*) AS cnt,
               CAST(SUM(total_pagu) AS DOUBLE) AS tp
        FROM ddac_anomaly_2026
        GROUP BY anomaly_type ORDER BY cnt DESC
    """)
    print("\nAnomaly Distribution:")
    for row in cur.fetchall():
        print("  %-25s: %6d rows | Rp %.1f T"
              % (row[0], row[1], (float(row[2]) / 1e12 if row[2] else 0)))

    cur.execute("""
        SELECT alignment_strength, COUNT(*) AS cnt,
               CAST(SUM(total_pagu) AS DOUBLE) AS tp
        FROM ddac_anomaly_2026
        GROUP BY alignment_strength
        ORDER BY FIELD(alignment_strength,'strong','moderate','weak','none')
    """)
    print("\nAlignment Distribution:")
    for row in cur.fetchall():
        print("  %-10s: %6d rows | Rp %.1f T"
              % (row[0], row[1], (float(row[2]) / 1e12 if row[2] else 0)))

    print("\n=== TOP 10 ANOMALIES (by review_priority) ===")
    cur.execute("""
        SELECT kementerian_kode, LEFT(kementerian_uraian, 30),
               alignment_score, alignment_strength, anomaly_type,
               review_priority,
               LEFT(best_match_name, 60),
               LEFT((SELECT alignment_text FROM ddac_pagu_akun_2026
                     WHERE id = pagu_id), 70)
        FROM ddac_anomaly_2026
        WHERE anomaly_type IN ('policy_orphan', 'weak_alignment')
        ORDER BY review_priority DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print("\n  %s %s" % (row[0], row[1]))
        print("  Score: %.1f | %s | %s | Priority: %.1f"
              % (row[2], row[3], row[4], row[5]))
        print("  Match: %s" % row[6])
        print("  Pagu : %s" % (row[7] or "")[:70])

    conn.close()


if __name__ == "__main__":
    main()
