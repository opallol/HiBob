# Hibob Documentation Index

Dokumentasi ini dibuat sebagai blueprint matang untuk membangun Hibob menuju sistem AI personal-agent yang bisa tumbuh jangka panjang. Blueprint sudah mulai dieksekusi: backend `hibob_core` berjalan (Phase 1 + 2 + 2.5).

## Status implementasi

- Ringkasan per fase: `11_ROADMAP.md` (lihat penanda ✅/🚧/⏳).
- Kode + cara menjalankan: `../backend/README.md`.
- Selesai: Phase 1 (Core), Phase 2 (Memory Core), Phase 2.5 (Memory Graph & Calibration).
- Aturan: dokumentasi mengikuti kode (`14_REPO_STRUCTURE.md` §3). Saat perilaku berubah, doc terkait ikut di-update.

## Dokumen produk

- `00_EXECUTIVE_BLUEPRINT.md` - visi, arah, prinsip non-negotiable.
- `01_PRD.md` - Product Requirements Document.
- `11_ROADMAP.md` - fase pengembangan dari blueprint sampai self-building loop.

## Dokumen teknis

- `02_SYSTEM_ARCHITECTURE.md` - arsitektur konseptual dan runtime.
- `03_ERD_DATA_MODEL.md` - ERD dan model data canonical.
- `04_MEMORY_SYSTEM.md` - desain memory-first Hibob.
- `05_AGENT_AND_TOOL_POLICY.md` - agent, tools, permission, audit.
- `06_RAG_INGESTION_PIPELINE.md` - pipeline dokumen, web crawling, chunking, retrieval.
- `07_LOCAL_FIRST_STACK.md` - pemanfaatan Ollama, Open WebUI, Qdrant, AnythingLLM, Crawl4AI, Unstructured, Playwright MCP, Activepieces, Phoenix, DeepEval, Cline, Aider, Docker/WSL2, Hermes Agent.
- `08_SECURITY_PRIVACY_GOVERNANCE.md` - keamanan, privacy tier, threat model.
- `09_OBSERVABILITY_EVALUATION.md` - tracing, evals, regression tests, quality gates.
- `10_DEVELOPMENT_WORKFLOW.md` - workflow coding, GitHub, Cline/Aider, review, CI.
- `13_API_SPEC.md` - rancangan API internal.
- `14_REPO_STRUCTURE.md` - struktur monorepo target.
- `15_OPERATING_MANUAL.md` - cara menjalankan Hibob sebagai sistem hidup.
- `12_FUTURE_AI_ADAPTATION.md` - future-proofing terhadap perkembangan AI.
- `16_GLOSSARY.md` - daftar istilah, termasuk istilah dari ADR 0005-0013.
- `99_REFERENCES.md` - referensi teknologi.

## ADR (Architecture Decision Records)

`../adr/` - lihat `14_REPO_STRUCTURE.md` §4 untuk daftar lengkap. ADR 0001-0004 adalah keputusan fondasi awal; ADR 0005-0013 adalah hasil review `REVIEW_DAN_REKOMENDASI_OVERPOWER.md` yang sudah diterima (Accepted) dan diintegrasikan ke seluruh dokumen di atas: policy-as-code (0005), memory graph (0006), confidence calibration (0007), replay harness (0008), self-red-team & eval judge integrity (0009), reflective sibling (0010), ephemeral sandbox (0011), learned router & cost circuit breaker (0012), self-building loop safety gate (0013).

## Diagram

- `diagrams/architecture.mmd`
- `diagrams/agent_loop.mmd`
- `diagrams/erd.mmd`
- `diagrams/rag_pipeline.mmd`

## Checklists

- `checklists/MVP_ACCEPTANCE.md`
- `checklists/SECURITY_GATE.md`
- `checklists/MEMORY_QUALITY_GATE.md`

