# SENTINEL — Spending Intelligence for National Alignment Review
## Dokumentasi Utama

**Tanggal:** 2026-06-07 (terakhir diperbarui: 2026-06-12)
**Direktori proyek:** D:\Project\deepseek-kms
**Database:** ddac2026 @ 172.16.2.153

> **Update 2026-06-08:** Pipeline kini lengkap end-to-end — K/L mapping (08),
> koherensi 3 level (13), pembersihan nama simpul (14). Lihat Bagian 5.4–5.6
> untuk hasil terbaru.
>
> **Update 2026-06-11:** Tuning presisi menyeluruh — model anomaly diganti ke
> LazarusNLP/all-indo-e5-small, klasifikasi routine dipindah ke kode resmi EB/DM,
> KB nodes dibersihkan (9 false PN + spillover KP + canonical PN names), ABS_FLOOR
> diturunkan 50→45. Coherence L1 false positive dibersihkan: Program DM + military K/L
> di-suppress (135→30 combos). L2 EB-series output di-suppress (F3). Lihat Bagian 5.2
> dan 5.4 untuk distribusi terkini.
>
> **Update 2026-06-12:** TreasurAI reasoning diperluas ke **semua** anomali. Script 11
> kini memproses 1 orphan + 1,541 weak_alignment (total 1,542 item); script 15 (baru)
> memproses coherence L3 top-30 output unik → 19,235 baris. Model upgrade ke oss120b.
> Prompt di-enrich konteks mandat RPJMN/RKP per K/L via `common/kl_context.py` (baru).
> SSL self-signed Kemenkeu ditangani `verify=False`. Lihat Bagian 2.4, 3, dan 6.1.

---

# 1. SYSTEM OVERVIEW

Sistem ini menganalisis APBN 2026 (DIPA) terhadap dokumen perencanaan nasional
(RPJMN 2025-2029 dan RKP 2026) menggunakan AI/ML untuk mendeteksi anomali
secara multi-dimensi.

## 1.1 Source Documents

| Document | Regulation | Files |
|----------|-----------|-------|
| RPJMN 2025-2029 | Perpres 12/2025 | 7 PDF (Salinan + Lamp I-IV) |
| RKP 2025 | Perpres 109/2024 | 3 PDF (Salinan + Lamp I-II) |
| RKP 2026 | Perpres 117/2025 | 6 PDF (Salinan + Lamp I-IV) |
| Mandate K/L | Perpres 139/2024 | 1 PDF |

## 1.2 Architecture

```
                    RPJMN/RKP PDFs (17 files)
                           │
                    ┌──────┴──────┐
                    │  PyMuPDF    │
                    │  Extraction │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │  AI OCR     │
                    │  Cleaning   │──→ DeepSeek API
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
         deepseek_     ddac_pagu_    t_kmpnen_
         policy_*      akun_2026     2026
         (963 nodes,   (1.5M rows)   (96K rows)
          857 edges,
          e5-small
          runtime)
              │            │            │
              └────────────┼────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            │            ▼
         Policy          │         Internal
         Alignment       │         Coherence
         (e5-small cos.) │         (rule-based)
              │            │            │
              ▼            │            ▼
         ddac_             │         ddac_
         anomaly_2026      │         coherence_2026
         (1 orphan+1541 weak) │
              │            │
              ▼            │
         TreasuryAI        │
         OSS 120B          │
         (reasoning)       │
              │            │
              └────────────┘
                     │
                     ▼
              Web Visualisasi (Peta Anomali)
              (human-in-the-loop · Bagian 9)
```

---

# 2. DATABASE SCHEMA

## 2.1 deepseek_policy_* — Planning Knowledge Graph

Knowledge base terstruktur dari dokumen RPJMN/RKP.

### deepseek_policy_documents (17 rows)
Registry 17 file PDF sumber.

| Column | Desc |
|--------|------|
| doc_family | RPJMN / RKP_2025 / RKP_2026 / MANDATE |
| doc_year | Tahun dokumen |
| attachment | salinan / Lampiran I / II / III / IV |
| source_file | Nama file asli |
| extraction_status | pending / extracted / done |

### deepseek_policy_pages (4,478 rows)
Teks mentah per halaman PDF.

| Column | Desc |
|--------|------|
| document_id | FK ke documents |
| page_number | 0-based index |
| raw_text | Teks hasil ekstraksi PyMuPDF |
| clean_text | Teks setelah AI cleaning |

### deepseek_policy_chunks (1,001 rows; 990 AI-cleaned)
Potongan teks untuk processing LLM.

| Column | Desc |
|--------|------|
| text | Teks mentah (garbled OCR) |
| clean_text_ai | Teks setelah AI cleaning via DeepSeek API |
| level_hint | PN / PP / KP / TEXT / KL_MATRIX |
| oc_text | 1 jika perlu OCR correction |

### deepseek_policy_nodes (963 rows)
Entitas perencanaan (PN, PP, KP). Komposisi: 43 PN + 167 PP + 753 KP.
9 false PN (nomor halaman PDF) dan 5 PP anak-nya telah dihapus (2026-06-11).

| Column | Desc |
|--------|------|
| source_type | RPJMN / RKP_2025 / RKP_2026 |
| node_type | PN / PP / KP |
| node_code | 01 / 01.01 / 01.01.01 |
| node_name | Nama entitas (AI-cleaned) |
| parent_code | Kode parent untuk edge building |

### deepseek_policy_edges (857 rows)
Hierarchy tree PN→PP→KP.

| Column | Desc |
|--------|------|
| parent_node_id | FK ke nodes |
| child_node_id | FK ke nodes |
| edge_type | HAS_PP / HAS_KP |

### deepseek_policy_embeddings (tabel legacy, tidak aktif)
Tabel ini menyimpan bge-m3 vector (1024 dimensi) yang dihasilkan script 07.
**Tidak digunakan lagi oleh pipeline aktif.** Script 10 kini meng-embed ulang
`clean_node_name_ai` (atau `node_name`) secara runtime menggunakan model
`LazarusNLP/all-indo-e5-small` (384 dimensi, Indonesian-specific fine-tune)
dengan prefix `"query: "`. Pendekatan runtime menghindari stale embeddings.

| Column | Desc |
|--------|------|
| object_type | 'node' |
| model | BAAI/bge-m3 (legacy) |
| dims | 1024 |
| vector | float32 binary blob |

## 2.2 ddac_pagu_akun_2026 — Budget Data (1,504,455 rows)

Agregasi dari ringkasan_pagu_2026 (4.4M rows) ke level akun.

| Key Columns | Desc |
|-------------|------|
| kementerian_kode | K/L code (100 unique) |
| program_kode | Program code (111 unique) |
| kegiatan_kode | Kegiatan code (2,716 unique) |
| outputkro_kode | Output/KRO code |
| akun_kode | Akun code (439 unique) |
| total_pagu | Total pagu (Rp) |
| alignment_text | program+kegiatan+output (for KP matching) |
| scope_text | fungsi+subfungsi+program+kegiatan+output |

## 2.3 ddac_pagu_vectors — Embedding Cache (7,235 rows, legacy)

bge-m3 vectors untuk setiap unique alignment_text.
**Tidak digunakan lagi oleh pipeline aktif.** Script 10 kini meng-embed alignment_text
secara runtime menggunakan e5-small. Tabel ini adalah sisa dari versi bge-m3 sebelumnya.

## 2.4 ddac_anomaly_2026 — Policy Alignment Results (7,235 rows)

| Key Columns | Desc |
|-------------|------|
| pagu_id | FK ke ddac_pagu_akun_2026 |
| alignment_score | Cosine similarity x 100 (0-100) |
| alignment_strength | strong / moderate / weak / none |
| anomaly_type | policy_orphan / weak_alignment / routine / aligned |
| anomaly_score | Composite anomaly score (0-100) |
| materiality_score | Bobot pagu (0-100) |
| review_priority | anomaly × materiality (0-100) |
| best_match_code | KP node code terdekat |
| best_match_name | KP node name terdekat |
| top3_matches | JSON top-3 KP candidates |
| llm_reasoning | TreasurAI reasoning naratif (oss120b) — terisi untuk 1,542 item |
| llm_model | Model yang digunakan: 'oss120b' |
| treasurai_verdict | valid / false_positive / manual_review |
| review_status | confirmed / dismissed / needs_review / pending |

## 2.5 ddac_coherence_2026 — Internal Coherence (1,504,455 rows)

Deteksi anomali struktur internal DIPA secara **3 level** (semua kolom kini terisi).

| Key Columns | Desc |
|-------------|------|
| jenis_komponen | Utama / Pendukung / none (dari t_kmpnen_2026) |
| jenis_anomaly | pendukung_dominan / utama_kecil / unclassified / normal |
| jenis_anomaly_score | Severity score (0-100) |
| prog_keg_coherence | **Level 1** Program↔Kegiatan cosine e5-small (×100) ✅ |
| keg_out_coherence | **Level 2** Kegiatan↔Output cosine e5-small (×100) ✅ |
| out_komp_coherence | **Level 3** keselarasan komposisi akun (100 − deviasi) ✅ |
| akun_komposisi_score | **Level 3** skor anomali komposisi belanja (0-100) ✅ |
| coherence_score | Composite: 0.35·jenis + 0.20·L1 + 0.20·L2 + 0.25·L3 |
| anomaly_flags | JSON daftar level yang terpicu (mis. `["level3_akun_tidak_lazim"]`) |
| llm_reasoning | TreasurAI reasoning untuk L3 anomali (oss120b) — terisi 19,235 baris |
| llm_model | 'oss120b' |
| treasurai_verdict | valid / false_positive / manual_review |
| review_status_coherence | confirmed / dismissed / needs_review / pending |

Threshold flag: L1/L2 dipicu bila similarity < persentil-5 distribusinya
(model e5-small, prefix "query: "). Suppression rules:
- **L1**: skip jika program mengandung `'dukungan manajemen'` (catch-all DIPA resmi)
  atau K/L militer (012=Kemhan, 060=Polri) — model tidak bisa capture jargon domain spesifik.
- **L2**: skip jika output name cocok `GENERIC_OUTPUT_PATTERNS` (dukungan teknis,
  kerja sama, dll.), atau output kode `EB%` (EBA/EBB/EBC/EBD = internal/rutin per
  Kemenkeu), atau K/L militer dengan output operasional pertahanan/keamanan (Fix E1).
- **L3**: dipicu bila `peer_count >= 5` dan deviasi >= 0.40 (atau >= 0.65 untuk
  output internal EB-series). Self-exclusion diterapkan: peer profile dihitung tanpa
  kontribusi K/L itu sendiri.

## 2.6 ddac_coherence_akun_2026 — Level-3 Peer Detail (~8K rows)

Detail perbandingan komposisi belanja per output terhadap **peer lintas K/L**
(output berkode sama, mis. semua "EBA"). Satu baris per (K/L, program, kegiatan, output).

| Key Columns | Desc |
|-------------|------|
| outputkro_kode | Kode output (peer dibandingkan per kode ini) |
| akun_komposisi_score | Deviasi komposisi vs peer × 100 (0-100) |
| out_komp_coherence | 100 − deviasi |
| peer_count | Jumlah K/L peer dengan output kode sama |
| akun_detail | JSON `{own, peer, deviation, peer_count, top_unexpected}` |

`top_unexpected` memuat kategori akun 2-digit yang share-nya jauh di atas peer,
mis. `{"akun":"53","label":"Belanja Modal","own":0.98,"peer":0.00}`.

## 2.7 deepseek_policy_kl_assignments — K/L Mapping (604 rows)

Pemetaan KP → K/L pelaksana (dari Matriks Lampiran III RPJMN/RKP).

| Key Columns | Desc |
|-------------|------|
| node_id | FK ke deepseek_policy_nodes (KP/PP) |
| kddept | Kode K/L |
| nmdept_normalized | Nama K/L ternormalisasi |
| role | pelaksana / pendukung |
| confidence | Skor keyakinan (0-1) |

---

# 3. PIPELINE SCRIPTS

Semua script di `D:\Project\deepseek-kms\scripts\`

| # | Script | Input | Output | Status |
|---|--------|-------|--------|--------|
| 01 | create_schema.py | - | 9 deepseek_policy_* tables | ✅ |
| 02 | extract_pages.py | 17 PDFs | pages + documents | ✅ |
| 03 | chunk_and_clean.py | pages | chunks | ✅ |
| 03b | ai_clean.py | chunks | clean_text_ai (deprecated) | ✅ |
| 03c | batch_clean.py | chunks | clean_text_ai (produksi, 990/1001 chunks cleaned) | ✅ |
| 04 | extract_nodes.py | clean chunks | nodes (PN/PP/KP) | ✅ |
| 05 | build_edges.py | nodes | edges (hierarchy) | ✅ |
| 07 | generate_embeddings.py | nodes | bge-m3 embeddings | ✅ |
| 08 | extract_kl.py | KL_MATRIX chunks | kl_assignments (585) | ✅ |
| 09 | master_pipeline.py | all above | final nodes+edges+emb | ✅ |
| 10 | anomaly_detect.py | pagu + KP (e5-small runtime) | ddac_anomaly_2026 (1 orphan, 1,541 weak) | ✅ |
| 11 | treasurai_reasoning.py | ddac_anomaly (orphan+weak) | llm_reasoning — **1,542 item** (1 orphan + 1,541 weak, oss120b + RPJMN/RKP mandate ctx) | ✅ |
| 12 | coherence.py | pagu + t_kmpnen | ddac_coherence_2026 (jenis komponen) | ✅ |
| 13 | coherence_levels.py | coherence + pagu | Level 1/2/3 + composite + peer detail (v2: pct_low=5, peer_min=5, --cli-args) | ✅ |
| 14 | fix_node_names.py | nodes | clean_node_name_ai (753 KP + 43 PN) | ✅ |
| 15 | coherence_reasoning.py | coherence L3 anomali | llm_reasoning — **19,235 baris** (30 output unik top pagu, oss120b + RPJMN/RKP mandate ctx) | ✅ |
| 15b | coherence_template.py | coherence L3 anomali | llm_reasoning — **142,384 baris** (SEMUA output dengan akun_komposisi_score ≥ 40, oss120b, idempotent) | ✅ |
| 16 | export_web.py | coherence + anomaly + KB | JSON statis ke `web/public/data/` (manifest, nodes, details per K/L, knowledge_graph, pipeline) | ✅ |
| 17 | refresh_analysis.py | - | Orchestrator refresh: jalankan 10→11→12→13→15b→16 + web build | ✅ |

> **Perbedaan 15 vs 15b:** Script 15 hanya memproses top-30 output unik berdasarkan pagu
> (19,235 baris). Script **15b adalah produksi** — memproses SEMUA output dengan
> `akun_komposisi_score >= 40` (142,384 baris), idempotent (skip baris yang sudah ada reasoning).
>
> **Web Visualisasi:** `scripts/16_export_web.py` mengekspor JSON statis →
> `web/` (Vite + React). Peta anomali interaktif tanpa backend. Lihat Bagian 9.

---

# 4. HOW TO RUN

## 4.1 Prerequisites

```bash
pip install pymysql pymupdf sentence-transformers openai numpy
```

## 4.2 Full Pipeline (from laptop kantor)

```bash
cd D:\Project\deepseek-kms

# Phase 1: Knowledge Extraction (sekali pakai — KB tidak berubah kecuali RPJMN/RKP baru)
python scripts\01_create_schema.py
python scripts\02_extract_pages.py
python scripts\03_chunk_and_clean.py
python scripts\03c_batch_clean.py
python scripts\04_extract_nodes.py
python scripts\05_build_edges.py
python scripts\08_extract_kl.py             # K/L mapping dari KL_MATRIX
python scripts\09_master_pipeline.py
python scripts\14_fix_node_names.py         # bersihkan nama simpul KB

# Phase 2: Analisis DIPA (jalankan setiap DIPA diperbarui — lihat Bagian 11)
python scripts\10_anomaly_detect.py         # deteksi policy_orphan + weak_alignment
python scripts\11_treasurai_reasoning.py    # reasoning semua orphan + weak_alignment (oss120b)
python scripts\12_coherence.py              # rebuild tabel coherence (jenis komponen)
python scripts\13_coherence_levels.py       # Level 1/2/3 + composite + peer comparison
python scripts\15b_coherence_template.py   # reasoning L3 coherence SEMUA output ≥40 (oss120b)
python scripts\16_export_web.py             # ekspor JSON statis ke web/public/data/
cd web && npm run build                     # rebuild frontend → web/dist/
```

> **Cara cepat refresh:** gunakan orchestrator
> ```bash
> python scripts\17_refresh_analysis.py
> ```
> Menjalankan semua step Phase 2 secara berurutan, berhenti otomatis jika ada error,
> dan menampilkan waktu tiap step. Opsi: `--skip-reasoning`, `--from-step 12`.
>
> **Catatan:** Script 11 dan 15b memerlukan koneksi ke jaringan internal Kemenkeu
> (TreasurAI endpoint). SSL self-signed ditangani otomatis (`verify=False`).

## 4.3 Web Visualisasi (Peta Anomali)

```bash
# 1. Ekspor data JSON statis dari DB
python scripts\16_export_web.py        # → web/public/data/

# 2. Jalankan frontend (development)
cd web && npm install && npm run dev   # http://localhost:5173

# 3. Build statis untuk deploy
npm run build                          # → web/dist/ (siap host di mana saja)
```

Peta anomali interaktif gaya bubblemaps: bubble dikelompokkan per cluster (pola
akun / verdict / per K/L), warna = status verdict, ukuran = pagu. Klik bubble/baris
menampilkan kartu detail (reasoning oss120b + komposisi akun + mandat RPJMN/RKP).
**Statis, tanpa backend** — cukup file JSON hasil ekspor. Detail di Bagian 9.

---

# 5. KEY FINDINGS

## 5.1 Knowledge Graph

- **963 planning nodes** (43 PN + 167 PP + 753 KP)
- **857 edges** — connected RPJMN/RKP hierarchy tree (PN→PP→KP)
- **e5-small runtime embeddings** — di-embed ulang setiap run dari `clean_node_name_ai`
- **990/1,001 chunks** AI-cleaned (11 chunks tidak butuh cleaning)
- Node names fully cleaned: 9 false PN (nomor halaman PDF) dihapus, spillover KP
  diperbaiki, semua PN 01-08 diberi canonical name RPJMN resmi

### Sample Hierarchy:
```
PN 01: Memperkokoh Ideologi Pancasila, Demokrasi, dan HAM
  PP 01.01: Penguatan Ideologi Pancasila
    KP 01.01.01: Penguatan Wawasan Ideologi Pancasila di Kalangan Penyelenggara
    KP 01.01.02: Pelaksanaan Gerakan Nasional KITA BERSAUDARA
    KP 01.01.03: Peningkatan Kualitas Pemimpin
  PP 01.02: Penguatan Komunikasi Publik dan Media
    KP 01.02.01: Penguatan Pers dan Media Massa
    KP 01.02.02: Penguatan Sistem Komunikasi
```

## 5.2 Policy Alignment Detection

- **7,235 unique alignment texts** — grain (K/L, program, kegiatan)
- **Model:** LazarusNLP/all-indo-e5-small (384-dim, Indonesian fine-tune), runtime embed
- **Klasifikasi berbasis kode resmi:** output `EB%` = routine_support,
  program `Dukungan Manajemen` = routine_support (bukan keyword mining)
- **ABS_FLOOR = 45** — semua item dengan skor < 45 dinyatakan policy_orphan

### Distribusi Anomaly (terkini):
| anomaly_type | spending_nature | Rows | Pagu |
|-------------|----------------|------|------|
| aligned | substantive | 2,747 | Rp 83.0 T |
| weak_alignment | substantive | 1,541 | Rp 152.1 T |
| routine | routine_support | 2,905 | Rp 8.3 T |
| routine | treasury_crosscutting | 41 | Rp 564.9 T |
| policy_orphan | substantive | **1** | Rp 0.0 T |

Policy orphan tersisa 1 item: ESDM kegiatan kecil, skor 44.47 — genuine orphan.
Item Rp 4.21T "Wajib Belajar 13 Tahun" (Kemendikdasmen) sebelumnya false orphan
karena nomenklatur DIPA ≠ nama KP RPJMN; setelah ABS_FLOOR diturunkan 50→45
ter-reklasifikasi sebagai weak_alignment (skor 47, KP 04.01.01).

## 5.3 AI Cleaning Quality

### Before → After:
```
"PRTORTTAS IlAsIOrAL lPlll/"  →  "PRIORITAS NASIONAL 1"
"PRES!DEN K INDONESIA"        →  "PRESIDEN REPUBLIK INDONESIA"
"FengeEbangan Tenaga Tektia"  →  "Pengembangan Tenaga Teknis"
"Demolqasi, dan Hek Asasi"    →  "Demokrasi, dan Hak Asasi"
```

## 5.4 Internal Coherence — Model 3 Level (NEW 2026-06-08)

Koherensi internal kini dianalisis pada tiga tingkat hierarki anggaran:

| Level | Cek | Basis |
|-------|-----|-------|
| 1. Program↔Kegiatan | Apakah kegiatan selaras dengan program? | cosine e5-small |
| 2. Kegiatan↔Output | Apakah output selaras dengan kegiatan? | cosine e5-small |
| 3. Output↔Akun/Komponen | Apakah jenis belanja masuk akal untuk output ini? | peer comparison lintas K/L |

**Hasil flag** (dari `anomaly_flags`, threshold pct_low=5, peer_min=5):

| Level | Unique combos | Pagu | Keterangan |
|-------|--------------|------|------------|
| L1 program↔kegiatan | **30** | Rp 1.1 T | 135→30 setelah suppress DM+militer |
| L2 kegiatan↔output | **200** | Rp 4.5 T | 217→200 setelah suppress EB+militer |
| L3 akun composition | **895** | Rp 420.0 T | threshold EB=0.65, substantif=0.40 |

Avg coherence scores: L1=51.7 · L2=46.8 · L3=79.9 · composite=28.7

**Genuine L1 anomalies tersisa (sample, diverifikasi dari DB):**
- KL 147 EK/7824 "Peningkatan Hubungan Antar Lembaga Internasional" ↔ "Program
  Pariwisata" — L1=7.2, hubungan internasional ≠ pariwisata
- KL 153 EH/8123 "Hubungan Kelembagaan" ↔ "Program Pengembangan Kawasan
  Strategis" — L1=14.4, kelembagaan non-spasial ≠ kawasan strategis
- KL 141 DC/8102 "Pengelolaan Data dan Informasi" ↔ "Program Kerukunan Umat"
  — L1=19.5, data management ≠ kerukunan beragama

**Inti Level 3 (peer comparison):** komposisi belanja sebuah output dibandingkan
dengan rata-rata seluruh output berkode sama lintas K/L. Contoh nyata dari data:
- Output **"Bantuan Masyarakat" (QEA)** di BGN (MBG) → Rp 197T, 100% transfer
  vs peer yang lebih beragam → flagged karena program baru tanpa historical peer.
- Output **"Layanan Dukungan Manajemen Internal" (EBA)** di Polri → **100% Belanja
  Barang (akun 52)** vs peer 99 K/L rata-rata 21% barang → genuine anomali.
- KL 024 keg=7958/EBA "Pelayanan Kesehatan Lanjutan" — kegiatan substantif
  RS vertikal Kemenkes menggunakan output kode internal EBA — flagged L3.

> **Catatan:** Model e5-small (Indonesian fine-tune, 384-dim) lebih akurat dari
> bge-m3 untuk istilah birokrasi Indonesia. Threshold `pct_low=5` (persentil ke-5)
> dipilih untuk mengurangi false positive. Untuk hasil lebih ketat, gunakan
> `--pct-low 3`.

## 5.5 Pembersihan Nama Simpul (NEW 2026-06-08)

`node_name` hasil ekstraksi PDF ternyata berupa blob ~250 karakter (nama + sasaran
+ indikator + angka + K/L) dengan kata-kata yang menempel akibat hilangnya spasi
line-break. Script `14_fix_node_names.py` membersihkannya secara deterministik ke
kolom `clean_node_name_ai` (non-destruktif): potong ke nama asli sebelum penanda
sasaran `NN -`, pisah camelCase (`HakAsasi`→`Hak Asasi`) dan kata sambung yang
menempel (`Abadidan`→`Abadi dan`).

**Hasil terkini (963 nodes):**
- **753 KP**: `clean_node_name_ai` terisi 100% (AI-cleaned + Fix C1/C2)
- **43 PN**: `clean_node_name_ai` terisi 100% (canonical names RPJMN resmi)
- **167 PP**: `clean_node_name_ai` NULL — menggunakan `node_name` langsung.
  PP names dari dokumen RPJMN umumnya sudah bersih (nama program resmi).

Ekspor web & query memakai `COALESCE(clean_node_name_ai, node_name)` untuk semua 963 nodes.

## 5.6 K/L Institutional Mapping (NEW)

Script `08_extract_kl.py` memetakan KP → K/L pelaksana dari Matriks Lampiran III:
**604 penugasan** (362 simpul KP/PP, 72 K/L), confidence mayoritas @0.9.

---

# 6. API CONFIGURATIONS

## 6.1 TreasurAI (Internal Kemenkeu)

```
Base URL: https://treasurai-src-treasury-ai-dev.apps.ocpsdc-djpb.kemenkeu.go.id
Model:    /api/v1/openshift/oss120b/chat  (aktif — 120B parameter)
Auth:     X-API-Key header
Config:   scripts/common/config.py  (TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS)
SSL:      verify=False (server menggunakan self-signed certificate Kemenkeu)
Timeout:  60 detik per request
```

Digunakan oleh script 11 (policy alignment) dan script 15 (coherence L3).
Setiap prompt di-enrich konteks mandat RPJMN/RKP per K/L via `common/kl_context.py`.

## 6.2 DeepSeek API

```
Purpose: AI OCR cleaning (Phase 3b)
Config:  .env file with DEEPSEEK_API_KEY
```

## 6.3 bge-m3 Embeddings (legacy — tidak aktif)

```
Model:    BAAI/bge-m3 (1024 dimensions)  [LEGACY — tidak digunakan]
Replaced: LazarusNLP/all-indo-e5-small (384-dim, runtime, Indonesian fine-tune)
Cache:    ~/.cache/huggingface/hub/models--BAAI--bge-m3
```

Model aktif untuk semua embedding (script 10 dan 13) adalah **e5-small**,
di-embed ulang setiap run sehingga vector space selalu konsisten.

---

# 7. USEFUL QUERIES

## 7.1 Top Policy Orphans (Valid Anomalies)
```sql
SELECT kementerian_kode, kementerian_uraian,
       alignment_score, review_priority,
       best_match_name, llm_reasoning
FROM ddac_anomaly_2026
WHERE anomaly_type = 'policy_orphan'
  AND llm_reasoning LIKE '%valid%'
  AND llm_reasoning NOT LIKE '%false%'
ORDER BY review_priority DESC
LIMIT 20;
```

## 7.2 Hierarchy Tree (RKP 2026)
```sql
SELECT pn.node_code, pn.node_name,
       pp.node_code, pp.node_name,
       kp.node_code, kp.node_name
FROM deepseek_policy_nodes pn
JOIN deepseek_policy_edges e1 ON pn.id = e1.parent_node_id
JOIN deepseek_policy_nodes pp ON e1.child_node_id = pp.id
JOIN deepseek_policy_edges e2 ON pp.id = e2.parent_node_id
JOIN deepseek_policy_nodes kp ON e2.child_node_id = kp.id
WHERE pn.source_type = 'RKP_2026'
ORDER BY pn.node_code, pp.node_code, kp.node_code;
```

## 7.3 AI Cleaning Quality Check
```sql
SELECT d.doc_family, d.attachment,
       LEFT(c.text, 80) as raw,
       LEFT(c.clean_text_ai, 80) as cleaned
FROM deepseek_policy_chunks c
JOIN deepseek_policy_documents d ON c.document_id = d.id
WHERE c.clean_text_ai IS NOT NULL
LIMIT 10;
```

## 7.4 Jenis Komponen Anomaly
```sql
SELECT kementerian_kode, kementerian_uraian,
       program_kode, program_uraian,
       komponen_uraian, jenis_komponen, jenis_anomaly,
       total_pagu
FROM ddac_coherence_2026
WHERE jenis_anomaly IN ('pendukung_dominan', 'utama_kecil')
ORDER BY total_pagu DESC;
```

## 7.5 Anomali Koherensi 3 Level (Level 3 paling parah)
```sql
SELECT kementerian_kode, program_kode, kegiatan_kode, outputkro_kode,
       prog_keg_coherence, keg_out_coherence,
       out_komp_coherence, akun_komposisi_score,
       coherence_score, anomaly_flags
FROM ddac_coherence_2026
WHERE JSON_CONTAINS(anomaly_flags, '"level3_akun_tidak_lazim"')
ORDER BY akun_komposisi_score DESC
LIMIT 20;
```

---

# 8. LIMITATIONS & CAVEATS

## 8.1 e5-small Embedding Notes

Model aktif: `LazarusNLP/all-indo-e5-small` (384-dim, Indonesian fine-tune dari
multilingual-e5-small). Model ini **lebih akurat** untuk istilah birokrasi Indonesia
dibandingkan bge-m3 (1024-dim, multilingual general-purpose) yang sebelumnya digunakan.

Keterbatasan yang tersisa:

- Prefix wajib `"query: "` saat inference — tanpa prefix, similarity turun ~15%.
- Vocabulary militer teknis masih under-represented: "Penggunaan Kekuatan",
  "Operasi Bidang Pertahanan" masih berpotensi under-score di L1/L2.
  Mitigasi: MILITARY_DOMAIN_KL {"012","060"} (012=Kemhan, 060=Polri) di-suppress.
- Kode output generik (EBA/EBB/EBC/EBD) tidak mengandung semantik yang bisa
  dibandingkan dengan nama kegiatan. Mitigasi: EB-series di-suppress di L2.

**Rekomendasi jika akurasi perlu ditingkatkan:** fine-tune e5-small dengan
pasangan program↔kegiatan dari 10 tahun DIPA historis sebagai training set.

## 8.2 Peer Comparison Caveats

- **Peer count rendah (< 5):** beberapa output code hanya digunakan oleh 1-2
  K/L, sehingga perbandingan statistik tidak bermakna. Detail table (`ddac_
  coherence_akun_2026`) hanya memuat baris dengan `peer_count >= 3`.
- **Kesamaan kode ≠ kesamaan makna:** kode output seperti "EBA" (Layanan
  Dukungan Manajemen Internal) bersifat generik dan digunakan lintas K/L
  dengan karakteristik berbeda — komposisi belanja wajar bervariasi.

## 8.3 Data Duplication Note

`ddac_pagu_akun_2026` memiliki 1.5M baris yang merupakan ekspansi dari ~62K
kombinasi unik — setiap akun 6-digit menjadi baris terpisah. Agregasi di
script 13 menggunakan `LEFT(akun_kode,2)` untuk mengelompokkan per kategori
2-digit. Ini sudah benar dan tidak menyebabkan overcounting.

---

# 9. FILE INVENTORY

```
D:\Project\deepseek-kms\
├── README.md
├── konfigurasi
├── .env                          (DEEPSEEK_API_KEY)
├── treasurai_config.json         (TreasurAI credentials)
├── docs\
│   ├── MASTER_DOCUMENTATION.md   ← this file
│   ├── METHODOLOGY.md            ← metodologi detail (baru)
│   ├── ARCHITECTURE.md
│   ├── SCHEMA.md
│   ├── COMPARISON.md
│   └── FINAL_REPORT.md
├── scripts\
│   ├── 01_create_schema.py
│   ├── 02_extract_pages.py
│   ├── 03_chunk_and_clean.py
│   ├── 03b_ai_clean.py           (deprecated — gunakan 03c)
│   ├── 03c_batch_clean.py        ← produksi AI OCR cleaning
│   ├── 04_extract_nodes.py
│   ├── 05_build_edges.py
│   ├── 06_extract_tables.py
│   ├── 07_generate_embeddings.py (legacy bge-m3, digantikan runtime embed di 10)
│   ├── 08_extract_kl.py
│   ├── 09_master_pipeline.py
│   ├── 10_anomaly_detect.py
│   ├── 11_treasurai_reasoning.py ← reasoning semua orphan + weak_alignment (oss120b)
│   ├── 12_coherence.py
│   ├── 13_coherence_levels.py    ← Level 1/2/3 + peer comparison
│   ├── 14_fix_node_names.py
│   ├── 15_coherence_reasoning.py ← reasoning coherence L3 top-30 (referensi)
│   ├── 15b_coherence_template.py ← PRODUKSI: reasoning L3 semua output ≥40 (oss120b)
│   ├── 16_export_web.py          ← ekspor JSON statis ke web/public/data/
│   ├── 17_refresh_analysis.py    ← orchestrator refresh (10→11→12→13→15b→16→web)
│   └── common\
│       ├── config.py             (BUDGET_YEAR, TABLE_*, EMBEDDING_MODEL, TREASURAI_*, DB)
│       ├── db.py
│       ├── verdict.py
│       └── kl_context.py         ← konteks mandat RPJMN/RKP per K/L
├── web\                          ← Vite + React + TS + Tailwind frontend
│   ├── public\data\              ← output 16_export_web.py (JSON statis)
│   ├── src\                      ← komponen React (BubbleMap, AnomalyList, dll.)
│   ├── dist\                     ← hasil npm run build (siap deploy)
│   └── package.json
└── output\
    ├── batch_clean_log.txt
    └── extraction_logs\
```

---

# 10. PERBANDINGAN: SENTINEL vs Sistem Lama (codex_policy_*)

| Metric | Sistem lama | SENTINEL |
|--------|-------------|----------|
| Documents | 17 | 17 |
| Pages | 4,478 | 4,478 |
| Chunks | 1,444 | 990 (smarter) |
| Nodes | 5,334 | 963 (connected) |
| **Edges** | **0** ❌ | **857** ✅ |
| **Embeddings** | **0** ❌ | **e5-small runtime** ✅ |
| **AI Cleaned** | **0%** ❌ | **100%** ✅ |
| **K/L Mapping** | **N/A** ❌ | **604 penugasan, 72 K/L** ✅ |
| **Anomaly Detection** | **N/A** ❌ | **1 orphan + 1,541 weak (e5-small, ABS_FLOOR=45)** ✅ |
| **Coherence (3 level)** | **N/A** ❌ | **L1=30 · L2=200 · L3=895 combos flagged** ✅ |
| **Name Cleaning** | **N/A** ❌ | **796 AI-cleaned + 167 PP (node_name) = 963 total** ✅ |
| **Web Visualisasi** | **N/A** ❌ | **Peta anomali bubblemaps (Vite + React, statis)** ✅ |
| **Hierarchy** | Flat list | Connected tree |
| **Self-contained** | No | 17 scripts + web visualisasi + 6 docs |

---

## 9. Web Visualisasi (Peta Anomali)

Antarmuka eksplorasi interaktif gaya **bubblemaps** untuk menyajikan hasil ke pemangku kepentingan.

- **Skrip ekspor:** `scripts/16_export_web.py` → JSON statis ke `web/public/data/`
  (manifest, 1.101 node bubble, detail per K/L lazy-load, knowledge graph, pipeline).
- **Frontend:** `web/` — Vite + React + TypeScript + Tailwind, bubble via `react-force-graph-2d`
  (WebGL/d3-force), motion via Framer Motion. Data **statis, tanpa backend**.
- **Encoding:** posisi = cluster (filter: pola akun / verdict / per K/L), warna = status verdict
  (merah valid · oranye review · hijau false-pos · abu normal), ukuran = pagu.
- **Interaksi:** klik bubble ⇄ klik baris daftar sinkron; kartu detail menampilkan reasoning
  oss120b + komposisi akun (own vs peer) + chip mandat RPJMN/RKP.
- **Embed:** `?embed=1` (iframe) atau custom element `<ddac-anomaly-map>` via `embed.js`.
  `base: "./"` → aset relatif, host di mana saja (statis). Lihat `web/README.md`.

Build: `cd web && npm install && npm run build` → `web/dist/` siap deploy.

---

---

# 11. REFRESH RUNBOOK

Panduan operasional ketika data DIPA berubah. KB (nodes/edges RPJMN/RKP) stabil —
hanya tabel pagu-derived yang perlu di-refresh.

## 11.1 Skenario A — APBN-P (revisi tengah tahun, tahun sama)

Berlaku ketika: pagu DIPA berubah tetapi kode tahun tetap (mis. revisi Mei 2026).
DBA memperbarui `ddac_pagu_akun_2026` dengan data baru.

```bash
cd D:\Project\deepseek-kms

# Cara cepat — satu perintah:
python scripts\17_refresh_analysis.py

# Atau manual step-by-step:
python scripts\10_anomaly_detect.py       # hapus + rebuild ddac_anomaly_2026
python scripts\11_treasurai_reasoning.py  # idempotent — isi reasoning yang kosong saja
python scripts\12_coherence.py            # DROP + CREATE ddac_coherence_2026
python scripts\13_coherence_levels.py     # hitung ulang L1/L2/L3 + peer
python scripts\15b_coherence_template.py # idempotent — isi reasoning yang kosong saja
python scripts\16_export_web.py           # ekspor JSON statis ke web/public/data/
cd web && npm run build                   # rebuild frontend
```

**Catatan penting:**
- Script 12 menghapus seluruh `ddac_coherence_2026` — reasoning lama hilang.
- Script 15b dan 11 idempotent: skip baris yang sudah punya `llm_reasoning`.
  Jika ingin reasoning diulang dari nol, SET `llm_reasoning = NULL` dulu di DB.
- Script 10 menghapus seluruh `ddac_anomaly_2026` tetapi juga preserve reasoning
  lama (simpan ke temp table, restore setelah re-insert).

## 11.2 Skenario B — Tahun Anggaran Baru (mis. APBN 2027)

Berlaku ketika: DBA membuat tabel baru `ddac_pagu_akun_2027`, `t_kmpnen_2027`, dll.

**Langkah 1:** Set tahun baru di `.env`:
```bash
# .env
BUDGET_YEAR=2027
```

**Langkah 2:** Jalankan refresh — semua script otomatis menggunakan tabel 2027:
```bash
python scripts\17_refresh_analysis.py
```

Semua konstanta tabel di-generate otomatis dari `BUDGET_YEAR`:

| Variabel | Nilai (BUDGET_YEAR=2027) |
|----------|--------------------------|
| `TABLE_PAGU_AKUN` | `ddac_pagu_akun_2027` |
| `TABLE_ANOMALY` | `ddac_anomaly_2027` |
| `TABLE_COHERENCE` | `ddac_coherence_2027` |
| `TABLE_COHERENCE_AKUN` | `ddac_coherence_akun_2027` |
| `TABLE_KMPNEN` | `t_kmpnen_2027` |
| `TABLE_RINGKASAN` | `ringkasan_pagu_2027` |

Tidak ada perubahan kode yang diperlukan.

## 11.3 Verifikasi Setelah Refresh

```bash
python scripts\00_status_check.py
```

Cek yang diharapkan:
- `ddac_anomaly_<year>` — ada baris policy_orphan + weak_alignment
- `ddac_coherence_<year>` — row count ≈ row count pagu (1.5M+)
- `ddac_coherence_akun_<year>` — ada ribuan baris (L3 peer detail)
- `llm_reasoning` di coherence — ada puluhan ribu baris

## 11.4 Troubleshooting

| Gejala | Kemungkinan penyebab | Solusi |
|--------|---------------------|--------|
| Script 10 error tabel tidak ada | `ddac_pagu_akun_<year>` belum dibuat | Minta DBA buat tabel sebelum refresh |
| Script 11/15b timeout | TreasurAI overloaded | Tunggu dan jalankan ulang dengan `--from-step 11` |
| Web build gagal | Node modules belum di-install | `cd web && npm install` dulu |
| `BUDGET_YEAR` tidak terbaca | `.env` belum disimpan | `set BUDGET_YEAR=2027 && python ...` (Windows) |
| Reasoning lama ingin diulang | Butuh re-run reasoning | `UPDATE ddac_coherence_2026 SET llm_reasoning=NULL` lalu `--from-step 11` |

---

*SENTINEL · Dokumentasi Utama — 2026-06-07, diperbarui 2026-06-12 (web visualisasi, refresh runbook, parameterisasi BUDGET_YEAR).*
