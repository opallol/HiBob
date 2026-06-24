"""Project lifecycle (Phase 8). Repo faked."""

import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.projects import repository as repo
from hibob_core.projects import service

USER = core_repo.BOB_USER_ID


async def test_create_project(monkeypatch):
    async def name_exists(conn, *, user_id, name):
        return False

    async def create(conn, **k):
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "name_exists", name_exists)
    monkeypatch.setattr(repo, "create", create)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await service.create_project(None, user_id=USER, name="Hibob", description="x")
    assert out["name"] == "Hibob" and out["status"] == "active"


async def test_duplicate_name_rejected(monkeypatch):
    async def name_exists(conn, *, user_id, name):
        return True
    monkeypatch.setattr(repo, "name_exists", name_exists)
    with pytest.raises(service.ProjectError):
        await service.create_project(None, user_id=USER, name="Hibob")


async def test_blank_name_rejected():
    with pytest.raises(service.ProjectError):
        await service.create_project(None, user_id=USER, name="   ")


async def test_archive(monkeypatch):
    async def get(conn, pid):
        return {"id": str(pid)}

    async def set_status(conn, pid, status):
        return None

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "set_status", set_status)
    monkeypatch.setattr(core_repo, "write_audit", audit)
    out = await service.archive_project(None, project_id=uuid.uuid4(), user_id=USER)
    assert out["status"] == "archived"
