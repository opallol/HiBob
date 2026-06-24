"""Document retrieval (Phase 3, doc 06 §9/§10).

Dense vector search + privacy containment + source-referenced results. Containment mirrors memory
retrieval: a chunk more sensitive than the conversation tier never surfaces, so private/secret docs
can't leak into a cloud-eligible prompt (doc 06 §4, doc 08 §4). Embedding is local (router), so the
query itself never leaves the machine for private/secret conversations.
"""

from __future__ import annotations

import json
import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.knowledge import repository as repo
from hibob_core.knowledge import vector_store
from hibob_core.models.router import ModelRouter

_SENS_RANK = {"public": 0, "internal": 1, "private": 2, "secret": 3}


def _allowed_tiers(privacy_tier: str) -> list[str]:
    """Tiers at or below the conversation tier (never surface more-sensitive docs)."""
    ceiling = _SENS_RANK.get(privacy_tier, 1)
    return [t for t, r in _SENS_RANK.items() if r <= ceiling]


def _source_ref(row: dict) -> str:
    meta = row.get("metadata_json")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    heading = "/".join((meta or {}).get("heading_path") or [])
    base = row.get("source_uri") or row.get("title") or "document"
    return f"{base}#{heading}" if heading else base


async def retrieve(
    conn: asyncpg.Connection,
    router: ModelRouter,
    *,
    query: str,
    privacy_tier: str,
) -> list[dict]:
    """Return ranked active chunks: [{chunk_id, document_id, score, text, source}] (doc 06 §9)."""
    vector = (await router.embed_adapter().embed_text([query]))[0]
    hits = await vector_store.search(
        vector, allowed_tiers=_allowed_tiers(privacy_tier),
        limit=settings.doc_retrieval_candidate_k,
    )
    if not hits:
        return []

    rows = await repo.fetch_chunks_by_ids(conn, [uuid.UUID(h[0]) for h in hits])
    out: list[dict] = []
    for hit_id, score, _payload in hits:
        row = rows.get(hit_id)
        if row is None or row.get("doc_status") != "active":
            continue
        # Defensive double-check of containment against canonical metadata.
        if _SENS_RANK.get(row["privacy_tier"], 1) > _SENS_RANK.get(privacy_tier, 1):
            continue
        out.append({
            "chunk_id": hit_id,
            "document_id": str(row["document_id"]),
            "score": round(score, 4),
            "text": row["content"],
            "source": _source_ref(row),
        })
        if len(out) >= settings.doc_retrieval_top_k:
            break
    return out


def render_for_prompt(chunks: list[dict]) -> str:
    """Format retrieved chunks for context assembly (doc 06 §10: cite sources, don't fabricate)."""
    if not chunks:
        return ""
    lines = [f"- [{c['source']}] {c['text']}" for c in chunks]
    return (
        "Dokumen relevan (jawab berbasis bukti ini; sebut sumbernya; jangan mengarang sitasi; "
        "jika tidak cukup, katakan tidak cukup):\n" + "\n".join(lines)
    )
