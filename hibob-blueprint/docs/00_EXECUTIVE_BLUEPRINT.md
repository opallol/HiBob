# Hibob Executive Blueprint

Status: Blueprint v0.1 - eksekusi berjalan (Phase 1-5 selesai; lihat `11_ROADMAP.md`)
Tanggal baseline: 2026-06-23

## 1. Ringkasan satu kalimat

**Hibob adalah AI saudara digital milik Bob: local-first, memory-first, model-agnostic, permission-controlled, dan mampu membantu membangun dirinya sendiri melalui siklus diskusi, dokumentasi, coding, evaluasi, dan pembelajaran terkurasi.**

## 2. Identitas produk

Hibob bukan sekadar chatbot. Hibob juga bukan sekadar UI lokal untuk Ollama, bukan workspace RAG generik, bukan coding agent, dan bukan automation tool. Hibob adalah **lapisan koordinasi personal** di atas semua resource tersebut.

Hibob memiliki empat identitas utama:

1. **Saudara digital**  
   Berinteraksi dengan Bob secara natural, kritis, dan personal. Hibob boleh berbeda pendapat, menguji asumsi, dan menjaga Bob agar tidak terlalu cepat lompat ke solusi rapuh.

2. **Second brain**  
   Menyimpan memory, keputusan, prinsip, ide, blueprint, konflik asumsi, dokumen, dan konteks proyek.

3. **Agent operator**  
   Mampu menggunakan tools secara bertahap: search memory, baca dokumen, crawl web, baca repo, membuat draft, menjalankan test, mengoperasikan browser sandbox, dan memicu workflow automation.

4. **AI dev partner**  
   Membantu membangun Hibob: menulis blueprint, membuat issue, mengusulkan patch, menjalankan evaluasi, membaca trace, dan memperbaiki kualitas sistem.

## 3. Prinsip non-negotiable

### 3.1 Hibob Core harus independen dari tools

Ollama, Open WebUI, AnythingLLM, Hermes Agent, Cline, Aider, Qdrant, Activepieces, Phoenix, DeepEval, Crawl4AI, Unstructured, dan Playwright MCP adalah resource. Mereka boleh diganti. **Hibob Core tidak boleh larut menjadi salah satu tool.**

### 3.2 Memory adalah aset utama

Model AI akan berubah. UI akan berubah. Tooling akan berubah. Yang harus bertahan adalah:

- memory Bob,
- keputusan desain,
- konteks proyek,
- riwayat evolusi Hibob,
- policy tool,
- kualitas data,
- evaluasi.

### 3.3 Model-agnostic sejak awal

Hibob harus bisa memakai model lokal dan cloud:

- Local model via Ollama untuk private/cheap/offline-ish tasks.
- Frontier/cloud model untuk reasoning berat, coding kompleks, dan agentic planning.
- Model router memilih model berdasarkan risiko, biaya, privacy tier, dan task type.

### 3.4 Tool access harus lewat gateway

Tidak ada tool yang boleh dipanggil langsung oleh model tanpa policy. Semua aksi masuk lewat **Tool Gateway** yang mencatat:

- siapa meminta aksi,
- tool apa yang dipanggil,
- input/output,
- risiko,
- permission,
- audit log,
- rollback plan bila ada.

### 3.5 Memory bukan tempat sampah chat

Memory harus dikurasi. Setiap kandidat memory punya tipe, confidence, source, status, expiry, dan conflict state. Mood sesaat Bob tidak boleh otomatis menjadi fakta permanen.

### 3.6 Local-first, cloud-optional

Data sensitif harus bisa diproses lokal. Cloud boleh dipakai, tapi harus melewati privacy policy dan redaction jika perlu.

### 3.7 Evaluasi adalah bagian produk, bukan bonus

Hibob harus bisa diuji. Kualitas tidak boleh hanya berdasarkan rasa. Setiap versi harus bisa dicek melalui:

- memory recall tests,
- RAG faithfulness tests,
- tool permission tests,
- personality consistency tests,
- safety regression tests,
- observability traces.

### 3.8 Keputusan izin harus deterministik, bukan judgement model (ADR 0005)

Allow/ask/deny untuk tool apa pun dihasilkan oleh Policy Engine berbasis aturan tertulis (`policy_rules`), bukan oleh model yang menilai permintaannya sendiri saat itu. Tool boleh makin dipercaya dari riwayat pemakaian (`tool_trust_scores`), tapi kenaikan itu tidak pernah melewati risk ceiling tool tersebut dan tidak pernah berlaku untuk aksi critical.

### 3.9 Tool berisiko tinggi harus terkurung secara teknis (ADR 0011)

Policy yang mengizinkan sebuah aksi bukan jaminan keamanan yang cukup. Tool type shell, browser, dan MCP pihak ketiga harus berjalan di ephemeral sandbox (no-network/read-only default) sebagai lapisan independen dari permission policy - defense in depth, bukan satu titik kegagalan.

### 3.10 Biaya cloud harus punya hard ceiling, bukan dashboard yang dipantau manual (ADR 0012)

Setiap call model cloud dicatat ke cost ledger terhadap budget ceiling. Ceiling yang terlampaui memaksa pause otomatis dan approval request - Bob tidak boleh baru tahu lewat tagihan di akhir bulan.

### 3.11 Hibob boleh proaktif, tapi tidak boleh otonom (ADR 0010)

Hibob boleh mendatangi Bob dengan temuan (reflection terjadwal atas memory, graph, dan RAG), tapi temuan itu selalu read-only - tidak pernah jadi durable memory atau tool call tanpa lewat jalur approval yang sama dengan kandidat memory biasa.

### 3.12 Hibob tidak boleh mengubah rule keamanannya sendiri tanpa pengawasan yang sama ketatnya (ADR 0013)

Self-build proposal (blueprint update, draft patch, issue draft) dievaluasi sebagai tool_run berisiko, bukan jalur pintas. Perubahan pada file security/policy/schema selalu high risk apa pun ukuran diff-nya, tidak pernah lolos lewat trust-tier escalation, dan selalu butuh approval eksplisit Bob.

### 3.13 Kredensial operasional (login, kirim pesan/email) hidup di vault terenkripsi, bukan di memory atau dokumen (ADR 0014)

Credential asli (password, token) tidak pernah disimpan sebagai memory atau file dokumentasi biasa, karena keduanya didesain untuk masuk ke prompt/vector - persis hal yang harus dihindari kredensial hidup. Tool yang butuh kredensial menerima `credential_ref`, bukan nilai asli; nilai asli diresolusi server-side di dalam Sandbox (ADR 0011) saat eksekusi, tidak pernah masuk prompt/trace/memory. Risk tier kredensial selalu `critical` dan tidak pernah lolos trust-tier escalation. Tool yang benar-benar memakai kredensial (login, kirim email/pesan) tetap mengikuti exclusion v0.1 di §6 - vault-nya boleh dibangun lebih awal, tool yang memakainya tidak.

## 4. Bentuk akhir yang dituju

Bentuk maksimal realistis dengan resource personal saat ini:

```text
Hibob = Self-building local-first personal AI operating layer
```

Dengan kemampuan:

- berdialog sebagai saudara digital,
- mengingat konteks Bob dan proyek,
- membaca dokumen dan web,
- mengelola knowledge base,
- menggunakan tools lewat izin,
- membantu coding dan review,
- mengevaluasi performa dirinya,
- menjaga blueprint hidup,
- tetap relevan saat model AI masa depan muncul,
- mengingat dengan konteks relasi antar-keputusan, bukan cuma daftar fakta lepas,
- mendatangi Bob dengan temuan sebelum ditanya, dalam batas yang aman,
- menyerang dirinya sendiri secara terkendali untuk menemukan celah sebelum orang lain menemukannya,
- menjaga dompet Bob tanpa diminta.

## 5. MVP yang benar

MVP Hibob bukan voice, avatar, mobile app, atau browser full-control. MVP yang benar:

```text
Hibob v0.1 = Blueprint Guardian + Memory Core + Knowledge Base dasar + Tool Policy dasar
```

Target v0.1:

- Bob bisa ngobrol dengan Hibob melalui UI sederhana.
- Hibob bisa menyimpan memory terkurasi.
- Hibob bisa membedakan memory Bob vs memory Hibob.
- Hibob bisa membaca dokumen blueprint dan melakukan retrieval.
- Hibob bisa menjelaskan kenapa dia mengambil jawaban tertentu.
- Hibob memiliki tool registry dan permission level, walau tool yang aktif masih sedikit.
- Setiap sesi diskusi bisa menghasilkan session summary, decision log, dan candidate memory.

## 6. Hal yang tidak boleh masuk v0.1

- Avatar 3D.
- Voice realtime.
- Autopilot browser publik.
- Auto-commit ke main branch.
- Auto-delete file.
- Email/calendar/write action - ditunda, bukan ditolak permanen; lihat ADR 0014. Storage kredensial (vault) boleh dibangun lebih awal (Phase 4), tapi tool yang benar-benar login/kirim pesan memakainya tetap tidak aktif sebelum Phase 7 dan tetap butuh approval per-aksi tanpa trust-tier escalation.
- Fine-tuning model sendiri.
- Multi-agent kompleks tanpa kebutuhan jelas.
- Kubernetes.
- Microservices.

Alasannya sederhana: semua itu akan membuat Hibob terlihat keren tapi rapuh jika memory, permission, dan evaluasi belum matang.

## 7. Hipotesis produk

Hipotesis utama:

> Hibob akan terasa berbeda dari chatbot generik jika ia punya memory terkurasi, konteks proyek, gaya hubungan personal, dan kemampuan bertindak dengan batas izin yang jelas.

Hipotesis yang perlu diuji:

1. Apakah memory-first membuat Hibob terasa lebih hidup?
2. Apakah Bob merasa dibantu saat Hibob menantang asumsi, bukan hanya memberi jawaban?
3. Apakah local-first mode cukup berguna untuk dokumen privat?
4. Apakah evaluasi otomatis benar-benar membantu peningkatan kualitas?
5. Apakah self-building loop mempercepat pengembangan Hibob tanpa membuat sistem chaos?

## 8. Strategi perkembangan

Hibob harus tumbuh seperti organisme, bukan dibangun seperti monolit fitur.

Urutan pertumbuhan:

1. **Identity & blueprint** - Hibob tahu dirinya sedang dibangun untuk apa.
2. **Memory** - Hibob mulai mengingat secara sehat.
3. **Knowledge** - Hibob membaca dokumen dan web.
4. **Tools** - Hibob bertindak secara terbatas.
5. **Evaluation** - Hibob bisa diuji dan diperbaiki.
6. **Self-building** - Hibob membantu membangun versi berikutnya.
7. **Personal AI OS** - Hibob menjadi lapisan operasi personal Bob.

Catatan: kemampuan refleksi proaktif (ADR 0010, identitas "saudara digital") diaktifkan secepat Memory dan Knowledge cukup matang (roadmap Phase 3.5) - tidak ditahan sampai langkah 7, karena itu salah satu hal paling khas yang membedakan Hibob dari chatbot biasa. Lihat `docs/11_ROADMAP.md`.

## 9. Definisi sukses awal

Hibob v0.1 sukses jika Bob bisa berkata:

> “Hibob ini belum canggih penuh, tapi dia sudah ingat arah proyek, bisa menjaga blueprint, bisa membantah gue dengan konteks, dan bisa membantu gue membangun dirinya tanpa kehilangan arah.”

## 10. Definisi gagal

Hibob gagal jika menjadi:

- chatbot lokal biasa,
- tumpukan tools tanpa core,
- RAG app generik,
- automation liar tanpa izin,
- sistem memory penuh noise,
- produk yang hanya mengejar fitur keren tanpa evaluasi,
- tool yang trust score-nya lepas dari risk ceiling atau berlaku untuk aksi critical,
- biaya cloud yang meledak tanpa terdeteksi sampai tagihan datang,
- self-build yang mengubah rule keamanan/policy/schema-nya sendiri tanpa approval eksplisit Bob.
