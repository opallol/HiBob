"""image_generate flows through the gateway: high-risk -> ask, draft-only (ADR 0013/0015). Faked."""

import json
import uuid

from hibob_core.db import repositories as core_repo
from hibob_core.tools import gateway
from hibob_core.tools import repository as repo


def _patch(monkeypatch):
    async def get_tool_by_name(conn, name):
        return {"id": uuid.uuid4(), "name": name, "risk_level": "high",
                "tool_type": "internal", "enabled": True}

    async def get_trust(conn, *, tool_id, context):
        return 1.0

    async def create_tool_run(conn, **k):
        return uuid.uuid4()

    async def create_approval(conn, **k):
        return uuid.uuid4()

    async def set_tool_run(conn, **k):
        return None

    async def bump_trust(conn, **k):
        return 1.0

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_tool_by_name", get_tool_by_name)
    monkeypatch.setattr(repo, "get_trust", get_trust)
    monkeypatch.setattr(repo, "create_tool_run", create_tool_run)
    monkeypatch.setattr(repo, "create_approval", create_approval)
    monkeypatch.setattr(repo, "set_tool_run", set_tool_run)
    monkeypatch.setattr(repo, "bump_trust", bump_trust)
    monkeypatch.setattr(core_repo, "write_audit", audit)


async def test_image_generate_asks_even_at_max_trust(monkeypatch):
    _patch(monkeypatch)
    out = await gateway.request_tool(None, name="image_generate",
                                     input={"prompt": "a cat"}, reason="bikin gambar")
    assert out["status"] == "pending_approval"  # high risk -> never auto


async def test_approved_image_generate_is_draft(monkeypatch):
    _patch(monkeypatch)
    run_id = uuid.uuid4()
    captured = {}

    async def get_approval(conn, approval_id):
        return {"status": "pending", "payload_json": json.dumps(
            {"name": "image_generate", "input": {"prompt": "a cat"}, "context": "chat"})}

    async def get_run_by_approval(conn, approval_id):
        return {"id": run_id}

    async def decide_approval(conn, **k):
        return None

    async def set_tool_run(conn, *, tool_run_id, status, output_json=None, **k):
        if output_json is not None:
            captured["output"] = output_json

    monkeypatch.setattr(repo, "get_approval", get_approval)
    monkeypatch.setattr(repo, "get_run_by_approval", get_run_by_approval)
    monkeypatch.setattr(repo, "decide_approval", decide_approval)
    monkeypatch.setattr(repo, "set_tool_run", set_tool_run)

    out = await gateway.approve_run(None, approval_id=uuid.uuid4(), decision="approve")
    assert out["status"] == "succeeded"
    assert captured["output"]["published"] is False  # never auto-published (ADR 0015)
