import sys
sys.path.insert(0, r"d:/Project/deepseek-kms/scripts")
from common.db import get_connection

c = get_connection()
cur = c.cursor()

cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes")
print("total nodes:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes WHERE clean_node_name_ai IS NOT NULL AND clean_node_name_ai<>''")
print("clean_node_name_ai populated:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes WHERE clean_node_name_ai IS NOT NULL AND clean_node_name_ai<>node_name")
print("clean differs from raw:", cur.fetchone()[0])

print("\n-- KP raw vs clean (first 12) --")
cur.execute("SELECT node_code, node_name, clean_node_name_ai FROM deepseek_policy_nodes WHERE node_type='KP' ORDER BY node_code LIMIT 12")
for r in cur.fetchall():
    print("CODE", r[0])
    print("  raw  :", repr(r[1]))
    print("  clean:", repr(r[2]))

print("\n-- node_name length distribution (long = extraction noise) --")
cur.execute("SELECT node_type, MAX(CHAR_LENGTH(node_name)), AVG(CHAR_LENGTH(node_name)) FROM deepseek_policy_nodes GROUP BY node_type")
print(cur.fetchall())
cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes WHERE node_type='KP' AND CHAR_LENGTH(node_name) > 120")
print("KP names >120 chars:", cur.fetchone()[0])
c.close()
