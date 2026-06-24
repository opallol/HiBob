"""Unified multi-source recall (Phase 8) - the "second brain" query.

Merges approved-memory recall and document recall into one ranked, source-labeled list. Each source
already enforces privacy containment (memory/retrieval, knowledge/retrieval), so a private/secret
item never surfaces into a lower-tier query here either. Scores from the two sources are on different
scales, so each list is normalized to [0,1] by its own max before merging (rank-preserving, fair).
"""

from __future__ import annotations

import asyncpg

from hibob_core.config import settings
from hibob_core.knowledge import retrieval as doc_retrieval
from hibob_core.memory import retrieval as mem_retrieval
from hibob_core.models.router import ModelRouter


def _normalize(items: list[dict]) -> None:
    top = max((i["score"] for i in items), default=0.0)
    if top > 0:
        for i in items:
            i["score"] = round(i["score"] / top, 4)


async def recall(
    conn: asyncpg.Connection,
    router: ModelRouter,
    *,
    query: str,
    privacy_tier: str = "internal",
    project: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return merged [{source_type, id, text, label, score}] across memory + documents."""
    limit = limit or settings.recall_top_k

    mems = await mem_retrieval.retrieve(
        conn, router, query=query, privacy_tier=privacy_tier, scope=project
    )
    docs = await doc_retrieval.retrieve(conn, router, query=query, privacy_tier=privacy_tier)

    mem_items = [
        {"source_type": "memory", "id": m["id"], "text": m["content"],
         "label": f"{m['memory_type']}/{m['scope']}: {m['title']}", "score": m["final_score"]}
        for m in mems
    ]
    doc_items = [
        {"source_type": "document", "id": d["chunk_id"], "text": d["text"],
         "label": d["source"], "score": d["score"]}
        for d in docs
    ]
    _normalize(mem_items)
    _normalize(doc_items)

    merged = mem_items + doc_items
    merged.sort(key=lambda i: i["score"], reverse=True)
    return merged[:limit]
