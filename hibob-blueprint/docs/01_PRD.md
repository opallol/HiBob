# Product Requirements Document (PRD) - Hibob

Status: Draft matang v0.1
Tanggal baseline: 2026-06-23

## 1. Nama produk

**Hibob**

## 2. Visi produk

Hibob adalah AI saudara digital yang memahami Bob, mengingat konteks jangka panjang, membantu berpikir, menjaga blueprint proyek, menggunakan tools secara aman, dan ikut membangun dirinya sendiri secara bertahap.

## 3. Masalah yang ingin diselesaikan

Bob ingin membangun sistem AI personal dari nol, tetapi ruang teknologi AI sangat fluktuatif. Model berubah, tools berubah, protokol berubah, dan aplikasi generik cepat basi. Bob butuh sistem yang:

- punya konteks personal,
- bisa menjadi partner dialog kritis,
- bisa menyimpan dan mengelola memory,
- bisa menyerap dokumen dan web,
- bisa memakai tools dengan izin,
- bisa diuji kualitasnya,
- tetap relevan saat perkembangan AI baru muncul.

## 4. Target pengguna awal

### Primary user

- Bob sebagai pembangun, pemilik, dan pengguna utama Hibob.

### Secondary user masa depan

- Developer yang ingin menjalankan Hibob lokal.
- User teknis yang ingin AI personal local-first.
- Tim kecil yang ingin agent private berbasis memory dan tools.

Namun v0.1 hanya dioptimalkan untuk Bob. Multi-user adalah fase berikutnya.

## 5. Persona Hibob

Hibob harus terasa seperti:

- saudara digital,
- kritis tapi konstruktif,
- tidak terlalu formal,
- tidak asal setuju,
- menjaga arah,
- bisa mengingat keputusan lama,
- punya batas moral/operasional.

Hibob tidak boleh terasa seperti:

- customer support bot,
- guru menggurui,
- chatbot korporat,
- “AI yang selalu memuji user”,
- agent liar yang bertindak tanpa izin.

## 6. North Star Metric

Untuk fase awal:

```text
Jumlah keputusan desain penting yang berhasil ditangkap, dikurasi, dan dipakai kembali oleh Hibob dengan benar.
```

Metric pendukung:

- memory precision,
- memory recall relevance,
- RAG faithfulness,
- tool approval compliance,
- session summary usefulness,
- blueprint update accuracy,
- Bob satisfaction per session.

## 7. Scope v0.1

### 7.1 In-scope

1. Chat UI awal melalui Open WebUI atau custom UI sederhana.
2. Hibob Core API.
3. Model router minimal: local Ollama + optional cloud provider.
4. Memory Core:
   - candidate memory extraction,
   - memory approval,
   - memory search,
   - memory conflict detection dasar.
5. Knowledge ingestion dasar:
   - markdown,
   - txt,
   - PDF/DOCX melalui Unstructured,
   - web markdown melalui Crawl4AI.
6. Vector store via Qdrant.
7. Canonical relational store via PostgreSQL atau SQLite pada fase prototyping.
8. Tool Registry dan Permission Policy.
9. Observability awal via Phoenix.
10. Eval awal via DeepEval.
11. Dokumentasi hidup:
    - PRD,
    - arsitektur,
    - ERD,
    - memory design,
    - roadmap,
    - ADR.

### 7.2 Out-of-scope v0.1

- avatar visual,
- speech realtime,
- mobile app,
- autonomous email/calendar write,
- production deployment publik,
- multi-user enterprise,
- model training/fine-tuning,
- autonomous full browser control,
- auto-commit tanpa review,
- monetisasi.

## 8. User stories

### 8.1 Dialog dan persona

Sebagai Bob, gue ingin ngobrol dengan Hibob secara natural agar diskusi terasa seperti dengan saudara digital, bukan chatbot formal.

Acceptance criteria:

- Hibob menggunakan gaya bicara yang disepakati.
- Hibob boleh tidak setuju dengan alasan.
- Hibob menanyakan atau menguji asumsi penting.
- Hibob tidak menyimpan semua ucapan sebagai fakta permanen.

### 8.2 Session summary

Sebagai Bob, gue ingin setiap sesi penting diringkas agar keputusan dan asumsi tidak hilang.

Acceptance criteria:

- Hibob menghasilkan ringkasan sesi.
- Hibob membedakan fakta, keputusan, asumsi, risiko, dan pertanyaan lanjutan.
- Hibob membuat kandidat memory dari sesi.
- Bob bisa approve/reject/edit kandidat memory.

### 8.3 Memory recall

Sebagai Bob, gue ingin Hibob mengingat keputusan lama supaya diskusi tidak mulai dari nol.

Acceptance criteria:

- Hibob bisa mengambil memory relevan.
- Hibob mencantumkan sumber internal atau alasan retrieval.
- Hibob tidak memaksakan memory lemah.
- Hibob memberi tanda jika ada konflik memory.

### 8.4 Knowledge ingestion

Sebagai Bob, gue ingin memasukkan dokumen dan website ke knowledge base agar Hibob bisa membaca sumber proyek.

Acceptance criteria:

- Dokumen diproses menjadi chunks.
- Chunks punya metadata sumber.
- Embedding tersimpan di Qdrant.
- Dokumen asli tetap disimpan atau direferensikan.
- Jawaban berbasis dokumen bisa menunjukkan sumber.

### 8.5 Tool action dengan izin

Sebagai Bob, gue ingin Hibob bisa memakai tools, tapi aksi berisiko harus minta izin.

Acceptance criteria:

- Setiap tool punya risk level.
- Tool risk medium/high membutuhkan approval sesuai policy.
- Semua tool run masuk audit log.
- Hibob tidak boleh menjalankan destructive action tanpa konfirmasi eksplisit.

### 8.6 Self-building loop

Sebagai Bob, gue ingin Hibob membantu membangun dirinya sendiri agar proses development menjadi cepat tapi tetap terkontrol.

Acceptance criteria:

- Diskusi dapat berubah menjadi blueprint update.
- Blueprint dapat berubah menjadi issue/task.
- Task dapat dibantu oleh Cline/Aider.
- Hasil perubahan diuji oleh DeepEval/CI.
- Hasil evaluasi masuk improvement log.

### 8.7 Memory yang tahu seberapa yakin dirinya (ADR 0006, ADR 0007)

Sebagai Bob, gue ingin Hibob bisa menjelaskan kenapa sebuah keputusan lama berubah, dan makin jarang membawa fakta yang sudah terbukti salah.

Acceptance criteria:

- Hibob bisa menjawab "kenapa kita pindah dari keputusan X ke Y?" lewat relasi `memory_edges`, bukan cuma timestamp terbaru.
- Memory yang berulang kali dikoreksi confidence-nya turun dan berhenti muncul di top retrieval.
- Penurunan confidence tidak pernah otomatis mengubah status memory - itu tetap keputusan Bob.

### 8.8 Reflective sibling - Hibob yang proaktif (ADR 0010)

Sebagai Bob, gue ingin Hibob kadang mendatangi gue dengan temuan, bukan cuma menunggu ditanya - itu yang bikin dia terasa seperti saudara, bukan search engine.

Acceptance criteria:

- Reflection job terjadwal menyisir memory/graph/RAG untuk konflik belum selesai, asumsi belum diuji, atau sumber stale.
- Temuan tersimpan sebagai `reflections` yang Bob baca async, tidak mengganggu sesi chat aktif.
- Reflection job tidak pernah menulis durable memory atau memanggil tool sendiri - hanya mengusulkan kandidat lewat jalur approval yang sama dengan memory candidate biasa.

### 8.9 Tool yang makin dipercaya tapi tidak pernah lepas kendali (ADR 0005, ADR 0011)

Sebagai Bob, gue ingin tool yang sering dipakai dengan aman jadi sedikit lebih lancar dipakai, tapi tool berisiko tinggi tetap terkurung secara teknis, bukan cuma lewat aturan di atas kertas.

Acceptance criteria:

- Keputusan allow/ask/deny dihasilkan Policy Engine deterministik (`policy_rules`), bukan judgment model saat itu.
- Trust score tool boleh naik dari ask ke auto seiring riwayat bersih, tapi tidak pernah melewati risk ceiling-nya dan tidak pernah berlaku untuk aksi critical.
- Tool shell/browser/MCP pihak ketiga selalu berjalan di ephemeral sandbox (no-network/read-only default), terlepas dari trust score atau hasil approval.

### 8.10 Hemat tapi tidak pelit (ADR 0012)

Sebagai Bob, gue ingin Hibob otomatis berhenti memanggil model cloud kalau sudah kelewat budget, tanpa gue harus mengecek tagihan setiap hari.

Acceptance criteria:

- Setiap call cloud dicatat ke `cost_ledger` terhadap `budget_ceilings` harian/sesi.
- Ceiling terlampaui memaksa pause otomatis pada cloud call dan mengangkat approval request - model lokal tidak terdampak.
- Di antara model yang sudah diizinkan untuk sebuah task, router boleh belajar bias pilihan dari riwayat performa/biaya, tapi tidak pernah memperluas model mana yang eligible.

## 9. Functional requirements

### FR-001 Conversation management

Sistem harus menyimpan percakapan, pesan, metadata model, dan trace ID.

### FR-002 Model router

Sistem harus menyediakan interface model-agnostic untuk local/cloud model.

### FR-003 Memory candidate extraction

Sistem harus mengekstrak kandidat memory dari percakapan penting.

### FR-004 Memory approval workflow

Sistem harus menyediakan status memory: candidate, approved, rejected, archived, superseded.

### FR-005 Memory retrieval

Sistem harus mencari memory berdasarkan semantic search, keyword filter, tipe, confidence, recency, dan source.

### FR-006 Memory conflict detection

Sistem harus mendeteksi potensi konflik antara memory baru dan lama, dimodelkan sebagai `memory_edges` dengan `relation_type = contradicts` (ADR 0006), bukan tabel konflik terpisah.

### FR-007 Document ingestion

Sistem harus memproses dokumen menjadi text blocks, chunks, embedding, metadata, dan source references.

### FR-008 Web ingestion

Sistem harus mengambil halaman web menjadi markdown bersih, chunk, dan index.

### FR-009 Tool registry

Sistem harus menyimpan definisi tool, schema input/output, risk level, permission rule, dan owner.

### FR-010 Tool gateway

Sistem harus mengeksekusi tool hanya melalui gateway yang melakukan validation, permission, logging, dan error handling. Keputusan permission dihasilkan Policy Engine deterministik (`policy_rules`), dan tipe tool berisiko tinggi (shell/browser/MCP pihak ketiga) selalu dieksekusi di dalam ephemeral sandbox, bukan di proses utama (ADR 0005, ADR 0011).

### FR-011 Approval workflow

Sistem harus bisa pause action dan meminta approval Bob.

### FR-012 Audit log

Semua aksi penting harus tercatat.

### FR-013 Observability

Setiap run harus punya trace untuk model call, retrieval, tool call, latency, error, dan keputusan policy.

### FR-014 Evaluation

Sistem harus menyediakan eval suite untuk memory, RAG, tool policy, persona, dan safety.

### FR-015 Blueprint guardian

Sistem harus bisa menghubungkan diskusi dengan dokumen blueprint dan memberi rekomendasi update.

### FR-016 Memory graph (ADR 0006)

Sistem harus menyimpan relasi antar-memory (`supersedes`, `contradicts`, `depends_on`, `supports`, `derived_from`) sebagai `memory_edges` bi-temporal, dan mendukung traversal multi-hop untuk pertanyaan seperti "apa yang bergantung pada asumsi ini".

### FR-017 Memory confidence calibration (ADR 0007)

Sistem harus memperbarui confidence memory dari sinyal pemakaian nyata (`memory_usage_feedback`: used/corrected/accepted/ignored) lewat update Bayesian, dan tidak pernah mempromosikan `status` memory secara otomatis dari proses ini.

### FR-018 Policy-as-code engine dan trust tier (ADR 0005)

Sistem harus mengevaluasi setiap tool call lewat `policy_rules` versioned yang deterministik, dan boleh menaikkan tool dari `ask` ke `auto` lewat `tool_trust_scores` hanya dalam batas risk ceiling tool tersebut, tidak pernah untuk risk critical.

### FR-019 Deterministic replay harness (ADR 0008)

Sistem harus bisa merakit ulang dan menjalankan ulang historical request terhadap model kandidat dalam mode dry-run, lalu membandingkan hasilnya dengan `eval_results` yang ada, sebelum migrasi model disetujui.

### FR-020 Adversarial self-red-team loop (ADR 0009)

Sistem harus menjalankan serangan terjadwal (prompt injection lewat dokumen, permission persuasion, social engineering persona) terhadap instance sandboxed-nya sendiri, dan mengonversi setiap serangan yang berhasil menjadi eval case permanen.

### FR-021 Reflective sibling job (ADR 0010)

Sistem harus menjalankan job reflection terjadwal, read-only, berbasis model lokal, yang menyisir memory/graph/RAG dan mengusulkan kandidat lewat pipeline approval yang sama dengan memory candidate biasa - tidak pernah menulis durable memory atau memanggil tool langsung.

### FR-022 Ephemeral sandbox execution (ADR 0011)

Sistem harus mengeksekusi tool type shell/browser/MCP pihak ketiga di dalam container ephemeral per-run dengan default no-network dan filesystem read-only, dihancurkan segera setelah run selesai.

### FR-023 Cost circuit breaker dan learned routing (ADR 0012)

Sistem harus mencatat setiap call model cloud ke `cost_ledger` terhadap `budget_ceilings`, menghentikan call cloud dan mengangkat approval request saat ceiling terlampaui, dan boleh membiaskan pilihan model lewat `router_policy_feedback` hanya di antara kandidat yang sudah eligible secara privacy/risk.

### FR-024 Self-building loop safety gate (ADR 0013)

Sistem harus memperlakukan proposal self-build (blueprint update, draft patch, issue draft) sebagai `tool_run` yang dievaluasi Policy Engine, mengklasifikasikan risk berdasarkan file yang disentuh (bukan ukuran diff), tidak pernah meng-escalate trust tier untuk file security/policy/schema, dan mewajibkan approval eksplisit Bob sebelum merge.

## 10. Non-functional requirements

### NFR-001 Local-first

Hibob harus dapat berjalan secara lokal untuk mode private.

### NFR-002 Provider agnostic

Model provider harus bisa diganti tanpa merombak business logic.

### NFR-003 Secure by default

Tool high-risk harus default blocked sampai policy dan approval tersedia.

### NFR-004 Explainable enough

Hibob harus bisa menjelaskan memory/dokumen/tool apa yang memengaruhi jawaban.

### NFR-005 Testable

Perubahan prompt, retrieval, model, dan tool policy harus bisa diuji regression.

### NFR-006 Evolvable

Arsitektur harus mendukung model baru, embedding baru, MCP server baru, dan UI baru.

### NFR-007 Recoverable

Data penting harus bisa backup/restore. Perubahan file harus lewat git agar rollback tersedia.

### NFR-008 Cost governance (ADR 0012)

Pengeluaran cloud harus punya hard ceiling yang ditegakkan sistem, bukan sekadar dashboard yang dipantau manual.

### NFR-009 Defense in depth (ADR 0005, ADR 0011)

Permission policy dan sandbox eksekusi adalah dua lapisan independen. Tidak ada satu lapisan yang boleh menjadi satu-satunya penjamin keamanan eksekusi tool.

## 11. Product risks

| Risiko | Dampak | Mitigasi |
|---|---:|---|
| Hibob jadi wrapper tool | Tinggi | Hibob Core sebagai pusat identitas dan policy |
| Memory penuh noise | Tinggi | Candidate + approval + confidence + expiry |
| Tool action liar | Tinggi | Tool Gateway + risk level + approval |
| RAG mengarang | Tinggi | Source attribution + faithfulness eval |
| Terlalu banyak stack | Sedang | Core vs sandbox separation |
| Vendor lock-in model | Sedang | ModelAdapter sejak awal |
| Local model kurang pintar | Sedang | Hybrid local/cloud routing |
| Evaluasi diabaikan | Tinggi | DeepEval/Phoenix masuk v0.1 |
| Biaya cloud tidak terkendali | Tinggi | Cost circuit breaker sejak Phase 1 (ADR 0012) |
| Self-build patch merusak rule keamanan sendiri | Tinggi | Merge gate ADR 0013 - file security/policy/schema selalu high risk |
| Eval judge/model drift tanpa terdeteksi | Sedang | Pinned judge version + golden-set agreement score (ADR 0009) |

## 12. MVP acceptance summary

Hibob v0.1 dianggap layak jika:

- bisa chat dengan persona dasar,
- bisa membuat session summary,
- bisa menghasilkan candidate memory,
- bisa approve/search memory,
- bisa ingest minimal satu dokumen dan satu halaman web,
- bisa retrieval dokumen dengan sumber,
- punya tool registry minimal,
- punya audit log tool run,
- punya Phoenix trace untuk run utama,
- punya minimal 20 eval test DeepEval,
- punya docs blueprint yang sinkron dengan keputusan terbaru.

FR-016 sampai FR-024 (ADR 0006-0013) adalah keputusan arsitektur yang **accepted** untuk blueprint ini, tetapi bukan bagian dari gate MVP v0.1 di atas - timing aktivasinya diatur fase demi fase oleh `docs/11_ROADMAP.md`, bukan dipaksakan masuk ke v0.1 secara langsung. Lihat `docs/checklists/MVP_ACCEPTANCE.md` untuk gate yang sebenarnya dipakai saat ini.
