"""Sandbox API (doc 13 §6a): inspect a recorded sandbox run (Phase 7, ADR 0011)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from hibob_core.db.pool import get_pool
from hibob_core.sandbox import repository as repo

router = APIRouter()


@router.get("/sandbox/runs/{sandbox_run_id}")
async def get_sandbox_run(sandbox_run_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        run = await repo.get_sandbox_run(conn, sandbox_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="sandbox run not found")
    return run
