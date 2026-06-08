# DeepSeek Policy KMS — Architecture

## 1. System Overview

DeepSeek Policy KMS adalah knowledge management system yang mengekstrak, membersihkan, dan menstrukturkan dokumen perencanaan nasional ke dalam relational knowledge graph.

### Core Pipeline

```
17 PDF files
    │
    ▼
[Phase 1: Schema] ── Create deepseek_policy_* tables
    │
    ▼
[Phase 2: Extraction] ── PyMuPDF text extraction per page
    │  deepseek_policy_documents + deepseek_policy_pages
    │
    ▼
[Phase 3: Cleaning] ── LLM-based OCR correction + chunking
    │  deepseek_policy_chunks (with clean_text_ai)
    │
    ▼
[Phase 4: Nodes] ── Parse PN/PP/KP/PROG/KEG/KRO/RO hierarchy
    │  deepseek_policy_nodes (with clean_node_name_ai)
    │
    ▼
[Phase 5: Edges] ── Build parent-child tree
    │  deepseek_policy_edges
    │
    ▼
[Phase 6: Tables] ── Extract structured tables
    │  deepseek_policy_tables + deepseek_policy_table_rows
    │
    ▼
[Phase 7: Embeddings] ── bge-m3 vector embeddings
    │  deepseek_policy_embeddings
    │
    ▼
[Phase 8: K/L Assign] ── Parse institutional assignments
       deepseek_policy_kl_assignments
```

## 2. Why DeepSeek Wins

### Problem with Codex System

1. **No edges**: 5.334 nodes are flat — no parent-child relationships. You can't traverse PN → PP → KP.
2. **No AI cleaning**: clean_text_ai and clean_node_name_ai are ALL NULL. Garbled text like "FengeEbangan Tenaga Tektia P€f" unfixed.
3. **No embeddings**: Zero embedding vectors. Semantic search impossible.
4. **Poor node type categorization**: PN/PP/KP mixed with PROGRAM/KEGIATAN/KRO/RO — no clear distinction between planning entities and budget entities.
5. **Tables only from RPJMN**: 199 tables extracted but only from Lampiran III. RKP tables untouched.

### DeepSeek Solutions

1. **Full hierarchy**: PN → PP → KP → (PROGRAM → KEGIATAN → KRO → RO) with explicit edges
2. **AI cleaning first**: LLM-based OCR correction BEFORE node extraction
3. **bge-m3 embeddings**: 1024-dimension vectors for all KP nodes
4. **Clean node taxonomy**: Planning nodes (PN/PP/KP) clearly separated from budget nodes
5. **All documents processed**: Every table from every document

## 3. Node Hierarchy

```
PN (Prioritas Nasional) ──── 8 items (RPJMN-defined)
 │
 └─ PP (Program Prioritas) ── ~30 items
     │
     └─ KP (Kegiatan Prioritas) ── ~200 items
         │
         └─ PROGRAM ── K/L program codes
             │
             └─ KEGIATAN ── activity codes
                 │
                 └─ KRO (Keluaran/Output) ── output codes
                     │
                     └─ RO (Rincian Output) ── detail output
```

## 4. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Clean BEFORE parse | Garbled text breaks hierarchy parsing |
| Edges separate from nodes | Multi-document hierarchies differ (RPJMN vs RKP) |
| Evidence per node | Every node traceable to source page |
| bge-m3 for embeddings | 1024d, local, multilingual, proven in poc1 |
| Dedicated table schema | KMS tables + future alignment tables stay separate |
| source_type column | RPJMN, RKP_2025, RKP_2026 — enables cross-document comparison |

## 5. Technical Stack

- **PDF Extraction**: PyMuPDF (pymupdf) — fast, reliable text layer extraction
- **OCR Cleaning**: LLM (DeepSeek) — context-aware correction of garbled text
- **Embeddings**: bge-m3 (BAAI) via sentence-transformers — local, no API cost
- **Database**: MySQL 8.4 (172.16.2.153) — existing infrastructure
- **Language**: Python 3.11+ with pymysql, pymupdf, sentence-transformers
