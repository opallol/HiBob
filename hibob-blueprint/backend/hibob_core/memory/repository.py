"""DB access for memory tables (service-layer; tools/UI never touch DB directly)."""

from __future__ import annotations

import json
import uuid

import asyncpg


async def create_candidate(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    memory_type: str,
    scope: str,
    title: str,
    content: str,
    sensitivity: str,
    stability: str,
    confidence: float,
    metadata: dict | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO memories
            (user_id, memory_type, scope, title, content, status,
             confidence, sensitivity, stability, metadata_json)
        VALUES ($1,$2,$3,$4,$5,'candidate',$6,$7,$8,$9) RETURNING id
        """,
        user_id, memory_type, scope, title, content,
        confidence, sensitivity, stability, json.dumps(metadata or {}),
    )
    return row["id"]


async def add_source(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID | None,
    quote: str | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO memory_sources (memory_id, source_type, source_id, quote_or_excerpt)
        VALUES ($1,$2,$3,$4)
        """,
        memory_id, source_type, source_id, quote,
    )


async def get(conn: asyncpg.Connection, memory_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM memories WHERE id = $1", memory_id)


async def get_with_sources(conn: asyncpg.Connection, memory_id: uuid.UUID) -> dict | None:
    mem = await get(conn, memory_id)
    if mem is None:
        return None
    sources = await conn.fetch(
        "SELECT source_type, source_id, quote_or_excerpt, created_at "
        "FROM memory_sources WHERE memory_id = $1 ORDER BY created_at",
        memory_id,
    )
    return {"memory": dict(mem), "sources": [dict(s) for s in sources]}


async def set_status(
    conn: asyncpg.Connection, memory_id: uuid.UUID, status: str
) -> None:
    await conn.execute(
        "UPDATE memories SET status = $2, updated_at = now() WHERE id = $1",
        memory_id, status,
    )


async def set_superseded(
    conn: asyncpg.Connection, memory_id: uuid.UUID, by_memory_id: uuid.UUID
) -> None:
    await conn.execute(
        "UPDATE memories SET status='superseded', superseded_by_memory_id=$2, "
        "updated_at=now() WHERE id=$1",
        memory_id, by_memory_id,
    )


async def add_review(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    decision: str,
    note: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO memory_reviews (memory_id, reviewer_user_id, decision, note)
        VALUES ($1,$2,$3,$4)
        """,
        memory_id, reviewer_user_id, decision, note,
    )


async def add_embedding(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    collection: str,
    vector_id: str,
    model: str,
    dim: int,
    version: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO memory_embeddings
            (memory_id, vector_collection, vector_id, embedding_model, embedding_dim, embedding_version)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        memory_id, collection, vector_id, model, dim, version,
    )


async def add_conflict(
    conn: asyncpg.Connection,
    *,
    memory_id_a: uuid.UUID,
    memory_id_b: uuid.UUID,
    conflict_type: str,
    severity: str = "medium",
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO memory_conflicts (memory_id_a, memory_id_b, conflict_type, severity)
        VALUES ($1,$2,$3,$4) RETURNING id
        """,
        memory_id_a, memory_id_b, conflict_type, severity,
    )
    return row["id"]


async def search_sql(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    q: str | None,
    scope: str | None,
    memory_type: str | None,
    status: str | None,
    limit: int = 50,
) -> list[dict]:
    """Keyword/metadata search (the GET /v1/memory/search backing query)."""
    clauses = ["user_id = $1"]
    args: list = [user_id]
    if status:
        args.append(status)
        clauses.append(f"status = ${len(args)}")
    if scope:
        args.append(scope)
        clauses.append(f"scope = ${len(args)}")
    if memory_type:
        args.append(memory_type)
        clauses.append(f"memory_type = ${len(args)}")
    if q:
        args.append(f"%{q}%")
        clauses.append(f"(title ILIKE ${len(args)} OR content ILIKE ${len(args)})")
    args.append(limit)
    rows = await conn.fetch(
        f"SELECT id, memory_type, scope, title, content, status, confidence, sensitivity "
        f"FROM memories WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ${len(args)}",
        *args,
    )
    return [dict(r) for r in rows]


async def fetch_by_ids(conn: asyncpg.Connection, ids: list[uuid.UUID]) -> dict[str, dict]:
    """Map memory_id(str) -> row for the candidate set returned by Qdrant."""
    if not ids:
        return {}
    rows = await conn.fetch(
        "SELECT id, memory_type, scope, title, content, status, confidence, sensitivity, "
        "created_at FROM memories WHERE id = ANY($1::uuid[])",
        ids,
    )
    return {str(r["id"]): dict(r) for r in rows}


async def approved_without_embedding(conn: asyncpg.Connection) -> list[dict]:
    """Approved memories missing a vector row - used to reindex seeds at startup."""
    rows = await conn.fetch(
        """
        SELECT m.id, m.user_id, m.memory_type, m.scope, m.title, m.content,
               m.status, m.sensitivity, m.confidence, m.created_at
        FROM memories m
        LEFT JOIN memory_embeddings e ON e.memory_id = m.id
        WHERE m.status = 'approved' AND e.id IS NULL
        """
    )
    return [dict(r) for r in rows]
