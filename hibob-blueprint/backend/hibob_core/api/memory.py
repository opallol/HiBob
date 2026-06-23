"""Memory API (doc 13 §4). Approval is human-only; no endpoint sets confidence/status directly."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hibob_core.db import repositories as core_repo
from hibob_core.db.pool import get_pool
from hibob_core.memory import extraction, repository as repo, service, summary
from hibob_core.models.router import ModelRouter

router = APIRouter()
_router = ModelRouter()


class CandidatesRequest(BaseModel):
    conversation_id: uuid.UUID


class SummarizeRequest(BaseModel):
    conversation_id: uuid.UUID


class ReviewRequest(BaseModel):
    note: str | None = None


class SupersedeRequest(BaseModel):
    by_memory_id: uuid.UUID


@router.post("/memory/candidates")
async def create_candidates(req: CandidatesRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await core_repo.conversation_exists(conn, req.conversation_id):
                raise HTTPException(status_code=404, detail="conversation not found")
            ids = await extraction.extract_candidates(
                conn, _router, user_id=core_repo.BOB_USER_ID,
                conversation_id=req.conversation_id,
            )
    return {"candidate_ids": [str(i) for i in ids], "count": len(ids)}


@router.post("/memory/summarize")
async def summarize(req: SummarizeRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await core_repo.conversation_exists(conn, req.conversation_id):
                raise HTTPException(status_code=404, detail="conversation not found")
            return await summary.summarize_session(
                conn, _router, user_id=core_repo.BOB_USER_ID,
                conversation_id=req.conversation_id,
            )


@router.get("/memory/search")
async def search(
    q: str | None = None,
    scope: str | None = None,
    memory_type: str | None = None,
    status: str | None = None,
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        results = await repo.search_sql(
            conn, user_id=core_repo.BOB_USER_ID, q=q, scope=scope,
            memory_type=memory_type, status=status,
        )
    return {"results": [{**r, "id": str(r["id"]), "confidence": float(r["confidence"])} for r in results]}


@router.get("/memory/{memory_id}")
async def get_memory(memory_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        data = await repo.get_with_sources(conn, memory_id)
    if data is None:
        raise HTTPException(status_code=404, detail="memory not found")
    mem = data["memory"]
    mem["id"] = str(mem["id"])
    mem["confidence"] = float(mem["confidence"])
    return data


@router.post("/memory/{memory_id}/approve")
async def approve(memory_id: uuid.UUID, req: ReviewRequest | None = None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.approve(
                    conn, _router, memory_id=memory_id,
                    reviewer_user_id=core_repo.BOB_USER_ID,
                    note=(req.note if req else None),
                )
            except service.MemoryError as e:
                raise HTTPException(status_code=400, detail=str(e))


@router.post("/memory/{memory_id}/reject")
async def reject(memory_id: uuid.UUID, req: ReviewRequest | None = None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.reject(
                    conn, memory_id=memory_id, reviewer_user_id=core_repo.BOB_USER_ID,
                    note=(req.note if req else None),
                )
            except service.MemoryError as e:
                raise HTTPException(status_code=400, detail=str(e))


@router.post("/memory/{memory_id}/supersede")
async def supersede(memory_id: uuid.UUID, req: SupersedeRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await service.supersede(
                    conn, memory_id=memory_id, by_memory_id=req.by_memory_id,
                    reviewer_user_id=core_repo.BOB_USER_ID,
                )
            except service.MemoryError as e:
                raise HTTPException(status_code=400, detail=str(e))
