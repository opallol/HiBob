# Hibob Blueprint Documentation Pack

Tanggal baseline: 2026-06-23
Status: Blueprint v0.1 - pre-implementation
Pemilik konsep: Bob

Paket ini adalah fondasi dokumentasi untuk membangun **Hibob** dari nol: AI saudara digital, second brain, agent operator, dan AI dev partner yang local-first, memory-first, model-agnostic, permission-controlled, serta future-proof terhadap perkembangan model AI.

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

