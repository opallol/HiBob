 # Hibob Core — Backend (Phase 1 + 2 + 2.5 + 3 + 3.5 + 3.7 + 4)  

The FastAPI modular monolith that owns Hibob's identity, conversation, model routing,
cost governance, memory, knowledge base, reflection, multimodal input, and the tool gateway.
Implemented so far against `docs/11_ROADMAP.md`:

- **Phase 1 — Core Minimal** ✅ : Bob can chat, messages persist, local/cloud models are
  selectable, and **no cloud call passes without a cost-ceiling check** (ADR 0012).
- **Phase 2 — Memory Core** ✅ : candidate extraction, human-only approval, hybrid retrieval
  (Qdrant + SQL re-score) wired into chat, session summary, minimal conflict detection.
- **Phase 2.5 — Memory Graph & Calibration** ✅ : typed `memory_edges` (ADR 0006) with
  recursive-CTE traversal, and self-calibrating confidence via `memory_usage_feedback`
  (ADR 0007) — calibration moves `confidence` only, **never** `status`.
- **Phase 3 — Knowledge Base / RAG** ✅ : document/web ingestion → chunking → local embedding →
  Qdrant, and source-referenced retrieval wired into chat (doc 06). v0.1 is **text extraction
  only** (Markdown/TXT native; PDF/DOCX via Unstructured, web via Crawl4AI as optional adapters).
- **Phase 3.5 — Reflective Sibling** ✅ : a strictly **read-only** scheduled-capable job (ADR 0010)
  that scans the memory graph + RAG sources for unresolved conflicts, fragile `depends_on`
  assumptions, and stale sources, writing findings to `reflections` for Bob to review. It **never**
  writes durable memory or calls a tool (doc 13 §11).
- **Phase 3.7 — Multimodal Input** ✅ : `/v1/chat` accepts image/audio `attachments`. Audio is
  transcribed locally (STT) into the text path; images become multimodal blocks the adapters
  translate per provider. Privacy still routes by tier (private/secret images stay local); raw
  media is never persisted (v0.1). Output generation/voice is Phase 9.
- **Phase 4 — Tool Gateway + Policy Engine** ✅ : a **deterministic** Policy Engine (ADR 0005)
  returns `allow|ask|deny` (the model never adjudicates); trust accrues on clean runs and may
  auto-allow medium risk, never high/critical; an injection classifier flags suspicious requests
  and forces `ask`. Ships internal read-only tools (memory/document search, repo read, draft patch).
  **Sandbox runtime (ADR 0011) and Credential Vault (ADR 0014) are deferred seams** — `shell|browser|mcp`
  tools are default-deny until a sandbox exists.

Everything else (sandbox runtime, credential vault, multimodal **output**, Hermes) is intentionally
**not** here yet — see "Module map" for the reserved seams.

## What's implemented

- `POST /v1/chat` — chat with Hibob; accepts optional image/audio `attachments` (Phase 3.7),
  recalls relevant approved memory **and document chunks**, persists the turn, routes a model,
  returns trace IDs + `used_memory_ids` + `used_document_chunk_ids` (doc 13 §3). Used memories get
  a `used` calibration signal (ADR 0007).
- `GET /v1/conversations/{id}` — conversation metadata + messages.
- `POST /v1/documents/register` · `POST /v1/documents/{id}/ingest` · `GET /v1/documents/search` ·
  `GET /v1/ingestion-jobs/{id}` — the Phase 3 knowledge surface (doc 13 §5). Embedding is local,
  so `private`/`secret` documents never leave the machine; retrieval applies privacy containment.
- `GET /v1/reflections` · `POST /v1/reflections/run` · `POST /v1/reflections/{id}/status` — the
  Phase 3.5 reflective-sibling surface (ADR 0010). `run` is the job trigger (a cron/scheduler calls
  it daily/weekly); output is read-only findings, never auto-applied.
- `GET /v1/tools` · `POST /v1/tools/{name}/request` · `GET /v1/tools/{name}/trust-score` ·
  `POST /v1/approvals/{id}/decide` · `GET /v1/policy/rules` — the Phase 4 Tool Gateway (ADR 0005).
  Decisions come from the Policy Engine; high-risk requests become `approval_requests` Bob decides.
- `POST /v1/memory/candidates` · `POST /v1/memory/summarize` · `GET /v1/memory/search` ·
  `GET /v1/memory/{id}` · `POST /v1/memory/{id}/{approve|reject|supersede}` — the Phase 2
  memory lifecycle (doc 13 §4). Approval is human-only; nothing auto-promotes a candidate.
- `POST /v1/memory/edges` · `GET /v1/memory/{id}/edges?depth=N` · `POST /v1/memory/{id}/feedback`
  — the Phase 2.5 graph + calibration surface (doc 13 §4a). `feedback` accepts
  `used|corrected|accepted|ignored` and never takes `confidence`/`status` directly.
- Model router (ADR 0003): `local` → Ollama (ai-stack), `cloud` → Anthropic Claude,
  `auto` → local. `privacy_tier` of `private`/`secret` can **never** route to cloud (doc 08 §4).
  Memory embeddings are always local, so private/secret memory never hits the cloud (doc 04 §6).
- Cost circuit breaker (ADR 0012): every cloud call is gated against a daily USD ceiling;
  a breach returns HTTP 402 and writes an audit row. Local calls are never gated.
- Thin Phoenix tracing (OTLP) so trace IDs land on `model_runs`/`messages` from day one.

## Module map

```
hibob_core/
  api/         FastAPI app + /v1 routes (chat + memory + documents)
  identity/    persona/system-prompt assembly from persona_rules
  models/      ModelAdapter ABC + ollama/anthropic adapters (vision-capable) + static router  <-- model-agnostic seam
  multimodal/  Phase 3.7 input: attachments, vision blocks, local STT (optional faster-whisper)
  agents/      orchestrator: persona -> recall (memory+docs) -> route -> generate -> persist <-- HERMES SEAM
  memory/      extraction, approval service, hybrid retrieval, vector_store,
               summary, graph (ADR 0006), calibration (ADR 0007)
  knowledge/   RAG (Phase 3): parsers, chunking, ingestion, vector_store, retrieval (doc 06)
  reflection/  reflective sibling (Phase 3.5): read-only conflict/assumption/stale scans (ADR 0010)
  tools/       Tool Gateway (Phase 4): registry, builtins, gateway (request->policy->approve->execute)
  policy/      Policy Engine (Phase 4, ADR 0005): deterministic decide() + injection provenance
  cost/        cost circuit breaker (ADR 0012)
  audit/       audit log helper
  db/          asyncpg pool, repositories, migrations/ (0001 P1 .. 0006 P3.5, 0007 P4)
  sandbox/     (planned) Ephemeral sandbox runtime (ADR 0011) — shell/browser/mcp default-deny until then
  telemetry.py OTLP → Phoenix
  config.py    pydantic-settings (HIBOB_* env)
```

## The Hermes seam (forward-compatible, not built yet)

Per the decision recorded in `docs/07_LOCAL_FIRST_STACK.md` §5.13 and ADR 0014, Hermes is a
**read-only reference implementation**, never a runtime dependency. Phase 1 keeps the boundary
clean so Phase 5 can plug it in without touching Core:

- `models/base.py` follows the adapter pattern in `hermes-agent/agent/anthropic_adapter.py`,
  `bedrock_adapter.py`, `gemini_native_adapter.py` (one interface, many providers).
- `agents/orchestrator.py` is the single extension point. Later, an `AgentBackend` ABC (separate
  from `ModelAdapter`) defines `run_agent(...)`; Hermes is registered as one `tool_type='agent'`
  tool in `tools/`, governed by `policy/` (ADR 0005), executed in the ephemeral Sandbox (ADR 0011),
  with secrets from the Credential Vault (ADR 0014). Core never `import`s Hermes.

Other Hermes files worth reading (later, not now): `agent/memory_provider.py` (memory ABC → Phase 2),
`agent/curator.py` (reflective loop → Phase 3.5), `agent/iteration_budget.py` (→ Phase 6).

## Run it (via ai-stack compose)

The canonical Postgres + Core service live in `../../../ai-stack/docker-compose.yml`.

```bash
# from ai-stack/
docker compose up -d hibob-postgres ollama phoenix     # DB schema+seed auto-apply on first init
docker exec hibob-ollama ollama pull qwen3.5:9b        # fits 8GB VRAM (ai-stack/README.md)
docker compose up -d --build hibob-core
curl localhost:8088/healthz
```

### Smoke test

```bash
# local model
curl -s localhost:8088/v1/chat -H 'content-type: application/json' \
  -d '{"message":"halo Hibob, kenalin dirimu","model_preference":"local"}'

# cloud model (needs HIBOB_ANTHROPIC_API_KEY set in ai-stack/.env)
curl -s localhost:8088/v1/chat -H 'content-type: application/json' \
  -d '{"message":"halo","model_preference":"cloud"}'

# privacy guard — must be rejected (400)
curl -s localhost:8088/v1/chat -H 'content-type: application/json' \
  -d '{"message":"rahasia","privacy_tier":"secret","model_preference":"cloud"}'
```

A successful chat creates rows in `conversations`, `messages`, `model_runs` (and `cost_ledger`
for cloud) and a span in Phoenix (`localhost:6006`).

## Local dev (without Docker)

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
cp .env.example .env          # point DSN/Ollama at host ports; set ANTHROPIC key if using cloud
uv run pytest                 # unit tests (no DB/model needed — all faked)
uv run uvicorn hibob_core.api.app:app --reload --port 8088
```

## Tests

`tests/` covers the load-bearing invariants without a live DB or model (all deps faked):
- `test_router_privacy.py` — secret/private never routes to cloud.
- `test_cost_breaker.py` — cloud calls blocked at/over the daily ceiling; fail-closed with no ceiling.
- `test_chat_persistence.py` — both turns persisted; breaker gates cloud only, never local.
- `test_memory_extraction.py` / `test_memory_service.py` — candidate extraction; approval is
  human-only and only candidates can be approved.
- `test_memory_retrieval.py` — privacy containment (no leak up-tier) + conflict suppression.
- `test_memory_graph.py` — typed-edge validation, traversal assembly, auto-`supersedes` edge (ADR 0006).
- `test_memory_calibration.py` — Beta posterior moves confidence, clamped, and never touches `status` (ADR 0007).
- `test_knowledge_chunking.py` — heading-aware markdown split, sizing/overlap, stable hashes (doc 06 §7).
- `test_knowledge_retrieval.py` — document privacy containment + source-referenced results (doc 06 §4/§9).
- `test_knowledge_ingestion.py` — pending→active pipeline, quality gate fails empty docs, job/embedding recorded.
- `test_reflection_service.py` — one finding per scan category, dedup skips open duplicates, status validation (ADR 0010).
- `test_multimodal_attachments.py` / `test_multimodal_vision.py` / `test_multimodal_stt.py` —
  attachment validation, per-provider image-block translation, STT graceful-degrade (Phase 3.7).
- `test_chat_multimodal.py` — audio → transcript folded into the turn; image → multimodal final message.
- `test_policy_engine.py` — allow/ask/deny matrix, trust ceiling (high/critical never auto), sandbox guard, injection forces ask (ADR 0005).
- `test_provenance_classifier.py` — injection patterns flagged; benign text not.
- `test_tool_gateway.py` — low→execute+trust↑, high→pending_approval (no exec), critical→deny, approve→executes.

Run them with `uv run pytest` (see "Local dev" — `uv sync` pulls the deps; the suite needs no DB/model).
The heavy RAG parsers (Unstructured/Crawl4AI) are an optional extra — `uv pip install -e ".[ingest]"` —
and lazy-imported; text/markdown ingestion and the whole test suite work without them. Local STT
(faster-whisper) is likewise an optional extra — `uv pip install -e ".[multimodal]"` — needed only
for audio understanding; image/vision needs no extra dep.

## Applying migrations

The DB volume persists across phases, so `docker-entrypoint-initdb.d` only runs `0001`/`0002`
on first init. Apply later migrations by hand (idempotent — safe to re-run):

```bash
docker exec -i hibob-core-postgres psql -U hibob -d hibob < hibob_core/db/migrations/0003_phase2.sql
docker exec -i hibob-core-postgres psql -U hibob -d hibob < hibob_core/db/migrations/0004_phase2_5.sql
docker exec -i hibob-core-postgres psql -U hibob -d hibob < hibob_core/db/migrations/0005_phase3.sql
docker exec -i hibob-core-postgres psql -U hibob -d hibob < hibob_core/db/migrations/0006_phase3_5.sql
docker exec -i hibob-core-postgres psql -U hibob -d hibob < hibob_core/db/migrations/0007_phase4.sql
```
