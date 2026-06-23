# Hibob Blueprint Documentation Pack

Tanggal baseline: 2026-06-23
Status: Blueprint v0.1 - pre-implementation
Pemilik konsep: Bob

Paket ini adalah fondasi dokumentasi untuk membangun **Hibob** dari nol: AI saudara digital, second brain, agent operator, dan AI dev partner yang local-first, memory-first, model-agnostic, permission-controlled, serta future-proof terhadap perkembangan model AI.

Dokumen utama berada di folder `docs/`. Diagram Mermaid berada di `docs/diagrams/`. Skema database awal berada di `database/schema.sql`. ADR awal berada di `adr/`.

## Cara baca cepat

1. Mulai dari `docs/00_EXECUTIVE_BLUEPRINT.md` untuk arah besar.
2. Lanjut ke `docs/01_PRD.md` untuk requirement produk.
3. Baca `docs/02_SYSTEM_ARCHITECTURE.md` dan `docs/03_ERD_DATA_MODEL.md` untuk fondasi sistem.
4. Baca `docs/04_MEMORY_SYSTEM.md`, `docs/05_AGENT_AND_TOOL_POLICY.md`, dan `docs/08_SECURITY_PRIVACY_GOVERNANCE.md` sebelum coding agent/tool.
5. Gunakan `docs/11_ROADMAP.md` untuk eksekusi bertahap.
6. Gunakan `docs/12_FUTURE_AI_ADAPTATION.md` supaya Hibob tidak cepat basi saat model, tools, dan protokol berubah.

## Prinsip inti

Hibob bukan wrapper ChatGPT, Open WebUI, AnythingLLM, Hermes Agent, Cline, Aider, atau Ollama. Semua itu adalah resource. Intinya adalah **Hibob Core**: lapisan yang mengatur identitas, memory, context, tool routing, permission, observability, evaluasi, dan evolusi sistem.
