"""Memory graph (ADR 0006): typed edges, traversal assembly, auto-edge on supersede."""

import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.memory import graph
from hibob_core.memory import repository as repo
from hibob_core.memory import service
from hibob_core.memory import vector_store

A = uuid.uuid4()
B = uuid.uuid4()
REVIEWER = core_repo.BOB_USER_ID


async def test_create_edge_rejects_unknown_relation():
    with pytest.raises(service.MemoryError):
        await graph.create_edge(
            None, from_id=A, to_id=B, relation_type="causes", actor_user_id=REVIEWER
        )


async def test_create_edge_rejects_self_loop():
    with pytest.raises(service.MemoryError):
        await graph.create_edge(
            None, from_id=A, to_id=A, relation_type="supports", actor_user_id=REVIEWER
        )


async def test_create_edge_happy_path(monkeypatch):
    async def get(conn, mid):
        return {"id": mid}

    async def add_edge(conn, **k):
        return uuid.uuid4()

    audits = {"n": 0}

    async def audit(conn, **k):
        audits["n"] += 1

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "add_edge", add_edge)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await graph.create_edge(
        None, from_id=A, to_id=B, relation_type="supersedes", actor_user_id=REVIEWER
    )
    assert out["created"] is True
    assert out["relation_type"] == "supersedes"
    assert audits["n"] == 1


async def test_create_edge_duplicate_is_noop(monkeypatch):
    async def get(conn, mid):
        return {"id": mid}

    async def add_edge(conn, **k):
        return None  # unique index suppressed the duplicate

    audits = {"n": 0}

    async def audit(conn, **k):
        audits["n"] += 1

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "add_edge", add_edge)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await graph.create_edge(
        None, from_id=A, to_id=B, relation_type="supports", actor_user_id=REVIEWER
    )
    assert out["created"] is False
    assert audits["n"] == 0  # no audit row for a no-op


async def test_get_edges_depth1_assembles_nodes_and_edges(monkeypatch):
    edge = {
        "id": uuid.uuid4(), "memory_id_from": A, "memory_id_to": B,
        "relation_type": "depends_on", "confidence": 0.5, "note": None,
    }

    async def edges_for(conn, mid):
        return [edge]

    async def fetch_by_ids(conn, ids):
        return {
            str(A): {"title": "a", "memory_type": "decision", "scope": "project", "status": "approved"},
            str(B): {"title": "b", "memory_type": "decision", "scope": "project", "status": "approved"},
        }

    monkeypatch.setattr(repo, "edges_for", edges_for)
    monkeypatch.setattr(repo, "fetch_by_ids", fetch_by_ids)

    out = await graph.get_edges(None, A, depth=1)
    assert out["depth"] == 1
    assert len(out["edges"]) == 1
    assert out["edges"][0]["relation_type"] == "depends_on"
    assert {n["id"] for n in out["nodes"]} == {str(A), str(B)}


async def test_supersede_creates_supersedes_edge(monkeypatch):
    captured = {"edge": None}

    async def get(conn, mid):
        return {"id": mid}

    async def set_superseded(conn, mid, by):
        return None

    async def delete(mid):
        return None

    async def add_edge(conn, *, from_id, to_id, relation_type, **k):
        captured["edge"] = (from_id, to_id, relation_type)
        return uuid.uuid4()

    async def add_review(conn, **k):
        return None

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "set_superseded", set_superseded)
    monkeypatch.setattr(vector_store, "delete", delete)
    monkeypatch.setattr(repo, "add_edge", add_edge)
    monkeypatch.setattr(repo, "add_review", add_review)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    await service.supersede(None, memory_id=A, by_memory_id=B, reviewer_user_id=REVIEWER)
    # new (B) supersedes old (A)
    assert captured["edge"] == (B, A, "supersedes")
