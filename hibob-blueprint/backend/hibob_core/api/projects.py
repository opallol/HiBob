"""Projects API (Phase 8)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hibob_core.db import repositories as core_repo
from hibob_core.db.pool import get_pool
from hibob_core.projects import repository as repo, service

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


@router.post("/projects")
async def create_project(req: CreateProjectRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.create_project(
                    conn, user_id=core_repo.BOB_USER_ID, name=req.name, description=req.description
                )
            except service.ProjectError as e:
                raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects")
async def list_projects(status: str | None = None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        items = await repo.list_projects(conn, user_id=core_repo.BOB_USER_ID, status=status)
    return {"projects": items, "count": len(items)}


@router.get("/projects/{project_id}")
async def get_project(project_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        proj = await repo.get(conn, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="project not found")
    return proj


@router.post("/projects/{project_id}/archive")
async def archive_project(project_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.archive_project(
                    conn, project_id=project_id, user_id=core_repo.BOB_USER_ID
                )
            except service.ProjectError as e:
                raise HTTPException(status_code=404, detail=str(e))
