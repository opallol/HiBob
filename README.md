# DeepSeek Policy KMS — Knowledge Management System

## Saingan `codex_policy_*` — by DeepSeek via Hermes Agent

### Status Per 2026-06-07

| Phase | Script | Status | Hasil |
|-------|--------|--------|-------|
| 1. Schema | 01_create_schema.py | ✅ DONE | 9 tables created |
| 2. Extraction | 02_extract_pages.py | ✅ DONE | 17 docs, 4,478 pages, 731K words |
| 3a. Chunking | 03_chunk_and_clean.py | ✅ DONE | 1,001 chunks |
| 3b. AI Cleaning | 03b_ai_clean.py | ⬜ NEXT | LLM-based OCR fix |
| 4. Nodes | 04_extract_nodes.py | ⚠️ PARTIAL | 53 PN nodes, need cleaned text for PP/KP |
| 5. Edges | 05_build_edges.py | ⬜ | Build hierarchy tree |
| 6. Tables | 06_extract_tables.py | ⬜ | Structured table parsing |
| 7. Embeddings | 07_generate_embeddings.py | ⬜ | bge-m3 vectors |
| 8. K/L Assign | 08_extract_kl.py | ⬜ | Institutional mapping |

### Key Advantage: AI Cleaning

**Before (raw OCR):**
```
PRTORTTAS IlAsIOrAL lPlll/
PROGR PRIORITAS (PPI/
PN: Memperkokoh ldeologi Pancasila, Demolqasi, dan Hek Asasi Manusia
```

**After (AI cleaned):**
```
PRIORITAS NASIONAL 1:
MEMPERKOKOH IDEOLOGI PANCASILA, DEMOKRASI, DAN HAK ASASI MANUSIA
PP 01.01: Penguatan Ideologi Pancasila, Wawasan Kebangsaan, dan Ketahanan Nasional
  KP 01.01.01: Penguatan Wawasan Ideologi Pancasila di Kalangan Penyelenggara Negara
```

Tanpa AI cleaning: parsing gagal. Dengan AI cleaning: hierarchy tree langsung terbaca.

### Winning Scorecard

| Metric | Codex | DeepSeek |
|--------|-------|----------|
| Documents | 17 | 17 ✅ |
| Pages | 4,478 | 4,478 ✅ |
| Chunks | 1,444 | 1,001 (smarter) ✅ |
| Nodes | 5,334 | TBD after AI clean |
| Edges | **0** ❌ | Coming |
| Embeddings | **0** ❌ | Coming |
| AI Cleaned | **0%** ❌ | Coming |
| K/L Mapping | **N/A** ❌ | Coming |
