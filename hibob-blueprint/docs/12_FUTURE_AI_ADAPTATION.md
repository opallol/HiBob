# Future AI Adaptation Strategy

Status: Draft matang v0.1 - catatan: kapabilitas `vision`/`audio` (§2) sudah mulai dipakai sebagai
input understanding sejak Phase 3.7 (lihat `../backend/hibob_core/multimodal/` + `11_ROADMAP.md`).

## 1. Purpose

AI capabilities are unstable and fast-moving. Hibob must be designed so future model, protocol, and tooling improvements can be adopted without rewriting the system.

## 2. Assumption

The best model today will not be the best model tomorrow. Therefore Hibob should preserve:

- memory,
- tool contracts,
- evaluation data,
- traces,
- documents,
- policies,
- adapter boundaries.

## 3. Model abstraction

All model usage goes through `ModelAdapter`.

Required capabilities:

```text
generate
stream
embed
rerank optional
vision optional
audio optional
tool_calling optional
structured_output optional
agent_run optional
```

Each provider adapter declares capabilities.

Example:

```json
{
  "provider": "ollama",
  "models": ["qwen", "gpt-oss", "deepseek"],
  "supports_streaming": true,
  "supports_tool_calling": "model-dependent",
  "privacy_mode": "local"
}
```

## 4. Capability routing

Route by task:

| Task | Preferred route |
|---|---|
| Private summarization | local model |
| Light classification | local model |
| Complex reasoning | cloud frontier |
| Coding architecture | cloud frontier or best coding model |
| Embeddings | selected embedding model, versioned |
| Evaluation judge | strong judge model, possibly cloud |
| Sensitive memory | local unless approved |

This table is the static eligibility floor, not the final word. Since ADR 0012, once enough `model_runs`/`eval_results` history exists per task type, the router may bias its choice among the candidates this table already allows using a bounded epsilon-greedy bandit (`router_policy_feedback`) - it never expands eligibility beyond this table, and privacy tier/risk constraints always override the bandit's preference. A budget ceiling (`budget_ceilings`/`cost_ledger`) also gates every cloud route: crossing it pauses cloud calls and raises an approval request regardless of which route the table/bandit picked.

## 5. Embedding migration

Embedding models will change. Hibob must support:

- multiple vector collections,
- embedding version metadata,
- reindex jobs,
- A/B retrieval evaluation,
- rollback to old collection.

Do not overwrite old embeddings blindly.

## 6. Tool protocol future-proofing

MCP may evolve. Hibob should:

- keep internal tool schema independent,
- map internal tools to MCP/OpenAPI/SDK adapters,
- store tool version,
- validate tool descriptions,
- allow disabling tools quickly.

## 7. UI future-proofing

Open WebUI may be replaced by custom UI later. Therefore:

- UI should call Hibob Core API.
- UI should not own canonical memory.
- UI should not own global tool policy.
- UI can be swapped.

## 8. Agent runtime future-proofing

Hibob may later use:

- OpenAI Agents SDK,
- LangGraph,
- Hermes Agent,
- custom orchestrator,
- future agent runtime.

Keep orchestration interface separate from product logic:

```text
AgentRuntime.run(task, context, tools, policy) -> AgentResult
```

## 9. Evaluation as upgrade shield

Before adopting a new model/tool:

1. Run baseline evals.
2. Run candidate evals.
3. Compare memory/RAG/tool/persona metrics.
4. Inspect Phoenix traces.
5. Approve migration if net benefit.
6. Record ADR.

No model upgrade should be accepted solely because benchmark hype says it is better.

Since ADR 0008, steps 1-4 are no longer a manual checklist - they are a pipeline. The Replay Harness takes historical `model_runs` (real prompts, real context, already assembled), re-executes them in dry-run mode against the candidate model, and diffs the result against existing `eval_results`. "A new frontier model appears -> replay N historical runs -> compare persona/RAG/tool-compliance metrics -> accept if net positive -> record ADR" is now an actual procedure with a `replay_runs.decision` field (`adopt`/`reject`/`inconclusive`), not a hope. Any model-migration ADR must cite a replay batch result.

## 10. Future capabilities to watch

- better long-context models,
- durable agent state,
- standardized tool permissions,
- local multimodal models,
- better browser/computer-use safety,
- on-device embeddings,
- native memory in model providers,
- agent evaluation benchmarks,
- verifiable tool execution,
- personal data vaults,
- local secure enclaves.

Two items that used to be on this watch list are no longer speculative: agent self-red-teaming and learned routing are now in the blueprint itself (ADR 0009, ADR 0012) rather than something to watch for externally.

## 11. Adaptation decision framework

When a new AI technology appears, ask:

1. Does it improve Hibob's core mission?
2. Does it preserve Bob's data control?
3. Can it be integrated via adapter?
4. Can it be evaluated against current baseline?
5. Does it reduce or increase tool risk?
6. Does it create lock-in?
7. Does it duplicate existing capability?
8. Can it be rolled back?

## 12. Anti-hype rule

New AI tech enters Hibob only if it improves at least one of:

- memory quality,
- reasoning quality,
- tool safety,
- development speed,
- local privacy,
- evaluation reliability,
- user experience.

If it only makes Hibob look cool, delay it.

## 13. Future-proof artifacts

Keep these stable and versioned:

- PRD,
- architecture diagrams,
- data schema,
- memory schema,
- tool registry,
- eval datasets,
- prompt versions,
- ADRs,
- model performance reports.

## 14. Long-term North Star

Hibob should be able to swap its brain while preserving its identity.

```text
Model changes, Hibob remains.
UI changes, Hibob remains.
Tools change, Hibob remains.
Memory, policy, and relationship persist.
```

The Replay Harness (ADR 0008) is this North Star turned into a runnable check: "model changes, Hibob remains" is no longer just an aspiration, it is the thing `replay_migration_eval` verifies before any migration is accepted.
