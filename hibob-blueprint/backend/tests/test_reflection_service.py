"""Reflective sibling job (ADR 0010): finds per category, dedups, stays read-only. Deps faked."""

import datetime
import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.reflection import repository as repo
from hibob_core.reflection import service

USER = core_repo.BOB_USER_ID


def _conflict():
    return {"id": uuid.uuid4(), "memory_id_a": uuid.uuid4(), "memory_id_b": uuid.uuid4(),
            "conflict_type": "duplicate_or_contradiction", "severity": "medium",
            "title_a": "PHP", "title_b": "Python"}


def _assumption():
    return {"edge_id": uuid.uuid4(), "memory_id_from": uuid.uuid4(), "memory_id_to": uuid.uuid4(),
            "title": "asumsi performa", "confidence": 0.2}


def _stale():
    return {"document_id": uuid.uuid4(), "title": "Doc Lama",
            "last_crawled_at": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
            "url": "http://example.com/x"}


def _patch_writes(monkeypatch, created):
    async def create_reflection(conn, **k):
        rid = uuid.uuid4()
        created.append(k["reflection_type"])
        return rid

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "create_reflection", create_reflection)
    monkeypatch.setattr(core_repo, "write_audit", audit)


async def test_run_creates_one_finding_per_category(monkeypatch):
    created: list[str] = []

    async def open_conflicts(conn, limit):
        return [_conflict()]

    async def untested(conn, *, max_conf, limit):
        return [_assumption()]

    async def stale(conn, *, older_than_days, limit):
        return [_stale()]

    async def exists(conn, *, reflection_type, key_id):
        return False

    monkeypatch.setattr(repo, "open_conflicts", open_conflicts)
    monkeypatch.setattr(repo, "untested_assumptions", untested)
    monkeypatch.setattr(repo, "stale_sources", stale)
    monkeypatch.setattr(repo, "reflection_exists", exists)
    _patch_writes(monkeypatch, created)

    out = await service.run(None, user_id=USER)
    assert out["created"] == 3
    assert set(created) == {"conflict_scan", "untested_assumption", "stale_source"}


async def test_dedup_skips_existing_findings(monkeypatch):
    created: list[str] = []

    async def open_conflicts(conn, limit):
        return [_conflict()]

    async def empty(conn, **k):
        return []

    async def exists(conn, *, reflection_type, key_id):
        return True  # an open finding already references this

    monkeypatch.setattr(repo, "open_conflicts", open_conflicts)
    monkeypatch.setattr(repo, "untested_assumptions", empty)
    monkeypatch.setattr(repo, "stale_sources", empty)
    monkeypatch.setattr(repo, "reflection_exists", exists)
    _patch_writes(monkeypatch, created)

    out = await service.run(None, user_id=USER)
    assert out["created"] == 0
    assert created == []


async def test_set_status_rejects_invalid():
    with pytest.raises(service.ReflectionError):
        await service.set_status(None, reflection_id=uuid.uuid4(), status="bogus")
