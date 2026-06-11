"""
Phase 7: Embedding Generation
Generates bge-m3 embeddings for all KP nodes.
Requires: pip install sentence-transformers
"""
import os, sys, struct
import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.config import DB_CONFIG  # noqa: E402

try:
    from sentence_transformers import SentenceTransformer
    MODEL = SentenceTransformer("BAAI/bge-m3")
    MODEL_READY = True
except ImportError:
    MODEL_READY = False
    print("WARNING: sentence-transformers not installed. Run: pip install sentence-transformers")


def generate_embeddings(conn, limit=None):
    """Generate embeddings for nodes."""
    if not MODEL_READY:
        print("Cannot generate embeddings — model not loaded")
        return 0
    
    cur = conn.cursor()
    
    where = "" if limit is None else f"LIMIT {limit}"
    
    # Get nodes that need embeddings (KP nodes first)
    cur.execute(f"""
        SELECT n.id, n.node_type, n.node_code, 
               COALESCE(n.clean_node_name_ai, n.node_name) as display_name,
               n.source_type
        FROM deepseek_policy_nodes n
        WHERE n.id NOT IN (
            SELECT object_id FROM deepseek_policy_embeddings 
            WHERE object_type = 'node'
        )
        ORDER BY 
            CASE n.node_type WHEN 'KP' THEN 1 WHEN 'PP' THEN 2 WHEN 'PN' THEN 3 ELSE 4 END
        {where}
    """)
    nodes = cur.fetchall()
    
    if not nodes:
        print("All nodes already embedded")
        return 0
    
    print(f"Generating embeddings for {len(nodes)} nodes...")
    
    # Prepare texts with instruction prefix (bge-m3 requires this)
    texts = [f"Represent this Indonesian government planning entity: {n[3]}" for n in nodes]
    
    # Generate embeddings in batches
    batch_size = 32
    embedded = 0
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        batch_nodes = nodes[i:i+batch_size]
        
        embeddings = MODEL.encode(batch_texts, normalize_embeddings=True)
        
        for j, (node_id, node_type, node_code, name, source_type) in enumerate(batch_nodes):
            vector = embeddings[j]
            # Pack float32 array to binary
            binary = struct.pack(f'{len(vector)}f', *vector)
            
            cur.execute("""
                INSERT INTO deepseek_policy_embeddings
                (object_type, object_id, model, dims, vector, text_embedded)
                VALUES ('node', %s, 'BAAI/bge-m3', %s, %s, %s)
            """, (node_id, len(vector), binary, name))
            
            embedded += 1
        
        conn.commit()
        print(f"  {embedded}/{len(nodes)} nodes embedded...")
    
    return embedded


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Max nodes to embed")
    args = parser.parse_args()
    
    conn = pymysql.connect(**DB_CONFIG)
    count = generate_embeddings(conn, args.limit)
    print(f"\nEmbedded {count} nodes")
    conn.close()


if __name__ == "__main__":
    main()
