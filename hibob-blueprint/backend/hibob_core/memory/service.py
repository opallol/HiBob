"""Memory lifecycle: approve / reject / supersede, embedding+indexing, minimal conflict.

Hard rules (doc 04 §6, ADR 0007): approval is human-only; nothing here auto-promotes a
candidate. Embedding is local (router.embed_adapter) so private/secret memory never hits cloud.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.memory import repository as repo
from hibob_core.memory import vector_store
from hibob_core.models.router import ModelRouter

_CONFLICT_SIMILARITY = 0.90  # same (scope,type) above this = potential conflict


class MemoryError(Exception):
    pass


def _payload(mem: dict) -> dict:
    return {
        "memory_id": str(mem["id"]),
        "user_id": str(mem["user_id"]),
        "memory_type": mem["memory_type"],
        "scope": mem["scope"],
        "status": mem["status"],
        "sensitivity": mem["sensitivity"],
        "confidence": float(mem["confidence"]),
        "created_at": mem["created_at"].isoformat() if mem.get("created_at") else None,
    }


async def _embed_and_index(
    conn: asyncpg.Connection, router: ModelRouter, mem: dict
) -> list[float]:
    text = f"{mem['title']}\n{mem['content']}"
    vector = (await router.embed_adapter().embed_text([text]))[0]
    await vector_store.upsert(mem["id"], vector, _payload(mem))
    await repo.add_embedding(
        conn, memory_id=mem["id"], collection=settings.memory_collection,
        vector_id=str(mem["id"]), model=settings.embed_model, dim=settings.embed_dim,
        version="v1",
    )
    return vector


async def approve(
    conn: asyncpg.Connection,
    router: ModelRouter,
    *,
    memory_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    note: str | None = None,
) -> dict:
    mem = await repo.get(conn, memory_id)
    if mem is None:
        raise MemoryError("memory not found")
    if mem["status"] != "candidate":
        raise MemoryError(f"only candidates can be approved (status={mem['status']})")

    await repo.set_status(conn, memory_id, "approved")
    mem = dict(await repo.get(conn, memory_id))  # re-read with status=approved
    vector = await _embed_and_index(conn, router, mem)

    # Minimal conflict detection (doc 04 §9): same scope+type, high similarity, different row.
    conflicts: list[str] = []
    hits = await vector_store.search(
        vector, scope=mem["scope"], memory_type=mem["memory_type"],
        limit=5,
    )
    for hit_id, score, _ in hits:
        if hit_id != str(memory_id) and score >= _CONFLICT_SIMILARITY:
            cid = await repo.add_conflict(
                conn, memory_id_a=uuid.UUID(hit_id), memory_id_b=memory_id,
                conflict_type="duplicate_or_contradiction",
            )
            conflicts.append(str(cid))
            # ADR 0006 (doc 04 §9): a conflict IS a `contradicts` edge in the memory graph.
            await repo.add_edge(
                conn, from_id=uuid.UUID(hit_id), to_id=memory_id,
                relation_type="contradicts", confidence=round(float(score), 3),
                note=f"conflict {cid}",
            )

    await repo.add_review(
        conn, memory_id=memory_id, reviewer_user_id=reviewer_user_id,
        decision="approved", note=note,
    )
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(reviewer_user_id),
        event_type="memory.approved", target_type="memory", target_id=str(memory_id),
        metadata={"conflicts": conflicts},
    )
    return {"id": str(memory_id), "status": "approved", "conflicts": conflicts}


async def reject(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    note: str | None = None,
) -> dict:
    mem = await repo.get(conn, memory_id)
    if mem is None:
        raise MemoryError("memory not found")
    await repo.set_status(conn, memory_id, "rejected")
    await vector_store.delete(memory_id)  # no-op if never indexed
    await repo.add_review(
        conn, memory_id=memory_id, reviewer_user_id=reviewer_user_id,
        decision="rejected", note=note,
    )
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(reviewer_user_id),
        event_type="memory.rejected", target_type="memory", target_id=str(memory_id),
    )
    return {"id": str(memory_id), "status": "rejected"}


async def supersede(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    by_memory_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
) -> dict:
    if await repo.get(conn, memory_id) is None or await repo.get(conn, by_memory_id) is None:
        raise MemoryError("memory not found")
    await repo.set_superseded(conn, memory_id, by_memory_id)
    await vector_store.delete(memory_id)  # superseded memory stops surfacing
    # ADR 0006 (doc 04 §9 step 5): record the supersession as a graph edge (new -> old).
    await repo.add_edge(
        conn, from_id=by_memory_id, to_id=memory_id, relation_type="supersedes",
    )
    await repo.add_review(
        conn, memory_id=memory_id, reviewer_user_id=reviewer_user_id,
        decision="superseded", note=f"superseded_by={by_memory_id}",
    )
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(reviewer_user_id),
        event_type="memory.superseded", target_type="memory", target_id=str(memory_id),
        metadata={"superseded_by": str(by_memory_id)},
    )
    return {"id": str(memory_id), "status": "superseded", "superseded_by": str(by_memory_id)}


async def reindex_approved(conn: asyncpg.Connection, router: ModelRouter) -> int:
    """Embed+index any approved memory missing a vector (e.g. DB seeds). Idempotent."""
    pending = await repo.approved_without_embedding(conn)
    for mem in pending:
        await _embed_and_index(conn, router, mem)
    return len(pending)
