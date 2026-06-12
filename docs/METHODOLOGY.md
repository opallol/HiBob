# Metodologi SENTINEL
## Sistem Analisis Keselarasan dan Koherensi Anggaran APBN 2026

**Versi:** 1.1 (2026-06-12)
**Database:** `ddac2026` @ 172.16.2.153

---

## Arsitektur Tiga-Model: Prinsip Privasi Data

Sebelum masuk ke fase-fase teknis, hal paling fundamental yang perlu dipahami adalah **mengapa sistem ini menggunakan tiga model AI yang berbeda** — bukan satu model untuk segalanya.

| Model | Jenis | Digunakan Pada | Alasan |
|-------|-------|----------------|--------|
| **DeepSeek Chat** | API Eksternal (Cloud) | Dokumen PDF publik | RPJMN/RKP adalah dokumen publik yang sudah dipublikasikan pemerintah. Aman dikirim ke API eksternal. |
| **LazarusNLP/all-indo-e5-small** | Model Lokal (On-premise) | Data anggaran DIPA | Data DIPA per K/L bersifat internal pemerintah. Model dijalankan lokal — **tidak ada data yang meninggalkan server**. |
| **TreasurAI OSS 120B** | API Internal Kemenkeu | Reasoning **semua** anomali keselarasan (1 orphan + 1,541 weak) dan anomali koherensi L3 (19,235 baris) | Data DIPA yang sudah dianalisis dikirim ke sistem internal Kemenkeu. Tidak keluar jaringan. |

**Prinsip dasar:** Data yang lebih sensitif ditangani oleh infrastruktur yang lebih tertutup. Dokumen kebijakan publik → cloud. Data anggaran K/L → lokal. Analisis kualitatif anggaran → jaringan internal Kemenkeu.

---

## Gambaran Alur Sistem

```
[17 PDF Publik: RPJMN, RKP]
          │
          ▼ PyMuPDF (text extraction)
    [deepseek_policy_pages]
          │
          ▼ Chunking berbasis hierarki
    [deepseek_policy_chunks]
          │
          ▼ DeepSeek Chat API ← (dokumen publik, aman ke cloud)
    [clean_text_ai per chunk]
          │
          ▼ Regex state machine
    [deepseek_policy_nodes: 963 node PN/PP/KP]
          │
          ▼ Code prefix matching
    [deepseek_policy_edges: 857 relasi hierarki]
          │
          ▼ DeepSeek Chat API ← (dokumen publik)
    [deepseek_policy_kl_assignments: 604 penugasan K/L]
          │
          ▼ Digabung dengan:
    [ddac_pagu_akun_2026: 1.504.455 baris DIPA 2026] ← DATA INTERNAL
          │
          ├─▶ LazarusNLP e5-small (lokal) → cosine similarity
          │   [ddac_anomaly_2026: status keselarasan per output DIPA]
          │         │
          │         └─▶ TreasurAI OSS 120B + kl_context.py (jaringan Kemenkeu)
          │             [llm_reasoning: 1 orphan + 1,541 weak = 1,542 item]
          │
          └─▶ LazarusNLP e5-small (lokal) → 3-level coherence
              [ddac_coherence_2026: 1.504.455 baris skor koherensi]
                    │
                    └─▶ TreasurAI OSS 120B + kl_context.py (jaringan Kemenkeu)
                        [llm_reasoning coherence L3: 19,235 baris (30 output unik)]
```

---

## Fase 1 — Inventarisasi dan Ekstraksi Dokumen

### Detail Teknis

**Script:** `02_extract_pages.py`
**Library:** PyMuPDF (`pymupdf`)
**Input:** 17 file PDF regulasi perencanaan nasional

| Kelompok Dokumen | Isi |
|-----------------|-----|
| RPJMN 2025–2029 | Lampiran I (narasi), Lampiran II (matriks KP), Lampiran III (penugasan K/L) |
| RKP 2025 | Salinan + Lampiran I/II |
| RKP 2026 | Salinan + Lampiran I/II |
| MANDATE | Perpres terkait prioritas nasional |

Proses per halaman:
1. Ekstraksi text-layer via `page.get_text("text")`
2. Hitung `word_count` dan klasifikasi `page_kind` (text/table/mixed/blank)
3. SHA-256 hash dari `raw_text` untuk deduplication
4. Simpan ke `deepseek_policy_pages` dengan FK ke dokumennya

**Output DB:**
- `deepseek_policy_documents` → 17 baris (registri + `extraction_status`)
- `deepseek_policy_pages` → 4.478 baris (1 baris = 1 halaman PDF)

### Penjelasan Konseptual

Bayangkan kita ingin membaca 17 buku tebal secara otomatis. Langkah pertama adalah membuka setiap buku, halaman demi halaman, dan menyalin semua tulisan yang ada ke dalam catatan digital. PyMuPDF melakukan pekerjaan ini — ia membaca "layer teks tersembunyi" yang ada di dalam file PDF (bukan mengenali gambar/foto, melainkan teks yang sudah dikodekan secara digital di dalam PDF). Hasilnya adalah teks mentah per halaman yang tersimpan rapi di database, lengkap dengan nomor halaman, jumlah kata, dan sidik jari unik tiap halaman. Ini adalah fondasi dari semua analisis selanjutnya — tanpa teks yang tersimpan dengan baik, tidak ada yang bisa diproses lebih lanjut.

---

## Fase 2 — Chunking Adaptif Berbasis Hierarki

### Detail Teknis

**Script:** `03_chunk_and_clean.py`
**Strategi:** Boundary-aware chunking (bukan fixed-size)

Algoritma:
1. Scan teks tiap halaman untuk penanda hierarki: `PRIORITAS NASIONAL`, `PROGRAM PRIORITAS`, `KEGIATAN PRIORITAS`
2. Jika ditemukan penanda → mulai chunk baru, set `level_hint`
3. Kelompokkan halaman-halaman berurutan ke chunk yang sama selama tidak ada penanda baru
4. Estimasi token dengan `len(text) // 4`
5. Chunk dengan `token_estimate ≤ 50` dilewati di fase cleaning (terlalu pendek untuk diproses LLM)

**Level hint yang diassign:**
- `PN` — chunk berisi penanda Prioritas Nasional
- `PP` — chunk berisi penanda Program Prioritas
- `KP` — chunk berisi penanda Kegiatan Prioritas
- `KL_MATRIX` — chunk berisi tabel penugasan K/L (Lampiran III)
- `TEXT` — chunk narasi umum

**Output DB:**
- `deepseek_policy_chunks` → 1.001 baris
- Kolom kunci: `text` (teks asli), `level_hint`, `token_estimate`, `page_start`, `page_end`

### Penjelasan Konseptual

Dokumen RPJMN memiliki struktur hirarkis yang sangat khas: ada bab Prioritas Nasional, di dalamnya ada Program Prioritas, di dalamnya lagi ada Kegiatan Prioritas. Jika kita memotong teks secara sembarangan setiap 500 kata (fixed-size), bisa terjadi kondisi di mana satu Kegiatan Prioritas yang tersebar di 3 halaman dipotong menjadi 3 potongan kecil — sehingga saat dikirim ke AI untuk dibersihkan, konteksnya hilang. Chunking berbasis hierarki memastikan bahwa setiap "unit informasi yang bermakna" (satu PN, satu PP, atau satu KP beserta seluruh deskripsinya) masuk ke dalam satu paket yang utuh. Analoginya: jangan potong satu paragraf di tengah kalimat — potonglah di antara paragraf.

---

## Fase 3 — AI Cleaning: Koreksi OCR dengan DeepSeek

### Detail Teknis

**Script:** `03c_batch_clean.py`
**Model:** `deepseek-chat` via DeepSeek API (eksternal)
**Alasan menggunakan API eksternal:** Input adalah dokumen PDF pemerintah yang sudah **dipublikasikan secara resmi** (RPJMN, RKP tersedia di setneg.go.id). Tidak ada data sensitif yang dikirim.

**Prompt yang digunakan (dipangkas):**
```
"Perbaiki teks OCR rusak dari dokumen pemerintah Indonesia.
Output HANYA teks bersih, tanpa kata pembuka.

ATURAN:
1. Perbaiki error OCR: PRTORTTAS→PRIORITAS, ldeoIogi→Ideologi,
   Demolqasi→Demokrasi, PRES!DEN→PRESIDEN, REPU BLIK→REPUBLIK
2. PERTAHANKAN SEMUA angka, kode (01.01.01), nilai Rp APA ADANYA
3. JANGAN tambah, kurang, ringkas, atau ubah struktur teks
4. JANGAN beri kata pembuka (Tentu, Berikut, Baik, dll.)"
```

**Parameter API:**
- `temperature = 0.1` — hampir deterministik, meminimalkan "kreativitas" LLM
- `max_tokens = 4000`
- Teks input di-truncate ke 6.000 karakter pertama

**Mekanisme loop:**
```python
while True:
    # Ambil batch 8 chunk yang belum dibersihkan, prioritas PN→PP→KP
    SELECT ... WHERE clean_text_ai IS NULL AND token_estimate > 50
    ORDER BY CASE level_hint WHEN 'PN' THEN 1 ... END

    # Proses → simpan ke clean_text_ai
    # Commit per item (tidak hilang jika interrupt)

    if remaining == 0: break
```

**Idempoten:** Bisa dijalankan ulang kapan saja — hanya memproses `clean_text_ai IS NULL`.

**Output DB:**
- `deepseek_policy_chunks.clean_text_ai` — terisi untuk **990 dari 1.001 chunk**
- `deepseek_policy_chunks.oc_text = 1` — flag bahwa chunk ini pernah di-clean
- `deepseek_policy_chunks.model_used = 'deepseek-chat'`
- 11 chunk tidak diproses karena `token_estimate ≤ 50` (halaman transisi, header kosong)

**Contoh transformasi nyata:**

| Sebelum (Raw OCR) | Sesudah (AI Cleaned) |
|-------------------|----------------------|
| `PRTORTTAS IlAsIOrAL lPlll/` | `PRIORITAS NASIONAL 1:` |
| `ldeoIogi Pancasila, Demolqasi` | `Ideologi Pancasila, Demokrasi` |
| `XFI}IATAITPRIO TAA(XP}` | `KEGIATAN PRIORITAS (KP)` |
| `Peng€mbangan Tenaga Tektia P€f,adilan` | `Pengembangan Tenaga Teknis Peradilan` |

### Penjelasan Konseptual

Dokumen pemerintah Indonesia sering kali tersedia hanya dalam format scan atau PDF berbasis gambar yang kemudian di-OCR (Optical Character Recognition) secara otomatis. Proses OCR tidak sempurna — ia sering salah membaca huruf yang mirip secara visual: huruf `I` dibaca `l`, tanda `!` dibaca sebagai `i`, spasi di dalam kata hilang, dan karakter khusus muncul di tempat yang salah. Akibatnya, teks yang keluar adalah campuran kata yang benar dan "sampah digital". Tanpa koreksi, semua analisis berikutnya akan gagal karena sistem tidak bisa mengenali kata `PRIORITAS` jika tulisannya adalah `PRTORTTAS`. Di sinilah DeepSeek Chat difungsikan bukan sebagai sistem yang "memahami kebijakan", melainkan murni sebagai **proofreader bertenaga AI** — ia diberi instruksi sangat ketat untuk hanya memperbaiki ejaan yang rusak tanpa mengubah makna, angka, atau struktur dokumen.

---

## Fase 4 — Ekstraksi Node: Membangun Ensiklopedi Prioritas Nasional

### Detail Teknis

**Script:** `04_extract_nodes.py`
**Tidak menggunakan LLM** — murni regex + state machine deterministic
**Input:** `COALESCE(clean_text_ai, text)` — selalu gunakan versi bersih jika ada

**Tiga pola regex utama:**

```python
# PN: menangkap variasi OCR yang masih tersisa
PN_HEADER = re.compile(
    r'(?:PRIORITAS\s*(?:NASIONAL|IIAAIOITL|TASIONAL|NASIOIIAL))\s*(\d{1,2})',
    re.IGNORECASE
)

# PP: kode 2-part (01.01)
PP_HEADER = re.compile(
    r'(?:PROGRAM|PROGRA[UM])\s*(?:PRIORITAS|PRIORNAA)\s*(\d{1,2})[\.\-]+(\d{1,2})',
    re.IGNORECASE
)

# KP: kode 3-part (01.01.01)
KP_HEADER = re.compile(
    r'(?:KEGIATAN|KEGIATAII)\s*(?:PRIORITAS|PRIORITTS)\s*(\d{1,2})[\.\-]+(\d{1,2})[\.\-]+(\d{1,2})',
    re.IGNORECASE
)
```

**Dua format dokumen yang ditangani:**

*Format A — Inline OCR (Lampiran I, narasi):*
```
"KEGIATAN PRIORITAS 01.01.01 Penguatan Ideologi Pancasila..."
```
→ Regex KP_HEADER menangkap kode + nama dari satu baris.

*Format B — Matrix Clean (Lampiran II, tabel matriks):*
```
01.01.01
KP: Penguatan Ideologi Pancasila
```
→ CODE_PATTERN mendeteksi kode 3-part, lalu look-ahead mencari label `KP:` dalam 5 baris berikutnya.

**State machine lintas chunk:**
```python
current_pn = None
current_pp = None

for chunk in chunks_ordered_by_index:
    nodes, current_pn, current_pp = extract_pn_pp_kp_from_text(
        text=COALESCE(clean, raw),
        initial_pn=current_pn,   # ← state dibawa dari chunk sebelumnya
        initial_pp=current_pp
    )
```

Tanpa mekanisme ini: KP di chunk ke-5 yang tidak mengulang "PRIORITAS NASIONAL 01" tidak akan punya `parent_code`. State machine memastikan konteks hierarki terbawa sepanjang dokumen.

**Normalisasi kode:**
- `01` → `PN-01`
- `01.01` → `PP-01-01`
- `01.01.01` → `KP-01-01-01`

**Deduplikasi:** `WHERE (document_id, node_type, node_code)` sudah ada → skip.

**Output DB:**
- `deepseek_policy_nodes` → **963 baris**
  - 43 PN (Prioritas Nasional 01–08 + turunan RKP)
  - 167 PP (Program Prioritas)
  - 753 KP (Kegiatan Prioritas)
- Setiap node menyimpan: `node_code`, `node_name` (nama asli), `parent_code`, `normalized_code`, `source_page`, `raw_text` (kutipan bukti), `confidence`

### Penjelasan Konseptual

Setelah teks bersih tersedia, sistem perlu membaca teks itu layaknya seorang analis yang membaca dokumen RPJMN — dan mengidentifikasi setiap entitas perencanaan yang disebutkan. Dalam RPJMN, hierarki perencanaan tersusun seperti pohon: Prioritas Nasional (setara "bab besar") → Program Prioritas (setara "sub-bab") → Kegiatan Prioritas (setara "poin-poin rencana konkret"). Fase ini mengotomatisasi pembacaan pohon tersebut. Hasilnya bukan sekadar daftar kata — melainkan struktur terorganisir yang merekam kode unik setiap entitas (misal KP 01.01.01), nama lengkapnya, dan siapa induknya (PP mana, PN mana). Ini adalah pondasi dari "knowledge graph" — kita tahu apa saja entitas yang ada dan bagaimana mereka terhubung secara hierarkis.

---

## Fase 5 — Pembangunan Graf Pengetahuan (Edge Building)

### Detail Teknis

**Script:** `05_build_edges.py`
**Input:** `deepseek_policy_nodes` — 963 node dengan `parent_code`

**Pass 1 — Direct parent_code matching:**
```sql
SELECT n1.id, n2.id, n1.document_id, n1.source_type
FROM deepseek_policy_nodes n1
LEFT JOIN deepseek_policy_nodes n2
    ON n1.parent_code = n2.node_code
    AND n1.document_id = n2.document_id   -- dalam dokumen yang sama
WHERE n1.parent_code != ''
AND n2.id IS NOT NULL
```
→ Edge dibuat jika ada node parent dengan kode yang cocok di dokumen yang sama.

**Pass 2 — Code prefix matching (fallback lintas dokumen):**
```sql
WHERE
    (n1.node_type = 'PP' AND n2.node_type = 'PN'
     AND SUBSTRING_INDEX(n1.node_code, '.', 1) = n2.node_code)
    OR
    (n1.node_type = 'KP' AND n2.node_type = 'PP'
     AND SUBSTRING_INDEX(n1.node_code, '.', 2) = n2.node_code)
```
→ PP `01.02` secara matematis adalah anak dari PN `01` — ini dipakai sebagai fallback jika PN-nya ada di dokumen berbeda.

**Edge types:**

| Parent Type | Child Type | Edge Type |
|-------------|-----------|-----------|
| PN | PP | `HAS_PP` |
| PP | KP | `HAS_KP` |
| KP | PROGRAM | `HAS_PROGRAM` |
| PROGRAM | KEGIATAN | `HAS_KEGIATAN` |
| KEGIATAN | KRO | `HAS_KRO` |
| KRO | RO | `HAS_RO` |

**Deduplikasi:** `UNIQUE KEY (parent_node_id, child_node_id, edge_type)` di level DB.

**Output DB:**
- `deepseek_policy_edges` → **857 baris**
- Setiap edge: `parent_node_id`, `child_node_id`, `edge_type`, `source_type`, `confidence`
- Graf ini yang mengubah 963 node flat menjadi pohon yang bisa di-traverse

### Penjelasan Konseptual

Jika node-node dari fase sebelumnya ibarat kartu nama yang masing-masing bertuliskan nama dan kode — maka edge adalah benang yang menghubungkan kartu-kartu itu membentuk pohon keluarga. Tanpa edge, kita hanya punya 963 kartu nama yang berserakan dan tidak bisa menjawab pertanyaan "KP mana saja yang berada di bawah PN Transformasi Ekonomi?" Dengan 857 edge, kita kini punya graf yang bisa ditelusuri — mulai dari PN di level tertinggi, turun ke PP, turun lagi ke KP. Ini yang membedakan sistem ini dari sistem lain yang hanya menyimpan daftar entitas tanpa relasi: kita bisa melakukan graph traversal, menjawab pertanyaan hierarkis, dan memvisualisasikan pohon perencanaan secara utuh.

---

## Fase 6 — Pembersihan Nama Node

### Detail Teknis

**Script:** `14_fix_node_names.py`
**Tidak menggunakan LLM** — murni regex deterministik
**Alasan tidak pakai LLM:** Nama node adalah data struktural, bukan teks bebas. Regex lebih cepat, konsisten, dan tidak berisiko mengubah makna.

**Problem yang diselesaikan:**
Proses ekstraksi (fase 4) menarik nama node dari teks PDF yang panjang. Akibatnya `node_name` sering berisi "blob" seperti:
```
"Pengelolaan Keamanan LautSasaran: Terselesaikannya kasus pelanggaran
di wilayah laut. Target 2026: 85% kasus. Alokasi: Rp 2.1 T"
```
Padahal nama yang diinginkan hanyalah: `"Pengelolaan Keamanan Laut"`

**Tiga transformasi regex:**

1. **Truncate sasaran/indikator:** Potong semua teks setelah kata `Sasaran:`, `Indikator:`, `Target`, `Alokasi`
2. **Pisah camelCase:** `KeamananLaut` → `Keamanan Laut` (terjadi ketika line-break PDF hilang)
3. **Pisah kata sambung menempel:** `Abadidan` → `Abadi dan` (spasi sebelum kata penghubung hilang)

**Hasil disimpan di kolom terpisah** `clean_node_name_ai` — tidak menimpa `node_name` asli.

**Cakupan:**
- **753 KP + 43 PN** mendapat `clean_node_name_ai` eksplisit
- **167 PP** dibiarkan `NULL` di kolom `clean_node_name_ai` karena `node_name` PP sudah bersih secara alami (nama PP dalam RPJMN pendek dan terstruktur: *"Penguatan Ideologi Pancasila, Wawasan Kebangsaan"*)
- Semua konsumen data memakai `COALESCE(clean_node_name_ai, node_name)` — dengan demikian PP tetap tampil benar

**Output DB:**
- `deepseek_policy_nodes.clean_node_name_ai` → terisi untuk 796 node (753 KP + 43 PN)

### Penjelasan Konseptual

Ketika mesin membaca PDF dan menarik nama entitas, ia tidak tahu persis di mana nama berakhir dan deskripsi teknis dimulai. Hasilnya, nama yang diekstrak sering membawa "ekor" yang panjang — berisi sasaran, indikator, target angka, dan alokasi anggaran yang seharusnya bukan bagian dari nama. Ini menyulitkan tampilan visual dan menyulitkan pencocokan nama. Fase ini membersihkan ekor tersebut secara deterministik: cukup potong di kata penanda tertentu, pisah kata yang menempel, rapikan spasi. Tidak ada AI yang diperlukan karena polanya sangat konsisten — dan pendekatan deterministik jauh lebih dapat dipercaya untuk data struktural daripada LLM yang bisa menginterpretasikan ulang makna.

---

## Fase 7 — Pemetaan Institusional K/L

### Detail Teknis

**Script:** `08_extract_kl.py`
**Model:** `deepseek-chat` via DeepSeek API (dokumen publik)
**Input:** Chunk dengan `level_hint = 'KL_MATRIX'` (Lampiran III RPJMN/RKP)

Lampiran III berisi tabel matriks yang memetakan setiap KP ke K/L yang bertanggung jawab, beserta peran masing-masing:

| KP | Koordinator | Pengampu | Pelaksana | Pendukung |
|----|-------------|----------|-----------|-----------|
| 01.01.01 | BPIP | Kemenko Polhukam | Kemendagri, Kemdikbud | ... |

DeepSeek diminta:
1. Parse struktur tabel dari teks (yang kadang rusak format akibat OCR)
2. Ekstrak pasangan (kode KP, kode K/L, peran) dalam format JSON
3. Normalisasi nama K/L ke kode 3-digit (`kddept`)

**Deduplikasi:** `seen` set mencegah duplikasi pasangan (node_id, kddept, role).

**Output DB:**
- `deepseek_policy_kl_assignments` → **604 baris**
- 72 K/L unik
- Kolom: `node_id` (FK ke KP), `kddept` (kode K/L), `nmdept_normalized`, `role`, `confidence`, `evidence`

### Penjelasan Konseptual

RPJMN bukan hanya daftar rencana — ia juga menetapkan siapa yang bertanggung jawab atas setiap rencana. Fase ini menjawab pertanyaan institusional: "Kementerian mana yang diamanahi KP 01.01.01?" Informasi ini tersimpan di Lampiran III dalam bentuk tabel matriks yang kompleks. DeepSeek digunakan di sini karena tabel matriks memerlukan pemahaman struktural yang cukup kompleks untuk diparsing — baris dan kolom kadang terpotong, heading berulang, dan nama K/L ditulis dengan variasi. Hasilnya adalah peta penugasan yang terstruktur: untuk setiap Kegiatan Prioritas, kita tahu siapa koordinator, siapa pelaksana utama, dan siapa pendukungnya — informasi penting untuk analisis akuntabilitas anggaran.

---

## Fase 8 — Integrasi Data Anggaran DIPA (Sumber Eksternal)

### Detail Teknis

**Tabel:** `ddac_pagu_akun_2026` — **sudah ada di DB, bukan dibuat pipeline ini**
**Jumlah baris:** 1.504.455
**Grain:** Satu baris = satu kombinasi unik (K/L, Program, Kegiatan, Output/KRO, Komponen, Akun)

Ini adalah data DIPA (Daftar Isian Pelaksanaan Anggaran) resmi 2026 — dokumen pelaksanaan anggaran per satuan kerja K/L. **Bersifat internal pemerintah.**

**Kolom kunci yang digunakan pipeline:**

| Kolom | Penjelasan | Dipakai di Fase |
|-------|-----------|-----------------|
| `kementerian_kode` | Kode K/L 3-digit | 9, 10, 11, 12 |
| `program_kode` / `program_uraian` | Program DIPA | 9, 11, 12 |
| `kegiatan_kode` / `kegiatan_uraian` | Kegiatan DIPA | 9, 11, 12 |
| `outputkro_kode` / `outputkro_uraian` | Kode output (EB* = internal) | 9, 11, 12 |
| `komponen_kode` / `komponen_uraian` | Komponen belanja | 11 |
| `akun_kode` | Akun belanja 2-digit | 12 |
| `total_pagu` | Alokasi Rp | 9, 11, 12 |
| `alignment_text` | Gabungan `program + kegiatan + output` untuk embedding | 9 |

**Total pagu APBN 2026 dalam data: Rp 3.559,7 T**

**Mengapa 1,5 juta baris?** DIPA distrukturkan sangat granular: satu program bisa punya 50 kegiatan, tiap kegiatan punya 10 output, tiap output punya 5 komponen, tiap komponen punya 5 akun. Perkalian itulah yang menghasilkan 1,5 juta kombinasi.

### Penjelasan Konseptual

Knowledge graph yang kita bangun dari RPJMN/RKP adalah "rencana di atas kertas". Tapi apa yang benar-benar terjadi di anggaran negara? Di sinilah data DIPA masuk — ini adalah data **nyata** yang menunjukkan berapa rupiah dialokasikan untuk apa oleh siapa. DIPA adalah dokumen eksekusi anggaran; setiap K/L mendapat DIPA yang merinci program, kegiatan, output, dan akun belanjanya secara sangat rinci. Dengan menggabungkan knowledge graph RPJMN/RKP (rencana) dengan data DIPA (pelaksanaan), kita bisa menjawab pertanyaan paling penting: "Apakah alokasi anggaran yang ada benar-benar sejalan dengan prioritas yang ditetapkan pemerintah?" Ini adalah inti dari seluruh sistem.

---

## Fase 9 — Analisis Keselarasan Kebijakan (Policy Alignment)

### Detail Teknis

**Script:** `10_anomaly_detect.py`
**Model:** `LazarusNLP/all-indo-e5-small` — **dijalankan LOKAL**
**Alasan lokal:** Input berisi data DIPA (internal pemerintah). Tidak boleh keluar jaringan.

**Spesifikasi model:**
- Arsitektur: E5 (Embeddings from Bidirectional Encoder Representations)
- Fine-tuned untuk Bahasa Indonesia (corpus birokrasi)
- Dimensi vektor: 384
- Prefix wajib: `"query: "` sebelum setiap teks yang di-embed
- Dijalankan via `sentence-transformers` library (on-premise)

**Mengapa e5-small bukan bge-m3?**
Pengujian menunjukkan bge-m3 menghasilkan distribusi skor yang sangat sempit (std ±2.5) untuk teks birokrasi Indonesia — semua teks mendapat skor 50–60, tidak ada diferensiasi. e5-small (fine-tuned Indonesia) menghasilkan std ±10–15, artinya teks yang benar-benar terkait mendapat skor jauh lebih tinggi dari teks yang tidak terkait.

**Step 1 — Embedding KP Nodes (runtime):**
```python
model = SentenceTransformer("LazarusNLP/all-indo-e5-small")

kp_texts = ["query: " + COALESCE(clean_node_name_ai, node_name) for each KP]
kp_vecs  = model.encode(kp_texts, normalize_embeddings=True)
# → 753 vektor × 384 dimensi, ternormalisasi L2
```

**Step 2 — Embedding unique alignment texts dari DIPA:**
```python
unique_alignment_texts = SELECT DISTINCT alignment_text FROM ddac_pagu_akun_2026

pagu_vecs = model.encode(["query: " + t for t in unique_texts],
                          normalize_embeddings=True)
# → N_unique × 384 dimensi
```

**Step 3 — Cosine Similarity Matrix:**
```python
sim_matrix = np.dot(pagu_vecs, kp_vecs.T)
# shape: (N_texts, 753_KP)
# Karena kedua vektor ternormalisasi L2, dot product = cosine similarity

top3_indices = np.argsort(-sim_matrix, axis=1)[:, :3]
top3_scores  = np.take_along_axis(sim_matrix, top3_indices, axis=1)
```
Untuk setiap teks DIPA, diperoleh 3 KP RPJMN/RKP yang paling mirip secara semantik.

**Step 4 — Klasifikasi Spending Nature (kode resmi DIPA, bukan keyword):**

```python
if kl_kode in {"999"}:              # BAUN — Bendahara Umum Negara
    nature = "treasury_crosscutting"
elif outputkro_kode.startswith("EB"):    # EBA/EBB/EBC/EBD = output internal
    nature = "routine_support"
elif "dukungan manajemen" in program_uraian.lower():
    nature = "routine_support"
else:
    nature = "substantive"
```

> **Catatan kritis:** Klasifikasi ini menggunakan kode resmi Kemenkeu (EB-series), bukan text mining berbasis keyword. Verifikasi sebelumnya menunjukkan klasifikasi berbasis keyword seperti "pembinaan", "koordinasi", "pengelolaan" salah mengklasifikasikan 2.738 item (49%) sebagai routine padahal 68% di antaranya sebenarnya moderate/strong aligned ke KP.

**Step 5 — Klasifikasi Anomaly Status:**

```python
rank = percentile_rank(best_score)  # posisi dalam distribusi aktual

if rank >= 85:   aligned_status = "strong_alignment"
elif rank >= 50: aligned_status = "moderate_alignment"
elif rank >= 15: aligned_status = "weak_alignment"
else:            aligned_status = "none"  # kandidat orphan

# Dual condition untuk policy_orphan (mencegah false positive)
if nature in ("routine_support", "treasury_crosscutting"):
    anomaly_type = "routine"
elif aligned_status == "none" and best_score < 45.0:  # ABS_FLOOR
    anomaly_type = "policy_orphan"   # rendah RELATIF dan ABSOLUT
elif aligned_status in ("none", "weak"):
    anomaly_type = "weak_alignment"  # rendah relatif, masih masuk akal
else:
    anomaly_type = "aligned"
```

**Alasan ABS_FLOOR = 45.0:**
Verifikasi menunjukkan bahwa item dengan rank rendah tapi skor 45–50 adalah kasus *mismatch nomenklatur*, bukan ketiadaan relevansi. Contoh: *"Wajib Belajar 13 Tahun"* (Kemendikdasmen) mendapat skor 47 ke KP Pendidikan — ini jelas terkait pendidikan, hanya nomenklatur DIPA-nya berbeda dari nama KP di RPJMN. Menurunkan floor ke 45.0 membuat sistem tidak salah mengklasifikasikannya sebagai orphan.

**Review Priority Score:**
```python
materiality = log(total_pagu + 1) / log(max_pagu + 1) * 100
anomaly_score = 100.0 - percentile_rank(best_score)
review_priority = anomaly_score * materiality / 100
```
Item dengan pagu besar DAN skor rendah diprioritaskan untuk review manusia.

**Output DB:**
- `ddac_anomaly_2026` — satu baris per unique `alignment_text`
  - **1** `policy_orphan`
  - **1.541** `weak_alignment`
  - Sisanya: `strong/moderate/routine`
- Kolom: `aligned_status`, `alignment_score`, `anomaly_type`, `anomaly_score`, `review_priority`, `top3_matches` (JSON: kode + nama + skor 3 KP terdekat), `spending_nature`

### Penjelasan Konseptual

Pertanyaan intinya adalah: "Apakah uang yang dialokasikan dalam DIPA 2026 benar-benar diperuntukkan bagi hal-hal yang menjadi prioritas nasional dalam RPJMN/RKP?" Untuk menjawab ini, kita perlu "menerjemahkan" teks DIPA dan teks KP RPJMN ke dalam bahasa yang sama — bahasa angka. Inilah fungsi embedding: setiap teks direpresentasikan sebagai titik di ruang 384 dimensi sedemikian rupa sehingga teks yang bermakna mirip akan berdekatan secara geometris. Model yang digunakan (e5-small fine-tune Indonesia) dilatih khusus pada teks berbahasa Indonesia termasuk corpus birokrasi, sehingga ia memahami bahwa "Pengelolaan Pendidikan Dasar" dan "Peningkatan Mutu Pendidikan Usia Dini" itu mirip maknanya meski tidak ada kata yang persis sama. Hasil akhirnya adalah setiap baris DIPA mendapat "skor keselarasan" 0–100 terhadap KP RPJMN/RKP yang paling relevan — dan dari distribusi skor itulah anomali terdeteksi.

---

## Fase 10 — TreasurAI: Reasoning Kualitatif Anomali

### Detail Teknis

**Script keselarasan:** `11_treasurai_reasoning.py`
**Script koherensi:** `15_coherence_reasoning.py`
**Model:** TreasurAI OSS 120B (sistem internal Kemenkeu)
**Endpoint:** Internal network Kemenkeu — **tidak melewati internet publik**
**SSL:** `verify=False` — server Kemenkeu menggunakan self-signed certificate
**Alasan TreasurAI (bukan DeepSeek):** Input berisi data DIPA spesifik K/L (nama program, kegiatan, pagu, kode) yang bersifat internal pemerintah. TreasurAI adalah sistem yang beroperasi di infrastruktur Kemenkeu sendiri.

#### Enrichment Konteks Mandat (common/kl_context.py — BARU)

Setiap prompt di-enrich dengan konteks mandat K/L dari knowledge graph RPJMN/RKP:

```python
# Untuk setiap K/L, ambil KP/PP yang ditugaskan ke K/L tersebut
def get_kl_mandate_context(cur, kl_kode, max_kp=10):
    # Query deepseek_policy_kl_assignments JOIN deepseek_policy_nodes
    # Prioritas: RPJMN > RKP_2026 > RKP_2025 > lainnya
    # Output format:
    # "Mandat K/L 128 dalam RPJMN/RKP:
    #   - KP 04.12.01 [pelaksana]: Pemberian Makan Bergizi untuk Siswa... (RPJMN)
    #   - KP 04.12.02 [pelaksana]: Penguatan Ekosistem Pendukung... (RPJMN)"
```

Coverage: 72 K/L memiliki penugasan KP — mencakup ~80% dari weak_alignment items dan ~70% dari K/L dengan L3 anomali. K/L tanpa penugasan tetap diproses tanpa konteks mandat.

#### Script 11 — Policy Alignment Reasoning

**Cakupan:**
```sql
WHERE anomaly_type IN ('policy_orphan', 'weak_alignment')
  AND llm_reasoning IS NULL
ORDER BY
    CASE anomaly_type WHEN 'policy_orphan' THEN 0 ELSE 1 END,
    review_priority DESC
```
Policy orphan diprioritaskan, lalu weak_alignment diurut dari `review_priority` tertinggi (anomaly_score × materiality).

**Struktur prompt:**
```
[Weak Alignment] Item DIPA:
K/L     : 025 - Kementerian Agama
Prog/Keg: Program Wajib Belajar 13 Tahun | Layanan Pembiayaan Pendidikan...

KP RPJMN/RKP terdekat (skor 47/100):
KP 04.01.01: Perluasan Layanan Pendidikan Anak Usia Dini...

Top-3 semantic match:
- KP 04.01.01: Perluasan Layanan PAUD (skor 47)
- KP 04.02.01: Peningkatan Mutu Pendidikan Dasar (skor 44)
...

Mandat K/L 025 dalam RPJMN/RKP:
  - KP 04.06.01 [pelaksana]: Peningkatan Kualitas Pendidikan Keagamaan (RPJMN)
  ...

Item ini memiliki alignment lemah (rank < P15, skor ≥ 45). Berdasarkan mandat K/L
di atas, apakah ada penjelasan mengapa similaritynya rendah?
```

**Output DB:**
- `ddac_anomaly_2026.llm_reasoning` — reasoning naratif
- `ddac_anomaly_2026.llm_model` — `'oss120b'`
- `ddac_anomaly_2026.treasurai_verdict` — `valid` / `false_positive` / `manual_review`
- `ddac_anomaly_2026.review_status` — `confirmed` / `dismissed` / `needs_review` / `pending`
- **1,542 item** memiliki reasoning (1 orphan + 1,541 weak_alignment, oss120b)

#### Script 15 — Coherence L3 Reasoning

**Cakupan:** `ddac_coherence_akun_2026` JOIN `ddac_coherence_2026` WHERE `akun_komposisi_score >= 40`, diurut by total pagu DESC.

**Struktur prompt:**
```
Anomali Koherensi Level 3 — Komposisi Akun vs Peer:
K/L     : 128 - Badan Gizi Nasional
Output  : QEA - Bantuan Masyarakat (MBG)

Deviasi total: 95.8% vs 12 K/L peer
  Belanja Bansos (57): K/L ini=100% | rata-rata peer= 5%

Total pagu K/L ini: Rp 0.19 T

Mandat K/L 128 dalam RPJMN/RKP:
  - KP 04.12.01 [pelaksana]: Pemberian Makan Bergizi untuk Siswa, Santri, Ibu Hamil (RPJMN)

Apakah pola belanja yang sangat berbeda dari 12 K/L peer ini dapat dijelaskan
oleh mandat RPJMN/RKP K/L tersebut?
```

Satu reasoning di-update ke **semua baris** coherence_2026 yang memiliki kombinasi (kl, prog, keg, output) yang sama — sehingga 30 output unik menghasilkan update 19,235 baris.

**Output DB (kolom baru di ddac_coherence_2026):**
- `llm_reasoning`, `llm_model`, `treasurai_verdict`, `review_status_coherence`
- **19,235 baris** memiliki reasoning (dari 30 output unik top pagu, oss120b)

**Mekanisme preserve reasoning:**
Script 10 (anomaly detect) selalu menyimpan `llm_reasoning` sebelum reinsert — reasoning tidak hilang meski script 10 dijalankan ulang. Script 15 hanya memproses `llm_reasoning IS NULL`.

### Penjelasan Konseptual

Deteksi anomali berbasis cosine similarity dan peer comparison menghasilkan angka — tapi angka tidak selalu cukup untuk membuat keputusan kebijakan. Apakah Badan Gizi Nasional yang mengalokasikan 100% anggaran ke Belanja Bansos itu anomali yang harus dipersoalkan, atau justru sesuai tugasnya karena RPJMN memang menugaskan program Makan Bergizi Gratis? Komputer tidak bisa membedakan keduanya — dibutuhkan pemahaman konteks kebijakan. Di sinilah TreasurAI masuk: ia adalah LLM berukuran besar (120 miliar parameter) yang di-deploy di infrastruktur Kemenkeu sendiri, sehingga data DIPA yang sensitif tidak perlu keluar jaringan. Yang membedakan sistem ini dari sekadar "tanya ke LLM" adalah **grounding ke knowledge graph**: setiap reasoning di-inject konteks mandat RPJMN/RKP yang relevan untuk K/L tersebut — sehingga TreasurAI tidak bergantung pada pengetahuan umum saja, melainkan pada data yang sudah terverifikasi dari dokumen kebijakan resmi. Hasilnya adalah sistem "human-in-the-loop" di mana AI melakukan pemindaian skala besar dengan konteks kebijakan yang tepat, dan manusia hanya perlu memverifikasi temuan yang benar-benar meragukan.

---

## Fase 11 — Koherensi Internal: Klasifikasi Jenis Komponen

### Detail Teknis

**Script:** `12_coherence.py`
**Tidak menggunakan model AI** — rule-based, join tabel referensi
**Input:** `ddac_pagu_akun_2026` + tabel referensi `t_kmpnen_2026`

Tabel `t_kmpnen_2026` adalah tabel master resmi Kemenkeu yang mengklasifikasikan setiap komponen belanja DIPA ke dalam:
- `Utama` — komponen yang langsung mendukung output substantif
- `Pendukung` — komponen overhead/administratif

**Teknik optimasi — temp table untuk 1,5 juta baris:**

JOIN langsung `ddac_pagu_akun_2026 × t_kmpnen_2026` tidak efisien karena index `t_kmpnen_2026` memiliki prefix kolom `kdunit` yang tidak ada di pagu table. Solusi: pre-aggregate ke temp table berindex kecil terlebih dahulu.

```sql
-- Tmp table kecil, berindex pada 5 kolom join
CREATE TABLE tmp_kmpnen_map (
    PRIMARY KEY (kddept, kdprogram, kdgiat, kdoutput, kdkmpnen)
) SELECT kddept, kdprogram, kdgiat, kdoutput, kdkmpnen,
         MAX(CASE WHEN jenis_komponen = 'Utama' THEN 'Utama'
                  WHEN jenis_komponen = 'Pendukung' THEN 'Pendukung' END)
  FROM t_kmpnen_2026
  GROUP BY ...

-- Kemudian INSERT ke ddac_coherence_2026 dengan join yang cepat
INSERT INTO ddac_coherence_2026 ...
SELECT ... FROM ddac_pagu_akun_2026 p
LEFT JOIN tmp_kmpnen_map m ON p.kementerian_kode = m.kddept AND ...
```

**Deteksi anomali jenis komponen (rule-based):**

```python
# pendukung_dominan: komponen Pendukung > 50% pagu output tersebut
if jenis = 'Pendukung' AND pendukung_share > 0.50:
    jenis_anomaly = 'pendukung_dominan'
    score = 85

# utama_kecil: komponen Utama < 10% pagu output tersebut
if jenis = 'Utama' AND utama_share < 0.10:
    jenis_anomaly = 'utama_kecil'
    score = 50
```

**Output DB:**
- `ddac_coherence_2026` — **1.504.455 baris** (1:1 dengan ddac_pagu_akun_2026)
- Kolom yang terisi di fase ini: `jenis_komponen`, `jenis_anomaly`, `jenis_anomaly_score`, `coherence_score` (inisial)

### Penjelasan Konseptual

Di dalam DIPA, setiap output program punya dua jenis komponen belanja: "Utama" (yang langsung menghasilkan output — misal biaya cetak buku pelajaran) dan "Pendukung" (overhead untuk melaksanakannya — misal honor panitia, perjalanan dinas). Secara ideal, komponen Utama harus mendominasi; jika sebuah output justru 80% diisi oleh komponen Pendukung, itu sinyal bahwa anggaran lebih banyak habis untuk rapat dan perjalanan dinas daripada untuk kegiatan substansialnya. Inilah yang dicek fase ini: apakah komposisi Utama vs Pendukung untuk setiap output masuk akal? Deteksinya murni berbasis aturan (rule-based) karena definisi "Utama" dan "Pendukung" sudah tersedia secara resmi di tabel referensi Kemenkeu — tidak perlu AI untuk menentukan ini.

---

## Fase 12 — Koherensi Internal: 3-Level Semantic & Peer Analysis

### Detail Teknis

**Script:** `13_coherence_levels.py`
**Model L1/L2:** `LazarusNLP/all-indo-e5-small` — **lokal, tidak keluar jaringan**
**Model L3:** Statistik murni (total variation distance) — tidak ada model AI
**Input:** `ddac_coherence_2026` (1,5M baris) + `ddac_pagu_akun_2026`

### Level 1 — Keselarasan Program ↔ Kegiatan

**Pertanyaan:** Apakah nama kegiatan DIPA konsisten dengan nama program DIPA-nya?

```python
# Ambil pasangan unik (program, kegiatan) — jumlahnya jauh lebih kecil dari 1,5M
pairs = SELECT DISTINCT program_uraian, kegiatan_uraian FROM ddac_coherence_2026

# Embed semuanya sekaligus (murah: hanya ~2.900 pasang unik)
prog_vecs = model.encode(["query: " + p for p in program_uraians])
keg_vecs  = model.encode(["query: " + k for k in kegiatan_uraians])

# Cosine similarity per pair
similarities = [dot(prog_vecs[i], keg_vecs[i]) * 100 for i ...]

# Threshold: persentil ke-5 dari distribusi aktual (bukan angka hardcoded)
threshold_L1 = np.percentile(similarities, 5)  # pct_low = 5

# Flag: similarity < threshold → level1_program_kegiatan_lemah
```

**Pengecualian L1 (Fix F1):**
Program `"Dukungan Manajemen"` adalah program catch-all regulasi Kemenkeu. Secara desain, semua kegiatan administratif K/L dimasukkan ke sini tanpa memandang substansinya. Flagging L1 pada program ini tidak bermakna — dikecualikan.

**Hasilnya ditulis balik ke 1,5M baris dengan single UPDATE...JOIN via PK-indexed temp table** (bukan update per baris — performa kritis untuk 1,5M baris).

**14.272 baris** tertandai `level1_program_kegiatan_lemah`.

---

### Level 2 — Keselarasan Kegiatan ↔ Output

**Pertanyaan:** Apakah output yang dihasilkan sebuah kegiatan DIPA konsisten dengan nama kegiatannya?

Logika identik dengan L1: embed pasangan unik `(kegiatan, output)`, hitung cosine similarity, flag jika < P5.

**Pengecualian L2 — Military domain (Fix E1):**
```python
MILITARY_DOMAIN_KL = {"012", "060"}   # Kemhan + Polri ONLY (011=Kemenlu ≠ militer)
MILITARY_DOMAIN_OUTPUT_PATTERNS = [
    'operasi bidang pertahanan', 'operasi bidang keamanan',
    'om prasarana bidang pertahanan', 'sarana bidang pertahanan dan keamanan',
]
```
K/L militer menggunakan jargon teknis operasional yang under-scored oleh model embedding. Verifikasi: 17 kombinasi kegiatan-output di K/L 012+060 yang domain-nya pertahanan/keamanan operasional adalah false positive — dikecualikan. Output manajemen/koordinasi generik di K/L yang sama tetap di-flag.

**Pengecualian L2 — Output generik:**
```python
GENERIC_OUTPUT_PATTERNS = [
    'dukungan teknis', 'kerja sama', 'data dan informasi',
    'dukungan manajemen', 'layanan perkantoran', 'administrasi umum',
]
```
Output-output ini terlalu abstrak untuk dibandingkan secara semantik dengan kegiatan apapun — selalu akan mendapat skor rendah meski konteksnya valid.

**16.310 baris** tertandai `level2_kegiatan_output_lemah`.

---

### Level 3 — Keselarasan Output ↔ Komposisi Akun (Peer Comparison)

**Pertanyaan:** Apakah pola belanja (jenis akun) untuk suatu output *normal* dibandingkan K/L lain yang memiliki output berkode sama?

**Ini bukan embedding — ini statistik distribusi.**

```python
# Untuk setiap outputkro_kode (contoh: "RBC" = Prasarana Jalan):
# 1. Kumpulkan semua K/L yang punya output ini
# 2. Hitung distribusi belanja per akun 2-digit untuk setiap K/L:
#    {51: 5%, 52: 80%, 53: 15%} (Pegawai/Barang/Modal)
# 3. Hitung rata-rata distribusi PEER (K/L lain — self-excluded)

# Self-exclusion (Fix 3A): K/L itu sendiri tidak boleh masuk peer aggregate
peer_avg = mean([distrib for kl in all_kl if kl != this_kl])

# Total Variation Distance = ukuran "jarak" antar distribusi
TVD = 0.5 * sum(abs(own_share[akun] - peer_avg[akun]) for akun in akuns)

# Flag jika deviasi terlalu jauh dari peer
if outputkro_kode.startswith("EB"):
    flag = TVD >= 0.65   # looser: EB-series secara alami bervariasi antar K/L
else:
    flag = TVD >= 0.40
```

**Persyaratan minimum peer:**
```python
if peer_count < 5:
    # Tidak cukup K/L lain untuk membentuk profil peer yang representatif
    # → tidak di-flag
    pass
```

**Contoh anomali nyata:**
- Output "Layanan Dukungan Manajemen" (EBA) di Polri (060): 98% Belanja Modal (akun 53) padahal rata-rata 99 K/L peer = ~0% Modal. TVD = 0.98 >> 0.65 → flagged.
- Output "Prasarana Jalan" (RBC) di satu K/L: 100% Belanja Barang (akun 52) padahal peer = 1% Barang. TVD = 0.99 >> 0.40 → flagged.

**Detail peer disimpan di tabel terpisah:**
- `ddac_coherence_akun_2026` → ~8.000 baris per (K/L, program, kegiatan, output)
- Kolom `akun_detail` (JSON): distribusi akun own vs peer, top unexpected account, peer_count

**142.384 baris** tertandai `level3_akun_tidak_lazim`.

---

### Composite Score

```
coherence_score = 0.35 × jenis_score
               + 0.20 × L1_score
               + 0.20 × L2_score
               + 0.25 × L3_score
```

Bobot L3 lebih tinggi (0.25) karena peer comparison lintas K/L memberikan sinyal yang paling kuat dan sulit dijelaskan oleh faktor nomenklatur.

`anomaly_flags` (JSON array) merekam level mana yang terpicu, misal: `["level1_program_kegiatan_lemah", "level3_akun_tidak_lazim"]`.

**Output DB:**
- `ddac_coherence_2026` — seluruh kolom koherensi terisi: `prog_keg_coherence`, `keg_out_coherence`, `out_komp_coherence`, `akun_komposisi_score`, `akun_detail`, `coherence_score`, `anomaly_flags`

### Penjelasan Konseptual

Bayangkan sistem ini seperti seorang auditor berpengalaman yang memeriksa laporan keuangan dari tiga sudut sekaligus. **Level 1** memeriksa apakah nama kegiatan masuk akal untuk program yang menaunginya — seperti mengecek apakah isi bab sesuai dengan judul bab. **Level 2** memeriksa apakah output yang dihasilkan masuk akal untuk kegiatan yang menghasilkannya — seperti mengecek apakah kesimpulan bab konsisten dengan isinya. **Level 3** yang paling unik: ia tidak menggunakan teks sama sekali, melainkan membandingkan *perilaku belanja* suatu K/L dengan K/L-K/L lain yang mengerjakan hal yang sama. Jika hampir semua K/L yang membangun jalan mengalokasikan ~80% untuk Belanja Modal, tapi satu K/L hanya 5% Modal, itu sinyal kuat bahwa ada yang tidak wajar — bukan karena teksnya salah, melainkan karena polanya berbeda dari norma. Ini adalah pendekatan peer comparison yang lazim digunakan dalam audit keuangan, diterapkan secara otomatis pada 1,5 juta baris anggaran.

---

## Ringkasan: Tiga Model, Tiga Peran, Satu Tujuan

| # | Model | Fase | Peran | Data yang Diproses |
|---|-------|------|-------|-------------------|
| 1 | **DeepSeek Chat** (cloud) | 3, 7 | OCR correction + K/L parsing | Dokumen publik (RPJMN, RKP) |
| 2 | **LazarusNLP e5-small** (lokal) | 9, 12 | Semantic embedding + cosine similarity | Data DIPA internal (tidak keluar server) |
| 3 | **TreasurAI OSS 120B** (internal Kemenkeu) | 10 | Reasoning kualitatif **semua** anomali keselarasan (1,542 item) + koherensi L3 (19,235 baris); di-grounding ke RPJMN/RKP via kl_context.py | Data DIPA + hasil analisis (jaringan Kemenkeu) |

**Prinsip akhir:** Sistem ini bukan "satu AI yang memutuskan segalanya" — melainkan pipeline bertahap di mana setiap komponen melakukan apa yang paling ia kuasai: LLM cloud untuk pembersihan teks publik, model embedding lokal untuk analisis kuantitatif data sensitif, LLM internal untuk judgment kualitatif. Hasilnya adalah analisis yang dapat diaudit, transparan, dan aman dari perspektif keamanan data pemerintah.

---

## Lampiran: Tabel DB yang Dihasilkan

| Tabel | Dibuat Oleh | Jumlah Baris | Deskripsi |
|-------|------------|-------------|-----------|
| `deepseek_policy_documents` | Script 01/02 | 17 | Registri dokumen PDF |
| `deepseek_policy_pages` | Script 02 | 4.478 | Raw text per halaman |
| `deepseek_policy_chunks` | Script 03/03c | 1.001 | Chunk + clean_text_ai |
| `deepseek_policy_nodes` | Script 04/14 | 963 | Node PN/PP/KP knowledge graph |
| `deepseek_policy_edges` | Script 05 | 857 | Relasi hierarki |
| `deepseek_policy_kl_assignments` | Script 08 | 604 | Penugasan K/L per KP |
| `ddac_anomaly_2026` | Script 10/11 | 7.235 | Keselarasan DIPA vs RPJMN/RKP; 1,542 item dengan reasoning TreasurAI oss120b |
| `ddac_coherence_2026` | Script 12/13/15 | 1.504.455 | Koherensi internal 3 level; 19,235 baris dengan reasoning TreasurAI oss120b |
| `ddac_coherence_akun_2026` | Script 13 | ~8.000 | Detail peer komposisi akun L3 |
