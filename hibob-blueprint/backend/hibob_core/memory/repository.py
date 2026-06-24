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


# ---- Phase 2.5: memory graph (ADR 0006) ----

async def add_edge(
    conn: asyncpg.Connection,
    *,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    relation_type: str,
    confidence: float = 0.5,
    note: str | None = None,
) -> uuid.UUID | None:
    """Create a directed typed relation. Idempotent: the unique (from,to,relation) index
    (migration 0004) makes a duplicate a no-op, returning None."""
    row = await conn.fetchrow(
        """
        INSERT INTO memory_edges (memory_id_from, memory_id_to, relation_type, confidence, note)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (memory_id_from, memory_id_to, relation_type) DO NOTHING
        RETURNING id
        """,
        from_id, to_id, relation_type, confidence, note,
    )
    return row["id"] if row else None


async def edges_for(conn: asyncpg.Connection, memory_id: uuid.UUID) -> list[dict]:
    """Direct edges (in + out) touching a node."""
    rows = await conn.fetch(
        "SELECT id, memory_id_from, memory_id_to, relation_type, confidence, note, discovered_at "
        "FROM memory_edges WHERE memory_id_from = $1 OR memory_id_to = $1",
        memory_id,
    )
    return [dict(r) for r in rows]


async def traverse(
    conn: asyncpg.Connection,
    memory_id: uuid.UUID,
    *,
    relation_types: list[str] | None,
    max_depth: int,
) -> list[dict]:
    """Walk the graph outward from `memory_id` via a recursive CTE (ADR 0006 - no graph DB).

    Returns edge rows reachable within `max_depth` hops, each annotated with `depth`.
    `relation_types=None` follows every relation; otherwise only the listed types.
    A visited-set in the path column prevents cycles from looping forever.
    """
    rows = await conn.fetch(
        """
        WITH RECURSIVE walk AS (
            SELECT e.id, e.memory_id_from, e.memory_id_to, e.relation_type,
                   e.confidence, e.note, e.discovered_at,
                   1 AS depth,
                   ARRAY[e.memory_id_from, e.memory_id_to] AS path
            FROM memory_edges e
            WHERE e.memory_id_from = $1
              AND ($2::text[] IS NULL OR e.relation_type = ANY($2::text[]))
          UNION ALL
            SELECT e.id, e.memory_id_from, e.memory_id_to, e.relation_type,
                   e.confidence, e.note, e.discovered_at,
                   w.depth + 1,
                   w.path || e.memory_id_to
            FROM memory_edges e
            JOIN walk w ON e.memory_id_from = w.memory_id_to
            WHERE w.depth < $3
              AND ($2::text[] IS NULL OR e.relation_type = ANY($2::text[]))
              AND NOT (e.memory_id_to = ANY(w.path))
        )
        SELECT id, memory_id_from, memory_id_to, relation_type, confidence, note,
               discovered_at, depth
        FROM walk ORDER BY depth, discovered_at
        """,
        memory_id, relation_types, max_depth,
    )
    return [dict(r) for r in rows]


# ---- Phase 2.5: confidence calibration (ADR 0007) ----

async def add_usage_feedback(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    event_type: str,
    signal_strength: float = 1.0,
    note: str | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO memory_usage_feedback
            (memory_id, conversation_id, event_type, signal_strength, note)
        VALUES ($1,$2,$3,$4,$5) RETURNING id
        """,
        memory_id, conversation_id, event_type, signal_strength, note,
    )
    return row["id"]


async def feedback_tallies(conn: asyncpg.Connection, memory_id: uuid.UUID) -> dict[str, float]:
    """Sum of signal_strength per event_type for a memory - the input to the Beta update."""
    rows = await conn.fetch(
        "SELECT event_type, COALESCE(SUM(signal_strength), 0) AS total "
        "FROM memory_usage_feedback WHERE memory_id = $1 GROUP BY event_type",
        memory_id,
    )
    return {r["event_type"]: float(r["total"]) for r in rows}


async def set_confidence(
    conn: asyncpg.Connection, memory_id: uuid.UUID, confidence: float
) -> None:
    """Update confidence ONLY (never status - ADR 0007 forbids auto-promotion)."""
    await conn.execute(
        "UPDATE memories SET confidence = $2, updated_at = now() WHERE id = $1",
        memory_id, confidence,
    )


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
