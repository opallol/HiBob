"""
Anomaly Detection Pipeline
Embeds pagu texts -> cosine similarity vs KP nodes -> classify anomalies.

Scores from bge-m3 are tightly compressed (most fall in 0.60-0.77), so absolute
thresholds are not meaningful. Strength is therefore derived from each item's
*percentile rank* within the actual score distribution: the lowest-aligned items
relative to their peers become the policy-orphan review candidates. TreasurAI
(scripts 11/13) is the authoritative judge of whether a candidate is real.
"""
import json, time

import numpy as np
from sentence_transformers import SentenceTransformer

from common.db import get_connection

# Percentile cut-offs (rank within the actual score distribution).
# Lowest 15% of relative alignment => policy-orphan candidates.
PCT = {"strong": 85, "moderate": 50, "weak": 15}
ROUTINE_KEYWORDS = [
    'dukungan manajemen', 'administrasi', 'operasional', 'sekretariat',
    'pengawasan', 'pengelolaan', 'koordinasi', 'perkantoran', 'tata usaha',
    'kepegawaian', 'keuangan dan', 'perencanaan dan', 'pemeliharaan',
    'layanan perkantoran', 'gaji dan tunjangan', 'sarana dan prasarana',
    'pembinaan', 'fasilitasi', 'penyelenggaraan',
]


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
    cur = conn.cursor()
    t0 = time.time()
    
    # STEP 1: Load bge-m3 and all KP vectors
    print("=== STEP 1: Loading bge-m3 + KP vectors ===")
    model = SentenceTransformer("BAAI/bge-m3")
    
    cur.execute("""
        SELECT e.object_id, e.vector, n.node_type, n.node_code, n.node_name, n.source_type
        FROM deepseek_policy_embeddings e
        JOIN deepseek_policy_nodes n ON e.object_id = n.id
        WHERE e.object_type = 'node' AND n.node_type = 'KP'
    """)
    kp_nodes = cur.fetchall()
    print("Loaded %d KP vectors" % len(kp_nodes))
    
    # Unpack vectors
    kp_vectors = np.zeros((len(kp_nodes), 1024), dtype=np.float32)
    kp_info = []
    for i, (nid, blob, ntype, ncode, nname, src) in enumerate(kp_nodes):
        vec = np.frombuffer(blob, dtype=np.float32)
        kp_vectors[i] = vec
        kp_info.append({"id": nid, "type": ntype, "code": ncode, "name": nname, "source": src})
    
    # STEP 2: Get unique alignment texts + embed
    print("\n=== STEP 2: Embedding unique pagu texts ===")
    cur.execute("""
        SELECT alignment_text, COUNT(*) as cnt, SUM(total_pagu) as total_pagu,
               MIN(id) as sample_id
        FROM ddac_pagu_akun_2026
        WHERE alignment_text != '' AND alignment_text IS NOT NULL
        GROUP BY alignment_text
    """)
    texts = cur.fetchall()
    print("%d unique texts to embed" % len(texts))
    
    unique_texts = [t[0] for t in texts]
    text_info = [{"text": t[0], "count": t[1], "total_pagu": float(t[2]), "sample_id": t[3]} for t in texts]
    
    # Embed with instruction prefix
    prefixed = ["Represent this Indonesian government budget item: " + t for t in unique_texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
    print("Embedded %d texts" % len(embeddings))
    
    pagu_vectors = np.array(embeddings, dtype=np.float32)
    
    # STEP 3: Cosine similarity
    print("\n=== STEP 3: Computing cosine similarity ===")
    # Cosine = dot product (already normalized)
    sim_matrix = np.dot(pagu_vectors, kp_vectors.T)  # (N_texts, N_kp)
    
    # Get top-3 per text
    top3_indices = np.argsort(-sim_matrix, axis=1)[:, :3]  # descending
    top3_scores = np.take_along_axis(sim_matrix, top3_indices, axis=1)
    
    print("Similarity computed!")

    # Percentile thresholds derived from the actual best-score distribution.
    best_scores = top3_scores[:, 0].astype(np.float64) * 100
    sorted_bs = np.sort(best_scores)
    n_bs = len(sorted_bs)
    thr = {k: float(np.percentile(best_scores, p)) for k, p in PCT.items()}
    print("Percentile thresholds: strong>=%.1f  moderate>=%.1f  weak>=%.1f"
          % (thr["strong"], thr["moderate"], thr["weak"]))

    def pct_rank(score):
        return float(np.searchsorted(sorted_bs, score, side="right")) / n_bs * 100

    # STEP 4: Classify & insert
    print("\n=== STEP 4: Classifying & inserting anomalies ===")

    # Preserve TreasurAI work (keyed by alignment_text) across re-runs.
    _ensure_verdict_column(cur)
    conn.commit()
    cur.execute(
        """SELECT p.alignment_text, a.llm_reasoning, a.llm_model,
                  a.treasurai_verdict, a.review_status
           FROM ddac_anomaly_2026 a
           JOIN ddac_pagu_akun_2026 p ON a.pagu_id = p.id
           WHERE a.llm_reasoning IS NOT NULL""")
    preserved = cur.fetchall()
    print("Preserving %d existing reasonings across re-run" % len(preserved))

    # Clear previous results
    cur.execute("DELETE FROM ddac_anomaly_2026")
    
    # Batch insert
    batch_size = 500
    batch = []
    total_inserted = 0

    max_pagu = max(ti["total_pagu"] for ti in text_info)
    max_pagu = max(max_pagu, 1)

    for i, ti in enumerate(text_info):
        # Get top-3
        scores = [float(s * 100) for s in top3_scores[i]]
        indices = [int(idx) for idx in top3_indices[i]]

        best_score = scores[0]
        best_kp = kp_info[indices[0]]
        rank = pct_rank(best_score)

        # Alignment strength by percentile rank
        if rank >= PCT["strong"]:
            strength = "strong"
        elif rank >= PCT["moderate"]:
            strength = "moderate"
        elif rank >= PCT["weak"]:
            strength = "weak"
        else:
            strength = "none"

        # Spending nature
        text_lower = ti["text"].lower()
        is_routine = any(kw in text_lower for kw in ROUTINE_KEYWORDS)
        nature = "routine_support" if is_routine else "substantive"

        # Anomaly type
        if nature == "routine_support":
            atype = "routine"
        elif strength == "none":
            atype = "policy_orphan"
        elif strength == "weak":
            atype = "weak_alignment"
        else:
            atype = "aligned"

        # Materiality
        materiality = np.log(ti["total_pagu"] + 1) / np.log(max_pagu + 1) * 100

        # Anomaly score: inverse percentile rank (lower alignment => higher score).
        # Routine support is expected to be unaligned, so it carries no anomaly.
        ascore = 0.0 if nature == "routine_support" else (100.0 - rank)

        review_priority = ascore * materiality / 100
        
        # Top 3 as JSON
        top3_json = json.dumps([
            {"code": kp_info[indices[j]]["code"], "name": kp_info[indices[j]]["name"][:100], 
             "score": round(scores[j], 2), "source": kp_info[indices[j]]["source"]}
            for j in range(3)
        ])
        
        # Find a sample pagu row to get K/L info
        cur.execute("SELECT kementerian_kode, kementerian_uraian, program_kode, kegiatan_kode, total_pagu FROM ddac_pagu_akun_2026 WHERE id = %s", (ti["sample_id"],))
        kl = cur.fetchone()
        if not kl:
            continue
        
        batch.append((
            ti["sample_id"], kl[0], kl[1], kl[2], kl[3], kl[4],
            round(best_score, 2), strength, None, None,
            best_kp["source"], best_kp["code"], best_kp["name"][:300], round(best_score, 2),
            top3_json,
            nature, atype, round(ascore, 2), round(materiality, 2), round(review_priority, 2)
        ))
        
        if len(batch) >= batch_size:
            cur.executemany("""
                INSERT INTO ddac_anomaly_2026 
                (pagu_id, kementerian_kode, kementerian_uraian, program_kode, kegiatan_kode, total_pagu,
                 alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
                 best_match_type, best_match_code, best_match_name, best_match_score,
                 top3_matches, spending_nature, anomaly_type, anomaly_score, materiality_score, review_priority)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, batch)
            conn.commit()
            total_inserted += len(batch)
            batch = []

        if (i+1) % 1000 == 0:
            elapsed = time.time() - t0
            print("  %d/%d (%.0f%%) | %.0fs" % (i+1, len(text_info), (i+1)/len(text_info)*100, elapsed))
    
    # Final batch
    if batch:
        cur.executemany("""
            INSERT INTO ddac_anomaly_2026 
            (pagu_id, kementerian_kode, kementerian_uraian, program_kode, kegiatan_kode, total_pagu,
             alignment_score, alignment_strength, rpjmn_alignment, rkp_alignment,
             best_match_type, best_match_code, best_match_name, best_match_score,
             top3_matches, spending_nature, anomaly_type, anomaly_score, materiality_score, review_priority)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, batch)
        conn.commit()
        total_inserted += len(batch)

    # Re-apply preserved TreasurAI reasoning/verdict to the rebuilt rows.
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
    
    # FINAL SUMMARY
    print("\n" + "=" * 60)
    print("ANOMALY DETECTION COMPLETE")
    print("=" * 60)
    print("Time: %.0f seconds" % elapsed)
    print("Rows: %d unique texts → %d anomaly records" % (len(text_info), total_inserted))
    
    cur.execute("""
        SELECT anomaly_type, COUNT(*) as cnt, 
               CAST(SUM(total_pagu) AS DOUBLE) as total_pagu
        FROM ddac_anomaly_2026
        GROUP BY anomaly_type
        ORDER BY cnt DESC
    """)
    print("\nAnomaly Distribution:")
    for row in cur.fetchall():
        pagu_t = float(row[2]) / 1e12 if row[2] else 0
        print("  %-20s: %6d rows | Rp %.1f T" % (row[0], row[1], pagu_t))
    
    cur.execute("""
        SELECT alignment_strength, COUNT(*) as cnt,
               CAST(SUM(total_pagu) AS DOUBLE) as total_pagu
        FROM ddac_anomaly_2026
        GROUP BY alignment_strength
        ORDER BY FIELD(alignment_strength, 'strong', 'moderate', 'weak', 'none')
    """)
    print("\nAlignment Distribution:")
    for row in cur.fetchall():
        pagu_t = float(row[2]) / 1e12 if row[2] else 0
        print("  %-10s: %6d rows | Rp %.1f T" % (row[0], row[1], pagu_t))
    
    # TOP anomalies
    print("\n=== TOP 10 ANOMALIES (by review_priority) ===")
    cur.execute("""
        SELECT kementerian_kode, LEFT(kementerian_uraian,30),
               alignment_score, alignment_strength, anomaly_type,
               review_priority, 
               LEFT(best_match_name, 60) as match_name,
               LEFT((SELECT alignment_text FROM ddac_pagu_akun_2026 WHERE id = pagu_id), 70) as pagu_text
        FROM ddac_anomaly_2026
        WHERE anomaly_type IN ('policy_orphan', 'weak_alignment')
        ORDER BY review_priority DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print("\n  %s %s" % (row[0], row[1]))
        print("  Score: %.1f | %s | %s | Priority: %.1f" % (row[2], row[3], row[4], row[5]))
        print("  Match: %s" % row[6][:60])
        print("  Pagu:  %s" % row[7][:70])
    
    conn.close()

if __name__ == "__main__":
    main()
