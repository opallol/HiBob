# HiBob

**HiBob** adalah fondasi AI saudara digital, second brain, agent operator, dan AI dev partner milik Bob.

Status repo saat ini: **Hibob Core Phase 2 - Memory Core mulai masuk**.

## Posisi arsitektur

HiBob bukan sekadar wrapper ChatGPT, Open WebUI, AnythingLLM, Hermes Agent, Cline, Aider, atau Ollama. Semua itu diperlakukan sebagai resource/adaptor. Inti sistem adalah **Hibob Core**: lapisan yang memegang identity, memory, context, model routing, permission, observability, evaluasi, dan evolusi sistem.

## Struktur final repo

Target struktur final repo:

```text
HiBob/
├── README.md
├── adr/
├── backend/
├── database/
├── docs/
├── evals/
├── frontend/
├── infra/
└── tools/
```

Catatan migrasi: paket awal masih tersimpan di `hibob-blueprint/`. Folder itu sedang dipromosikan ke root repo final agar struktur repository sesuai `docs/14_REPO_STRUCTURE.md`.

## Backend

Backend berada di `backend/` setelah migrasi final. Untuk sementara, bila belum semua file root terlihat karena cache/sync GitHub, sumber kanoniknya masih bisa dibaca di:

```text
hibob-blueprint/backend/
```

Fokus backend saat ini:

- FastAPI modular monolith.
- Chat endpoint dan conversation persistence.
- Local/cloud model routing.
- Privacy guard agar data `private`/`secret` tidak route ke cloud.
- Cost circuit breaker untuk cloud model.
- Phase 2 Memory Core: extraction, retrieval, vector store, memory API, dan tests.

## Quick start backend

```bash
cd backend
uv venv
uv pip install -e ".[dev]"
cp .env.example .env
uv run pytest
uv run uvicorn hibob_core.api.app:app --reload --port 8088
```

Jika backend belum termigrasi ke root pada local clone, gunakan:

```bash
cd hibob-blueprint/backend
```

## Dokumen utama

Mulai baca dari:

1. `docs/00_EXECUTIVE_BLUEPRINT.md`
2. `docs/01_PRD.md`
3. `docs/02_SYSTEM_ARCHITECTURE.md`
4. `docs/03_ERD_DATA_MODEL.md`
5. `docs/04_MEMORY_SYSTEM.md`
6. `docs/05_AGENT_AND_TOOL_POLICY.md`
7. `docs/11_ROADMAP.md`
8. `docs/14_REPO_STRUCTURE.md`

Sebelum migrasi root penuh selesai, dokumen tersebut masih ada di `hibob-blueprint/docs/`.

## Prinsip non-negotiable

- Hibob Core memegang identity, memory, policy, dan canonical database.
- Tool/agent seperti Hermes hanya boleh masuk lewat Tool Gateway + Policy Engine + Sandbox.
- Core tidak boleh larut menjadi tool milik agent executor.
- Memory harus approval-aware, confidence-aware, dan bisa diaudit.
- Cloud call wajib melewati privacy guard dan cost circuit breaker.
