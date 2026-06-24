"""DB access for sandbox_runs (Phase 7, ADR 0011)."""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.sandbox.spec import SandboxSpec


async def create_sandbox_run(
    conn: asyncpg.Connection, *, tool_run_id: uuid.UUID, spec: SandboxSpec
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO sandbox_runs
            (tool_run_id, container_image, network_mode, filesystem_mode, workdir_scope, started_at)
        VALUES ($1,$2,$3,$4,$5, now()) RETURNING id
        """,
        tool_run_id, spec.container_image, spec.network_mode, spec.filesystem_mode, spec.workdir_scope,
    )
    return row["id"]


async def finish_sandbox_run(
    conn: asyncpg.Connection, *, sandbox_run_id: uuid.UUID, exit_status: str
) -> None:
    await conn.execute(
        "UPDATE sandbox_runs SET exit_status=$2, destroyed_at=now() WHERE id=$1",
        sandbox_run_id, exit_status,
    )


async def get_sandbox_run(conn: asyncpg.Connection, sandbox_run_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM sandbox_runs WHERE id = $1", sandbox_run_id)
    if row is None:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    d["tool_run_id"] = str(d["tool_run_id"]) if d.get("tool_run_id") else None
    return d
