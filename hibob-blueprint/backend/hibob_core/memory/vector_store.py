"""Thin Qdrant wrapper for the hibob_memories collection (ADR 0002).

Qdrant is the index, never source of truth (ERD doc 03 §1) - payload carries only filter
metadata; canonical content lives in Postgres `memories`. Collection point id == memory_id.
"""

from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from hibob_core.config import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client


async def ensure_collection() -> None:
    """Create hibob_memories if missing. Called once at app startup."""
    client = get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if settings.memory_collection not in existing:
        await client.create_collection(
            collection_name=settings.memory_collection,
            vectors_config=qm.VectorParams(
                size=settings.embed_dim, distance=qm.Distance.COSINE
            ),
        )


async def upsert(memory_id: uuid.UUID, vector: list[float], payload: dict) -> None:
    client = get_client()
    await client.upsert(
        collection_name=settings.memory_collection,
        points=[qm.PointStruct(id=str(memory_id), vector=vector, payload=payload)],
    )


async def delete(memory_id: uuid.UUID) -> None:
    """Remove a memory's point (used on supersede/reject so it stops surfacing)."""
    client = get_client()
    await client.delete(
        collection_name=settings.memory_collection,
        points_selector=qm.PointIdsList(points=[str(memory_id)]),
    )


async def search(
    vector: list[float], *, scope: str | None, memory_type: str | None, limit: int
) -> list[tuple[str, float, dict]]:
    """Return [(memory_id, semantic_score, payload)]. Only approved memories are indexed,
    but we also filter status='approved' defensively."""
    client = get_client()
    must = [qm.FieldCondition(key="status", match=qm.MatchValue(value="approved"))]
    if scope:
        must.append(qm.FieldCondition(key="scope", match=qm.MatchValue(value=scope)))
    if memory_type:
        must.append(qm.FieldCondition(key="memory_type", match=qm.MatchValue(value=memory_type)))

    # qdrant-client >=1.12 uses query_points (the old .search() was removed in 1.18).
    resp = await client.query_points(
        collection_name=settings.memory_collection,
        query=vector,
        query_filter=qm.Filter(must=must),
        limit=limit,
        with_payload=True,
    )
    return [(str(p.id), p.score, p.payload or {}) for p in resp.points]
