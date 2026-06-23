"""FastAPI app: lifespan wires the DB pool + tracing; routers attach the v1 surface."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from hibob_core.api import chat, documents, memory
from hibob_core.db.pool import close_pool, get_pool, init_pool
from hibob_core.knowledge import vector_store as doc_vector_store
from hibob_core.memory import service as memory_service
from hibob_core.memory import vector_store
from hibob_core.models.router import ModelRouter
from hibob_core.telemetry import init_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    init_tracing()
    # Memory Core (Phase 2) + Knowledge Base (Phase 3): ensure Qdrant collections + reindex any
    # approved memory (seeds) missing a vector. Failures here must not block chat (degrade gracefully).
    try:
        await vector_store.ensure_collection()
        await doc_vector_store.ensure_collection()
        async with get_pool().acquire() as conn:
            await memory_service.reindex_approved(conn, ModelRouter())
    except Exception:
        pass
    yield
    await close_pool()


app = FastAPI(title="Hibob Core", version="0.1.0", lifespan=lifespan)
app.include_router(chat.router, prefix="/v1")
app.include_router(memory.router, prefix="/v1")
app.include_router(documents.router, prefix="/v1")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": "0.1.0"}
