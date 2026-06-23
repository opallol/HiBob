# ADR 0001 - Use Core-and-Adapters Architecture

## Status
Accepted for blueprint v0.1

## Context
Hibob will use many fast-changing resources: local models, cloud models, Open WebUI, Qdrant, MCP tools, automation platforms, and coding agents. If Hibob is tightly coupled to one tool, it will become obsolete or hard to maintain.

## Decision
Hibob will use a core-and-adapters architecture. Hibob Core owns identity, memory, tool policy, orchestration, audit, and evaluation. External tools are adapters.

## Consequences
Positive: future model/tool swaps are easier. Memory and policy remain stable.  
Negative: more upfront design discipline is required.

## Alternatives considered
- Build directly inside Open WebUI: faster but high lock-in.
- Use AnythingLLM as core: fast RAG but duplicates memory/policy.
- Use Hermes Agent as core: agentic quickly but identity/policy too dependent.
