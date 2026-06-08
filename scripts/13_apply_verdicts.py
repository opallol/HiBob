"""
13_apply_verdicts.py — Structure TreasurAI reasoning into queryable verdicts.

The embedding alignment_score is non-discriminative (valid vs false-positive
orphans both average ~66). The authoritative anomaly signal therefore comes from
TreasurAI's semantic reasoning. This script extracts that free-text verdict into
a structured column so it can drive review_priority, dashboards and metrics.

Idempotent: safe to re-run after 11_treasurai_reasoning.py adds new reasoning.
"""
from common.db import get_connection
from common.verdict import parse_verdict


def column_exists(cur, table, column):
    cur.execute(
        """SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s""",
        (table, column),
    )
    return cur.fetchone()[0] > 0


def main():
    conn = get_connection()
    cur = conn.cursor()

    if not column_exists(cur, "ddac_anomaly_2026", "treasurai_verdict"):
        print("Adding column treasurai_verdict ...")
        cur.execute(
            "ALTER TABLE ddac_anomaly_2026 "
            "ADD COLUMN treasurai_verdict VARCHAR(20) NULL AFTER llm_model"
        )
        conn.commit()
    else:
        print("Column treasurai_verdict already exists.")

    cur.execute(
        "SELECT id, llm_reasoning FROM ddac_anomaly_2026 WHERE llm_reasoning IS NOT NULL"
    )
    rows = cur.fetchall()
    print(f"Reasoned anomalies to classify: {len(rows)}")

    counts = {}
    for aid, reason in rows:
        v = parse_verdict(reason)
        counts[v] = counts.get(v, 0) + 1
        cur.execute(
            "UPDATE ddac_anomaly_2026 SET treasurai_verdict=%s WHERE id=%s", (v, aid)
        )
    conn.commit()

    # Reflect verdict into review_status so the dashboard can filter triage state.
    #   false_positive -> 'dismissed'  (TreasurAI judged not a real anomaly)
    #   valid          -> 'confirmed'  (real anomaly worth follow-up)
    #   manual_review  -> 'needs_review'
    cur.execute(
        """UPDATE ddac_anomaly_2026
           SET review_status = CASE treasurai_verdict
                 WHEN 'false_positive' THEN 'dismissed'
                 WHEN 'valid'          THEN 'confirmed'
                 WHEN 'manual_review'  THEN 'needs_review'
                 ELSE review_status END
           WHERE treasurai_verdict IS NOT NULL"""
    )
    conn.commit()

    print("\n=== Verdict counts ===")
    total = sum(counts.values()) or 1
    for v in sorted(counts, key=lambda k: -counts[k]):
        print(f"  {v:<16} {counts[v]:>5} ({counts[v]/total*100:.0f}%)")

    cur.execute(
        """SELECT review_status, COUNT(*), ROUND(SUM(total_pagu)/1e12,1)
           FROM ddac_anomaly_2026 WHERE treasurai_verdict IS NOT NULL
           GROUP BY review_status ORDER BY 2 DESC"""
    )
    print("\n=== review_status after sync (pagu in Rp T) ===")
    for st, n, pagu in cur.fetchall():
        print(f"  {st:<14} n={n:<5} pagu={pagu}T")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
