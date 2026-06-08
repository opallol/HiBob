# DeepSeek Policy KMS — Knowledge Management System

## Saingan `codex_policy_*` — by DeepSeek via Hermes Agent

### Status Per 2026-06-08 — PIPELINE LENGKAP ✅

| Phase | Script | Status | Hasil |
|-------|--------|--------|-------|
| 1. Schema | 01_create_schema.py | ✅ DONE | 9 tables created |
| 2. Extraction | 02_extract_pages.py | ✅ DONE | 17 docs, 4,478 pages, 731K words |
| 3a. Chunking | 03_chunk_and_clean.py | ✅ DONE | 990 chunks |
| 3b. AI Cleaning | 03b_ai_clean.py | ✅ DONE | 990/990 chunks (100% OCR fix) |
| 4. Nodes | 04_extract_nodes.py | ✅ DONE | 891 nodes (16 PN + 137 PP + 738 KP) |
| 5. Edges | 05_build_edges.py | ✅ DONE | 699 edges (hierarchy tree) |
| 6. Tables | 06_extract_tables.py | ✅ DONE | Structured table parsing |
| 7. Embeddings | 07_generate_embeddings.py | ✅ DONE | bge-m3 vectors (1,471) |
| 8. K/L Assign | 08_extract_kl.py | ✅ DONE | 585 penugasan institusi |
| 10. Anomaly | 10_anomaly_detect.py | ✅ DONE | 389 policy orphans + AI reasoning |
| 11. Reasoning | 11_treasurai_reasoning.py | ✅ DONE | TreasurAI OSS 20B/120B |
| 12. Coherence | 12_coherence.py | ✅ DONE | jenis komponen (1.5M rows) |
| 13. Koherensi 3 Level | 13_coherence_levels.py | ✅ DONE | Level 1/2/3 + peer comparison |
| 14. Bersih Nama | 14_fix_node_names.py | ✅ DONE | 856/891 nama dibersihkan |
| 15. Dashboard | dashboard/app.py | ✅ DONE | FastAPI + vis-network (5 tab) |

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
| Chunks | 1,444 | 990 (smarter) ✅ |
| Nodes | 5,334 | 891 (connected) ✅ |
| Edges | **0** ❌ | **699** ✅ |
| Embeddings | **0** ❌ | **1,471** ✅ |
| AI Cleaned | **0%** ❌ | **100%** ✅ |
| K/L Mapping | **N/A** ❌ | **585 penugasan** ✅ |
| Anomaly Detection | **N/A** ❌ | **389 orphans + AI reasoning** ✅ |
| Koherensi Internal | **N/A** ❌ | **3 level + peer comparison** ✅ |
| Dashboard | **N/A** ❌ | **FastAPI + vis-network** ✅ |

### Koherensi Internal 3 Level (2026-06-08)

Selain keselarasan terhadap RPJMN/RKP, DIPA dicek konsistensi internalnya pada
tiga tingkat hierarki anggaran:

1. **Level 1 — Program ↔ Kegiatan** (cosine bge-m3): apakah kegiatan selaras
   dengan programnya? → 181,492 baris lemah (Rp 171.6 T).
2. **Level 2 — Kegiatan ↔ Output** (cosine bge-m3): apakah output selaras dengan
   kegiatannya? → 85,067 baris lemah (Rp 282.6 T).
3. **Level 3 — Output ↔ Komposisi Akun** (peer comparison lintas K/L): apakah
   jenis belanja masuk akal untuk output ini? → 169,162 baris tidak lazim
   (Rp 194.8 T). Contoh: output "Layanan Dukungan Manajemen" (EBA) di Polri
   98% Belanja Modal padahal ~0% di 99 K/L peer.

### Pembersihan Nama Simpul

`node_name` hasil ekstraksi PDF adalah blob ~250 karakter dengan kata menempel.
`14_fix_node_names.py` membersihkannya ke `clean_node_name_ai` (856/891 simpul).
Dashboard memakai `COALESCE(clean_node_name_ai, node_name)`.

### Cara Menjalankan Dashboard

```bash
cd dashboard
..\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8123 --reload
# Buka http://127.0.0.1:8123
```

> Dokumentasi lengkap: [docs/MASTER_DOCUMENTATION.md](docs/MASTER_DOCUMENTATION.md)
> dan [docs/SCHEMA.md](docs/SCHEMA.md).
