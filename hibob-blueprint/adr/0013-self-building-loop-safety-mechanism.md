# ADR 0013 - Self-Building Loop Safety Mechanism

## Status
Accepted for blueprint v0.1

## Context
The self-building loop (doc 01 §8.6, doc 10 §11, doc 11 Phase 5) is Hibob's most distinctive ambition — Hibob helps build itself — but was specified only as a sequence of steps (discussion -> blueprint update -> issue -> patch -> tests -> merge) without a concrete gate ensuring Hibob cannot propose or merge an unsafe change to its own rules. Without an explicit mechanism, "Hibob helps build Hibob" risks becoming the one unguarded path into the system, exactly the kind of special case the rest of the blueprint works hard to avoid.

## Decision
Blueprint Guardian and Builder Agent proposals (`propose_blueprint_update`, `draft_patch`, `create_github_issue_draft`) are themselves `tool_run`s evaluated by the Policy Engine (ADR 0005). The policy engine assigns risk level based on which files/areas a proposed change touches: changes to security policy, tool permission, or memory schema files are always classified high risk regardless of diff size, never auto-approved by trust-tier escalation. No patch merges without, in this order: unit tests passing, the relevant DeepEval suite passing, docs updated in the same change, and Bob's explicit approval recorded as an `approval_request`. When a change touches prompt, retrieval, or policy logic, the Replay Harness (ADR 0008) runs against the affected eval suites before merge.

## Consequences
Positive: "Hibob helps build Hibob" stays bounded by the same governance as every other action in the system, instead of being a separate, implicitly-trusted path; security/policy/schema changes get an automatic higher bar with no extra manual step required to remember it.
Negative: self-build iterations are intentionally slower than they could be — speed is deliberately traded for not letting the system modify its own safety rails without the same scrutiny as any other high-risk tool action.

## Alternatives considered
- Rely on Cline/Aider plus human review alone, with no policy-engine classification of the proposal itself: rejected, leaves security/policy/schema files without an automatic higher bar distinct from ordinary code changes.
- Allow auto-merge for self-build patches classified as "small": rejected, directly contradicts the existing anti-pattern "bypass audit for small tasks" (doc 05 §16).
