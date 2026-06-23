# Hibob Glossary

## Hibob Core

Central backend layer that owns identity, memory, tool policy, orchestration, audit, and evaluation contracts.

## Saudara digital

Relationship mode where Hibob speaks as Bob's close digital sibling: natural, critical, constructive, and personal.

## Memory candidate

Potential long-term memory extracted from conversation but not yet approved as durable truth.

## Canonical memory

Approved memory stored in relational DB as source of truth.

## Vector memory

Embedding representation of memory used for semantic retrieval.

## Knowledge base

Documents/web/repo contents indexed for retrieval; distinct from personal memory.

## RAG

Retrieval-Augmented Generation: retrieving relevant source chunks before generating an answer.

## Tool Gateway

Hibob component that validates, authorizes, executes, logs, and traces tool actions.

## MCP

Model Context Protocol, an open standard for connecting AI apps to external tools/data/workflows.

## Local-first

Architecture where core data and important computation can run locally, with cloud used only when beneficial and allowed.

## Model-agnostic

Hibob is not hardwired to one model/provider; model use is routed through adapters.

## Phoenix

AI observability/evaluation platform used for tracing and debugging model, retrieval, and tool behavior.

## DeepEval

LLM evaluation framework used for automated tests and regression suites.

## ADR

Architecture Decision Record: short document recording a significant decision, context, alternatives, and consequences.

## Memory edge

A typed, bi-temporal relation (`supersedes`, `contradicts`, `depends_on`, `supports`, `derived_from`) between two memories, stored in `memory_edges` (ADR 0006). The basis of Hibob's memory graph.

## Memory graph

The traversable network formed by memory edges, queried via recursive CTE rather than a separate graph database in v0.1 (ADR 0006).

## Confidence calibration

The process of adjusting a memory's confidence score from real usage signals (`memory_usage_feedback`: used/corrected/accepted/ignored) via a Bayesian update, capped to never auto-promote memory status (ADR 0007).

## Policy Engine

The deterministic, rule-based component (`policy_rules`) that decides allow/ask/deny for every tool call - never the model judging its own permission (ADR 0005).

## Trust score

A per-(tool, context) score (`tool_trust_scores`) that can move a tool from `ask` to `auto` based on clean run history, bounded by the tool's risk ceiling and never applied to critical-risk actions (ADR 0005).

## Content provenance flag

A tag (`content_provenance_flags`) marking where a piece of content came from (system/user/policy/retrieved_data/tool_output), used with structural delimiters and an injection classifier to defend against prompt injection (ADR 0005).

## Replay Harness

A mechanism that re-executes historical `model_runs` in dry-run mode against a candidate model and diffs the result against existing eval results, used as evidence before any model migration (ADR 0008).

## Adversarial self-red-team loop

Scheduled attacks (injected document, permission persuasion, persona social engineering) run against a sandboxed instance of Hibob; successful attempts auto-convert into permanent regression eval cases (ADR 0009).

## Eval judge integrity

The practice of pinning the model/version used to judge evals and tracking its agreement score against a golden dataset, so judge drift doesn't go unnoticed (ADR 0009).

## Reflection job / reflective sibling

A scheduled, local-model, read-only job that scans memory, the memory graph, and RAG sources for unresolved conflicts, untested assumptions, or stale data, writing only to `reflections` and never to durable memory or tools directly (ADR 0010).

## Ephemeral sandbox / Sandbox Runtime

A per-run, throwaway container used to execute high-risk tool types (shell, browser, third-party MCP), defaulting to no network access and a read-only filesystem, destroyed immediately after the run (ADR 0011). Independent of, and in addition to, the Policy Engine's allow/ask/deny decision.

## Cost ledger / budget ceiling

`cost_ledger` records spend per cloud model call; `budget_ceilings` defines the hard limit that, once crossed, pauses further cloud calls and raises an approval request (ADR 0012).

## Learned router bias

A bounded epsilon-greedy bandit (`router_policy_feedback`) that biases model selection among candidates the static routing table already allows, based on historical cost/latency/eval performance. It never expands which models are eligible (ADR 0012).

## Self-build merge gate

The set of checks (Policy Engine evaluation, file-based risk classification, no trust-tier escalation for security/policy/schema files, tests + DeepEval + docs + Bob's approval, Replay Harness for prompt/retrieval/policy changes) that every Hibob-authored patch or doc proposal must pass before merge (ADR 0013).
