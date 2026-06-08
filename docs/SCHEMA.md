# DeepSeek Policy KMS — Database Schema

Semua tabel dalam database `ddac2026`. Tabel knowledge graph berprefix
`deepseek_policy_*`; tabel hasil analisis berprefix `ddac_*`.

## Table Inventory

| # | Table | Grain | Purpose |
|---|-------|-------|---------|
| 1 | deepseek_policy_documents | 1 per PDF file | Document registry |
| 2 | deepseek_policy_pages | 1 per page | Raw + cleaned page text |
| 3 | deepseek_policy_chunks | 1 per chunk | Chunked text for LLM processing |
| 4 | deepseek_policy_nodes | 1 per planning entity | PN/PP/KP/PROG/KEG/KRO/RO |
| 5 | deepseek_policy_edges | 1 per parent-child | Hierarchy tree |
| 6 | deepseek_policy_tables | 1 per table | Extracted table metadata |
| 7 | deepseek_policy_table_rows | 1 per row | Parsed table rows |
| 8 | deepseek_policy_embeddings | 1 per vector | bge-m3 embeddings |
| 9 | deepseek_policy_kl_assignments | 1 per K/L-KP link | Institutional assignments |
| 10 | ddac_anomaly_2026 | 1 per alignment text | Policy alignment results |
| 11 | ddac_coherence_2026 | 1 per pagu akun | Koherensi internal 3 level |
| 12 | ddac_coherence_akun_2026 | 1 per (kl,prog,keg,out) | Detail peer komposisi akun (Level 3) |

---

## 1. deepseek_policy_documents

```sql
CREATE TABLE deepseek_policy_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doc_family VARCHAR(50) NOT NULL COMMENT 'RPJMN, RKP_2025, RKP_2026, MANDATE',
    doc_year INT NOT NULL,
    regulation_no VARCHAR(200) NOT NULL COMMENT 'Perpres 12/2025, etc.',
    title VARCHAR(1000) NOT NULL,
    attachment VARCHAR(200) NOT NULL COMMENT 'salinan, Lampiran I, etc.',
    source_file VARCHAR(500) NOT NULL COMMENT 'Original filename',
    source_path VARCHAR(1000) NOT NULL COMMENT 'Full path to PDF',
    page_count INT NOT NULL DEFAULT 0,
    extraction_status VARCHAR(50) DEFAULT 'pending' COMMENT 'pending, extracted, cleaned, done',
    extraction_error TEXT COMMENT 'Error messages if any',
    note VARCHAR(2000) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_family (doc_family, doc_year),
    UNIQUE KEY uk_document (doc_family, doc_year, attachment)
);
```

## 2. deepseek_policy_pages

```sql
CREATE TABLE deepseek_policy_pages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    page_number INT NOT NULL COMMENT '0-based page index',
    printed_page_number VARCHAR(50) DEFAULT '' COMMENT 'As printed on page',
    page_kind VARCHAR(50) DEFAULT 'unknown' COMMENT 'text, table, mixed, blank',
    has_text_layer TINYINT DEFAULT 0,
    word_count INT DEFAULT 0,
    raw_text LONGTEXT NOT NULL,
    clean_text LONGTEXT DEFAULT '' COMMENT 'AI-cleaned text',
    extract_error VARCHAR(2000) DEFAULT '',
    text_hash VARCHAR(64) DEFAULT '' COMMENT 'SHA-256 of raw_text',
    cleaned_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    INDEX idx_doc_page (document_id, page_number),
    INDEX idx_page_kind (page_kind)
);
```

## 3. deepseek_policy_chunks

```sql
CREATE TABLE deepseek_policy_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    chunk_index INT NOT NULL,
    page_start INT NOT NULL,
    page_end INT NOT NULL,
    section_hint VARCHAR(1000) DEFAULT '' COMMENT 'Detected section heading',
    level_hint VARCHAR(50) DEFAULT 'TEXT' COMMENT 'PN, PP, KP, TEXT, KL_MATRIX',
    text LONGTEXT NOT NULL,
    clean_text_ai LONGTEXT COMMENT 'LLM-cleaned text',
    clean_section_hint_ai VARCHAR(1000) COMMENT 'LLM-refined section',
    oc_text TINYINT DEFAULT 0 COMMENT '1 if OCR correction was needed',
    oc_hint TINYINT DEFAULT 0,
    token_estimate INT DEFAULT 0,
    text_hash VARCHAR(64) DEFAULT '',
    model_used VARCHAR(100) COMMENT 'LLM model for cleaning',
    cleaned_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    INDEX idx_doc_chunk (document_id, chunk_index),
    INDEX idx_level (level_hint)
);
```

## 4. deepseek_policy_nodes

```sql
CREATE TABLE deepseek_policy_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    chunk_id INT COMMENT 'Source chunk',
    source_type VARCHAR(50) NOT NULL COMMENT 'RPJMN, RKP_2025, RKP_2026',
    node_type VARCHAR(50) NOT NULL COMMENT 'PN, PP, KP, PROGRAM, KEGIATAN, KRO, RO',
    node_code VARCHAR(200) NOT NULL COMMENT 'Original code: 01, 01.01, etc.',
    node_name TEXT NOT NULL COMMENT 'Raw extracted name (blob ~250 char)',
    clean_node_name_ai TEXT COMMENT 'Nama bersih (14_fix_node_names: regex unglue)',
    parent_code VARCHAR(200) DEFAULT '' COMMENT 'Parent node code',
    normalized_code VARCHAR(200) DEFAULT '' COMMENT 'Normalized: PN-01, PP-01-01',
    source_page INT DEFAULT 0,
    raw_text TEXT COMMENT 'Source evidence excerpt',
    clean_raw_text_ai TEXT COMMENT 'AI-cleaned evidence',
    confidence DOUBLE DEFAULT 0.5 COMMENT 'Extraction confidence 0-1',
    oc_name TINYINT DEFAULT 0 COMMENT 'Name needed OCR fix',
    oc_raw TINYINT DEFAULT 0 COMMENT 'Raw text needed OCR fix',
    model_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    INDEX idx_source_type (source_type, node_type),
    INDEX idx_code (node_code),
    INDEX idx_parent (parent_code),
    INDEX idx_doc (document_id)
);
```

## 5. deepseek_policy_edges

```sql
CREATE TABLE deepseek_policy_edges (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    parent_node_id INT NOT NULL,
    child_node_id INT NOT NULL,
    edge_type VARCHAR(50) NOT NULL COMMENT 'HAS_PP, HAS_KP, HAS_PROGRAM, HAS_KEGIATAN, HAS_KRO, HAS_RO',
    source_type VARCHAR(50) NOT NULL,
    confidence DOUBLE DEFAULT 0.5,
    evidence_chunk_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    FOREIGN KEY (parent_node_id) REFERENCES deepseek_policy_nodes(id),
    FOREIGN KEY (child_node_id) REFERENCES deepseek_policy_nodes(id),
    INDEX idx_parent (parent_node_id),
    INDEX idx_child (child_node_id),
    INDEX idx_edge_type (edge_type),
    UNIQUE KEY uk_edge (parent_node_id, child_node_id, edge_type)
);
```

## 6. deepseek_policy_tables

```sql
CREATE TABLE deepseek_policy_tables (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    table_index INT NOT NULL,
    page_start INT DEFAULT 0,
    page_end INT DEFAULT 0,
    caption VARCHAR(2000) DEFAULT '',
    markdown LONGTEXT COMMENT 'Table as markdown',
    columns_json TEXT COMMENT 'Column headers as JSON array',
    row_count INT DEFAULT 0,
    text_hash VARCHAR(64) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    INDEX idx_doc_table (document_id, table_index)
);
```

## 7. deepseek_policy_table_rows

```sql
CREATE TABLE deepseek_policy_table_rows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_id INT NOT NULL,
    row_index INT NOT NULL,
    row_json TEXT COMMENT 'Full row as JSON',
    row_text TEXT COMMENT 'Row as plain text',
    code VARCHAR(200) DEFAULT '' COMMENT 'Entity code',
    name VARCHAR(2000) DEFAULT '' COMMENT 'Entity name',
    pn VARCHAR(50) DEFAULT '' COMMENT 'PN code',
    pp VARCHAR(50) DEFAULT '' COMMENT 'PP code',
    kp VARCHAR(50) DEFAULT '' COMMENT 'KP code',
    prop VARCHAR(50) DEFAULT '' COMMENT 'ProP code',
    node_type VARCHAR(50) DEFAULT '' COMMENT 'PN, PP, KP, etc.',
    clean_name_ai VARCHAR(2000) COMMENT 'AI-cleaned name',
    clean_row_text_ai TEXT COMMENT 'AI-cleaned row text',
    oc_name TINYINT DEFAULT 0,
    oc_row TINYINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (table_id) REFERENCES deepseek_policy_tables(id),
    INDEX idx_table_row (table_id, row_index),
    INDEX idx_pn (pn),
    INDEX idx_pp (pp),
    INDEX idx_kp (kp)
);
```

## 8. deepseek_policy_embeddings

```sql
CREATE TABLE deepseek_policy_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    object_type VARCHAR(50) NOT NULL COMMENT 'node, chunk, output',
    object_id INT NOT NULL COMMENT 'FK to respective table',
    provider VARCHAR(50) DEFAULT 'sentence-transformers',
    model VARCHAR(200) DEFAULT 'BAAI/bge-m3',
    dims INT DEFAULT 1024,
    vector MEDIUMBLOB NOT NULL COMMENT 'float32 binary blob',
    text_embedded TEXT COMMENT 'The text that was embedded',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_object (object_type, object_id),
    INDEX idx_model (model)
);
```

## 9. deepseek_policy_kl_assignments

```sql
CREATE TABLE deepseek_policy_kl_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    node_id INT NOT NULL COMMENT 'FK to deepseek_policy_nodes (KP level)',
    kddept VARCHAR(50) NOT NULL COMMENT 'K/L code',
    nmdept_original VARCHAR(500) COMMENT 'As written in document',
    nmdept_normalized VARCHAR(500) COMMENT 'After matching t_dept',
    role VARCHAR(50) DEFAULT 'pelaksana' COMMENT 'koordinator, pengampu, pelaksana, pendukung',
    confidence DOUBLE DEFAULT 0.5,
    source_page INT DEFAULT 0,
    evidence TEXT COMMENT 'Excerpt from document',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES deepseek_policy_documents(id),
    FOREIGN KEY (node_id) REFERENCES deepseek_policy_nodes(id),
    INDEX idx_node (node_id),
    INDEX idx_kddept (kddept),
    INDEX idx_role (role)
);
```

## 11. ddac_coherence_2026 — Koherensi Internal 3 Level

Satu baris per agregasi pagu akun (1,504,455 rows). Dibangun oleh `12_coherence.py`
(jenis komponen) lalu diperkaya `13_coherence_levels.py` (Level 1/2/3 + composite).

```sql
-- Kolom inti koherensi (selain kolom dimensi pagu)
jenis_komponen        VARCHAR  COMMENT 'Utama / Pendukung / none (t_kmpnen_2026)'
jenis_anomaly         VARCHAR  COMMENT 'pendukung_dominan / utama_kecil / unclassified / normal'
jenis_anomaly_score   DOUBLE   COMMENT 'Severity 0-100'
prog_keg_coherence    DOUBLE   COMMENT 'Level 1: cosine bge-m3 Program<->Kegiatan x100'
keg_out_coherence     DOUBLE   COMMENT 'Level 2: cosine bge-m3 Kegiatan<->Output x100'
out_komp_coherence    DOUBLE   COMMENT 'Level 3: 100 - deviasi komposisi akun'
akun_komposisi_score  DOUBLE   COMMENT 'Level 3: deviasi vs peer x100 (0-100)'
akun_detail           JSON     COMMENT 'Ringkasan komposisi own vs peer'
coherence_score       DOUBLE   COMMENT '0.35*jenis + 0.20*L1 + 0.20*L2 + 0.25*L3'
anomaly_flags         JSON     COMMENT 'Array level terpicu, mis. ["level3_akun_tidak_lazim"]'
```

**anomaly_flags** dapat berisi: `level1_program_kegiatan_lemah`,
`level2_kegiatan_output_lemah`, `level3_akun_tidak_lazim`.
Threshold: L1/L2 bila similarity < persentil-15; L3 bila `peer_count >= 5` dan
deviasi >= 0.40.

## 12. ddac_coherence_akun_2026 — Detail Peer Komposisi Akun (Level 3)

Satu baris per (K/L, program, kegiatan, output) dengan perbandingan komposisi
belanja terhadap peer (output berkode sama lintas K/L). ~8K rows.

```sql
PRIMARY KEY (kementerian_kode, program_kode, kegiatan_kode, outputkro_kode)
out_komp_coherence    DOUBLE   COMMENT '100 - deviasi'
akun_komposisi_score  DOUBLE   COMMENT 'Deviasi komposisi x100'
peer_count            INT      COMMENT 'Jumlah K/L peer (output kode sama)'
akun_detail           JSON     COMMENT '{own, peer, deviation, peer_count, top_unexpected}'
-- INDEX idx_ko (outputkro_kode) untuk enrich uraian dari ddac_coherence_2026
```

Deviasi = total variation distance = `0.5 * sum|own_share - peer_share|` atas
kategori akun 2-digit (51 Pegawai, 52 Barang, 53 Modal, 54 Bunga, 55 Subsidi,
57 Bansos, 58 Lain, 61-67 Pembiayaan).

---

## Key Differences vs Codex

| Feature | codex_policy_* | deepseek_policy_* |
|---------|---------------|-------------------|
| clean_text_ai | Empty (NULL) | Populated via LLM |
| clean_node_name_ai | Empty (NULL) | Populated (regex unglue, 856/891) |
| edges table | Exists but empty | Populated with hierarchy |
| embeddings | Exists but empty | Populated with bge-m3 |
| document_text_path | Not stored | source_path tracked |
| extraction_status | Not tracked | Per-document status field |
| kl_assignments | Not present | Dedicated table (585 baris) |
| coherence (3 level) | Not present | ddac_coherence_2026 + _akun_2026 |
| normalized_code | Not present | PN-01, PP-01-01 format |
