"""Tool Gateway end-to-end policy flow (ADR 0005). Repo + handlers faked."""

import json
import uuid

from hibob_core.db import repositories as core_repo
from hibob_core.tools import gateway
from hibob_core.tools import repository as repo

TOOL_ID = uuid.uuid4()


def _tool(risk, name="memory_search", tool_type="internal"):
    return {"id": TOOL_ID, "name": name, "risk_level": risk, "tool_type": tool_type, "enabled": True}


def _patch(monkeypatch, *, risk, trust=0.0, handler=None, created=None):
    async def get_tool_by_name(conn, name):
        return _tool(risk, name=name)

    async def get_trust(conn, *, tool_id, context):
        return trust

    async def create_tool_run(conn, *, status, **k):
        if created is not None:
            created.append(status)
        return uuid.uuid4()

    async def set_tool_run(conn, **k):
        return None

    async def create_approval(conn, **k):
        return uuid.uuid4()

    async def bump_trust(conn, **k):
        return trust + 0.1

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_tool_by_name", get_tool_by_name)
    monkeypatch.setattr(repo, "get_trust", get_trust)
    monkeypatch.setattr(repo, "create_tool_run", create_tool_run)
    monkeypatch.setattr(repo, "set_tool_run", set_tool_run)
    monkeypatch.setattr(repo, "create_approval", create_approval)
    monkeypatch.setattr(repo, "bump_trust", bump_trust)
    monkeypatch.setattr(core_repo, "write_audit", audit)
    if handler is not None:
        monkeypatch.setattr(gateway, "HANDLERS", {"memory_search": handler, "draft_patch": handler})


async def test_low_risk_executes_and_bumps_trust(monkeypatch):
    calls = {"n": 0}

    async def handler(conn, inp):
        calls["n"] += 1
        return {"ok": True}

    _patch(monkeypatch, risk="low", handler=handler)
    out = await gateway.request_tool(None, name="memory_search", input={"q": "x"}, reason="cari")
    assert out["status"] == "succeeded"
    assert calls["n"] == 1
    assert out["trust_score"] == 0.1


async def test_high_risk_asks_and_does_not_execute(monkeypatch):
    calls = {"n": 0}

    async def handler(conn, inp):
        calls["n"] += 1
        return {}

    _patch(monkeypatch, risk="high", handler=handler)
    out = await gateway.request_tool(None, name="draft_patch", input={"file": "x"}, reason="patch")
    assert out["status"] == "pending_approval"
    assert out["approval_request_id"] is not None
    assert calls["n"] == 0  # never runs without approval


async def test_critical_risk_denied(monkeypatch):
    calls = {"n": 0}

    async def handler(conn, inp):
        calls["n"] += 1
        return {}

    _patch(monkeypatch, risk="critical", handler=handler)
    out = await gateway.request_tool(None, name="memory_search", input={}, reason="x")
    assert out["status"] == "denied"
    assert calls["n"] == 0


async def test_approve_executes_pending_run(monkeypatch):
    calls = {"n": 0}

    async def handler(conn, inp):
        calls["n"] += 1
        return {"ok": True}

    _patch(monkeypatch, risk="high", handler=handler)
    run_id = uuid.uuid4()

    async def get_approval(conn, approval_id):
        return {"status": "pending",
                "payload_json": json.dumps({"name": "draft_patch", "input": {"file": "x"}, "context": "chat"})}

    async def get_run_by_approval(conn, approval_id):
        return {"id": run_id}

    async def decide_approval(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_approval", get_approval)
    monkeypatch.setattr(repo, "get_run_by_approval", get_run_by_approval)
    monkeypatch.setattr(repo, "decide_approval", decide_approval)

    out = await gateway.approve_run(None, approval_id=uuid.uuid4(), decision="approve")
    assert out["status"] == "succeeded"
    assert calls["n"] == 1
