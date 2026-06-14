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
from common.config import TABLE_PAGU_AKUN, TABLE_ANOMALY

T_PAGU   = TABLE_PAGU_AKUN   # ddac_pagu_akun_<year>
T_ANOMALY = TABLE_ANOMALY    # ddac_anomaly_<year>

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
MODEL_NAME    = "LazarusNLP/all-indo-e5-small"
QUERY_PREFIX  = "query: "

# Percentile cut-offs (rank dalam distribusi skor aktual).
PCT = {"strong": 85, "moderate": 50, "weak": 15}

# Mandate-aware anchoring (Fix D4, 2026-06-14):
# best_match (anchor yang ditampilkan + dipakai reasoning) di-PRIORITASKAN ke KP
# yang DITUGASKAN ke K/L tsb di RPJMN/RKP Lampiran III, bukan argmax global atas
# 753 KP. Mencegah anchor absurd akibat lexical overlap (mis. "Program Sumber Daya
# Kesehatan/Jaminan Kesehatan" K/L 024 ter-anchor ke "Sumber Daya Hayati/Ekosistem").
# Anchor mandat dipakai jika skornya >= skor global terbaik - MANDATE_DELTA.
# alignment_score (dasar klasifikasi percentile) tetap = skor global terbaik
# (konservatif: mengukur kedekatan ke prioritas nasional manapun).
MANDATE_DELTA = 8.0

# Absolute floor: item hanya bisa jadi policy_orphan jika skor JUGA di bawah
# nilai ini. Mencegah item dengan skor cukup tinggi tapi kebetulan rank rendah
# karena distribusi terkompres.
# Fix D1 (2026-06-11): Turun dari 50 → 45 setelah verifikasi menunjukkan semua
# orphan saat itu memiliki skor 45-50 dan sebenarnya false positive (nomenklatur).
# Fix audit (2026-06-14): Turun lagi 45 → 40. Satu-satunya kandidat orphan tersisa
# (ESDM "Pengelolaan Mineral & Batubara", skor 44,47 = item terendah di dataset)
# ternyata masih dalam domain energi ESDM — reasoning menilainya manual_review,
# bukan orphan sejati. Karena bahkan item terskor-terendah pun punya relasi domain,
# orphan kini hanya berlaku untuk skor < 40 (benar-benar tanpa relasi semantik).
# Hasil 2026: 0 policy_orphan — tidak ada belanja yang sepenuhnya di luar prioritas.
ABS_FLOOR = 40.0

# K/L yang berfungsi sebagai bendahara negara / cross-cutting treasury —
# fungsi ini tidak memetakan ke KP prioritas spesifik RPJMN/RKP.
TREASURY_KL = {"999"}

# Klasifikasi spending_nature menggunakan kode resmi DIPA, bukan keyword text mining.
# Verifikasi DB (2026-06-11): 2,738 item (49% dari routine_support) salah klasifikasi
# hanya karena keyword — 68% di antaranya sebenarnya moderate/strong alignment.
# EB* = kode resmi Kemenkeu untuk output dukungan internal (EBA/EBB/EBC/EBD).
ROUTINE_EB_PREFIX = "EB"
ROUTINE_PROGRAM_PATTERN = "dukungan manajemen"


def _ensure_column(cur, name, ddl):
    cur.execute(
        f"""SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=DATABASE() AND table_name='{T_ANOMALY}'
             AND column_name='{name}'""")
    if cur.fetchone()[0] == 0:
        cur.execute(f"ALTER TABLE {T_ANOMALY} ADD COLUMN {ddl}")


def _ensure_verdict_column(cur):
    _ensure_column(cur, "treasurai_verdict",
                   "treasurai_verdict VARCHAR(20) NULL AFTER llm_model")
    # Fix D4: kolom anchor mandat (transparansi + input prompt reasoning)
    _ensure_column(cur, "mandate_match_code",  "mandate_match_code VARCHAR(20) NULL")
    _ensure_column(cur, "mandate_match_name",  "mandate_match_name VARCHAR(300) NULL")
    _ensure_column(cur, "mandate_match_score", "mandate_match_score DECIMAL(6,2) NULL")
    _ensure_column(cur, "anchored_on_mandate", "anchored_on_mandate TINYINT(1) NOT NULL DEFAULT 0")


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

    # Fix D4: peta kddept -> indeks KP yang ditugaskan ke K/L tsb (Lampiran III).
    # Dipakai untuk menghitung mandate_best (kedekatan ke prioritas yang memang
    # diamanahkan ke K/L itu), bukan hanya argmax global.
    nodeid_to_idx = {info["id"]: i for i, info in enumerate(kp_info)}
    cur.execute("""
        SELECT ka.kddept, n.id
        FROM deepseek_policy_kl_assignments ka
        JOIN deepseek_policy_nodes n ON ka.node_id = n.id
        WHERE n.node_type = 'KP'
    """)
    kl_kp_indices = {}
    for kddept, nid in cur.fetchall():
        idx = nodeid_to_idx.get(nid)
        if idx is not None:
            kl_kp_indices.setdefault(kddept, []).append(idx)
    print("[%.0fs] Mandate map: %d K/L with assigned KP" % (time.time() - t0, len(kl_kp_indices)))

    # ------------------------------------------------------------------
    # STEP 2: Unique alignment texts + embed
    # ------------------------------------------------------------------
    print("\n=== STEP 2: Embedding unique pagu texts ===")
    cur.execute(f"""
        SELECT alignment_text, COUNT(*) AS cnt,
               SUM(total_pagu) AS total_pagu, MIN(id) AS sample_id
        FROM {T_PAGU}
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
        f"SELECT id, kementerian_kode, kementerian_uraian, "
        "program_kode, kegiatan_kode, total_pagu, "
        "outputkro_kode, program_uraian "
        f"FROM {T_PAGU} WHERE id IN ({ph})",
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
        f"""SELECT p.alignment_text, a.llm_reasoning, a.llm_model,
                  a.treasurai_verdict, a.review_status
           FROM {T_ANOMALY} a
           JOIN {T_PAGU} p ON a.pagu_id = p.id
           WHERE a.llm_reasoning IS NOT NULL""")
    preserved = cur.fetchall()
    print("Preserving %d existing reasonings" % len(preserved))

    cur.execute(f"DELETE FROM {T_ANOMALY}")

    batch        = []
    total_ins    = 0
    batch_size   = 500
    max_pagu     = max((ti["total_pagu"] for ti in text_info), default=1)
    max_pagu     = max(max_pagu, 1)

    for i, ti in enumerate(text_info):
        scores  = [float(s * 100) for s in top3_scores[i]]
        indices = [int(idx) for idx in top3_indices[i]]

        best_score = scores[0]          # skor global terbaik (max atas semua KP)
        best_kp    = kp_info[indices[0]]
        rank       = pct_rank(best_score)

        # Fix D4: hitung mandate_best = KP terbaik di antara KP yang ditugaskan
        # ke K/L ini. Anchor di-prioritaskan ke mandat bila cukup dekat.
        kl_kode_for_mandate = kl_lookup.get(ti["sample_id"], (None,)*2)[1]
        mand_idx_list = kl_kp_indices.get(kl_kode_for_mandate, [])
        mandate_code = mandate_name = None
        mandate_score = None
        anchored_on_mandate = 0
        if mand_idx_list:
            row_sims = sim_matrix[i]
            m_best_local = max(mand_idx_list, key=lambda idx: row_sims[idx])
            mandate_score = float(row_sims[m_best_local] * 100)
            mandate_code  = kp_info[m_best_local]["code"]
            mandate_name  = kp_info[m_best_local]["name"]
            # Anchor ke mandat jika skornya tidak jauh di bawah global terbaik.
            if mandate_score >= best_score - MANDATE_DELTA:
                best_kp = kp_info[m_best_local]
                anchored_on_mandate = 1

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

        # best_match_score = skor anchor (mandat bila anchored, else global)
        anchor_score = mandate_score if anchored_on_mandate else best_score
        batch.append((
            ti["sample_id"], kl_row[1], kl_row[2], kl_row[3], kl_row[4], kl_row[5],
            round(best_score, 2), strength, None, None,
            best_kp["source"], best_kp["code"], best_kp["name"][:300], round(anchor_score, 2),
            top3_json,
            nature, atype, round(ascore, 2), round(materiality, 2), round(review_priority, 2),
            mandate_code, (mandate_name[:300] if mandate_name else None),
            (round(mandate_score, 2) if mandate_score is not None else None),
            anchored_on_mandate,
        ))

        if len(batch) >= batch_size:
            cur.executemany(f"""
                INSERT INTO {T_ANOMALY}
                (pagu_id, kementerian_kode, kementerian_uraian, program_kode,
                 kegiatan_kode, total_pagu,
                 alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
                 best_match_type, best_match_code, best_match_name, best_match_score,
                 top3_matches, spending_nature, anomaly_type,
                 anomaly_score, materiality_score, review_priority,
                 mandate_match_code, mandate_match_name, mandate_match_score, anchored_on_mandate)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, batch)
            conn.commit()
            total_ins += len(batch)
            batch = []

        if (i + 1) % 1000 == 0:
            print("  %d/%d (%.0f%%) | %.0fs"
                  % (i + 1, len(text_info), (i + 1) / len(text_info) * 100, time.time() - t0))

    if batch:
        cur.executemany(f"""
            INSERT INTO {T_ANOMALY}
            (pagu_id, kementerian_kode, kementerian_uraian, program_kode,
             kegiatan_kode, total_pagu,
             alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
             best_match_type, best_match_code, best_match_name, best_match_score,
             top3_matches, spending_nature, anomaly_type,
             anomaly_score, materiality_score, review_priority,
             mandate_match_code, mandate_match_name, mandate_match_score, anchored_on_mandate)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, batch)
        conn.commit()
        total_ins += len(batch)

    if preserved:
        cur.executemany(
            f"""UPDATE {T_ANOMALY} a
               JOIN {T_PAGU} p ON a.pagu_id = p.id
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

    cur.execute(f"""
        SELECT anomaly_type, COUNT(*) AS cnt,
               CAST(SUM(total_pagu) AS DOUBLE) AS tp
        FROM {T_ANOMALY}
        GROUP BY anomaly_type ORDER BY cnt DESC
    """)
    print("\nAnomaly Distribution:")
    for row in cur.fetchall():
        print("  %-25s: %6d rows | Rp %.1f T"
              % (row[0], row[1], (float(row[2]) / 1e12 if row[2] else 0)))

    cur.execute(f"""
        SELECT alignment_strength, COUNT(*) AS cnt,
               CAST(SUM(total_pagu) AS DOUBLE) AS tp
        FROM {T_ANOMALY}
        GROUP BY alignment_strength
        ORDER BY FIELD(alignment_strength,'strong','moderate','weak','none')
    """)
    print("\nAlignment Distribution:")
    for row in cur.fetchall():
        print("  %-10s: %6d rows | Rp %.1f T"
              % (row[0], row[1], (float(row[2]) / 1e12 if row[2] else 0)))

    print("\n=== TOP 10 ANOMALIES (by review_priority) ===")
    cur.execute(f"""
        SELECT kementerian_kode, LEFT(kementerian_uraian, 30),
               alignment_score, alignment_strength, anomaly_type,
               review_priority,
               LEFT(best_match_name, 60),
               LEFT((SELECT alignment_text FROM {T_PAGU}
                     WHERE id = pagu_id), 70)
        FROM {T_ANOMALY}
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
