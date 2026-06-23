"""Retrieval scoring + privacy containment + conflict suppression (deps faked)."""

import uuid
from datetime import datetime, timezone

from hibob_core.memory import retrieval
from hibob_core.memory import vector_store


class _EmbedAdapter:
    async def embed_text(self, texts, model=None):
        return [[0.1, 0.2, 0.3]]


class _Router:
    def embed_adapter(self):
        return _EmbedAdapter()


def _row(mid, sensitivity="internal", confidence=0.9, mtype="decision"):
    return {
        "memory_type": mtype, "scope": "project", "title": f"t-{mid[:4]}",
        "content": "c", "status": "approved", "confidence": confidence,
        "sensitivity": sensitivity, "created_at": datetime.now(timezone.utc),
    }


async def test_privacy_containment_excludes_more_sensitive(monkeypatch):
    secret_id = str(uuid.uuid4())
    internal_id = str(uuid.uuid4())

    async def fake_search(vector, *, scope, memory_type, limit):
        return [(secret_id, 0.95, {}), (internal_id, 0.90, {})]

    async def fake_fetch(conn, ids):
        return {secret_id: _row(secret_id, "secret"), internal_id: _row(internal_id, "internal")}

    async def fake_conflicts(conn):
        return set()

    monkeypatch.setattr(vector_store, "search", fake_search)
    monkeypatch.setattr(retrieval.repo, "fetch_by_ids", fake_fetch)
    monkeypatch.setattr(retrieval, "_open_conflict_ids", fake_conflicts)

    # internal-tier conversation must NOT surface the secret memory
    out = await retrieval.retrieve(None, _Router(), query="x", privacy_tier="internal")
    ids = [m["id"] for m in out]
    assert internal_id in ids
    assert secret_id not in ids


async def test_secret_tier_sees_secret(monkeypatch):
    secret_id = str(uuid.uuid4())

    async def fake_search(vector, *, scope, memory_type, limit):
        return [(secret_id, 0.95, {})]

    async def fake_fetch(conn, ids):
        return {secret_id: _row(secret_id, "secret")}

    async def fake_conflicts(conn):
        return set()

    monkeypatch.setattr(vector_store, "search", fake_search)
    monkeypatch.setattr(retrieval.repo, "fetch_by_ids", fake_fetch)
    monkeypatch.setattr(retrieval, "_open_conflict_ids", fake_conflicts)

    out = await retrieval.retrieve(None, _Router(), query="x", privacy_tier="secret")
    assert out and out[0]["id"] == secret_id


async def test_conflict_suppression_downranks(monkeypatch):
    clean_id = str(uuid.uuid4())
    conflicted_id = str(uuid.uuid4())

    async def fake_search(vector, *, scope, memory_type, limit):
        # conflicted has higher semantic score but should be halved
        return [(conflicted_id, 0.99, {}), (clean_id, 0.80, {})]

    async def fake_fetch(conn, ids):
        return {clean_id: _row(clean_id, confidence=0.8),
                conflicted_id: _row(conflicted_id, confidence=0.8)}

    async def fake_conflicts(conn):
        return {conflicted_id}

    monkeypatch.setattr(vector_store, "search", fake_search)
    monkeypatch.setattr(retrieval.repo, "fetch_by_ids", fake_fetch)
    monkeypatch.setattr(retrieval, "_open_conflict_ids", fake_conflicts)

    out = await retrieval.retrieve(None, _Router(), query="x", privacy_tier="internal")
    # clean memory should now rank above the conflicted one despite lower semantic score
    assert out[0]["id"] == clean_id
