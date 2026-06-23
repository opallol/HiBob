# Hibob Observability & Evaluation

Status: Draft matang v0.1 - eval harness implemented (Phase 6 ✅): suite `tool_policy_eval` rule-based
jalan via `../backend/hibob_core/evals/` + endpoint `/v1/evals/*`. Replay (ADR 0008), eval-judge pin
(ADR 0009), learned-router bandit (ADR 0012) = seam murni; LLM-judge/replay-dry-run/bandit-live menyusul.

## 1. Why this matters

AI systems fail in ways normal apps do not. A response can be wrong because of model reasoning, prompt, retrieval, stale memory, tool output, parser failure, permission bug, or user ambiguity. Hibob needs observability and evals from the start.

## 2. Observability stack

- **Phoenix**: traces, model calls, retrieval, tool use, prompt iteration, datasets, experiments.
- **DeepEval**: automated test suite and regression gates.
- **Audit logs**: security/governance record.
- **Application logs**: runtime errors and performance.
- **Replay Harness** (ADR 0008): deterministic re-execution of historical `model_runs` against candidate models, the evidence trail behind any model-migration decision.
- **Adversarial red-team loop** (ADR 0009): scheduled attacks against a sandboxed instance, feeding successful attempts back as permanent regression cases.
- **Cost ledger** (ADR 0012): per-run spend tracked against budget ceilings, same observability discipline applied to money as to correctness.

## 3. Trace requirements

Every important run should store:

- `trace_id`
- `conversation_id`
- `agent_run_id`
- model provider/model
- prompt version
- retrieved memory IDs
- retrieved document chunk IDs
- tool calls
- approval decisions
- latency
- token/cost estimates if available
- errors
- final output hash
- policy decision (allow/ask/deny) and trust score at time of run (ADR 0005)
- content provenance flags / injection classifier score for any retrieved content involved (ADR 0005)
- sandbox_run_id if the call executed inside the ephemeral sandbox (ADR 0011)
- cost ledger entry and remaining budget ceiling for any cloud model call (ADR 0012)

## 4. Evaluation dimensions

### 4.1 Persona consistency

Does Hibob sound like Bob's digital sibling?

Checks:

- not overly formal,
- critical but constructive,
- does not blindly agree,
- keeps context of prior decisions.

### 4.2 Memory quality

Checks:

- relevant memory retrieved,
- stale memory avoided,
- hallucinated memory not used,
- conflict detected,
- durable memory not stored without approval.

### 4.3 RAG quality

Checks:

- faithfulness to source,
- retrieval relevance,
- citation/source correctness,
- refusal when source insufficient,
- stale data warning.

### 4.4 Tool policy compliance

Checks:

- high-risk tool asks approval,
- critical action denied,
- audit log created,
- schema validation works,
- prompt injection from tool output ignored.

### 4.5 Agent task success

Checks:

- plan quality,
- tool choice,
- completion rate,
- number of unnecessary steps,
- recoverability after tool failure.

### 4.6 Memory graph & calibration (ADR 0006, ADR 0007)

Checks:

- multi-hop graph traversal answers correctly (e.g. "what depends on this disputed assumption?"),
- confidence calibration error stays low (a 0.9-confidence memory is right ~90% of the time),
- repeatedly-corrected memory's confidence drops and stops surfacing in top retrieval,
- confidence calibration never silently promotes `status`.

### 4.7 Security resilience (ADR 0009)

Checks:

- red-team attack types (`injected_document`, `permission_persuasion`, `persona_social_engineering`) are blocked,
- any successful attempt is converted into a permanent eval case,
- eval judge agreement score against the golden dataset stays above threshold after any judge model/version change.

### 4.8 Cost & routing efficiency (ADR 0012)

Checks:

- cloud spend never crosses the budget ceiling without pausing and raising approval,
- learned router bias never selects a model outside the static eligibility table for a task,
- routing decisions remain explainable (logged reason for selection).

## 5. Evaluation suites

### `memory_core_eval`

Minimum cases:

- Bob wants discussion before implementation.
- Hibob is not a formal assistant.
- Open WebUI is not core.
- Memory candidate vs approved distinction.
- Conflicting stack decision resolution.

### `rag_blueprint_eval`

Minimum cases:

- Ask PRD scope.
- Ask architecture boundaries.
- Ask ERD source-of-truth design.
- Ask tool policy risk level.
- Ask roadmap v0.1 exclusions.

### `tool_policy_eval`

Minimum cases:

- Search memory auto allowed.
- Write file requires approval.
- Delete file denied.
- Public browser submit denied.
- Private context cloud request requires approval.

### `persona_eval`

Minimum cases:

- Hibob challenges weak idea.
- Hibob admits uncertainty.
- Hibob avoids robotic checklist tone in casual mode.
- Hibob provides rigorous counterargument when needed.

### `memory_graph_calibration_eval` (ADR 0006, ADR 0007)

Minimum cases:

- Multi-hop traversal: "what decisions depend on this now-disputed assumption?"
- Confidence drops after repeated corrections and stops surfacing in top-k retrieval.
- Confidence calibration never auto-promotes memory status.

### `redteam_eval` (ADR 0009)

Minimum cases: grows automatically — every `redteam_attempts` row with `outcome = succeeded` is converted into a permanent case here (`converted_to_eval_case_id`). Starting seed cases cover the three known attack types (`injected_document`, `permission_persuasion`, `persona_social_engineering`).

### `replay_migration_eval` (ADR 0008)

Minimum cases:

- A historical high-stakes `model_run` replays against a candidate model with no behavior regression.
- A known-failure historical run still fails the same way (sanity check that replay is faithful, not just lenient).

## 6. Quality gates

Before merging a change:

- unit tests pass,
- relevant DeepEval suite pass,
- no critical safety regression,
- docs updated if behavior changed,
- ADR added for architecture/policy change.

For self-build proposals specifically (ADR 0013, doc 05 §18), all of the above plus Bob's explicit approval recorded as an `approval_request`; if the change touches prompt/retrieval/policy logic, a Replay Harness batch (ADR 0008) must run against affected eval suites before merge.

Before enabling new tool:

- schema validation test,
- permission test,
- failure-mode test,
- audit-log test,
- injection test.

## 7. Metrics dashboard v0.1

Track:

- memory precision estimate,
- memory approval rate,
- rejected memory rate,
- conflict count,
- retrieval hit rate,
- RAG faithfulness score,
- tool approval compliance,
- denied unsafe action count,
- eval pass rate,
- trace coverage,
- confidence calibration error (ADR 0007),
- graph traversal correctness rate (ADR 0006),
- red-team block rate and count of attempts still unconverted to eval cases (ADR 0009),
- eval judge golden-set agreement score, by judge version (ADR 0009),
- cost burn rate vs budget ceiling, per day/session (ADR 0012),
- router bandit selection distribution per task type (ADR 0012),
- replay batch adopt/reject/inconclusive counts per migration candidate (ADR 0008).

## 8. Eval data management

Eval cases should live in repo:

```text
evals/
  memory/
  rag/
  persona/
  tool_policy/
  regression/
```

Each eval case should include:

- input,
- expected behavior,
- prohibited behavior,
- source docs/memory IDs if needed,
- metric,
- threshold.

## 9. Regression loop

When Hibob fails:

```text
failure -> inspect trace -> identify cause -> patch prompt/retrieval/tool/policy -> add eval -> rerun -> merge if pass
```

Never fix only by “prompt vibes” without adding a regression case.

## 10. Human feedback loop

Bob feedback should be stored as structured feedback:

- helpful/not helpful,
- too formal/too shallow/too risky,
- memory wrong,
- source missing,
- tool action inappropriate,
- should be saved as correction.

When the feedback is about a specific retrieved memory, it is recorded as `memory_usage_feedback` (`used`/`corrected`/`accepted`/`ignored`, ADR 0007) and feeds the confidence calibration update directly — this is the mechanism behind doc 04 §7a, not a separate system.

## 11. Evaluation maturity levels

### Level 0

Manual vibe check only. Not acceptable beyond experiments.

### Level 1

Basic DeepEval cases for persona/memory/RAG.

### Level 2

CI regression gate for core evals.

### Level 3

Phoenix traces feed datasets and experiments.

### Level 4

Self-improvement loop: Hibob proposes evals after failures — realized concretely by the adversarial red-team loop (ADR 0009), where successful attacks against the sandboxed instance auto-convert into permanent `redteam_eval` cases.

### Level 5

Migration-safe self-improvement: model/prompt/policy changes are validated against the Replay Harness (ADR 0008) before adoption, so the self-improvement loop above can also change *which model it runs on* without losing the regression guarantees Level 2-4 built up.

## 12. Anti-patterns

Do not:

- trust demo output as quality proof,
- skip tracing because local-only,
- store traces with secrets,
- only evaluate final answer and ignore retrieval/tool steps,
- change prompts without versioning,
- let model judge all evals without spot-checking,
- trust an eval judge without a pinned model/version and a golden-set agreement score (ADR 0009),
- adopt a model migration without citing a Replay Harness batch result (ADR 0008),
- let a successful red-team attempt go unconverted to a permanent regression case (ADR 0009).
