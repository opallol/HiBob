"""Sandbox tool types through the gateway (Phase 7, ADR 0011). Faked."""

import uuid

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.sandbox import repository as sandbox_repo
from hibob_core.tools import gateway
from hibob_core.tools import repository as repo

BROWSER_TOOL = {
    "id": uuid.uuid4(), "name": "browser_open", "risk_level": "high", "tool_type": "browser",
    "enabled": True, "input_schema_json": {"constraints": {"allow_hosts": ["localhost"]}},
}


def _patch(monkeypatch):
    async def get_tool_by_name(conn, name):
        return dict(BROWSER_TOOL)

    async def get_trust(conn, *, tool_id, context):
        return 1.0

    async def create_tool_run(conn, **k):
        return uuid.uuid4()

    async def create_approval(conn, **k):
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_tool_by_name", get_tool_by_name)
    monkeypatch.setattr(repo, "get_trust", get_trust)
    monkeypatch.setattr(repo, "create_tool_run", create_tool_run)
    monkeypatch.setattr(repo, "create_approval", create_approval)
    monkeypatch.setattr(core_repo, "write_audit", audit)


async def test_browser_denied_when_sandbox_off(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(settings, "sandbox_backend", "off")
    out = await gateway.request_tool(None, name="browser_open", input={"url": "http://localhost"},
                                     reason="open ui")
    assert out["status"] == "denied"  # no sandbox -> default-deny (ADR 0011 guard)


async def test_browser_asks_when_sandbox_enabled(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(settings, "sandbox_backend", "noop")
    out = await gateway.request_tool(None, name="browser_open", input={"url": "http://localhost"},
                                     reason="open ui")
    # sandbox available -> no longer auto-denied; high risk -> ask (never auto, even at trust 1.0)
    assert out["status"] == "pending_approval"


async def test_approved_browser_runs_in_sandbox(monkeypatch):
    _patch(monkeypatch)
    monkeypatch.setattr(settings, "sandbox_backend", "noop")
    run_id = uuid.uuid4()
    sandbox_calls = {"created": 0, "finished": 0}

    async def get_approval(conn, approval_id):
        import json
        return {"status": "pending", "payload_json": json.dumps(
            {"name": "browser_open", "input": {"url": "http://localhost"}, "context": "chat"})}

    async def get_run_by_approval(conn, approval_id):
        return {"id": run_id}

    async def decide_approval(conn, **k):
        return None

    async def set_tool_run(conn, **k):
        return None

    async def bump_trust(conn, **k):
        return 1.0

    async def create_sandbox_run(conn, *, tool_run_id, spec):
        sandbox_calls["created"] += 1
        return uuid.uuid4()

    async def finish_sandbox_run(conn, **k):
        sandbox_calls["finished"] += 1

    monkeypatch.setattr(repo, "get_approval", get_approval)
    monkeypatch.setattr(repo, "get_run_by_approval", get_run_by_approval)
    monkeypatch.setattr(repo, "decide_approval", decide_approval)
    monkeypatch.setattr(repo, "set_tool_run", set_tool_run)
    monkeypatch.setattr(repo, "bump_trust", bump_trust)
    monkeypatch.setattr(sandbox_repo, "create_sandbox_run", create_sandbox_run)
    monkeypatch.setattr(sandbox_repo, "finish_sandbox_run", finish_sandbox_run)

    out = await gateway.approve_run(None, approval_id=uuid.uuid4(), decision="approve")
    assert out["status"] == "succeeded"
    assert sandbox_calls["created"] == 1 and sandbox_calls["finished"] == 1
