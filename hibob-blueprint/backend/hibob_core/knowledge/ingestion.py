"""Ingestion orchestration (Phase 3, doc 06 §3/§11).

register -> parse -> chunk -> embed (local) -> store (Postgres + Qdrant) -> quality gate -> active.
Records an ingestion_jobs row and an audit event. Embedding is local (router.embed_adapter), so
private/secret documents never leave the machine (doc 06 §8, doc 08 §4).

Atomicity note (v0.1): callers run this WITHOUT a wrapping transaction, so a failure still persists
`documents.status='failed'` + the job row. Failed docs are excluded from retrieval (status filter).
"""

from __future__ import annotations

import json
import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.knowledge import chunking, parsers
from hibob_core.knowledge import repository as repo
from hibob_core.knowledge import vector_store
from hibob_core.models.router import ModelRouter


class IngestionError(Exception):
    pass


def _meta(doc: dict) -> dict:
    m = doc.get("metadata_json")
    if isinstance(m, str):
        try:
            return json.loads(m)
        except json.JSONDecodeError:
            return {}
    return m or {}


async def _load_blocks(conn: asyncpg.Connection, doc: dict) -> list[dict]:
    t = parsers.normalize_type(doc["source_type"])
    if t == "web":
        markdown, web_meta = await parsers.fetch_web(
            doc["source_uri"], allowlist=settings.crawl_allowlist
        )
        await repo.create_web_source(
            conn, user_id=doc["user_id"], url=doc["source_uri"],
            canonical_url=web_meta.get("canonical_url"), content_hash=web_meta.get("content_hash"),
        )
        return parsers.parse_markdown(markdown)
    inline = _meta(doc).get("inline_text")
    if inline is not None:
        return parsers.parse(t, content=inline)
    return parsers.parse(t, path=doc["source_uri"])


async def _store_chunks(
    conn: asyncpg.Connection, router: ModelRouter, doc: dict, chunks: list[dict]
) -> int:
    vectors = await router.embed_adapter().embed_text([c["content"] for c in chunks])
    for ch, vector in zip(chunks, vectors):
        chunk_id = await repo.add_chunk(
            conn, document_id=doc["id"], chunk_index=ch["chunk_index"],
            content=ch["content"], token_count=ch["token_count"],
            metadata={"heading_path": ch["heading_path"], "page_number": ch["page_number"],
                      "content_hash": ch["content_hash"]},
        )
        payload = {"document_id": str(doc["id"]), "privacy_tier": doc["privacy_tier"],
                   "chunk_id": str(chunk_id)}
        await vector_store.upsert(chunk_id, vector, payload)
        await repo.add_embedding(
            conn, chunk_id=chunk_id, collection=settings.documents_collection,
            vector_id=str(chunk_id), model=settings.embed_model, dim=settings.embed_dim,
            version="v1",
        )
    return len(chunks)


async def run(conn: asyncpg.Connection, router: ModelRouter, *, document_id: uuid.UUID) -> dict:
    doc = await repo.get_document(conn, document_id)
    if doc is None:
        raise IngestionError("document not found")
    doc = dict(doc)
    job_id = await repo.create_job(conn, document_id=document_id, job_type="ingest")
    try:
        blocks = await _load_blocks(conn, doc)
        chunks = chunking.chunk_blocks(
            blocks, target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens, min_chars=settings.chunk_min_chars,
        )
        # Quality gate (doc 06 §11): nothing extractable -> not active.
        if not chunks:
            raise IngestionError("no usable chunks extracted (text below threshold)")
        n = await _store_chunks(conn, router, doc, chunks)
        await repo.set_document_status(conn, document_id, "active")
        await repo.finish_job(conn, job_id=job_id, status="done", metadata={"chunks": n})
        await core_repo.write_audit(
            conn, actor_type="system", actor_id=str(doc["user_id"]),
            event_type="document.ingested", target_type="document", target_id=str(document_id),
            metadata={"chunks": n, "privacy_tier": doc["privacy_tier"]},
        )
        return {"document_id": str(document_id), "status": "active", "chunks": n,
                "job_id": str(job_id)}
    except Exception as e:
        await repo.set_document_status(conn, document_id, "failed")
        await repo.finish_job(conn, job_id=job_id, status="failed", error_message=str(e))
        raise IngestionError(str(e)) from e
