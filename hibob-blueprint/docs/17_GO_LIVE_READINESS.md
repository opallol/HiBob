# Hibob Go-Live Readiness & Next Steps

Status: Living document
Tanggal: 2026-06-24
Konteks: Phase 0–9 (backend) selesai, tapi banyak kapabilitas masih **seam/stub**. Dokumen ini jawaban
jujur atas dua pertanyaan — "apakah Hibob siap pegang credential?" dan "apakah UI setting ideal sudah
ada?" — sekaligus peta lengkap apa yang harus dikerjakan berikutnya.

---

## 1. TL;DR (status jujur)

- **Pegang credential asli? BELUM. Jangan kasih credential asli dulu.** Vault hanya *storage* tersegel;
  **tidak ada satu pun tool yang benar-benar memakai credential** (login/kirim) — sengaja dimatikan
  (ADR 0014). Sandbox isolasi nyata juga belum ada (`DockerSandboxRunner` masih seam), padahal
  credential cuma boleh diresolusi di dalam sandbox nyata.
- **UI setting ideal sudah ada? TIDAK. Belum ada UI sama sekali.** Semuanya API + `curl`. Tidak ada
  `frontend/`, tidak ada layar Settings (model/API key/budget/privacy/vault).
- **Belum pernah dijalankan live.** 124 unit test semuanya pakai *fake* (tanpa DB/Qdrant/Ollama nyata).
  Menjalankan beneran = pekerjaan #1 sebelum klaim "siap".

> Phase 1–9 membangun **otak/back-end yang lengkap arsitekturnya, dengan banyak seam** — bukan produk
> jadi yang punya UI dan akses dunia nyata. Itu normal & disengaja (golden rule: jangan nyalakan aksi
> berbahaya sebelum pengamannya nyata).

---

## 2. Peta status: feature nyata vs seam

Legenda: ✅ jalan (logic + unit test) · 🟡 jalan tapi butuh setup/stack · 🔌 seam/stub (belum nyata)

| Subsistem | Status | Catatan |
|---|---|---|
| Chat + persona + model router | 🟡 | butuh Ollama (lokal) / `HIBOB_ANTHROPIC_API_KEY` (cloud) + DB |
| Cost circuit breaker (ADR 0012) | ✅ | gate cloud per ceiling harian |
| Memory core + graph + calibration | 🟡 | butuh Postgres + Qdrant + model embed lokal |
| RAG / knowledge (text) | 🟡 | Markdown/TXT native; PDF/DOCX/web butuh extra `ingest` (🔌 belum dites live) |
| Reflective sibling | 🟡 | job read-only; trigger manual/cron |
| Tool Gateway + Policy Engine (ADR 0005) | ✅ | allow/ask/deny deterministik; tool internal read-only |
| Ephemeral Sandbox (ADR 0011) | 🔌 | hanya `NoopSandboxRunner`; Docker runner **belum diimplementasi** |
| Credential Vault (ADR 0014) | 🔌 | storage+resolusi ada; butuh `cryptography`+key; **tak ada tool yang memakainya** |
| Eval harness (ADR 0008/0009/0012) | 🟡/🔌 | `tool_policy_eval` jalan; LLM-judge/replay-dry-run/bandit-live = seam |
| Multimodal input (vision/STT) | 🟡/🔌 | kontrak jalan; STT butuh extra `multimodal`; vision butuh model multimodal Ollama |
| Multimodal output (image-gen/TTS) | 🔌 | governance jalan; provider gen/TTS **masih stub** |
| Projects + unified recall | 🟡 | butuh DB; recall reuse memory+doc retrieval |
| **UI / frontend** | 🔌 | **tidak ada sama sekali** |
| Deployment / backup / CI / auth | 🔌 | belum ada |

---

## 3. WS0 — Jalankan beneran (PRASYARAT #1, blocking)

Belum ada yang pernah jalan terhadap stack nyata. Sebelum apa pun, buktikan jalannya.

- Stand up **ai-stack**: Postgres + Qdrant + Ollama (+ Phoenix opsional). Lihat `backend/README.md`.
- Apply migrasi **urut `0001` → `0010`** (volume persist, jadi manual). Tarik model Ollama: model chat
  + `nomic-embed-text` (embed).
- Install extras sesuai kebutuhan: `dev` (test), `ingest` (PDF/web), `multimodal` (STT),
  `sandbox` (Docker), `vault` (crypto).
- **Smoke test tiap endpoint live**: `/v1/chat`, memory candidates→approve, documents register→ingest→
  search, tools list→request→approvals/decide, reflections run, evals run, recall, vault store.
- **Acceptance**: semua jalur balas 2xx dan menulis row yang benar di DB; chat lokal + (opsional) cloud
  jalan; privacy guard menolak secret→cloud.
- (Opsional) pasang session-start hook agar setup reproducible.

---

## 4. WS1 — UI / Cockpit ("setting Hibob full yang ideal")

Bangun `frontend/` (target di `docs/14_REPO_STRUCTURE.md`). Ini yang kamu tanyakan: layar setting +
operasi tanpa curl.

Layar minimal:
- **Chat** — kirim pesan (mode/privacy_tier/model_preference), lampiran gambar/audio, toggle `respond_voice`,
  lihat `used_memory_ids`/`used_document_chunk_ids`/`artifacts`.
- **Memory** — antrian kandidat → approve/reject/supersede; lihat graph & confidence.
- **Documents** — register + ingest + status job + search.
- **Tool approvals** — inbox approval (allow/ask/deny), trust score, decide.
- **Reflections** — inbox temuan; ubah jadi kandidat memory.
- **Projects** — buat/arsip; recall ber-scope.
- **Evals** — dashboard pass_rate per suite.
- **Settings (inti pertanyaanmu)** — model & API key (Anthropic), budget ceiling harian (ADR 0012),
  default privacy tier, vault key ref + sandbox backend, allowlist (crawl & browser).
- **Acceptance**: Bob bisa konfigurasi + mengoperasikan seluruh sistem dari UI, tanpa terminal.

---

## 5. WS2 — Credential nyata & aman (DIKERJAKAN TERAKHIR, paling hati-hati)

Urutan wajib (jangan loncat):
1. **Rotasi dulu** credential apa pun yang pernah ter-ekspos (mis. file plaintext lama di folder ops
   ter-sync) — ADR 0014 "immediate action". Jangan masukkan credential asli sebelum WS0 + sandbox nyata.
2. **Wire `DockerSandboxRunner` betulan** — container ephemeral: network `none` default, filesystem
   read-only kecuali workdir ber-scope, dihancurkan setelah run, dicatat `sandbox_runs`.
3. **Aktifkan crypto vault** — install `cryptography`, set `HIBOB_VAULT_KEY` di OS keystore / file kunci
   di luar repo & di luar folder ter-sync (jangan pernah di samping ciphertext).
4. **Bangun tool credential pertama** (mis. kirim email) di belakang: Tool Gateway + Sandbox + approval
   **per-aksi** + risk `critical` (tanpa eskalasi trust). Resolusi credential **hanya di dalam sandbox**;
   nilai dekripsi tidak pernah masuk prompt/trace/`tool_runs`/memory.
- **Acceptance (gate ADR 0014)**: nol nilai credential di trace/log/tool_runs; tiap pemakaian tercatat
  `credential_uses`; tiap aksi minta approval; tipe risk tetap `critical` selamanya.

---

## 6. WS3 — Ganti stub jadi provider nyata

Tiap item: dari seam → implementasi + test + (kalau perlu) extra opsional.
- **STT** lokal (`faster-whisper`, extra `multimodal`).
- **Image-gen + TTS** provider lokal (saat ini stub draft).
- **Ingestion** PDF/DOCX (Unstructured) + web (Crawl4AI) — extra `ingest`.
- **Browser** Playwright nyata via sandbox (Phase 7 + ADR 0011).
- **LLM eval-judge** (ADR 0009): judge model + golden set agreement (sekarang fungsi agreement saja).
- **Learned-router live** (ADR 0012): wire bandit ke router (default `epsilon=0`).
- **Replay dry-run** (ADR 0008): simpan assembled prompt + mode dry-run di adapter.

---

## 7. WS4 — Code semantic search

Seam Phase 8 (doc 06 §14): ingestion kode dengan **structure-aware chunking** (per simbol/fungsi, bukan
chunk generik) + tool `code_search`. Reuse pipeline knowledge.

---

## 8. WS5 — Ops hardening

- Backup Postgres + snapshot Qdrant; restore drill.
- Secret management (key vault OS), rotasi terjadwal.
- Deployment: `docker-compose.yml` + `infra/` (target doc 14).
- Observability: dashboard Phoenix; alert budget/eval-fail.
- CI: jalankan `pytest` + `tool_policy_eval` di tiap PR (menyambung gate self-build Phase 5/ADR 0013).
- **Asumsi single-user** ditegaskan: auth/multi-user tetap di luar scope v0.1.

---

## 9. Urutan rekomendasi & Definition of Ready

**Urutan**: **WS0** (jalankan beneran) → **WS1** (UI/Settings) + sebagian **WS3** (STT/providers biar
dipakai harian) → **WS2** (credential) **paling akhir** → **WS4/WS5**.

- ✅ **"Ready untuk credential"** = WS0 selesai + Docker sandbox nyata + vault crypto aktif + minimal 1
  credential tool lewat gate ADR 0014 + rotasi credential lama selesai.
- ✅ **"UI ideal ada"** = WS1 selesai (semua layar + Settings; Bob tak perlu curl).
- ✅ **"Dipakai harian"** = WS0 + WS1 + STT/provider inti (WS3 sebagian).

---

## 10. Tetap di luar scope (sengaja)

Echo `11_ROADMAP.md` "Things intentionally delayed": always-listening / wake-word voice, autonomous web
write, multi-user SaaS, fine-tuning, avatar, mobile app. Tambah kapan roadmap & kebutuhan nyata sampai
ke sana — bukan sekarang.
