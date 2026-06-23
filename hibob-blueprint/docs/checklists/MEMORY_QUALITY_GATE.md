# Memory Quality Gate

Before approving durable memory:

- [ ] Is it actually important long-term?
- [ ] Is it a fact, preference, decision, principle, correction, or warning?
- [ ] Is the source recorded?
- [ ] Is confidence appropriate?
- [ ] Is sensitivity classified?
- [ ] Does it conflict with existing memory?
- [ ] Is it stable or temporary?
- [ ] Should it expire?
- [ ] Did Bob approve if durable/private?
- [ ] If it conflicts with or supersedes another memory, is that recorded as a `memory_edges` relation, not just left implicit (ADR 0006)?
- [ ] If this memory has been corrected before, does its confidence already reflect that history (ADR 0007)?

Reject or keep as candidate if uncertain.
