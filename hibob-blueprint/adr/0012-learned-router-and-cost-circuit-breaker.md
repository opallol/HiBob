# ADR 0012 - Learned Model Router and Cost Circuit Breaker

## Status
Accepted for blueprint v0.1

## Context
The Model Router's task-to-model routing table (doc 12 §4) is static, while `model_runs` already records cost estimate, latency, and status per call — a feedback signal that currently goes unused. Separately, there is no budget ceiling anywhere in the system: an agent loop stuck in a retry cycle against a cloud frontier model could consume real money before anyone notices, and the risk table in doc 01 §11 does not list this risk at all.

## Decision
1. **Cost circuit breaker.** Every `model_run` debits its `cost_estimate` against a `budget_ceilings` ledger scoped per day and per session. Crossing the ceiling immediately pauses further cloud model calls and raises an `approval_requests` entry before any more cloud spend is allowed; local/Ollama calls are unaffected since they carry no cloud cost.
2. **Learned routing bias.** Once sufficient `model_runs` and `eval_results` history exists per `task_type`, the router may bias its choice among the candidates already allowed by the static table (doc 12 §4) using a bounded exploration strategy (epsilon-greedy bandit) — it never expands which models are eligible for a task; privacy tier and risk constraints always override the bandit's preference.

## Consequences
Positive: protects against silent cost overruns from the very first cloud call; over time, traffic shifts toward whichever model actually performs best for a given task type as measured by eval, not by benchmark hype — directly satisfying the anti-hype rule (doc 12 §12).
Negative: the bandit adds a layer of indirection in routing decisions that must remain explainable (logged with the reason for selection) and must stay overridable by Bob at any time.

## Alternatives considered
- No budget guard (status quo): rejected, identified as an unaddressed real risk in review (finding 2.8).
- Fully static routing table forever, no learning: rejected, wastes cost/eval data Hibob already collects for free.
- Let the bandit choose freely across all known models regardless of privacy/risk tier: rejected, would violate local-first/privacy-tier non-negotiables.
