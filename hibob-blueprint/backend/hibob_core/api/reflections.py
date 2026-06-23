"""Reflections API (doc 13: GET /v1/reflections + run/status).

By contract the reflection output is read-only: it never writes memory or triggers a tool
(doc 13 §11, ADR 0010). The job is triggered manually here; an external scheduler/cron hits
POST /v1/reflections/run on a daily/weekly cadence.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hibob_core.db import repositories as core_repo
from hibob_core.db.pool import get_pool
from hibob_core.reflection import repository as repo, service

router = APIRouter()


class StatusRequest(BaseModel):
    status: str  # read | acted_on | dismissed (unread is the default initial state)


@router.get("/reflections")
async def list_reflections(status: str | None = None, limit: int = 50) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        items = await repo.list_reflections(
            conn, user_id=core_repo.BOB_USER_ID, status=status, limit=limit
        )
    return {"reflections": items, "count": len(items)}


@router.post("/reflections/run")
async def run_reflection() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.run(conn, user_id=core_repo.BOB_USER_ID)


@router.post("/reflections/{reflection_id}/status")
async def set_reflection_status(reflection_id: uuid.UUID, req: StatusRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.set_status(
                    conn, reflection_id=reflection_id, status=req.status
                )
            except service.ReflectionError as e:
                raise HTTPException(status_code=400, detail=str(e))
