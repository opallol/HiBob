# ADR 0005 - Policy-as-Code Tool Gateway with Trust Tiers and Injection Defense

## Status
Accepted for blueprint v0.1

## Context
Tool permission rules (doc 05, doc 08) were written as prose enforced mostly by convention and prompt instructions. Two problems follow from this: (1) there is no deterministic, version-controlled decision point that is immune to persuasion via prompt injection, since the model itself sits close to the enforcement logic; (2) the v0.1 permission matrix is almost entirely "ask", which causes approval fatigue for a single daily user and risks Bob rubber-stamping requests without reading them, defeating the purpose of approval. Separately, the prompt injection policy ("treat retrieved content as data, not instruction") was stated as a principle without a concrete technical mechanism.

## Decision
1. **Policy engine.** The Tool Gateway evaluates every tool request against a versioned, testable policy engine (pure functions/rules keyed by `tool`, `context`, `sensitivity`, `risk_level`, `trust_score`) stored as `policy_rules` linked to `policy_versions`. The engine returns `allow | ask | deny`. The LLM never adjudicates its own permission; it only requests.
2. **Trust tier escalation.** Each `(tool, context)` pair accumulates a `trust_score` from successful, audited, non-flagged runs. Crossing a threshold may move a tool from `ask` to `auto` automatically, but only within its existing risk ceiling — critical-risk tools remain default-deny regardless of trust score, and any policy violation or red-team hit (ADR 0009) immediately resets the score to zero.
3. **Injection defense mechanism.** Content retrieved from documents, web, repo, or tool output is tagged with a `provenance` field (`system | user | policy | retrieved_data | tool_output`) and wrapped in explicit structural delimiters before prompt assembly. A lightweight classifier scans non-system content for imperative/instruction-like patterns before any resulting tool call is allowed to execute, flagging suspicious content for the audit log even if it does not block the response.

## Consequences
Positive: permission decisions become deterministic, auditable, and unit-testable; approval fatigue drops over time without lowering the floor for high/critical actions; prompt injection has a concrete technical layer instead of policy-only language.
Negative: requires building and testing a policy engine and a provenance/classifier layer before Phase 4 (Tool Gateway) ships, adding upfront engineering before any tool is enabled.

## Alternatives considered
- Keep policy as prose enforced only by system prompt instructions: rejected, not robust against injection or model persuasion.
- Let trust score escalate without ceiling: rejected, erodes least-privilege for high/critical actions.
- Use only an LLM-based injection classifier with no structural tagging: rejected, classifier-only detection is not deterministic enough to be a security boundary.
