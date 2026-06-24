# Hibob Internal API Spec

Status: Draft v0.1

## 1. API principles

- API is owned by Hibob Core.
- UI and tools call Core, not DB directly.
- Responses include IDs for traceability.
- Risky actions use approval flow.

## 2. Auth

v0.1 local mode:

- single user local token or no auth behind localhost.

Future:

- JWT/session,
- API keys for tools,
- scoped tokens,
- mTLS or local socket for sensitive adapters.

## 3. Conversation API

### POST `/v1/chat`

Request:

```json
{
  "conversation_id": "optional-uuid",
  "message": "Bob text",
  "mode": "chat|blueprint|debug|coding",
  "privacy_tier": "internal",
  "model_preference": "auto|local|cloud",
  "attachments": [
    {"type": "image|audio", "media_type": "image/png", "data": "<base64>", "uri": "optional-path"}
  ]
}
```

`attachments` (Phase 3.7) carries image/audio input. Audio is transcribed locally (STT) into the
text path; images become multimodal blocks. Attachments inherit the request `privacy_tier`, so
private/secret media never routes to a cloud model; raw media is not persisted.

Response:

```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "response": "...",
  "trace_id": "...",
  "used_memory_ids": [],
  "used_document_chunk_ids": [],
  "tool_run_ids": [],
  "artifacts": []
}
```

Request also accepts `respond_voice: bool` (Phase 9, ADR 0015): when true, the reply is synthesized
to a local audio artifact (push-to-talk voice out). `artifacts` carries generated audio/image refs;
generated artifacts are draft-only (never auto-published) and inherit the request `privacy_tier`.

### GET `/v1/conversations/{id}`

Returns conversation metadata and messages.

## 4. Memory API

### POST `/v1/memory/candidates`

Create memory candidates from conversation/session.

### GET `/v1/memory/search`

Query params:

- `q`
- `scope`
- `memory_type`
- `status`

### POST `/v1/memory/{id}/approve`

Approve memory candidate.

### POST `/v1/memory/{id}/reject`

Reject candidate.

### POST `/v1/memory/{id}/supersede`

Mark memory superseded by another.

## 4a. Memory graph & calibration API (ADR 0006, ADR 0007)

### POST `/v1/memory/edges`

Create a `memory_edges` relation (`supersedes|contradicts|depends_on|supports|derived_from`) between two memory IDs.

### GET `/v1/memory/{id}/edges`

List edges touching a memory, optionally traversed N hops (used for multi-hop graph questions, doc 04 §9a).

### POST `/v1/memory/{id}/feedback`

Record a `memory_usage_feedback` event (`used|corrected|accepted|ignored`) for a retrieved memory; feeds the Bayesian confidence update (doc 04 §7a). Never moves `status` directly - only `confidence`.

## 5. Knowledge API

### POST `/v1/documents/register`

Register document source.

### POST `/v1/documents/{id}/ingest`

Start ingestion job.

### GET `/v1/documents/search`

Search knowledge chunks.

### GET `/v1/ingestion-jobs/{id}`

Check ingestion status.

## 6. Tool API

### GET `/v1/tools`

List tools and risk levels.

### POST `/v1/tools/{name}/request`

Request a tool run.

Request:

```json
{
  "input": {},
  "reason": "why needed",
  "conversation_id": "uuid"
}
```

Response:

```json
{
  "tool_run_id": "uuid",
  "status": "approved|pending_approval|denied|running",
  "approval_request_id": "uuid-or-null",
  "risk_level": "medium",
  "trust_score": 0.0,
  "sandbox_run_id": "uuid-or-null"
}
```

## 6a. Policy & sandbox API (ADR 0005, ADR 0011)

### GET `/v1/policy/rules`

List active `policy_rules` and their version.

### GET `/v1/tools/{name}/trust-score`

Return current `tool_trust_scores` for a tool, scoped by context, including the risk ceiling it can never cross.

### GET `/v1/sandbox/runs/{id}`

Return container lifecycle metadata (`sandbox_runs`: started/destroyed timestamps, network/write exceptions used, if any) for a tool_run.

## 6b. Cost & budget API (ADR 0012)

### GET `/v1/cost/ledger`

Query `cost_ledger` entries, filterable by day/session/model.

### GET `/v1/cost/ceilings`

List `budget_ceilings` and current burn against each.

### POST `/v1/cost/ceilings`

Set/update a budget ceiling (high-risk admin action, not exposed to casual UI flows).

## 7. Approval API

### GET `/v1/approvals/pending`

List pending approvals.

### POST `/v1/approvals/{id}/approve`

Approve.

### POST `/v1/approvals/{id}/reject`

Reject.

## 8. Evaluation API

### POST `/v1/evals/run`

Run eval suite.

```json
{
  "suite": "memory_core_eval",
  "target_version": "local"
}
```

### GET `/v1/evals/runs/{id}`

Fetch result.

## 8a. Replay & red-team API (ADR 0008, ADR 0009)

### POST `/v1/replay/batches`

Start a Replay Harness batch: replays a set of historical `model_runs` against a candidate model in dry-run mode.

```json
{
  "model_run_ids": ["uuid"],
  "candidate_model": "provider/model-id"
}
```

### GET `/v1/replay/batches/{id}`

Fetch diff results against `eval_results` and the batch `decision` (`adopt|reject|inconclusive`).

### POST `/v1/redteam/run`

Trigger an adversarial red-team cycle against the sandboxed instance for one or more attack types (`injected_document|permission_persuasion|persona_social_engineering`).

### GET `/v1/redteam/attempts`

List `redteam_attempts`, filterable by `outcome`; successful, unconverted attempts are surfaced first (doc 09 §12).

## 9. Observability API

### GET `/v1/traces/{id}`

Return trace metadata or Phoenix link.

### GET `/v1/reflections`

List `reflections` produced by the scheduled reflection job (ADR 0010) - read-only output, Bob reviews and turns relevant ones into memory candidates through the existing approval pipeline, never auto-applied.

## 10. Blueprint API future

### POST `/v1/blueprint/propose-update`

Hibob proposes doc update after session.

### POST `/v1/blueprint/accept-update`

Bob accepts proposed update.

## 11. API anti-patterns

Do not:

- expose direct DB writes to UI,
- make tools bypass approval API,
- return secrets in debug endpoints,
- allow arbitrary shell command endpoint,
- merge memory approve and memory create without review,
- expose `/v1/memory/{id}/feedback` or any path that lets a caller set `confidence`/`status` directly instead of going through the calibration update (ADR 0007),
- expose `/v1/cost/ceilings` POST to casual UI flows without the same approval rigor as other high-risk admin actions (ADR 0012),
- let `/v1/reflections` output write memory or trigger a tool call directly - it is read-only by contract (ADR 0010).
