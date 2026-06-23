# ADR 0010 - Reflective Sibling Proactive Loop

## Status
Accepted for blueprint v0.1

## Context
Hibob's primary identity is "saudara digital" (Executive Blueprint §2) — natural, critical, and willing to challenge Bob rather than just respond. As specified, however, Hibob is purely reactive: it only reflects when Bob initiates (doc 15 §4 weekly ritual), and scheduled reflection was originally planned only for Phase 8. This delays the most direct realization of Hibob's core identity to the very end of the roadmap, for no architectural reason — the data it needs (memory, sessions, graph edges from ADR 0006) is available much earlier.

## Decision
Add a Reflection job (daily or weekly, running on a local model for cost/privacy reasons, strictly read-only) that scans recent memory, session summaries, and memory graph edges for: unresolved `memory_conflicts`/disputed edges, untested assumptions with downstream `depends_on` edges, and RAG sources flagged stale (doc 06 §13). Output is written to a `reflections` record Bob can read asynchronously — phrased the way doc 15 §5 already describes ("Bob, ini keputusan final atau masih hipotesis?"). Reflections never write durable memory or trigger tool action directly; they only produce memory/blueprint-update candidates through the existing approval pipeline (doc 04 §6, doc 13 §4).

## Consequences
Positive: realizes the digital-sibling identity early instead of at Phase 8; produces high-quality, structured conflict signals that make the Memory Graph (ADR 0006) and Self-Calibration (ADR 0007) more useful sooner.
Negative: another scheduled job to run, monitor, and tune; risk of being noisy or naggy if conflict/staleness thresholds are set too low — mitigated by keeping output as candidates, never forced action.

## Alternatives considered
- Keep reflection manual/Bob-initiated only until Phase 8 (status quo): rejected, review identified this as the cheapest, most direct way to deliver on the project's stated primary identity.
- Let reflection auto-write durable memory or trigger blueprint edits directly: rejected, violates the approval-required-for-durable-memory non-negotiable (Executive Blueprint §3.5).
