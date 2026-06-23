# Hibob MVP Acceptance Checklist

> ADR 0005-0013 (policy engine, memory graph/calibration, replay harness, red-team loop, reflective sibling, ephemeral sandbox, cost circuit breaker, self-build merge gate) are accepted architecture decisions but are intentionally **not** part of this v0.1 gate - they phase in per `docs/11_ROADMAP.md`. Their own readiness is tracked in `SECURITY_GATE.md` and `MEMORY_QUALITY_GATE.md` as each phase reaches them.

## Product

- [ ] Hibob speaks in agreed sibling style.
- [ ] Hibob can challenge Bob's assumptions constructively.
- [ ] Hibob distinguishes idea, hypothesis, decision, and memory.

## Chat

- [ ] `/chat` endpoint works.
- [ ] Conversation and messages persist.
- [ ] Response includes trace ID.

## Memory

- [ ] Session summary generated.
- [ ] Memory candidates extracted.
- [ ] Bob can approve/reject memory.
- [ ] Approved memory can be searched.
- [ ] Memory conflict can be recorded.

## Knowledge

- [ ] Markdown/TXT ingestion works.
- [ ] One PDF/DOCX parses via Unstructured.
- [ ] One web source crawls via Crawl4AI.
- [ ] Chunks indexed in Qdrant.
- [ ] RAG answer includes source reference.

## Tools

- [ ] Tool registry exists.
- [ ] Risk levels exist.
- [ ] High-risk action asks approval.
- [ ] Critical action denied.
- [ ] Tool run audit log exists.

## Evaluation

- [ ] Phoenix traces enabled.
- [ ] DeepEval memory suite exists.
- [ ] DeepEval RAG suite exists.
- [ ] DeepEval tool policy suite exists.

## Docs

- [ ] PRD updated.
- [ ] Architecture updated.
- [ ] ERD updated.
- [ ] Tool policy updated.
- [ ] ADRs written for major decisions.
