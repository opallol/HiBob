# Hibob Repository Structure

Status: Draft v0.1

## 1. Target monorepo

```text
HiBob/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docs/
│   ├── README.md
│   ├── 00_EXECUTIVE_BLUEPRINT.md
│   ├── 01_PRD.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_ERD_DATA_MODEL.md
│   ├── 04_MEMORY_SYSTEM.md
│   ├── 05_AGENT_AND_TOOL_POLICY.md
│   ├── 06_RAG_INGESTION_PIPELINE.md
│   ├── 07_LOCAL_FIRST_STACK.md
│   ├── 08_SECURITY_PRIVACY_GOVERNANCE.md
│   ├── 09_OBSERVABILITY_EVALUATION.md
│   ├── 10_DEVELOPMENT_WORKFLOW.md
│   ├── 11_ROADMAP.md
│   ├── 12_FUTURE_AI_ADAPTATION.md
│   ├── 13_API_SPEC.md
│   ├── 14_REPO_STRUCTURE.md
│   ├── 15_OPERATING_MANUAL.md
│   ├── 16_GLOSSARY.md
│   ├── 99_REFERENCES.md
│   ├── diagrams/
│   └── checklists/
├── adr/
├── backend/
│   ├── hibob_core/
│   │   ├── api/
│   │   ├── identity/
│   │   ├── memory/
│   │   ├── knowledge/
│   │   ├── models/
│   │   ├── agents/
│   │   ├── tools/
│   │   ├── policy/
│   │   ├── sandbox/
│   │   ├── reflection/
│   │   ├── evals/
│   │   ├── audit/
│   │   └── config.py
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── README.md
│   └── app/
├── evals/
│   ├── memory/
│   ├── rag/
│   ├── persona/
│   ├── tool_policy/
│   └── regression/
├── database/
│   ├── schema.sql
│   └── migrations/
├── tools/
│   ├── mcp/
│   ├── activepieces/
│   └── scripts/
└── infra/
    ├── docker/
    └── compose/
```

## 1.1 Pre-existing siblings at workspace root

Before this monorepo exists, four siblings already live at the workspace root and hold real decisions, not placeholders: `docs/` (ground-truth - machine spec, credentials, raw tool verdict), `ai-stack/` (running infra - Ollama/Qdrant/Postgres/Crawl4AI/Activepieces compose), `hermes-agent/` (third-party reference implementation, see `07_LOCAL_FIRST_STACK.md` §5.13), and this `hibob-blueprint/` itself. Migration notes:

- **Name collision**: top-level `docs/` (credentials, machine spec) and this `hibob-blueprint/docs/` (design docs) cannot both be `docs/` in the final repo. Rename the top-level one (e.g. `ops/` or `machine/`) before merge - it must never share a name with the design-doc folder that is meant to be readable/shareable.
- `ai-stack/docker-compose.yml` is the seed for the target `docker-compose.yml` + `infra/compose/` - extend it in place when Phase 1 starts rather than rewriting from scratch.
- `ai-stack/ingestion/` (currently a stub) folds into `backend/hibob_core/knowledge/` once Phase 3 starts - do not grow it as a standalone service before Phase 1-2 land.
- `hermes-agent/` stays outside the Hibob monorepo as a read-only reference clone - never vendored or imported as a runtime dependency (ADR 0001, ADR 0013).

## 2. Backend module responsibilities

### `identity/`

- persona rules,
- relationship modes,
- prompt fragments.

### `memory/`

- memory schema,
- candidate extraction,
- retrieval,
- conflict detection,
- approval.

### `knowledge/`

- ingestion jobs,
- parsers,
- chunking,
- embeddings,
- retrieval.

### `models/`

- model adapters,
- local/cloud provider routing,
- capability registry.

### `agents/`

- orchestration,
- agent roles,
- state machine,
- plan/act/observe loop.

### `tools/`

- tool registry,
- tool gateway,
- permission checks,
- adapters.

### `policy/` (ADR 0005)

- `policy_rules` evaluation engine,
- `tool_trust_scores` escalation/reset logic,
- `content_provenance_flags` tagging and injection classifier.

### `sandbox/` (ADR 0011)

- ephemeral container lifecycle per tool_run,
- network/filesystem exception allowlist,
- `sandbox_runs` bookkeeping.

### `vault/` (ADR 0014)

- `credential_vault` encrypted-at-rest storage adapter (OS keystore/DPAPI or external key file, key never stored beside the ciphertext),
- `credential_ref` resolution at tool-run time only, inside `sandbox/`,
- `credential_uses` audit bookkeeping - records that a credential was used and for what, never the decrypted value.

### `reflection/` (ADR 0010)

- scheduled read-only reflection job,
- memory/graph/RAG scan for conflicts, untested assumptions, stale sources,
- writes only to `reflections`, never to durable memory or tools.

### `evals/`

- eval runner integration,
- result storage,
- quality gates,
- Replay Harness dry-run execution and diffing (ADR 0008),
- adversarial red-team attack generation and conversion to regression cases (ADR 0009).

### `audit/`

- audit log service,
- trace links,
- approval records.

## 3. Documentation rules

- Any change to memory behavior updates `04_MEMORY_SYSTEM.md`.
- Any new tool updates `05_AGENT_AND_TOOL_POLICY.md`.
- Any schema change updates `03_ERD_DATA_MODEL.md` and migrations.
- Any model routing change updates `12_FUTURE_AI_ADAPTATION.md`.
- Any policy/trust/sandbox change updates `05_AGENT_AND_TOOL_POLICY.md` and `08_SECURITY_PRIVACY_GOVERNANCE.md`.
- Any important trade-off adds ADR.

## 4. ADR structure

```text
adr/
  0001-core-and-adapters.md
  0002-qdrant-for-vector-store.md
  0003-local-first-hybrid-model-routing.md
  0004-tool-gateway-before-autonomy.md
  0005-policy-as-code-tool-gateway.md
  0006-temporal-knowledge-graph-memory.md
  0007-self-calibrating-memory-confidence.md
  0008-deterministic-replay-harness.md
  0009-adversarial-self-redteam-and-eval-judge-integrity.md
  0010-reflective-sibling-proactive-loop.md
  0011-ephemeral-sandbox-tool-execution.md
  0012-learned-router-and-cost-circuit-breaker.md
  0013-self-building-loop-safety-mechanism.md
  0014-operational-credential-vault.md
  0015-multimodal-output-and-voice-safety.md
```

ADR template:

```markdown
# ADR XXXX - Title

## Status
Accepted/Proposed/Superseded

## Context

## Decision

## Consequences

## Alternatives considered
```

## 5. What not to add early

Avoid early folders for:

- microservices,
- mobile,
- kubernetes,
- avatar,
- enterprise admin,
- billing.

Add when roadmap reaches that phase.
