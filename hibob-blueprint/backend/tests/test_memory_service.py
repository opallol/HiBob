"""Memory approval lifecycle: approval is human-only and only candidates can be approved."""

import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.memory import repository as repo
from hibob_core.memory import service
from hibob_core.memory import vector_store

MID = uuid.uuid4()
REVIEWER = core_repo.BOB_USER_ID


def _mem(status):
    return {
        "id": MID, "user_id": REVIEWER, "memory_type": "decision", "scope": "project",
        "title": "t", "content": "c", "status": status, "confidence": 0.9,
        "sensitivity": "internal", "created_at": None,
    }


async def test_approve_rejects_non_candidate(monkeypatch):
    async def get(conn, mid):
        return _mem("approved")  # already approved
    monkeypatch.setattr(repo, "get", get)

    with pytest.raises(service.MemoryError):
        await service.approve(None, object(), memory_id=MID, reviewer_user_id=REVIEWER)


async def test_approve_happy_path_embeds_and_reviews(monkeypatch):
    states = iter([_mem("candidate"), _mem("approved")])

    async def get(conn, mid):
        return next(states)

    async def set_status(conn, mid, status):
        return None

    async def embed_and_index(conn, router, mem):
        return [0.1, 0.2, 0.3]

    async def search(vector, *, scope, memory_type, limit):
        return []  # no conflicts

    reviews = {"n": 0}

    async def add_review(conn, **k):
        reviews["n"] += 1

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "set_status", set_status)
    monkeypatch.setattr(service, "_embed_and_index", embed_and_index)
    monkeypatch.setattr(vector_store, "search", search)
    monkeypatch.setattr(repo, "add_review", add_review)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await service.approve(None, object(), memory_id=MID, reviewer_user_id=REVIEWER)
    assert out["status"] == "approved"
    assert out["conflicts"] == []
    assert reviews["n"] == 1


async def test_reject_sets_status_and_removes_vector(monkeypatch):
    async def get(conn, mid):
        return _mem("candidate")

    set_calls = {"status": None}

    async def set_status(conn, mid, status):
        set_calls["status"] = status

    deleted = {"n": 0}

    async def delete(mid):
        deleted["n"] += 1

    async def add_review(conn, **k):
        return None

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "set_status", set_status)
    monkeypatch.setattr(vector_store, "delete", delete)
    monkeypatch.setattr(repo, "add_review", add_review)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await service.reject(None, memory_id=MID, reviewer_user_id=REVIEWER)
    assert out["status"] == "rejected"
    assert set_calls["status"] == "rejected"
    assert deleted["n"] == 1
