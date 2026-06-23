# Hibob Blueprint Documentation Pack

Tanggal baseline: 2026-06-23
Status: Implementasi berjalan - Phase 1-3.7 selesai (Core, Memory Core, Memory Graph & Calibration, Knowledge Base/RAG, Reflective Sibling, Multimodal Input)
Pemilik konsep: Bob

Paket ini adalah fondasi dokumentasi untuk membangun **Hibob** dari nol: AI saudara digital, second brain, agent operator, dan AI dev partner yang local-first, memory-first, model-agnostic, permission-controlled, serta future-proof terhadap perkembangan model AI.

## Status implementasi

Repo ini bukan lagi sekadar blueprint - backend `hibob_core` sudah berjalan. Ringkas:

- **Phase 1 - Core Minimal** ✅ — `/v1/chat`, persona, model router (Ollama/Anthropic), cost circuit breaker (ADR 0012), persistence, Phoenix tracing.
- **Phase 2 - Memory Core** ✅ — extraction, approval human-only, hybrid retrieval (Qdrant + SQL) tersambung ke chat, session summary, conflict minimal.
- **Phase 2.5 - Memory Graph & Calibration** ✅ — `memory_edges` (ADR 0006) + traversal recursive CTE, dan kalibrasi confidence via `memory_usage_feedback` (ADR 0007).
- **Phase 3 - Knowledge Base/RAG** ✅ — ingestion dokumen/web → chunking → embedding lokal → Qdrant, dan retrieval ber-sumber tersambung ke chat (doc 06; v0.1 ekstraksi teks, PDF/DOCX/web via adapter opsional).
- **Phase 3.5 - Reflective Sibling** ✅ — job read-only (ADR 0010) yang menyisir memory graph + sumber RAG untuk konflik/asumsi rapuh/sumber basi, menulis temuan ke `reflections` untuk Bob review.
- **Phase 3.7 - Multimodal Input** ✅ — `/v1/chat` menerima `attachments` gambar/audio: audio ditranskrip lokal (STT), gambar jadi pesan multimodal; privacy tetap by tier (media private/secret tak ke cloud), media mentah tak dipersist.

Detail teknis & cara menjalankan ada di `backend/README.md`. Status per fase di `docs/11_ROADMAP.md`.

Dokumen utama berada di folder `docs/`. Diagram Mermaid berada di `docs/diagrams/`. Skema database awal berada di `database/schema.sql`. ADR berada di `adr/` - termasuk ADR 0005-0013, hasil `REVIEW_DAN_REKOMENDASI_OVERPOWER.md` yang sudah diterima (Accepted) dan diintegrasikan penuh ke seluruh dokumen di atas.

## Cara baca cepat

1. Mulai dari `docs/00_EXECUTIVE_BLUEPRINT.md` untuk arah besar.
2. Lanjut ke `docs/01_PRD.md` untuk requirement produk.
3. Baca `docs/02_SYSTEM_ARCHITECTURE.md` dan `docs/03_ERD_DATA_MODEL.md` untuk fondasi sistem.
4. Baca `docs/04_MEMORY_SYSTEM.md`, `docs/05_AGENT_AND_TOOL_POLICY.md`, dan `docs/08_SECURITY_PRIVACY_GOVERNANCE.md` sebelum coding agent/tool.
5. Gunakan `docs/11_ROADMAP.md` untuk eksekusi bertahap - termasuk kapan tiap ADR 0005-0013 diaktifkan.
6. Gunakan `docs/12_FUTURE_AI_ADAPTATION.md` supaya Hibob tidak cepat basi saat model, tools, dan protokol berubah.
7. Baca `adr/0005-*.md` sampai `adr/0013-*.md` untuk detail keputusan di balik policy engine, memory graph, confidence calibration, replay harness, self-red-team, reflective sibling, ephemeral sandbox, cost circuit breaker, dan self-building safety gate.

## Prinsip inti

Hibob bukan wrapper ChatGPT, Open WebUI, AnythingLLM, Hermes Agent, Cline, Aider, atau Ollama. Semua itu adalah resource. Intinya adalah **Hibob Core**: lapisan yang mengatur identitas, memory, context, tool routing, permission, observability, evaluasi, dan evolusi sistem.

