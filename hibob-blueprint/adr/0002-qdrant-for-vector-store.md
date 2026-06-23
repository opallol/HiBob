# ADR 0002 - Use Qdrant for Vector Store

## Status
Accepted for blueprint v0.1

## Context
Hibob needs semantic retrieval for memories, documents, and future code chunks. Bob listed Qdrant as an available resource.

## Decision
Use Qdrant for vector search. Keep relational DB as source of truth.

## Consequences
Positive: strong semantic search, metadata filtering, local/self-hosted path.  
Negative: another service to run; schema must avoid treating vector store as canonical truth.

## Alternatives considered
- pgvector: simpler one DB, but Bob specifically has Qdrant and it fits local AI lab.
- Chroma: simpler, but Qdrant is more robust for planned metadata/filtering.
