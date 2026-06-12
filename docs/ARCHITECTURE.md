# SENTINEL — Architecture

## 1. System Overview

SENTINEL adalah sistem analisis keselarasan belanja negara yang mengekstrak, membersihkan, dan menstrukturkan dokumen perencanaan nasional ke dalam relational knowledge graph untuk mendukung audit DIPA vs RPJMN/RKP.

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
[Phase 7: Embeddings] ── bge-m3 legacy (tabel kosong, tidak aktif)
    │  deepseek_policy_embeddings (0 rows)
    │
    ▼
[Phase 8: K/L Assign] ── Parse institutional assignments
    │  deepseek_policy_kl_assignments (604 rows, 72 K/L)
    │
    ▼
[Phase 10: Policy Alignment] ── e5-small cosine pagu vs KP nodes (runtime)
    │  ddac_anomaly_2026 (1 orphan + 1,541 weak) + TreasurAI reasoning
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
[Phase 16: Web Visualisasi] ── ekspor JSON statis → web/ (Vite + React, human review)
```

## 2. Keunggulan SENTINEL

### Problem with Codex System

1. **No edges**: 5.334 nodes are flat — no parent-child relationships. You can't traverse PN → PP → KP.
2. **No AI cleaning**: clean_text_ai and clean_node_name_ai are ALL NULL. Garbled text like "FengeEbangan Tenaga Tektia P€f" unfixed.
3. **No embeddings**: Zero embedding vectors. Semantic search impossible.
4. **Poor node type categorization**: PN/PP/KP mixed with PROGRAM/KEGIATAN/KRO/RO — no clear distinction between planning entities and budget entities.
5. **Tables only from RPJMN**: 199 tables extracted but only from Lampiran III. RKP tables untouched.

### Solusi SENTINEL

1. **Full hierarchy**: PN → PP → KP → (PROGRAM → KEGIATAN → KRO → RO) with explicit edges
2. **AI cleaning first**: LLM-based OCR correction BEFORE node extraction
3. **bge-m3 embeddings**: 1024-dimension vectors for all KP nodes
4. **Clean node taxonomy**: Planning nodes (PN/PP/KP) clearly separated from budget nodes
5. **All documents processed**: Every table from every document

## 3. Node Hierarchy

```
PN (Prioritas Nasional) ──── 43 nodes (RPJMN 01-08 + RKP)
 │
 └─ PP (Program Prioritas) ── 167 nodes
     │
     └─ KP (Kegiatan Prioritas) ── 753 nodes
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
| e5-small for embeddings | 384d, Indonesian fine-tune, runtime (no stored vecs) |
| Dedicated table schema | KMS tables + future alignment tables stay separate |
| source_type column | RPJMN, RKP_2025, RKP_2026 — enables cross-document comparison |

## 5. Technical Stack

- **PDF Extraction**: PyMuPDF (pymupdf) — fast, reliable text layer extraction
- **OCR Cleaning**: LLM API (cloud) — context-aware correction of garbled text
- **Embeddings**: LazarusNLP/all-indo-e5-small via sentence-transformers — runtime, no stored vectors
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
| 1 | Kegiatan selaras dgn program? | cosine e5-small (uraian) | prog_keg_coherence |
| 2 | Output selaras dgn kegiatan? | cosine e5-small (uraian) | keg_out_coherence |
| 3 | Jenis belanja lazim utk output ini? | peer comparison lintas K/L | out_komp_coherence, akun_komposisi_score |

**Level 3 (peer comparison):** untuk setiap output, distribusi belanja per kategori
akun 2-digit dibandingkan dengan rata-rata seluruh output berkode sama di semua K/L.
Deviasi memakai **total variation distance** `0.5·Σ|own−peer|`. Threshold: **persentil-5
(P5)** untuk L1/L2, deviasi ≥ 0.40 untuk L3 (0.65 untuk EB-series). Detail per output
disimpan di `ddac_coherence_akun_2026.akun_detail` (JSON).

Composite: `coherence_score = 0.35·jenis + 0.20·L1 + 0.20·L2 + 0.25·L3`.
Flag terkumpul di `anomaly_flags` (JSON array).

## 7. Pembersihan Nama Simpul

`node_name` dari ekstraksi PDF adalah blob ~250 karakter (nama + sasaran + indikator
+ angka + K/L) dengan kata menempel akibat hilangnya spasi line-break.
`14_fix_node_names.py` membersihkannya secara **deterministik (regex, bukan LLM)**
ke `clean_node_name_ai`: (1) potong sebelum penanda sasaran `NN -`; (2) pisah
camelCase; (3) pisah kata sambung yang menempel (`Abadidan`→`Abadi dan`).
753 KP + 43 PN mendapat `clean_node_name_ai` eksplisit. 167 PP menggunakan
`node_name` langsung (PP names sudah bersih dari struktur RPJMN). Non-destruktif;
ekspor web memakai `COALESCE(clean_node_name_ai, node_name)` untuk semua 963 nodes.

## 8. Web Visualisasi Review (Human-in-the-loop)

`scripts/16_export_web.py` mengekspor agregat hasil pipeline menjadi JSON statis ke
`web/public/data/` (manifest, node bubble, detail per K/L, knowledge graph, pipeline).
Frontend `web/` (Vite + React + TypeScript + Tailwind + react-force-graph-2d)
menyajikan peta anomali interaktif gaya bubblemaps — **tanpa backend**, cukup file
statis. Bubble dikelompokkan per cluster (pola akun / verdict / per K/L), warna =
status verdict, ukuran = pagu; klik menampilkan reasoning oss120b + komposisi akun
+ mandat RPJMN/RKP. Build: `cd web && npm run build` → `web/dist/` siap deploy.
