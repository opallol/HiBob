"""Project lifecycle (Phase 8). Lightweight organization for the daily-OS layer."""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.db import repositories as core_repo
from hibob_core.projects import repository as repo


class ProjectError(Exception):
    pass


async def create_project(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    name: str,
    description: str | None = None,
) -> dict:
    name = (name or "").strip()
    if not name:
        raise ProjectError("project name is required")
    if await repo.name_exists(conn, user_id=user_id, name=name):
        raise ProjectError(f"project '{name}' already exists")
    pid = await repo.create(conn, user_id=user_id, name=name, description=description)
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(user_id), event_type="project.created",
        target_type="project", target_id=str(pid), metadata={"name": name},
    )
    return {"id": str(pid), "name": name, "status": "active"}


async def archive_project(
    conn: asyncpg.Connection, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> dict:
    if await repo.get(conn, project_id) is None:
        raise ProjectError("project not found")
    await repo.set_status(conn, project_id, "archived")
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(user_id), event_type="project.archived",
        target_type="project", target_id=str(project_id),
    )
    return {"id": str(project_id), "status": "archived"}
