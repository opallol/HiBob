"""Knowledge API (doc 13 §5): register / ingest / search documents + ingestion-job status."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hibob_core.db import repositories as core_repo
from hibob_core.db.pool import get_pool
from hibob_core.knowledge import ingestion, parsers, repository as repo, retrieval
from hibob_core.models.router import ModelRouter

router = APIRouter()
_router = ModelRouter()


class RegisterRequest(BaseModel):
    title: str
    source_type: str                    # text | markdown | pdf | docx | web
    source_uri: str | None = None       # file path or URL
    privacy_tier: str = "internal"      # public | internal | private | secret
    inline_text: str | None = None      # convenience: ingest raw text without a file


@router.post("/documents/register")
async def register(req: RegisterRequest) -> dict:
    pool = get_pool()
    metadata = {"inline_text": req.inline_text} if req.inline_text else {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            doc_id = await repo.create_document(
                conn, user_id=core_repo.BOB_USER_ID, title=req.title,
                source_type=req.source_type, source_uri=req.source_uri,
                privacy_tier=req.privacy_tier, metadata=metadata,
            )
    return {"document_id": str(doc_id), "status": "pending"}


@router.post("/documents/{document_id}/ingest")
async def ingest(document_id: uuid.UUID) -> dict:
    pool = get_pool()
    # No wrapping transaction: ingestion persists status='failed' + the job row on error.
    async with pool.acquire() as conn:
        try:
            return await ingestion.run(conn, _router, document_id=document_id)
        except ingestion.IngestionError as e:
            if isinstance(e.__cause__, parsers.ParserUnavailable):
                raise HTTPException(status_code=503, detail=str(e))
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/search")
async def search(q: str | None = None, privacy_tier: str = "internal") -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        if q:
            results = await retrieval.retrieve(
                conn, _router, query=q, privacy_tier=privacy_tier
            )
        else:
            rows = await repo.search_sql(
                conn, user_id=core_repo.BOB_USER_ID, q=None, privacy_tier=privacy_tier
            )
            results = [
                {"chunk_id": str(r["id"]), "document_id": str(r["document_id"]),
                 "text": r["content"], "source": r.get("source_uri") or r["title"]}
                for r in rows
            ]
    return {"results": results}


@router.get("/ingestion-jobs/{job_id}")
async def get_ingestion_job(job_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        job = await repo.get_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ingestion job not found")
    job["id"] = str(job["id"])
    job["document_id"] = str(job["document_id"]) if job.get("document_id") else None
    return job
