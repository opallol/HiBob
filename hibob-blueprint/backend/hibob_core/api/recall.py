"""Unified recall API (Phase 8): one query across memory + documents."""

from __future__ import annotations

from fastapi import APIRouter

from hibob_core.db.pool import get_pool
from hibob_core.models.router import ModelRouter
from hibob_core.recall import recall as do_recall

router = APIRouter()
_router = ModelRouter()


@router.get("/recall")
async def recall(q: str, privacy_tier: str = "internal", project: str | None = None) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        results = await do_recall(
            conn, _router, query=q, privacy_tier=privacy_tier, project=project
        )
    return {"results": results, "count": len(results)}
