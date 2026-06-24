"""DB access for knowledge tables (service-layer; API/UI never touch the DB directly).

Mirrors the shape of memory/repository.py. Qdrant is the index; canonical chunk text lives here.
"""

from __future__ import annotations

import json
import uuid

import asyncpg


# ---- web_sources ----

async def create_web_source(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    url: str,
    canonical_url: str | None,
    content_hash: str | None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO web_sources (user_id, url, canonical_url, crawl_status, content_hash, last_crawled_at)
        VALUES ($1,$2,$3,'done',$4, now()) RETURNING id
        """,
        user_id, url, canonical_url, content_hash,
    )
    return row["id"]


# ---- documents ----

async def create_document(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    title: str,
    source_type: str,
    source_uri: str | None,
    privacy_tier: str,
    file_hash: str | None = None,
    web_source_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO documents
            (user_id, title, source_type, source_uri, web_source_id, file_hash,
             privacy_tier, status, metadata_json)
        VALUES ($1,$2,$3,$4,$5,$6,$7,'pending',$8) RETURNING id
        """,
        user_id, title, source_type, source_uri, web_source_id, file_hash,
        privacy_tier, json.dumps(metadata or {}),
    )
    return row["id"]


async def get_document(conn: asyncpg.Connection, document_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM documents WHERE id = $1", document_id)


async def set_document_status(
    conn: asyncpg.Connection, document_id: uuid.UUID, status: str
) -> None:
    await conn.execute(
        "UPDATE documents SET status = $2, updated_at = now() WHERE id = $1",
        document_id, status,
    )


# ---- document_chunks ----

async def add_chunk(
    conn: asyncpg.Connection,
    *,
    document_id: uuid.UUID,
    chunk_index: int,
    content: str,
    token_count: int | None,
    metadata: dict | None = None,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO document_chunks (document_id, chunk_index, content, token_count, metadata_json)
        VALUES ($1,$2,$3,$4,$5) RETURNING id
        """,
        document_id, chunk_index, content, token_count, json.dumps(metadata or {}),
    )
    return row["id"]


async def fetch_chunks_by_ids(conn: asyncpg.Connection, ids: list[uuid.UUID]) -> dict[str, dict]:
    """Map chunk_id(str) -> row for the candidate set returned by Qdrant."""
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT c.id, c.document_id, c.content, c.metadata_json,
               d.title, d.source_uri, d.privacy_tier, d.status AS doc_status
        FROM document_chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.id = ANY($1::uuid[])
        """,
        ids,
    )
    return {str(r["id"]): dict(r) for r in rows}


async def search_sql(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    q: str | None,
    privacy_tier: str | None,
    limit: int = 50,
) -> list[dict]:
    """Keyword/metadata fallback search over active chunks."""
    clauses = ["d.user_id = $1", "d.status = 'active'"]
    args: list = [user_id]
    if privacy_tier:
        args.append(privacy_tier)
        clauses.append(f"d.privacy_tier = ${len(args)}")
    if q:
        args.append(f"%{q}%")
        clauses.append(f"c.content ILIKE ${len(args)}")
    args.append(limit)
    rows = await conn.fetch(
        f"""
        SELECT c.id, c.document_id, c.content, d.title, d.source_uri, d.privacy_tier
        FROM document_chunks c JOIN documents d ON d.id = c.document_id
        WHERE {' AND '.join(clauses)}
        ORDER BY c.created_at DESC LIMIT ${len(args)}
        """,
        *args,
    )
    return [dict(r) for r in rows]


# ---- document_embeddings ----

async def add_embedding(
    conn: asyncpg.Connection,
    *,
    chunk_id: uuid.UUID,
    collection: str,
    vector_id: str,
    model: str,
    dim: int,
    version: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO document_embeddings
            (chunk_id, vector_collection, vector_id, embedding_model, embedding_dim, embedding_version)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        chunk_id, collection, vector_id, model, dim, version,
    )


# ---- ingestion_jobs ----

async def create_job(
    conn: asyncpg.Connection, *, document_id: uuid.UUID, job_type: str
) -> uuid.UUID:
    row = await conn.fetchrow(
        "INSERT INTO ingestion_jobs (document_id, job_type, status, started_at) "
        "VALUES ($1,$2,'running', now()) RETURNING id",
        document_id, job_type,
    )
    return row["id"]


async def finish_job(
    conn: asyncpg.Connection,
    *,
    job_id: uuid.UUID,
    status: str,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    await conn.execute(
        "UPDATE ingestion_jobs SET status=$2, error_message=$3, finished_at=now(), "
        "metadata_json=$4 WHERE id=$1",
        job_id, status, error_message, json.dumps(metadata or {}),
    )


async def get_job(conn: asyncpg.Connection, job_id: uuid.UUID) -> dict | None:
    row = await conn.fetchrow("SELECT * FROM ingestion_jobs WHERE id = $1", job_id)
    return dict(row) if row else None
