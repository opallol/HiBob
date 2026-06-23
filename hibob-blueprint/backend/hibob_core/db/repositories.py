"""Service-layer DB access. Tools/UI never touch the DB directly (ERD doc anti-pattern)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncpg

BOB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---- Conversations & messages ----

async def create_conversation(
    conn: asyncpg.Connection, *, user_id: uuid.UUID, conversation_type: str, privacy_tier: str
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO conversations (user_id, conversation_type, privacy_tier)
        VALUES ($1, $2, $3) RETURNING id
        """,
        user_id, conversation_type, privacy_tier,
    )
    return row["id"]


async def conversation_exists(conn: asyncpg.Connection, conversation_id: uuid.UUID) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM conversations WHERE id = $1)", conversation_id
    )


async def add_message(
    conn: asyncpg.Connection,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model_run_id: uuid.UUID | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO messages (conversation_id, role, content, model_run_id, trace_id)
        VALUES ($1, $2, $3, $4, $5) RETURNING id
        """,
        conversation_id, role, content, model_run_id, trace_id,
    )
    await conn.execute(
        "UPDATE conversations SET updated_at = now() WHERE id = $1", conversation_id
    )
    return row["id"]


async def get_conversation(conn: asyncpg.Connection, conversation_id: uuid.UUID) -> dict | None:
    conv = await conn.fetchrow(
        "SELECT * FROM conversations WHERE id = $1", conversation_id
    )
    if conv is None:
        return None
    msgs = await conn.fetch(
        "SELECT id, role, content, content_type, trace_id, created_at "
        "FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
        conversation_id,
    )
    return {"conversation": dict(conv), "messages": [dict(m) for m in msgs]}


async def get_history(conn: asyncpg.Connection, conversation_id: uuid.UUID) -> list[dict]:
    """Prior turns for prompt assembly: [{'role':..., 'content':...}, ...]."""
    rows = await conn.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1 "
        "AND role IN ('user', 'assistant') ORDER BY created_at ASC",
        conversation_id,
    )
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def create_session_summary(
    conn: asyncpg.Connection,
    *,
    conversation_id: uuid.UUID,
    summary: str,
    decisions: list | None = None,
    open_questions: list | None = None,
) -> uuid.UUID:
    import json
    row = await conn.fetchrow(
        """
        INSERT INTO session_summaries
            (conversation_id, summary, decisions_json, open_questions_json)
        VALUES ($1, $2, $3, $4) RETURNING id
        """,
        conversation_id, summary, json.dumps(decisions or []), json.dumps(open_questions or []),
    )
    return row["id"]


# ---- Persona (identity) ----

async def get_active_persona_rules(conn: asyncpg.Connection, user_id: uuid.UUID) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT pr.content
        FROM persona_rules pr
        JOIN personas p ON p.id = pr.persona_id
        WHERE p.user_id = $1 AND p.active = true AND pr.enabled = true
        ORDER BY pr.priority ASC
        """,
        user_id,
    )
    return [r["content"] for r in rows]


# ---- model_runs ----

async def record_model_run(
    conn: asyncpg.Connection,
    *,
    provider: str,
    model: str,
    task_type: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: int | None,
    cost_estimate: float,
    trace_id: str | None,
    status: str = "succeeded",
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO model_runs
            (provider, model, task_type, input_tokens, output_tokens,
             latency_ms, cost_estimate, trace_id, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        """,
        provider, model, task_type, input_tokens, output_tokens,
        latency_ms, cost_estimate, trace_id, status,
    )
    return row["id"]


# ---- Cost breaker (ADR 0012) ----

async def get_daily_ceiling(conn: asyncpg.Connection, user_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT id, ceiling_amount FROM budget_ceilings "
        "WHERE user_id = $1 AND scope = 'daily' ORDER BY created_at DESC LIMIT 1",
        user_id,
    )


async def get_spend_today(conn: asyncpg.Connection, budget_ceiling_id: uuid.UUID) -> float:
    val = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM cost_ledger "
        "WHERE budget_ceiling_id = $1 AND created_at >= date_trunc('day', now())",
        budget_ceiling_id,
    )
    return float(val or 0)


async def record_cost(
    conn: asyncpg.Connection,
    *,
    model_run_id: uuid.UUID,
    budget_ceiling_id: uuid.UUID,
    amount: float,
    running_total: float,
    ceiling_breached: bool,
) -> None:
    await conn.execute(
        """
        INSERT INTO cost_ledger
            (model_run_id, budget_ceiling_id, amount, running_total, ceiling_breached)
        VALUES ($1, $2, $3, $4, $5)
        """,
        model_run_id, budget_ceiling_id, amount, running_total, ceiling_breached,
    )


# ---- Audit ----

async def write_audit(
    conn: asyncpg.Connection,
    *,
    actor_type: str,
    actor_id: str | None,
    event_type: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    import json
    await conn.execute(
        """
        INSERT INTO audit_logs
            (actor_type, actor_id, event_type, target_type, target_id, metadata_json)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        actor_type, actor_id, event_type, target_type, target_id,
        json.dumps(metadata or {}),
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
