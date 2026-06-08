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
    │  deepseek_policy_kl_assignments
    │
    ▼
[Phase 10: Policy Alignment] ── bge-m3 cosine pagu vs KP nodes
    │  ddac_anomaly_2026 (389 policy orphans) + TreasurAI reasoning
    │
    ▼
[Phase 12-13: Internal Coherence] ── 3-level structural check
    │  ddac_coherence_2026 + ddac_coherence_akun_2026
    │
    ▼
[Phase 14: Name Cleanup] ── deterministic unglue node_name
    │  deepseek_policy_nodes.clean_node_name_ai
    │
    ▼
[Phase 15: Dashboard] ── FastAPI + vis-network (human review)
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

## 6. Internal Coherence — 3-Level Detection Model (2026-06-08)

Selain keselarasan ke RPJMN/RKP, struktur internal DIPA dicek konsistensinya pada
tiga tingkat hierarki anggaran. Diimplementasikan `13_coherence_levels.py`, mengisi
`ddac_coherence_2026` secara in-place (idempoten, tanpa rebuild).

```
Program ──L1 cosine──► Kegiatan ──L2 cosine──► Output ──L3 peer──► Komposisi Akun
```

| Level | Pertanyaan | Metode | Output kolom |
|-------|-----------|--------|--------------|
| 1 | Kegiatan selaras dgn program? | cosine bge-m3 (uraian) | prog_keg_coherence |
| 2 | Output selaras dgn kegiatan? | cosine bge-m3 (uraian) | keg_out_coherence |
| 3 | Jenis belanja lazim utk output ini? | peer comparison lintas K/L | out_komp_coherence, akun_komposisi_score |

**Level 3 (peer comparison):** untuk setiap output, distribusi belanja per kategori
akun 2-digit dibandingkan dengan rata-rata seluruh output berkode sama di semua K/L.
Deviasi memakai **total variation distance** `0.5·Σ|own−peer|`. Karena similarity
bge-m3 terkompresi (~0.40–0.77), **threshold memakai persentil (P15)** bukan nilai
absolut. Detail per output disimpan di `ddac_coherence_akun_2026.akun_detail` (JSON).

Composite: `coherence_score = 0.35·jenis + 0.20·L1 + 0.20·L2 + 0.25·L3`.
Flag terkumpul di `anomaly_flags` (JSON array).

## 7. Pembersihan Nama Simpul

`node_name` dari ekstraksi PDF adalah blob ~250 karakter (nama + sasaran + indikator
+ angka + K/L) dengan kata menempel akibat hilangnya spasi line-break.
`14_fix_node_names.py` membersihkannya secara **deterministik (regex, bukan LLM)**
ke `clean_node_name_ai`: (1) potong sebelum penanda sasaran `NN -`; (2) pisah
camelCase; (3) pisah kata sambung yang menempel (`Abadidan`→`Abadi dan`). 856/891
simpul dibersihkan. Sifatnya non-destruktif; dashboard memakai
`COALESCE(clean_node_name_ai, node_name)`.

## 8. Dashboard Review (Human-in-the-loop)

`dashboard/app.py` (FastAPI) menyajikan API JSON di atas seluruh tabel hasil, dengan
frontend statis (`dashboard/static/`, vis-network). Lima tab: Ringkasan, Knowledge
Graph, Anomali Keselarasan, Anomali Koherensi (filter Level 1/2/3 + tabel peer
komposisi akun), dan Penugasan K/L. Endpoint utama: `/api/summary`, `/api/graph`,
`/api/anomalies`, `/api/coherence`, `/api/coherence-akun`, `/api/kl-assignments`.
Backend memakai modul bersama `scripts/common` (config + koneksi DB).
