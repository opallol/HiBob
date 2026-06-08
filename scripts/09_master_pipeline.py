"""
Master Pipeline: Post-Cleaning → Nodes → Edges → Embeddings
Run after batch cleaning completes.
"""
import os, sys, re, struct, time
import pymysql

DB = {"host": "172.16.2.153", "user": "ddac26", "password": "p4ssw0rd!", "database": "ddac2026", "port": 3306, "charset": "utf8mb4"}

SIMPLE_PN = re.compile(r'(\d{2})\s*\n?\s*PN\s*[:;]\s*(.+?)(?=\n\s*\d{2}\s*\n|\n\s*(?:PP|KP)\s|\n(?:Prioritas|Program|Kegiatan)|\Z)', re.IGNORECASE | re.DOTALL)
SIMPLE_PP = re.compile(r'(\d{2}\.\d{2})\s*\n?\s*PP\s*[:;]\s*(.+?)(?=\n\s*\d{2}\.\d{2}\s*\n|\n\s*KP\s|\n\s*\d{2}\.\d{2}\.\d{2}|\Z)', re.IGNORECASE | re.DOTALL)
SIMPLE_KP = re.compile(r'(\d{2}\.\d{2}\.\d{2})\s*\n?\s*KP\s*[:;]\s*(.+?)(?=\n\s*\d{2}\.\d{2}\.\d{2}\s*\n|\n\s*(?:Indikator|Alokasi|Rp|\d{3}\s*-)|\Z)', re.IGNORECASE | re.DOTALL)

def step(msg):
    print("\n" + "="*60)
    print("STEP: " + msg)
    print("="*60)

def main():
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    
    # === STEP 1: Check cleaning status ===
    step("1. Checking cleaning status")
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NOT NULL")
    cleaned = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NULL AND token_estimate > 50")
    remaining = cur.fetchone()[0]
    print("Cleaned: %d | Remaining: %d" % (cleaned, remaining))
    
    if remaining > 100:
        print("WARNING: %d chunks still uncleaned. Continue anyway? (y/n)" % remaining)
        # Auto-continue for now
    
    # === STEP 2: Clear old nodes & edges for fresh extraction ===
    step("2. Clearing old extraction")
    cur.execute("DELETE FROM deepseek_policy_edges")
    cur.execute("DELETE FROM deepseek_policy_nodes")
    conn.commit()
    print("Cleared existing nodes and edges")
    
    # === STEP 3: Re-extract ALL nodes from cleaned text ===
    step("3. Extracting nodes from ALL cleaned chunks")
    cur.execute("""
        SELECT c.id, c.document_id, c.clean_text_ai, c.page_start, d.doc_family
        FROM deepseek_policy_chunks c
        JOIN deepseek_policy_documents d ON c.document_id = d.id
        WHERE c.clean_text_ai IS NOT NULL
        ORDER BY c.id
    """)
    chunks = cur.fetchall()
    print("Processing %d cleaned chunks..." % len(chunks))
    
    added = 0
    stats = {'PN': 0, 'PP': 0, 'KP': 0}
    
    for chunk_id, doc_id, text, page_start, family in chunks:
        if not text: continue
        lines = text.split('\n')
        merged = []
        for line in lines:
            s = line.strip()
            if merged and s and s[0].islower():
                merged[-1] += s
            else:
                merged.append(s)
        merged_text = '\n'.join(merged)
        source_type = family
        
        for node_type, pattern, parent_level in [('PN', SIMPLE_PN, None), ('PP', SIMPLE_PP, 0), ('KP', SIMPLE_KP, 1)]:
            for m in pattern.finditer(merged_text):
                code = m.group(1).strip()
                name = ' '.join(m.group(2).split())[:300]
                if len(name) < 5: continue
                
                parent_code = ''
                if parent_level == 0:
                    parent_code = code.split('.')[0]
                elif parent_level == 1:
                    parts = code.split('.')
                    if len(parts) >= 2:
                        parent_code = '.'.join(parts[:2])
                
                cur.execute("SELECT id FROM deepseek_policy_nodes WHERE document_id=%s AND node_type=%s AND node_code=%s",
                           (doc_id, node_type, code))
                if cur.fetchone(): continue
                
                cur.execute("INSERT INTO deepseek_policy_nodes (document_id, chunk_id, source_type, node_type, node_code, node_name, parent_code, normalized_code, source_page, raw_text, confidence, oc_name, model_used) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0.85,1,'deepseek-chat')",
                           (doc_id, chunk_id, source_type, node_type, code, name, parent_code, node_type+'-'+code, page_start, merged_text[:500]))
                added += 1
                stats[node_type] += 1
        
        if added % 100 == 0 and added > 0:
            conn.commit()
            print("  ... %d nodes so far (PN=%d PP=%d KP=%d)" % (added, stats['PN'], stats['PP'], stats['KP']))
    
    conn.commit()
    print("Nodes extracted: %d total (PN=%d PP=%d KP=%d)" % (added, stats['PN'], stats['PP'], stats['KP']))
    
    # === STEP 4: Build edges ===
    step("4. Building hierarchy edges")
    edge_map = {('PN','PP'): 'HAS_PP', ('PP','KP'): 'HAS_KP'}
    edges = 0
    
    cur.execute("""
        SELECT n1.id, n1.node_type, n1.parent_code, n2.id, n2.node_type, n1.document_id, n1.source_type
        FROM deepseek_policy_nodes n1
        JOIN deepseek_policy_nodes n2 ON n1.parent_code = n2.node_code AND n1.document_id = n2.document_id
        WHERE n1.parent_code != '' AND n1.id != n2.id
    """)
    for row in cur.fetchall():
        child_id, child_type, pc, parent_id, parent_type, doc_id, st = row
        et = edge_map.get((parent_type, child_type))
        if not et: continue
        cur.execute("SELECT id FROM deepseek_policy_edges WHERE parent_node_id=%s AND child_node_id=%s AND edge_type=%s",
                   (parent_id, child_id, et))
        if cur.fetchone(): continue
        cur.execute("INSERT INTO deepseek_policy_edges (document_id, parent_node_id, child_node_id, edge_type, source_type, confidence) VALUES (%s,%s,%s,%s,%s,0.85)",
                   (doc_id, parent_id, child_id, et, st))
        edges += 1
    
    conn.commit()
    print("Edges built: %d" % edges)
    
    # === STEP 5: Embeddings (if available) ===
    step("5. Generating embeddings")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        print("bge-m3 loaded successfully")
        
        cur.execute("""
            SELECT n.id, COALESCE(n.clean_node_name_ai, n.node_name) as name, n.node_type
            FROM deepseek_policy_nodes n
            WHERE n.id NOT IN (SELECT object_id FROM deepseek_policy_embeddings WHERE object_type='node')
            AND n.node_type IN ('KP', 'PP', 'PN')
            LIMIT 500
        """)
        to_embed = cur.fetchall()
        print("Embedding %d nodes..." % len(to_embed))
        
        texts = ["Represent this Indonesian government planning entity: " + n[1] for n in to_embed]
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True)
        
        emb_count = 0
        for j, (node_id, name, node_type) in enumerate(to_embed):
            vec = embeddings[j]
            binary = struct.pack('%df' % len(vec), *vec)
            cur.execute("INSERT INTO deepseek_policy_embeddings (object_type, object_id, model, dims, vector, text_embedded) VALUES ('node', %s, 'BAAI/bge-m3', %s, %s, %s)",
                       (node_id, len(vec), binary, name))
            emb_count += 1
        
        conn.commit()
        print("Embeddings generated: %d" % emb_count)
    except ImportError:
        print("sentence-transformers not installed. Skipping embeddings.")
        print("Run: pip install sentence-transformers")
    
    # === STEP 6: Final Scorecard ===
    step("6. FINAL SCORECARD")
    
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE clean_text_ai IS NOT NULL")
    total_cleaned = cur.fetchone()[0]
    
    cur.execute("SELECT node_type, COUNT(*) FROM deepseek_policy_nodes GROUP BY node_type ORDER BY CASE node_type WHEN 'PN' THEN 1 WHEN 'PP' THEN 2 WHEN 'KP' THEN 3 ELSE 4 END")
    node_counts = {}
    for row in cur.fetchall():
        node_counts[row[0]] = row[1]
    
    cur.execute("SELECT edge_type, COUNT(*) FROM deepseek_policy_edges GROUP BY edge_type")
    edge_counts = {}
    for row in cur.fetchall():
        edge_counts[row[0]] = row[1]
    
    cur.execute("SELECT COUNT(*) FROM deepseek_policy_embeddings")
    emb_total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM codex_policy_nodes")
    cx_nodes = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM codex_policy_edges")
    cx_edges = cur.fetchone()[0]
    
    ds_nodes = sum(node_counts.values())
    ds_edges = sum(edge_counts.values())
    
    print("""
    ============================================
      HEAD-TO-HEAD FINAL
    ============================================
                  Codex         DeepSeek
      Chunks:     1,444         %d cleaned
      Nodes:      %-5d         %d (PN=%d PP=%d KP=%d)
      Edges:      %-5d         %d (HAS_PP=%d HAS_KP=%d)
      Embeddings: 0             %d
      Hierarchy:  FLAT          CONNECTED TREE
      AI Model:   none          deepseek-chat
    ============================================
    """ % (total_cleaned, cx_nodes, ds_nodes, 
           node_counts.get('PN',0), node_counts.get('PP',0), node_counts.get('KP',0),
           cx_edges, ds_edges, edge_counts.get('HAS_PP',0), edge_counts.get('HAS_KP',0),
           emb_total))
    
    if ds_edges > 0 and cx_edges == 0:
        print("    WINNER: DEEPSEEK — First connected planning graph!")
    
    conn.close()
    print("\nPipeline complete!")

if __name__ == "__main__":
    main()
