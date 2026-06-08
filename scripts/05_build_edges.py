"""
Phase 5: Edge Building
Builds parent-child relationships (edges) between planning nodes.
Uses parent_code field to create the hierarchy tree.

Edge types: HAS_PP, HAS_KP, HAS_PROGRAM, HAS_KEGIATAN, HAS_KRO, HAS_RO
"""
import pymysql

DB_CONFIG = {
    "host": "172.16.2.153", "user": "ddac26", "password": "p4ssw0rd!",
    "database": "ddac2026", "port": 3306, "charset": "utf8mb4"
}

EDGE_MAP = {
    ('PN', 'PP'): 'HAS_PP',
    ('PP', 'KP'): 'HAS_KP',
    ('KP', 'PROGRAM'): 'HAS_PROGRAM',
    ('PROGRAM', 'KEGIATAN'): 'HAS_KEGIATAN',
    ('KEGIATAN', 'KRO'): 'HAS_KRO',
    ('KRO', 'RO'): 'HAS_RO',
}


def build_edges_from_parent_codes(conn):
    """Build edges using parent_code field from nodes."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT n1.id as child_id, n1.node_type as child_type, n1.node_code as child_code,
               n1.parent_code, n2.id as parent_id, n2.node_type as parent_type,
               n1.document_id, n1.source_type
        FROM deepseek_policy_nodes n1
        LEFT JOIN deepseek_policy_nodes n2 
            ON n1.parent_code = n2.node_code 
            AND n1.document_id = n2.document_id
        WHERE n1.parent_code != ''
        AND n2.id IS NOT NULL
    """)
    
    edges_created = 0
    for row in cur.fetchall():
        child_id, child_type, child_code, parent_code, parent_id, parent_type, doc_id, source_type = row
        
        edge_type = EDGE_MAP.get((parent_type, child_type))
        if not edge_type:
            continue
        
        # Check if edge already exists
        cur.execute("""
            SELECT id FROM deepseek_policy_edges
            WHERE parent_node_id = %s AND child_node_id = %s AND edge_type = %s
        """, (parent_id, child_id, edge_type))
        
        if cur.fetchone():
            continue
        
        cur.execute("""
            INSERT INTO deepseek_policy_edges
            (document_id, parent_node_id, child_node_id, edge_type, source_type, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (doc_id, parent_id, child_id, edge_type, source_type, 0.7))
        edges_created += 1
    
    conn.commit()
    return edges_created


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    edges = build_edges_from_parent_codes(conn)
    print(f"Created {edges} edges from parent_code relationships")
    
    # Also try to build edges from node code hierarchy
    cur.execute("""
        SELECT n1.id, n1.node_type, n1.node_code, n1.document_id, n1.source_type,
               n2.id as parent_id, n2.node_type as parent_type
        FROM deepseek_policy_nodes n1
        JOIN deepseek_policy_nodes n2 ON n1.document_id = n2.document_id
        WHERE n1.id != n2.id
        AND (
            (n1.node_type = 'PP' AND n2.node_type = 'PN' 
             AND LEFT(n1.node_code, 1) = n2.node_code)
            OR
            (n1.node_type = 'KP' AND n2.node_type = 'PP'
             AND SUBSTRING_INDEX(n1.node_code, '.', 2) = n2.node_code)
        )
    """)
    
    extra_edges = 0
    for row in cur.fetchall():
        child_id, child_type, child_code, doc_id, source_type, parent_id, parent_type = row
        edge_type = EDGE_MAP.get((parent_type, child_type))
        if not edge_type:
            continue
        
        cur.execute("""
            SELECT id FROM deepseek_policy_edges
            WHERE parent_node_id = %s AND child_node_id = %s AND edge_type = %s
        """, (parent_id, child_id, edge_type))
        if cur.fetchone():
            continue
        
        cur.execute("""
            INSERT INTO deepseek_policy_edges
            (document_id, parent_node_id, child_node_id, edge_type, source_type, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (doc_id, parent_id, child_id, edge_type, source_type, 0.6))
        extra_edges += 1
    
    conn.commit()
    print(f"Created {extra_edges} additional edges from code hierarchy")
    
    # Summary
    cur.execute("SELECT COUNT(*), edge_type FROM deepseek_policy_edges GROUP BY edge_type")
    print("\nEdge Summary:")
    for row in cur.fetchall():
        print(f"  {row[1]:20s}: {row[0]:,}")
    
    conn.close()


if __name__ == "__main__":
    main()
