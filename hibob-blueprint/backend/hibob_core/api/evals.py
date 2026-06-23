"""Eval & observability API (Phase 6, doc 09)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from hibob_core.db.pool import get_pool
from hibob_core.evals import repository as repo, runner

router = APIRouter()


@router.get("/evals/suites")
async def list_suites() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        suites = await repo.list_suites(conn)
    return {"suites": suites, "count": len(suites)}


@router.post("/evals/{suite}/run")
async def run_suite(suite: str, target_version: str | None = None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await runner.run_suite(conn, suite_name=suite, target_version=target_version)
            except runner.EvalError as e:
                raise HTTPException(status_code=404, detail=str(e))


@router.get("/evals/runs/{run_id}")
async def get_run(run_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        summary = await repo.run_summary(conn, run_id)
        results = await repo.get_results(conn, run_id)
    return {"run_id": str(run_id), **summary, "results": results}


@router.get("/evals/judge")
async def active_judge() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        judge = await repo.get_active_judge(conn)
    if judge is None:
        raise HTTPException(status_code=404, detail="no active eval judge pinned")
    return judge
