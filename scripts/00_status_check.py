"""
Phase 0: Read-only DB status check.
Verifies the real state of the deepseek-kms pipeline by counting rows
and key fields across all tables. Does NOT modify anything.
"""
from common.config import DB_CONFIG as DB
from common.db import get_connection


def scalar(cur, sql):
    try:
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        return f"ERR: {e}"


def grouped(cur, sql):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        return [("ERR", str(e))]


def table_exists(cur, name):
    cur.execute("SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name=%s", (DB["database"], name))
    return cur.fetchone()[0] > 0


def main():
    conn = get_connection()
    cur = conn.cursor()

    print("=" * 60)
    print("DEEPSEEK-KMS DB STATUS CHECK")
    print("=" * 60)

    tables = [
        "deepseek_policy_documents",
        "deepseek_policy_pages",
        "deepseek_policy_chunks",
        "deepseek_policy_nodes",
        "deepseek_policy_edges",
        "deepseek_policy_tables",
        "deepseek_policy_table_rows",
        "deepseek_policy_embeddings",
        "deepseek_policy_kl_assignments",
        "ddac_pagu_akun_2026",
        "t_kmpnen_2026",
        "ddac_anomaly_2026",
        "ddac_coherence_2026",
    ]

    print("\n--- ROW COUNTS ---")
    for t in tables:
        if table_exists(cur, t):
            cnt = scalar(cur, f"SELECT COUNT(*) FROM {t}")
            print(f"  {t:<35} {cnt}")
        else:
            print(f"  {t:<35} (table missing)")

    print("\n--- CHUNKS: AI cleaning progress ---")
    if table_exists(cur, "deepseek_policy_chunks"):
        total = scalar(cur, "SELECT COUNT(*) FROM deepseek_policy_chunks")
        cleaned = scalar(cur, "SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NOT NULL")
        print(f"  cleaned {cleaned} / {total}")

    print("\n--- NODES by type ---")
    if table_exists(cur, "deepseek_policy_nodes"):
        for row in grouped(cur, "SELECT node_type, COUNT(*) FROM deepseek_policy_nodes GROUP BY node_type ORDER BY 2 DESC"):
            print(f"  {row[0]:<12} {row[1]}")

    print("\n--- EDGES by type ---")
    if table_exists(cur, "deepseek_policy_edges"):
        for row in grouped(cur, "SELECT edge_type, COUNT(*) FROM deepseek_policy_edges GROUP BY edge_type ORDER BY 2 DESC"):
            print(f"  {row[0]:<14} {row[1]}")

    print("\n--- EMBEDDINGS by object_type ---")
    if table_exists(cur, "deepseek_policy_embeddings"):
        for row in grouped(cur, "SELECT object_type, COUNT(*) FROM deepseek_policy_embeddings GROUP BY object_type"):
            print(f"  {row[0]:<12} {row[1]}")

    print("\n--- ANOMALY by anomaly_type ---")
    if table_exists(cur, "ddac_anomaly_2026"):
        for row in grouped(cur, "SELECT anomaly_type, COUNT(*) FROM ddac_anomaly_2026 GROUP BY anomaly_type ORDER BY 2 DESC"):
            print(f"  {row[0]:<18} {row[1]}")
        reasoned = scalar(cur, "SELECT COUNT(*) FROM ddac_anomaly_2026 WHERE llm_reasoning IS NOT NULL")
        print(f"  with llm_reasoning: {reasoned}")

    print("\n--- COHERENCE by jenis_anomaly ---")
    if table_exists(cur, "ddac_coherence_2026"):
        for row in grouped(cur, "SELECT jenis_anomaly, COUNT(*) FROM ddac_coherence_2026 GROUP BY jenis_anomaly ORDER BY 2 DESC"):
            print(f"  {row[0]:<18} {row[1]}")

    print("\n--- KL ASSIGNMENTS ---")
    if table_exists(cur, "deepseek_policy_kl_assignments"):
        cnt = scalar(cur, "SELECT COUNT(*) FROM deepseek_policy_kl_assignments")
        print(f"  rows: {cnt}")

    cur.close()
    conn.close()
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
