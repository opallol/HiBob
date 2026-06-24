"""Cross-session recurring-open-question reflection (Phase 8). Scans faked."""

from hibob_core.db import repositories as core_repo
from hibob_core.reflection import repository as repo
from hibob_core.reflection import service

USER = core_repo.BOB_USER_ID


async def test_recurring_question_becomes_a_finding(monkeypatch):
    created = []

    async def empty(conn, *a, **k):
        return []

    async def recurring(conn, *, min_count, limit):
        return [{"question": "Pakai Postgres atau SQLite?", "n": 3}]

    async def exists(conn, *, reflection_type, key_id):
        return False

    async def create_reflection(conn, **k):
        created.append(k["reflection_type"])
        import uuid
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "open_conflicts", empty)
    monkeypatch.setattr(repo, "untested_assumptions", empty)
    monkeypatch.setattr(repo, "stale_sources", empty)
    monkeypatch.setattr(repo, "recurring_open_questions", recurring)
    monkeypatch.setattr(repo, "reflection_exists", exists)
    monkeypatch.setattr(repo, "create_reflection", create_reflection)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await service.run(None, user_id=USER)
    assert out["created"] == 1
    assert created == ["recurring_open_question"]
