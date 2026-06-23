# ADR 0007 - Self-Calibrating Memory Confidence

## Status
Accepted for blueprint v0.1

## Context
`memories.confidence` is set once at extraction time and never updated. A memory that turns out to be consistently useful and a memory that turns out to be wrong both keep their original confidence forever unless Bob manually intervenes. This contradicts the stated goal that "Hibob with bad memory becomes a confident but wrong chatbot" (doc 04 §1) — without feedback, confidence cannot reflect reality.

## Decision
Record a `memory_usage_feedback` event every time a memory is retrieved and used in an answer (`used_memory_ids` from `/v1/chat`), and whenever Bob gives explicit correction or acceptance signal (doc 09 §10 human feedback loop). Confidence is updated with a bounded Bayesian-style rule — a Beta(α, β) posterior mean per memory — where a "used and not corrected" event nudges α up slightly and an explicit correction nudges β up sharply. Confidence is capped so it can never auto-promote a memory's `status` (candidate -> approved still requires Bob's approval per doc 04 §6); calibration only affects retrieval ranking and triggers a review-queue entry when confidence drops below a threshold.

## Consequences
Positive: memory quality becomes measurable and self-correcting; stale or wrong memory naturally sinks in retrieval ranking and surfaces for review instead of waiting for a manual audit pass.
Negative: needs enough usage volume per memory to be meaningful; early feedback loops could reinforce initial bias if left unbounded — mitigated by hard caps and the existing weekly memory review ritual (doc 04 §11).

## Alternatives considered
- Leave confidence static forever (status quo): rejected per review finding 2.5.
- Let confidence automatically promote memory status without Bob's approval: rejected, violates the non-negotiable that durable memory requires approval (Executive Blueprint §3.5, doc 04 §6).
