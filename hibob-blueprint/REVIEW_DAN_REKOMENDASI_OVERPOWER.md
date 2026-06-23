# Review Blueprint Hibob + Rekomendasi "Gila" yang Overpower tapi Masuk Akal

Status: **Terintegrasi** - seluruh 9 celah (Bagian 2) dan 8 rekomendasi overpower (Bagian 3) di bawah ini sudah disetujui Bob ("Semua jadi Accepted sekarang") dan dipindahkan menjadi ADR 0005-0013 (status Accepted) plus pembaruan di seluruh `docs/00`-`docs/16`, `database/schema.sql`, dan diagram terkait. Dokumen ini sekarang berfungsi sebagai **rasionale/narasi** di balik ADR 0005-0013 - untuk keputusan kanonik dan timing aktivasi per fase, rujuk `adr/0005-*.md` s.d. `adr/0013-*.md` dan `docs/11_ROADMAP.md`, bukan dokumen ini.
Tanggal: 2026-06-23
Reviewer: Claude (atas permintaan Bob)
Sifat dokumen asal: Opini + rekomendasi yang ditulis sebelum integrasi. Dipertahankan sebagai catatan sejarah/alasan di balik ADR 0005-0013, bukan lagi sumber kebenaran yang berdiri sendiri.

---

## 0. TL;DR (versi 30 detik)

Blueprint ini **bagus secara mengejutkan**. Disiplinnya di level yang jarang dimiliki proyek personal: memory-first, core-and-adapters, tool-gateway-before-autonomy, privacy tier, eval sejak v0.1. Sembilan dari sepuluh proyek "AI personal" mati karena jadi tumpukan tool tanpa core — blueprint ini justru menulis anti-pattern itu secara eksplisit di hampir setiap dokumen.

Tapi justru karena fondasinya kuat, ada ruang untuk mendorong jauh lebih jauh **tanpa melanggar prinsipnya sendiri**. Bagian besar dokumen ini adalah 8 rekomendasi "overpower": ambisius, terdengar gila, tapi tetap patuh pada lima non-negotiable Hibob (local-first, memory-first, model-agnostic, permission-controlled, evaluation-driven).

Satu kalimat: **Hibob jangan cuma "AI yang punya memory" — jadikan dia "AI yang memorinya hidup, bisa di-replay, bisa membela diri, dan makin pintar tiap kali dikoreksi."**

---

## 1. Apa yang sudah benar (jangan diutak-atik)

Ini bukan basa-basi — ini hal-hal yang harus **dipertahankan mati-matian** karena justru di sinilah nilai Hibob:

| Keputusan | Kenapa ini kuat |
|---|---|
| **Core-and-adapters (ADR 0001)** | Memisahkan identitas/memory/policy dari tool. Ini satu-satunya alasan Hibob bisa "ganti otak tanpa ganti jiwa". |
| **Relational DB = source of truth, Qdrant = index** | Banyak proyek mati karena memperlakukan vector DB sebagai kebenaran. Blueprint menolak ini secara eksplisit (ERD §1). Benar. |
| **Memory punya lifecycle + status + source + conflict** | `candidate → approved → superseded` dengan `memory_sources` dan `memory_conflicts` adalah desain memory yang serius, bukan "vectorize semua chat". |
| **Tool Gateway sebelum autonomy (ADR 0004)** | Urutan yang benar. Risk level + approval + audit + rollback sebelum agent boleh bertindak. |
| **Privacy tier + redaction sebelum cloud** | Local-first yang sungguhan, bukan slogan. `secret` tidak pernah masuk prompt/trace/vector. |
| **Eval sebagai bagian produk, bukan bonus** | DeepEval + Phoenix masuk Phase 0. Ini yang membedakan "produk" dari "demo". |
| **Anti-hype rule (doc 12 §12)** | Aturan "kalau cuma bikin keren, tunda" adalah rem yang sehat. Rekomendasi di bawah saya tundukkan ke aturan ini. |

Kalau semua ini hilang, semua rekomendasi di bawah jadi tidak berguna. Jadi: **fondasi dulu, baru overpower.**

---

## 2. Celah jujur (sebelum ngomong yang gila-gila)

Beberapa hal yang menurut saya kurang, lemah, atau berisiko di v0.1. Saya urut dari yang paling penting.

### 2.1 "Self-building loop" adalah killer feature tapi paling under-specified
Phase 5 (Dev Partner) dan FR-015 (Blueprint Guardian) adalah jiwa proyek — Hibob membangun dirinya sendiri. Tapi dokumen hampir tidak menjelaskan **mekanisme amannya**: bagaimana Hibob mengusulkan patch, siapa yang menjalankan test, bagaimana hasil eval menutup loop. Ini bagian paling bernilai sekaligus paling kosong.

### 2.2 Approval fatigue akan membunuh UX
Permission matrix (doc 05 §8) hampir semuanya "ask". Untuk single-user yang dipakai harian, ini akan melelahkan dalam seminggu. Tidak ada konsep **trust yang bertumbuh** (tool yang berkali-kali aman boleh naik ke auto dalam sandbox). Risikonya: Bob mulai approve membabi-buta — yang justru menghancurkan tujuan keamanan.

### 2.3 Prompt injection dijaga di level policy, bukan teknis
Doc 05 §10 dan doc 08 §2 benar secara prinsip ("retrieved content = data, bukan instruksi"). Tapi tidak ada **kontrol teknis konkret**: tidak ada spotlighting/delimiter enforcement, tidak ada classifier injeksi, tidak ada structural separation di level prompt assembly. Prinsip tanpa mekanisme = harapan.

### 2.4 Memory itu flat; konflik cuma pairwise
`memory_conflicts` menghubungkan dua memory (A vs B). Tapi keyakinan Bob membentuk **rantai dan kelompok** ("PHP → Python → Python+FastAPI", "voice penting → ditunda → mungkin Phase 8"). Tidak ada struktur graph, tidak ada timeline bi-temporal ("apa yang Bob yakini soal X pada Mei vs Juni"). Untuk "second brain" sejati, ini batasan nyata.

### 2.5 Confidence memory itu statis
`confidence` di-set saat extraction lalu diam. Tidak ada mekanisme memory **belajar dari pemakaiannya sendiri** — memory yang sering membantu naik confidence, yang sering dikoreksi turun. Memory yang tidak pernah berevolusi adalah memory mati.

### 2.6 Eval bergantung berat pada LLM-as-judge
Banyak metrik (faithfulness, persona) butuh model penilai. Doc 09 §12 sadar ("jangan biarkan model menilai semua eval tanpa spot-check") tapi tidak ada **anchor objektif**: golden dataset dengan jawaban tetap, judge yang di-pin versinya, atau deteksi judge drift. Eval yang juri-nya ikut berubah = penggaris dari karet.

### 2.7 Router model statis, tidak belajar
Tabel routing (doc 12 §4) bagus sebagai default, tapi pemetaan task→model di-hardcode. Tidak ada feedback dari hasil eval/biaya/latency nyata yang menyetel ulang routing. Padahal datanya **sudah dicatat** di `model_runs` (cost, latency, status). Sayang tidak dipakai.

### 2.8 Tidak ada cost guard
`model_runs.cost_estimate` ada, tapi tidak ada budget ceiling, circuit breaker, atau alert. Satu loop agent yang nyangkut di cloud frontier bisa membakar uang/kuota diam-diam.

### 2.9 Isolasi tool masih level policy, bukan level OS
Doc 08 §8 melarang `rm -rf`, `curl | sh`, dll lewat aturan. Tapi "shell read-only" yang dijaga prompt/policy tetap bisa ditembus prompt injection. Tidak ada sandbox OS-level (container ephemeral, no-network default) untuk shell/browser.

---

## 3. Delapan Rekomendasi "Gila" (Overpower tapi Masuk Akal)

Aturan main saya: setiap rekomendasi harus **memperkuat minimal satu non-negotiable Hibob**, bisa di-adapter, bisa di-eval, dan bisa di-rollback. Tidak ada yang "keren doang". Saya beri tiap ide: ide inti, kenapa overpower, kenapa tetap masuk akal, dan kapan dikerjakan.

---

### ⚡ OP-1 — Temporal Knowledge Graph Memory ("Memory yang punya garis waktu & relasi")

**Ide.** Naikkan Memory Core dari "baris flat + konflik pairwise" menjadi **graph memory bi-temporal**: entitas (Bob, proyek, keputusan, tool, prinsip) sebagai node; relasi (`decided`, `superseded`, `contradicts`, `depends_on`, `prefers`) sebagai edge; setiap fakta punya **dua sumbu waktu** — kapan jadi benar di dunia (`valid_from/until`) dan kapan Hibob tahu (`created_at`). Vector + graph hidup berdampingan: Qdrant untuk "cari yang mirip", graph untuk "telusuri rantai keyakinan".

**Kenapa overpower.** Ini membuka pertanyaan yang chatbot biasa tidak bisa jawab:
- "Kenapa kita akhirnya pilih Python?" → telusuri edge `superseded` dari PHP→Python.
- "Apa yang gue yakini soal arsitektur 3 minggu lalu?" → query bi-temporal.
- "Keputusan apa saja yang bergantung pada asumsi yang sekarang gugur?" → traversal `depends_on` dari node yang `disputed`.

Ini mengubah "second brain" dari metafora jadi kemampuan nyata.

**Kenapa masuk akal.** Tidak melanggar apa pun — `memories`, `memory_conflicts`, `superseded_by_memory_id` **sudah** setengah jalan ke graph. Tinggal tambah tabel `memory_edges` dan jadikan konflik sebagai jenis edge. Bisa local (pakai Postgres recursive CTE atau Apache AGE; tidak wajib Neo4j). Bisa di-eval (recall multi-hop). Bisa rollback (graph adalah turunan dari canonical, bisa di-rebuild).

**Kapan.** Desain di Phase 2, aktifkan ringan di Phase 2.5. Jangan tunggu Phase 8.

---

### ⚡ OP-2 — Self-Calibrating Memory ("Memory yang makin pintar tiap dipakai")

**Ide.** Jadikan `confidence` **dinamis, berbasis bukti pemakaian**. Tiap kali sebuah memory di-retrieve lalu dipakai di jawaban, catat *outcome*: apakah Bob mengoreksi? apakah jawabannya diterima? apakah memory itu memicu konflik? Update confidence dengan aturan Bayesian sederhana (beta distribution: hit menaikkan, koreksi menurunkan tajam). Memory yang membusuk pelan-pelan turun di bawah ambang retrieval dan masuk antrian review otomatis.

**Kenapa overpower.** Memory berhenti jadi snapshot mati dan jadi **organisme yang belajar**. Memory yang benar mengangkat dirinya sendiri; memory basi tenggelam sendiri tanpa Bob harus rajin bersih-bersih manual. Ini langsung menyerang anti-pattern "chatbot percaya diri tapi salah" (doc 04 §1).

**Kenapa masuk akal.** Datanya sudah ada — `used_memory_ids` di response `/v1/chat` + feedback loop di doc 09 §10 tinggal disambung. Tetap permission-safe: confidence naik-turun otomatis, tapi **promosi status** (`candidate→approved`) tetap butuh Bob. Bisa di-eval (kalibrasi: apakah memory confidence 0.9 memang benar 90% kali). Reversible (confidence punya history).

**Kapan.** Phase 2 (skema), aktifkan setelah ada cukup data pemakaian (akhir Phase 3).

---

### ⚡ OP-3 — Policy-as-Code: "Konstitusi" Hibob yang Tidak Bisa Dibujuk Model

**Ide.** Ubah doc 05 (Tool Policy) dan doc 08 (Security) dari **prosa** menjadi **kebijakan yang dieksekusi mesin**. Tulis aturan permission/privacy/risk sebagai policy engine (gaya OPA/Rego, atau DSL Python sederhana yang murni & teruji) yang dievaluasi Tool Gateway di runtime. LLM **mengusulkan** aksi; konstitusi yang **memutuskan** allow/ask/deny. Model tidak pernah punya akses ke keputusan permission-nya sendiri.

**Kenapa overpower.** Ini menutup celah paling berbahaya di sistem agentic: "LLM membujuk dirinya sendiri untuk melewati aturan" (doc 05 §16 melarangnya tapi tanpa mekanisme). Dengan policy-as-code, mau prompt injection se-canggih apa pun, keputusan "boleh delete file?" diputus oleh fungsi deterministik yang **di-version, di-test, dan di-audit** — bukan oleh suasana hati model. `policy_versions` di schema sudah mengantisipasi ini; tinggal jadikan eksekutabel.

**Kenapa masuk akal.** Justru ini **memenuhi** janji blueprint, bukan melanggarnya. Doc 08 menyebut artifact `TOOL_POLICY.md`, `PRIVACY_TIERS.md` — jadikan mereka file kebijakan yang di-load Gateway, bukan dokumen yang dibaca manusia lalu dilupakan kode. Sangat testable (tiap aturan = unit test). Sangat reversible (rollback = ganti `policy_version`).

**Kapan.** Mulai Phase 4 (Tool Gateway). Ini bukan "nice to have" — ini cara Tool Gateway seharusnya dibangun sejak awal.

---

### ⚡ OP-4 — Time Machine: Deterministic Replay & Ganti Otak Tanpa Drama

**Ide.** Karena **semua** sudah dicatat (`messages`, `model_runs`, `agent_steps`, `trace_links`, `used_memory_ids`, prompt version), bangun **replay harness**: ambil run apa pun dari masa lalu, putar ulang konteks input yang persis sama ke **model baru**, lalu diff hasilnya. North Star doc 12 ("Model changes, Hibob remains") jadi tombol, bukan harapan.

**Kenapa overpower.** Migrasi model — momok semua proyek AI — jadi **prosedur terukur**: "model frontier baru keluar → replay 500 run historis → bandingkan persona/RAG/tool-compliance metric → terima kalau net positif → catat ADR." Ini langsung mengubah doc 12 §9 dari checklist manual jadi pipeline otomatis. Bonus: tiap regresi nyata jadi test case gratis.

**Kenapa masuk akal.** Nol arsitektur baru — ini **buah dari disiplin tracing yang sudah ada**. Cuma butuh: (a) simpan input prompt yang ter-assemble (bukan cuma output hash), (b) mode "dry-run" di Model Router. Sangat selaras dengan model-agnostic. Sangat reversible (replay tidak menyentuh data produksi).

**Kapan.** Phase 6 (Observability). Ini ROI tertinggi per-jam-koding di seluruh daftar.

---

### ⚡ OP-5 — Adversarial Self-Red-Team ("Hibob yang menyerang dirinya tiap malam")

**Ide.** Naikkan Security Skeptic Agent (doc 05 §3.5) dan Eval Level 4 (doc 09 §11) ke level berikutnya: agent yang **secara terjadwal menghasilkan serangan baru** terhadap Hibob — injeksi prompt lewat dokumen palsu, upaya membujuk Tool Gateway, percobaan ekstraksi memory `secret`, social engineering persona — lalu setiap serangan yang **tembus** otomatis jadi regression test di `tool_policy_eval` / `persona_eval`.

**Kenapa overpower.** Sistem keamanan yang **tumbuh lebih cepat dari ancamannya**. Alih-alih menunggu Bob menemukan bug keamanan, Hibob memburu kelemahannya sendiri tiap malam dan menambal lewat eval. Ini mengubah keamanan dari "daftar larangan statis" jadi imun yang adaptif.

**Kenapa masuk akal.** Murni defensif, single-user, local. Tidak menambah permukaan serang ke dunia luar — serangan dijalankan di sandbox terhadap Hibob sendiri. Sangat sejalan dengan "evaluation as product". Output-nya konkret: jumlah test keamanan yang bertambah otomatis. Reversible (cuma menambah eval case).

**Kapan.** Phase 6–7, setelah Tool Gateway + OP-3 (policy-as-code) ada sebagai target serangan.

---

### ⚡ OP-6 — Reflective Sibling: Hibob yang Proaktif, Bukan Cuma Reaktif

**Ide.** Aktifkan "scheduled reflection" (disinggung Phase 8) **jauh lebih awal** sebagai loop reflektif harian/mingguan: Hibob membaca sesi & memory terbaru, lalu **menginisiasi** — "3 minggu lalu lo bilang X, tapi keputusan kemarin mengarah ke Y, ini konflik?", "asumsi A belum pernah diuji padahal 4 keputusan bergantung padanya", "dokumen sumber jawaban kemarin sudah basi". Hasilnya ditulis ke "Hibob Journal" (jenis `session_summary` baru) yang Bob baca saat mau.

**Kenapa overpower.** Inilah yang membuat Hibob terasa seperti **saudara sungguhan, bukan tool**. Saudara tidak menunggu ditanya — dia nyeletuk waktu lihat kamu mau bikin kesalahan. Ini realisasi paling langsung dari identitas #1 ("saudara digital") di Executive Blueprint, dan ia memberi makan OP-1 (graph) + OP-2 (kalibrasi) dengan sinyal konflik berkualitas tinggi.

**Kenapa masuk akal.** Read-only by default (refleksi = analisis, bukan aksi) → risk rendah. Memakai memory & graph yang sudah ada. Bisa dijalankan local (Ollama) karena tugasnya ringan. Permission-safe: refleksi cuma **mengusulkan**, tidak pernah bertindak/menyimpan durable tanpa Bob. Bisa di-eval (apakah refleksi mingguan menangkap konflik nyata?).

**Kapan.** Phase 3.5 — segera setelah memory + graph cukup matang. Tidak perlu nunggu Phase 8.

---

### ⚡ OP-7 — Sandbox OS-level untuk Tool Berbahaya (bukan sekadar policy)

**Ide.** Untuk shell, browser, dan MCP server pihak ketiga: jalankan di **container ephemeral, no-network-by-default, filesystem read-only kecuali workdir**, yang dibuat dan dihancurkan per tool run. Policy (OP-3) memutuskan *boleh atau tidak*; sandbox memastikan *kalaupun tembus, blast radius-nya nol*.

**Kenapa overpower.** Pertahanan berlapis sejati. Doc 08 §8 melarang `curl | sh` lewat aturan — tapi aturan bisa dibujuk injeksi. Sandbox tidak bisa dibujuk: kalau shell jalan tanpa network di container sekali-pakai, exfiltrasi data **secara fisik tidak mungkin**, mau prompt-nya selicik apa pun. Ini membuat "earn autonomy step by step" (roadmap) aman dipercepat.

**Kenapa masuk akal.** Stack-nya sudah Docker/WSL2 — bahan bakunya ada. Tidak perlu Firecracker/gVisor di v0.1; Docker ephemeral + `--network=none` sudah 80% nilainya. Sangat selaras dengan least-privilege (doc 08 §1). Reversible & isolated by construction.

**Kapan.** Phase 4 (sebelum shell/browser tool benar-benar dinyalakan), sejalan dengan security gate doc 08 §13.

---

### ⚡ OP-8 — Learned Model Router (bandit) + Cost Circuit Breaker

**Ide.** Dua hal kembar. (a) Ubah tabel routing statis jadi **router yang belajar**: pakai history `model_runs` (latency, cost, dan skor eval per task type) sebagai feedback bandit ringan untuk memilih model — bukan if-else hardcoded. (b) Pasang **circuit breaker biaya**: budget ceiling per sesi/hari, dan agent loop otomatis berhenti + minta approval kalau menembus ambang.

**Kenapa overpower.** Router yang **menyetel dirinya sendiri**: kalau model local ternyata cukup bagus untuk suatu task (terbukti dari eval), trafik bergeser ke local → lebih privat + lebih murah, otomatis. Sementara circuit breaker mencegah skenario mimpi buruk "agent nyangkut membakar kuota cloud semalaman".

**Kenapa masuk akal.** Datanya **sudah dicatat** di `model_runs` — sekarang cuma jadi log mati, padahal bisa jadi sinyal kontrol. Tetap model-agnostic (router memilih di antara adapter). Tetap explainable (keputusan routing dicatat + alasannya). Mulai konservatif: bandit hanya menyetel di dalam batas yang Bob izinkan. Reversible (bisa balik ke tabel statis kapan saja).

**Kapan.** Router statis di Phase 1 (sesuai rencana). Cost breaker di Phase 1 juga (jangan tunda — ini murah & menyelamatkan dompet). Learned routing di Phase 6 setelah ada data eval.

---

## 4. Peta Prioritas (kalau harus pilih)

Tidak semua 8 setara. Kalau saya Bob, urutannya begini:

| Prioritas | Rekomendasi | Alasan |
|---|---|---|
| 🔴 **Kerjakan cepat** | OP-8b (cost breaker), OP-3 (policy-as-code) | Murah, menyelamatkan dompet & keamanan, dan OP-3 mengubah cara Tool Gateway dibangun — lebih murah dilakukan di awal daripada retrofit. |
| 🟠 **Investasi inti** | OP-1 (graph memory), OP-2 (self-calibrating), OP-4 (replay) | Ini yang membuat Hibob beda secara fundamental dari "RAG + memory biasa". OP-4 hampir gratis karena disiplin tracing sudah ada. |
| 🟡 **Pembeda jiwa** | OP-6 (reflective sibling) | Realisasi paling langsung dari "saudara digital". Begitu jalan, Hibob terasa hidup. |
| 🟢 **Pengeras keamanan** | OP-5 (self-red-team), OP-7 (OS sandbox) | Wajib sebelum autonomy/browser/shell benar-benar dipercepat. |

**Aturan emas:** jangan kerjakan satu pun dari ini sebelum Phase 0–2 (Core + Memory + Eval baseline) berdiri. Semua "overpower" ini adalah **pengali**, dan pengali dari nol tetap nol.

---

## 5. Tiga peringatan jujur

1. **Bahaya terbesar bukan kurang fitur, tapi over-engineering dini.** Roadmap §"Roadmap risks" sudah benar: melompat dari Phase 0 ke Phase 8 adalah racun. Rekomendasi di atas sengaja saya petakan ke fase — jangan tergoda mengerjakan OP-1 sebelum `/chat` dan memory dasar jalan.

2. **Scope creep persona.** Lima agent role (doc 05 §3) untuk single-user v0.1 berisiko jadi multi-agent kompleks yang dilarang sendiri oleh Executive Blueprint §6. Saran: di v0.1 ini cukup **satu agent dengan beberapa "mode/lensa"** (skeptic, builder, curator) lewat prompt+policy, bukan lima proses agent terpisah. Pisahkan jadi agent betulan hanya saat eval membuktikan perlu.

3. **Anti-hype rule berlaku untuk dokumen ini juga.** Saya percaya 8 rekomendasi ini lolos uji "memperbaiki minimal satu: memory/reasoning/tool-safety/dev-speed/privacy/eval". Tapi Bob yang pegang palu. Kalau ada yang cuma bikin Hibob *terlihat* keren di mata Bob, buang — sesuai aturan Bob sendiri.

---

## 6. Penutup

Blueprint ini sudah menjawab pertanyaan tersulit dengan benar: **"apa yang harus bertahan saat segalanya berubah?"** Jawabannya — memory, policy, identitas, eval — tertanam di setiap dokumen. Itu fondasi yang langka.

Delapan rekomendasi di atas tidak mengubah jawaban itu. Mereka **mempertajamnya**:

> Hibob v0.1 yang baik = AI yang punya memory terkurasi.
> Hibob yang overpower = AI yang memorinya **berbentuk graph, mengalibrasi diri, bisa di-replay ke otak baru, membela diri tiap malam, dan menegur Bob sebelum Bob salah** — sambil tetap local, tetap minta izin, tetap bisa diuji, tetap bisa di-rollback.

Itu bukan chatbot. Itu saudara digital yang benar-benar tumbuh.

---

*Dokumen ini opini reviewer. Untuk hal yang disetujui Bob: angkat jadi entri `docs/`, buat ADR, dan — sesuai jiwa Hibob — buat eval-nya dulu sebelum kodenya.*
