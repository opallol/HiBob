"""Self-build proposals run through the gateway with dynamic risk (ADR 0013). Faked."""

import uuid

from hibob_core.db import repositories as core_repo
from hibob_core.tools import gateway
from hibob_core.tools import repository as repo


def _patch(monkeypatch, *, base_risk, trust):
    async def get_tool_by_name(conn, name):
        return {"id": uuid.uuid4(), "name": name, "risk_level": base_risk,
                "tool_type": "internal", "enabled": True}

    async def get_trust(conn, *, tool_id, context):
        return trust

    async def create_tool_run(conn, **k):
        return uuid.uuid4()

    async def create_approval(conn, **k):
        return uuid.uuid4()

    async def set_tool_run(conn, **k):
        return None

    async def bump_trust(conn, **k):
        return min(1.0, trust + 0.1)

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_tool_by_name", get_tool_by_name)
    monkeypatch.setattr(repo, "get_trust", get_trust)
    monkeypatch.setattr(repo, "create_tool_run", create_tool_run)
    monkeypatch.setattr(repo, "create_approval", create_approval)
    monkeypatch.setattr(repo, "set_tool_run", set_tool_run)
    monkeypatch.setattr(repo, "bump_trust", bump_trust)
    monkeypatch.setattr(core_repo, "write_audit", audit)


async def test_sensitive_path_forces_ask_even_at_max_trust(monkeypatch):
    _patch(monkeypatch, base_risk="medium", trust=1.0)
    out = await gateway.request_tool(
        None, name="propose_blueprint_update",
        input={"summary": "tweak", "paths": ["backend/hibob_core/policy/engine.py"]},
        reason="update policy doc",
    )
    assert out["risk_level"] == "high"           # classifier raised it
    assert out["status"] == "pending_approval"   # high never auto, even at trust 1.0
    assert out["approval_request_id"] is not None


async def test_ordinary_path_keeps_base_risk(monkeypatch):
    _patch(monkeypatch, base_risk="medium", trust=1.0)
    out = await gateway.request_tool(
        None, name="propose_blueprint_update",
        input={"summary": "tweak", "paths": ["docs/16_GLOSSARY.md"]},
        reason="update glossary",
    )
    # medium + trust >= threshold -> auto-allow (executes the draft handler)
    assert out["risk_level"] == "medium"
    assert out["status"] == "succeeded"
