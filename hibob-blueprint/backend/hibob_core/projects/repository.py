"""DB access for projects (Phase 8)."""

from __future__ import annotations

import json
import uuid

import asyncpg


async def create(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    name: str,
    description: str | None,
    metadata: dict | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO projects (user_id, name, description, metadata_json)
        VALUES ($1,$2,$3,$4) RETURNING id
        """,
        user_id, name, description, json.dumps(metadata or {}),
    )
    return row["id"]


async def name_exists(conn: asyncpg.Connection, *, user_id: uuid.UUID, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM projects WHERE user_id=$1 AND name=$2)", user_id, name
    )


async def get(conn: asyncpg.Connection, project_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
    if row is None:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    d["user_id"] = str(d["user_id"]) if d.get("user_id") else None
    return d


async def list_projects(
    conn: asyncpg.Connection, *, user_id: uuid.UUID, status: str | None
) -> list[dict]:
    if status:
        rows = await conn.fetch(
            "SELECT id, name, description, status FROM projects WHERE user_id=$1 AND status=$2 "
            "ORDER BY updated_at DESC", user_id, status,
        )
    else:
        rows = await conn.fetch(
            "SELECT id, name, description, status FROM projects WHERE user_id=$1 "
            "ORDER BY updated_at DESC", user_id,
        )
    return [{**dict(r), "id": str(r["id"])} for r in rows]


async def set_status(conn: asyncpg.Connection, project_id: uuid.UUID, status: str) -> None:
    await conn.execute(
        "UPDATE projects SET status=$2, updated_at=now() WHERE id=$1", project_id, status
    )
