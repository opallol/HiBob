"""DB access for the reflection job (Phase 3.5, ADR 0010).

Scan queries are READ-ONLY over memory/graph/knowledge tables. The only table this module ever
writes is `reflections` itself (findings Bob reads async). It never touches memory durable state.
"""

from __future__ import annotations

import json
import uuid

import asyncpg


# ---- scans (read-only) ----

async def open_conflicts(conn: asyncpg.Connection, limit: int) -> list[dict]:
    """Unresolved memory_conflicts (== `contradicts` edges, doc 04 §9), with both titles."""
    rows = await conn.fetch(
        """
        SELECT c.id, c.memory_id_a, c.memory_id_b, c.conflict_type, c.severity,
               ma.title AS title_a, mb.title AS title_b
        FROM memory_conflicts c
        LEFT JOIN memories ma ON ma.id = c.memory_id_a
        LEFT JOIN memories mb ON mb.id = c.memory_id_b
        WHERE c.status = 'open' ORDER BY c.created_at DESC LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


async def untested_assumptions(
    conn: asyncpg.Connection, *, max_conf: float, limit: int
) -> list[dict]:
    """Low-confidence memories that other decisions `depends_on` - fragile load-bearing beliefs."""
    rows = await conn.fetch(
        """
        SELECT e.id AS edge_id, e.memory_id_from, e.memory_id_to,
               m.title, m.confidence
        FROM memory_edges e
        JOIN memories m ON m.id = e.memory_id_to
        WHERE e.relation_type = 'depends_on' AND m.confidence < $1
        ORDER BY m.confidence ASC LIMIT $2
        """,
        max_conf, limit,
    )
    return [dict(r) for r in rows]


async def recurring_open_questions(
    conn: asyncpg.Connection, *, min_count: int, limit: int
) -> list[dict]:
    """Open questions that recur across multiple session summaries (Phase 8, deeper reflection)."""
    rows = await conn.fetch(
        """
        SELECT q AS question, COUNT(*) AS n
        FROM session_summaries, jsonb_array_elements_text(open_questions_json) AS q
        GROUP BY q HAVING COUNT(*) >= $1
        ORDER BY n DESC LIMIT $2
        """,
        min_count, limit,
    )
    return [dict(r) for r in rows]


async def stale_sources(
    conn: asyncpg.Connection, *, older_than_days: int, limit: int
) -> list[dict]:
    """Active documents whose web source hasn't been recrawled within the window (doc 06 §13)."""
    rows = await conn.fetch(
        """
        SELECT d.id AS document_id, d.title, ws.last_crawled_at, ws.url
        FROM documents d
        JOIN web_sources ws ON ws.id = d.web_source_id
        WHERE d.status = 'active'
          AND ws.last_crawled_at < now() - make_interval(days => $1)
        ORDER BY ws.last_crawled_at ASC LIMIT $2
        """,
        older_than_days, limit,
    )
    return [dict(r) for r in rows]


# ---- reflections (the only table this module writes) ----

async def reflection_exists(
    conn: asyncpg.Connection, *, reflection_type: str, key_id: str
) -> bool:
    """Anti-noise dedup: an open finding (unread/read) already references this id."""
    return await conn.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM reflections
            WHERE reflection_type = $1 AND status IN ('unread', 'read')
              AND (related_memory_ids @> $2::jsonb OR related_edge_ids @> $2::jsonb)
        )
        """,
        reflection_type, json.dumps([key_id]),
    )


async def create_reflection(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    reflection_type: str,
    summary: str,
    related_memory_ids: list[str] | None = None,
    related_edge_ids: list[str] | None = None,
    proposed_candidate_ids: list[str] | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO reflections
            (user_id, reflection_type, summary, related_memory_ids, related_edge_ids,
             proposed_candidate_ids)
        VALUES ($1,$2,$3,$4,$5,$6) RETURNING id
        """,
        user_id, reflection_type, summary,
        json.dumps(related_memory_ids or []),
        json.dumps(related_edge_ids or []),
        json.dumps(proposed_candidate_ids or []),
    )
    return row["id"]


def _deser(row: dict) -> dict:
    out = dict(row)
    out["id"] = str(out["id"])
    if out.get("user_id"):
        out["user_id"] = str(out["user_id"])
    for k in ("related_memory_ids", "related_edge_ids", "proposed_candidate_ids"):
        v = out.get(k)
        if isinstance(v, str):
            out[k] = json.loads(v)
    return out


async def list_reflections(
    conn: asyncpg.Connection, *, user_id: uuid.UUID, status: str | None, limit: int
) -> list[dict]:
    if status:
        rows = await conn.fetch(
            "SELECT * FROM reflections WHERE user_id = $1 AND status = $2 "
            "ORDER BY created_at DESC LIMIT $3",
            user_id, status, limit,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM reflections WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id, limit,
        )
    return [_deser(r) for r in rows]


async def get(conn: asyncpg.Connection, reflection_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM reflections WHERE id = $1", reflection_id)
    return _deser(row) if row else None


async def set_status(
    conn: asyncpg.Connection, reflection_id: uuid.UUID, status: str
) -> None:
    await conn.execute(
        "UPDATE reflections SET status = $2 WHERE id = $1", reflection_id, status
    )
