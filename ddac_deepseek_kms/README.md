# SENTINEL — Spending Intelligence for National Alignment Review

### Status Per 2026-06-14 — PIPELINE LENGKAP ✅

| Phase | Script | Status | Hasil |
|-------|--------|--------|-------|
| 1. Schema | 01_create_schema.py | ✅ DONE | 9 tables created |
| 2. Extraction | 02_extract_pages.py | ✅ DONE | 17 docs, 4,478 pages, 731K words |
| 3a. Chunking | 03_chunk_and_clean.py | ✅ DONE | 990 chunks |
| 3b. AI Cleaning | 03b_ai_clean.py | ✅ DONE | 990/990 chunks (100% OCR fix) |
| 4. Nodes | 04_extract_nodes.py | ✅ DONE | 962 nodes (43 PN + 167 PP + 752 KP) |
| 5. Edges | 05_build_edges.py | ✅ DONE | 856 edges (hierarchy tree) |
| 6. Tables | 06_extract_tables.py | ✅ DONE | Structured table parsing |
| 7. Embeddings | (runtime di script 10/13) | ✅ DONE | e5-small lokal (LazarusNLP, 384-dim) |
| 8. K/L Assign | 08_extract_kl.py | ✅ DONE | 534 penugasan institusi (78 K/L) |
| 10. Anomaly | 10_anomaly_detect.py | ✅ DONE | 0 orphan + 1.546 weak + reasoning TreasurAI |
| 11. Reasoning | 11_treasurai_reasoning.py | ✅ DONE | TreasurAI OSS 20B/120B |
| 12. Coherence | 12_coherence.py | ✅ DONE | jenis komponen (1.5M rows) |
| 13. Koherensi 3 Level | 13_coherence_levels.py | ✅ DONE | Level 1/2/3 + peer comparison |
| 14. Bersih Nama | 14_fix_node_names.py | ✅ DONE | nama KP/PN dibersihkan (clean_node_name_ai) |
| 16. Web Visualisasi | 16_export_web.py + web/ | ✅ DONE | Peta anomali bubblemaps (Vite + React, statis) |
| 17. Refresh Orchestrator | 17_refresh_analysis.py | ✅ DONE | Jalankan ulang 10→16 saat DIPA berubah |

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

| Metric | Codex | SENTINEL |
|--------|-------|----------|
| Documents | 17 | 17 ✅ |
| Pages | 4,478 | 4,478 ✅ |
| Chunks | 1,444 | 990 (smarter) ✅ |
| Nodes | 5,334 | 962 (connected) ✅ |
| Edges | **0** ❌ | **856** ✅ |
| Embeddings | **0** ❌ | **e5-small lokal (runtime)** ✅ |
| AI Cleaned | **0%** ❌ | **100%** ✅ |
| K/L Mapping | **N/A** ❌ | **534 penugasan (78 K/L)** ✅ |
| Anomaly Detection | **N/A** ❌ | **0 orphan + 1.546 weak + reasoning** ✅ |
| Koherensi Internal | **N/A** ❌ | **3 level + peer comparison** ✅ |
| Web Visualisasi | **N/A** ❌ | **Peta anomali bubblemaps (Vite + React, statis)** ✅ |

### Koherensi Internal 3 Level

Selain keselarasan terhadap RPJMN/RKP, DIPA dicek konsistensi internalnya pada
tiga tingkat hierarki anggaran:

1. **Level 1 — Program ↔ Kegiatan** (cosine e5-small): apakah kegiatan selaras
   dengan programnya? → 14,272 baris lemah (Rp 1.1 T).
2. **Level 2 — Kegiatan ↔ Output** (cosine e5-small): apakah output selaras dengan
   kegiatannya? → 16,310 baris lemah (Rp 4.5 T).
3. **Level 3 — Output ↔ Komposisi Akun** (peer comparison lintas K/L, mean-of-shares): apakah
   jenis belanja masuk akal untuk output ini? → 24,224 baris tidak lazim
   (Rp 194.8 T). Contoh: output "Layanan Dukungan Manajemen" (EBA) di Polri
   98% Belanja Modal padahal ~0% di 99 K/L peer.

### Pembersihan Nama Simpul

`node_name` hasil ekstraksi PDF adalah blob ~250 karakter dengan kata menempel.
`14_fix_node_names.py` membersihkannya ke `clean_node_name_ai` (KP + PN).
Ekspor web memakai `COALESCE(clean_node_name_ai, node_name)`.

### Cara Menjalankan Web Visualisasi

```bash
# Ekspor data JSON statis dari DB
python scripts\16_export_web.py        # → web/public/data/

# Development server
cd web && npm install && npm run dev   # http://localhost:5173

# Build statis untuk deploy
npm run build                          # → web/dist/
```

### Refresh saat DIPA Berubah (APBN-P / tahun baru)

```bash
# Set BUDGET_YEAR di .env bila ganti tahun (mis. BUDGET_YEAR=2027), lalu:
python scripts\17_refresh_analysis.py  # jalankan ulang 10→11→12→13→15b→16 + build
```

Lihat Bagian 11 (Refresh Runbook) di MASTER_DOCUMENTATION untuk detail.

> Dokumentasi lengkap: [docs/MASTER_DOCUMENTATION.md](docs/MASTER_DOCUMENTATION.md)
> dan [docs/SCHEMA.md](docs/SCHEMA.md).
