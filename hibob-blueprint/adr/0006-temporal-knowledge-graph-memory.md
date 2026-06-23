# ADR 0006 - Temporal Knowledge Graph Memory

## Status
Accepted for blueprint v0.1

## Context
`memory_conflicts` only links two memories pairwise (A vs B) and has no notion of chains or dependency. Real belief revision is not pairwise: Bob's stack decisions, principles, and assumptions form chains and clusters ("PHP -> Python -> Python+FastAPI"; decisions that depend on an assumption later disputed). Without a graph structure, Hibob cannot answer "what does this decision depend on" or "what changed since I last decided X" — capabilities implied by the "second brain" identity in the Executive Blueprint.

## Decision
Add a `memory_edges` table connecting memory nodes with typed, directed relations: `supersedes`, `contradicts`, `depends_on`, `supports`, `derived_from`. Each edge carries its own `discovered_at` timestamp, separate from the connected memories' `valid_from/valid_until` (world time) and `created_at` (system time) — giving the graph a bi-temporal character: what was true, and when Hibob learned it. The relational DB plus `memory_edges` remains the canonical graph; Qdrant continues to serve semantic similarity only. Traversal uses recursive queries (Postgres recursive CTE) on the existing relational store; no separate graph database is introduced in v0.1.

## Consequences
Positive: enables multi-hop questions ("what decisions depend on this disputed assumption"), gives Hibob real decision provenance, and turns "second brain" from a metaphor into a queryable capability. `memory_conflicts` becomes a specialization of `memory_edges` (conflict-type edges) rather than a separate mechanism.
Negative: adds a table and traversal logic that must stay consistent whenever a memory is superseded, archived, or disputed; query complexity grows with graph depth.

## Alternatives considered
- Adopt a dedicated graph database (Neo4j/Apache AGE) immediately: rejected as premature infrastructure for single-user, personal-scale v0.1 (violates doc 02 anti-pattern "use multiple memory stores without sync policy" if not done carefully).
- Keep only flat pairwise `memory_conflicts`: rejected, insufficient for the second-brain ambition and for OP-6 reflection signal quality.
