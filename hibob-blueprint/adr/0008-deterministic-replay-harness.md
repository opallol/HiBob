# ADR 0008 - Deterministic Replay Harness

## Status
Accepted for blueprint v0.1

## Context
Doc 12 §9 describes a manual model-migration checklist (run baseline evals, run candidate evals, compare, inspect traces, approve, record ADR), but nothing guarantees the comparison uses identical historical context, and there is no mechanized way to prove a candidate model is a net improvement before adoption. Meanwhile `messages`, `model_runs`, `agent_steps`, and `trace_links` already capture nearly everything needed to reconstruct a past run.

## Decision
Persist the fully assembled prompt/context per `model_run` (system persona, retrieved memory/document references, tool policy, user message — not just the output hash). Build a Replay Harness that takes a past `agent_run`/`model_run`, re-executes the identical assembled input against a candidate model/provider through the Model Router's dry-run mode, and diffs the outcome against the same eval metrics used in `eval_results` (persona, memory, RAG faithfulness, tool-policy compliance). Any model/provider migration ADR must cite a replay batch result as evidence.

## Consequences
Positive: model swaps become a measured, repeatable procedure instead of a subjective judgment call; every replay failure becomes a regression case for free, directly feeding the eval suites in doc 09.
Negative: requires storing fully assembled prompts (more storage, and these must go through the same secret-redaction rules as traces per doc 08 §10); every model adapter must support a dry-run/no-side-effect mode.

## Alternatives considered
- Manual benchmark review only (status quo): rejected, doesn't satisfy "no model upgrade accepted solely because benchmark hype says so" (doc 12 §9).
- Rely solely on public third-party benchmarks: rejected, explicitly against the anti-hype rule (doc 12 §12).
