"""Memory graph service (Phase 2.5, ADR 0006, doc 04 §9a).

The relational DB + `memory_edges` IS the canonical graph; Qdrant stays semantic-only.
Edges are typed and directed; traversal uses a recursive CTE (repository.traverse) so no
separate graph database is introduced. This turns "second brain" questions like
"why did we move from X to Y?" into a queryable walk over `supersedes`/`depends_on` edges.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.memory import repository as repo
from hibob_core.memory.service import MemoryError

# Allowed relation types (ADR 0006). Anything else is rejected before it reaches the DB.
RELATION_TYPES = {"supersedes", "contradicts", "depends_on", "supports", "derived_from"}


async def create_edge(
    conn: asyncpg.Connection,
    *,
    from_id: uuid.UUID,
    to_id: uuid.UUID,
    relation_type: str,
    actor_user_id: uuid.UUID,
    confidence: float = 0.5,
    note: str | None = None,
) -> dict:
    if relation_type not in RELATION_TYPES:
        raise MemoryError(
            f"invalid relation_type '{relation_type}' (allowed: {sorted(RELATION_TYPES)})"
        )
    if from_id == to_id:
        raise MemoryError("an edge cannot connect a memory to itself")
    if await repo.get(conn, from_id) is None or await repo.get(conn, to_id) is None:
        raise MemoryError("memory not found")

    edge_id = await repo.add_edge(
        conn, from_id=from_id, to_id=to_id, relation_type=relation_type,
        confidence=confidence, note=note,
    )
    created = edge_id is not None  # None = duplicate suppressed by the unique index
    if created:
        await core_repo.write_audit(
            conn, actor_type="user", actor_id=str(actor_user_id),
            event_type="memory.edge.created", target_type="memory_edge",
            target_id=str(edge_id),
            metadata={"from": str(from_id), "to": str(to_id), "relation": relation_type},
        )
    return {
        "id": str(edge_id) if edge_id else None,
        "from_memory_id": str(from_id),
        "to_memory_id": str(to_id),
        "relation_type": relation_type,
        "created": created,
    }


async def get_edges(
    conn: asyncpg.Connection,
    memory_id: uuid.UUID,
    *,
    depth: int = 1,
    relation_types: list[str] | None = None,
) -> dict:
    """Edges reachable from `memory_id`. depth=1 = direct neighbours; depth>1 = multi-hop walk."""
    depth = max(1, min(depth, settings.graph_max_depth))
    if relation_types:
        bad = [r for r in relation_types if r not in RELATION_TYPES]
        if bad:
            raise MemoryError(f"invalid relation_type(s): {bad}")

    if depth == 1:
        raw = await repo.edges_for(conn, memory_id)
        edges = [_edge_payload(e) for e in raw]
    else:
        raw = await repo.traverse(
            conn, memory_id, relation_types=relation_types, max_depth=depth
        )
        edges = [_edge_payload(e, with_depth=True) for e in raw]

    # Collect the distinct node ids touched, so callers can fetch titles in one round-trip.
    node_ids: set[str] = {str(memory_id)}
    for e in edges:
        node_ids.add(e["from_memory_id"])
        node_ids.add(e["to_memory_id"])
    rows = await repo.fetch_by_ids(conn, [uuid.UUID(n) for n in node_ids])
    nodes = [
        {"id": nid, "title": rows[nid]["title"], "memory_type": rows[nid]["memory_type"],
         "scope": rows[nid]["scope"], "status": rows[nid]["status"]}
        for nid in node_ids if nid in rows
    ]
    return {"root": str(memory_id), "depth": depth, "nodes": nodes, "edges": edges}


def _edge_payload(e: dict, *, with_depth: bool = False) -> dict:
    out = {
        "id": str(e["id"]),
        "from_memory_id": str(e["memory_id_from"]),
        "to_memory_id": str(e["memory_id_to"]),
        "relation_type": e["relation_type"],
        "confidence": float(e["confidence"]) if e.get("confidence") is not None else None,
        "note": e.get("note"),
    }
    if with_depth:
        out["depth"] = e["depth"]
    return out
