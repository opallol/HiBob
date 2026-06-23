"""Thin Qdrant wrapper for the hibob_documents collection (ADR 0002, doc 06 §15).

Separate collection from memories. Payload carries only filter metadata (document_id,
privacy_tier); canonical chunk text lives in Postgres `document_chunks`. Point id == chunk_id.
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
    """Create hibob_documents if missing. Called once at app startup."""
    client = get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if settings.documents_collection not in existing:
        await client.create_collection(
            collection_name=settings.documents_collection,
            vectors_config=qm.VectorParams(
                size=settings.embed_dim, distance=qm.Distance.COSINE
            ),
        )


async def upsert(chunk_id: uuid.UUID, vector: list[float], payload: dict) -> None:
    client = get_client()
    await client.upsert(
        collection_name=settings.documents_collection,
        points=[qm.PointStruct(id=str(chunk_id), vector=vector, payload=payload)],
    )


async def search(
    vector: list[float], *, allowed_tiers: list[str], limit: int
) -> list[tuple[str, float, dict]]:
    """Return [(chunk_id, semantic_score, payload)], filtered to the allowed privacy tiers."""
    client = get_client()
    must = [qm.FieldCondition(key="privacy_tier", match=qm.MatchAny(any=allowed_tiers))]
    resp = await client.query_points(
        collection_name=settings.documents_collection,
        query=vector,
        query_filter=qm.Filter(must=must),
        limit=limit,
        with_payload=True,
    )
    return [(str(p.id), p.score, p.payload or {}) for p in resp.points]
