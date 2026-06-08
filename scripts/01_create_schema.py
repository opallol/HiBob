"""
Phase 1: Schema Creation
Creates all deepseek_policy_* tables in ddac2026 database.
"""
import pymysql

DB_CONFIG = {
    "host": "172.16.2.153", "user": "ddac26", "password": "p4ssw0rd!",
    "database": "ddac2026", "port": 3306, "charset": "utf8mb4"
}

TABLES = {
    "deepseek_policy_documents": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            doc_family VARCHAR(50) NOT NULL,
            doc_year INT NOT NULL,
            regulation_no VARCHAR(200) NOT NULL,
            title VARCHAR(1000) NOT NULL,
            attachment VARCHAR(200) NOT NULL,
            source_file VARCHAR(500) NOT NULL,
            source_path VARCHAR(1000) NOT NULL,
            page_count INT NOT NULL DEFAULT 0,
            extraction_status VARCHAR(50) DEFAULT 'pending',
            extraction_error TEXT,
            note VARCHAR(2000) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_family (doc_family, doc_year),
            UNIQUE KEY uk_document (doc_family, doc_year, attachment)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_pages": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_pages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            page_number INT NOT NULL,
            printed_page_number VARCHAR(50) DEFAULT '',
            page_kind VARCHAR(50) DEFAULT 'unknown',
            has_text_layer TINYINT DEFAULT 0,
            word_count INT DEFAULT 0,
            raw_text LONGTEXT NOT NULL,
            clean_text LONGTEXT DEFAULT '',
            extract_error VARCHAR(2000) DEFAULT '',
            text_hash VARCHAR(64) DEFAULT '',
            cleaned_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_doc_page (document_id, page_number),
            INDEX idx_page_kind (page_kind)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_chunks": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_chunks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            chunk_index INT NOT NULL,
            page_start INT NOT NULL,
            page_end INT NOT NULL,
            section_hint VARCHAR(1000) DEFAULT '',
            level_hint VARCHAR(50) DEFAULT 'TEXT',
            text LONGTEXT NOT NULL,
            clean_text_ai LONGTEXT,
            clean_section_hint_ai VARCHAR(1000),
            oc_text TINYINT DEFAULT 0,
            oc_hint TINYINT DEFAULT 0,
            token_estimate INT DEFAULT 0,
            text_hash VARCHAR(64) DEFAULT '',
            model_used VARCHAR(100),
            cleaned_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_doc_chunk (document_id, chunk_index),
            INDEX idx_level (level_hint)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_nodes": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_nodes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            chunk_id INT,
            source_type VARCHAR(50) NOT NULL,
            node_type VARCHAR(50) NOT NULL,
            node_code VARCHAR(200) NOT NULL,
            node_name TEXT NOT NULL,
            clean_node_name_ai TEXT,
            parent_code VARCHAR(200) DEFAULT '',
            normalized_code VARCHAR(200) DEFAULT '',
            source_page INT DEFAULT 0,
            raw_text TEXT,
            clean_raw_text_ai TEXT,
            confidence DOUBLE DEFAULT 0.5,
            oc_name TINYINT DEFAULT 0,
            oc_raw TINYINT DEFAULT 0,
            model_used VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_source_type (source_type, node_type),
            INDEX idx_code (node_code),
            INDEX idx_parent (parent_code),
            INDEX idx_doc (document_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_edges": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_edges (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            parent_node_id INT NOT NULL,
            child_node_id INT NOT NULL,
            edge_type VARCHAR(50) NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            confidence DOUBLE DEFAULT 0.5,
            evidence_chunk_id INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_parent (parent_node_id),
            INDEX idx_child (child_node_id),
            INDEX idx_edge_type (edge_type),
            UNIQUE KEY uk_edge (parent_node_id, child_node_id, edge_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_tables": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_tables (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            table_index INT NOT NULL,
            page_start INT DEFAULT 0,
            page_end INT DEFAULT 0,
            caption VARCHAR(2000) DEFAULT '',
            markdown LONGTEXT,
            columns_json TEXT,
            row_count INT DEFAULT 0,
            text_hash VARCHAR(64) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_doc_table (document_id, table_index)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_table_rows": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_table_rows (
            id INT AUTO_INCREMENT PRIMARY KEY,
            table_id INT NOT NULL,
            row_index INT NOT NULL,
            row_json TEXT,
            row_text TEXT,
            code VARCHAR(200) DEFAULT '',
            name VARCHAR(2000) DEFAULT '',
            pn VARCHAR(50) DEFAULT '',
            pp VARCHAR(50) DEFAULT '',
            kp VARCHAR(50) DEFAULT '',
            prop VARCHAR(50) DEFAULT '',
            node_type VARCHAR(50) DEFAULT '',
            clean_name_ai VARCHAR(2000),
            clean_row_text_ai TEXT,
            oc_name TINYINT DEFAULT 0,
            oc_row TINYINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_table_row (table_id, row_index),
            INDEX idx_pn (pn),
            INDEX idx_pp (pp),
            INDEX idx_kp (kp)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_embeddings": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_embeddings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            object_type VARCHAR(50) NOT NULL,
            object_id INT NOT NULL,
            provider VARCHAR(50) DEFAULT 'sentence-transformers',
            model VARCHAR(200) DEFAULT 'BAAI/bge-m3',
            dims INT DEFAULT 1024,
            vector MEDIUMBLOB NOT NULL,
            text_embedded TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_object (object_type, object_id),
            INDEX idx_model (model)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "deepseek_policy_kl_assignments": """
        CREATE TABLE IF NOT EXISTS deepseek_policy_kl_assignments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            document_id INT NOT NULL,
            node_id INT NOT NULL,
            kddept VARCHAR(50) NOT NULL,
            nmdept_original VARCHAR(500),
            nmdept_normalized VARCHAR(500),
            role VARCHAR(50) DEFAULT 'pelaksana',
            confidence DOUBLE DEFAULT 0.5,
            source_page INT DEFAULT 0,
            evidence TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_node (node_id),
            INDEX idx_kddept (kddept),
            INDEX idx_role (role)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
}

def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    for name, sql in TABLES.items():
        try:
            cur.execute(sql)
            print(f"  OK  {name}")
        except Exception as e:
            print(f"  ERR {name}: {e}")
    
    conn.commit()
    cur.execute("SHOW TABLES LIKE 'deepseek_policy_%'")
    tables = cur.fetchall()
    print(f"\nCreated {len(tables)} tables")
    conn.close()

if __name__ == "__main__":
    main()
