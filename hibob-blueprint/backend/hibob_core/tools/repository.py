"""DB access for the Tool Gateway (Phase 4): tools, tool_runs, approvals, trust scores."""

from __future__ import annotations

import json
import uuid

import asyncpg


# ---- tools ----

async def upsert_tool(
    conn: asyncpg.Connection,
    *,
    name: str,
    description: str,
    tool_type: str,
    input_schema: dict,
    output_schema: dict,
    risk_level: str,
    default_permission: str,
    enabled: bool,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO tools
            (name, description, tool_type, input_schema_json, output_schema_json,
             risk_level, default_permission, enabled)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (name) DO UPDATE SET
            description=EXCLUDED.description, tool_type=EXCLUDED.tool_type,
            risk_level=EXCLUDED.risk_level, default_permission=EXCLUDED.default_permission,
            enabled=EXCLUDED.enabled, updated_at=now()
        RETURNING id
        """,
        name, description, tool_type, json.dumps(input_schema), json.dumps(output_schema),
        risk_level, default_permission, enabled,
    )
    return row["id"]


async def get_tool_by_name(conn: asyncpg.Connection, name: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM tools WHERE name = $1", name)


async def list_tools(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT name, description, tool_type, risk_level, default_permission, enabled "
        "FROM tools ORDER BY name"
    )
    return [dict(r) for r in rows]


# ---- tool_runs ----

async def create_tool_run(
    conn: asyncpg.Connection,
    *,
    tool_id: uuid.UUID,
    requested_by: str,
    input_json: dict,
    risk_level: str,
    status: str,
    approval_request_id: uuid.UUID | None = None,
    trace_id: str | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO tool_runs
            (tool_id, requested_by, input_json, status, risk_level_at_run,
             approval_request_id, trace_id)
        VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id
        """,
        tool_id, requested_by, json.dumps(input_json), status, risk_level,
        approval_request_id, trace_id,
    )
    return row["id"]


async def get_tool_run(conn: asyncpg.Connection, tool_run_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM tool_runs WHERE id = $1", tool_run_id)


async def get_run_by_approval(
    conn: asyncpg.Connection, approval_id: uuid.UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "SELECT * FROM tool_runs WHERE approval_request_id=$1 ORDER BY created_at DESC LIMIT 1",
        approval_id,
    )


async def set_tool_run(
    conn: asyncpg.Connection,
    *,
    tool_run_id: uuid.UUID,
    status: str,
    output_json: dict | None = None,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> None:
    sets = ["status = $2"]
    args: list = [tool_run_id, status]
    if output_json is not None:
        args.append(json.dumps(output_json))
        sets.append(f"output_json = ${len(args)}")
    if mark_started:
        sets.append("started_at = now()")
    if mark_finished:
        sets.append("finished_at = now()")
    await conn.execute(f"UPDATE tool_runs SET {', '.join(sets)} WHERE id = $1", *args)


# ---- approval_requests ----

async def create_approval(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    request_type: str,
    summary: str,
    payload: dict,
    ttl_hours: int,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO approval_requests (user_id, request_type, summary, payload_json, expires_at)
        VALUES ($1,$2,$3,$4, now() + make_interval(hours => $5)) RETURNING id
        """,
        user_id, request_type, summary, json.dumps(payload), ttl_hours,
    )
    return row["id"]


async def get_approval(conn: asyncpg.Connection, approval_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM approval_requests WHERE id = $1", approval_id)


async def decide_approval(
    conn: asyncpg.Connection, *, approval_id: uuid.UUID, status: str
) -> None:
    await conn.execute(
        "UPDATE approval_requests SET status=$2, decided_at=now() WHERE id=$1",
        approval_id, status,
    )


# ---- tool_trust_scores (ADR 0005 #2) ----

async def get_trust(conn: asyncpg.Connection, *, tool_id: uuid.UUID, context: str) -> float:
    val = await conn.fetchval(
        "SELECT trust_score FROM tool_trust_scores WHERE tool_id=$1 AND context=$2",
        tool_id, context,
    )
    return float(val or 0.0)


async def bump_trust(
    conn: asyncpg.Connection, *, tool_id: uuid.UUID, context: str, increment: float
) -> float:
    """Reward a successful, non-flagged run. Capped at 1.0."""
    val = await conn.fetchval(
        """
        INSERT INTO tool_trust_scores (tool_id, context, trust_score, successful_runs, updated_at)
        VALUES ($1,$2,$3,1, now())
        ON CONFLICT (tool_id, context) DO UPDATE SET
            trust_score = LEAST(1.0, tool_trust_scores.trust_score + $3),
            successful_runs = tool_trust_scores.successful_runs + 1,
            updated_at = now()
        RETURNING trust_score
        """,
        tool_id, context, increment,
    )
    return float(val)


async def reset_trust(conn: asyncpg.Connection, *, tool_id: uuid.UUID, context: str) -> None:
    """Any policy violation / red-team hit resets trust to zero (ADR 0005 #2)."""
    await conn.execute(
        """
        INSERT INTO tool_trust_scores (tool_id, context, trust_score, flagged_runs, last_reset_at, updated_at)
        VALUES ($1,$2,0,1, now(), now())
        ON CONFLICT (tool_id, context) DO UPDATE SET
            trust_score = 0, flagged_runs = tool_trust_scores.flagged_runs + 1,
            last_reset_at = now(), updated_at = now()
        """,
        tool_id, context,
    )
