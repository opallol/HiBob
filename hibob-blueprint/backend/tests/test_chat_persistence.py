"""Orchestrator persists both turns and only gates the cost breaker for cloud calls."""

import uuid

from hibob_core.agents import orchestrator as orch_mod
from hibob_core.agents.orchestrator import Orchestrator
from hibob_core.cost import breaker
from hibob_core.db import repositories as repo
from hibob_core.identity import persona
from hibob_core.models.base import GenerateResult


class _Adapter:
    def __init__(self, is_cloud: bool):
        self.provider = "anthropic" if is_cloud else "ollama"
        self.is_cloud = is_cloud

    async def generate_text(self, *, system, messages, model=None):
        return GenerateResult(
            text="halo Bob", provider=self.provider, model="m",
            input_tokens=10, output_tokens=5,
            cost_estimate=0.001 if self.is_cloud else 0.0,
        )


class _Router:
    def __init__(self, adapter):
        self._a = adapter

    def route(self, *, privacy_tier, model_preference):
        return self._a


def _patch_common(monkeypatch, added: list):
    async def add_message(conn, *, conversation_id, role, content, model_run_id=None, trace_id=None):
        added.append((role, content))
        return uuid.uuid4()

    async def assemble(conn, uid):
        return "SYSTEM"

    async def history(conn, cid):
        return [{"role": "user", "content": "hai"}]

    async def record_run(conn, **k):
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "add_message", add_message)
    monkeypatch.setattr(persona, "assemble_system_prompt", assemble)
    monkeypatch.setattr(repo, "get_history", history)
    monkeypatch.setattr(repo, "record_model_run", record_run)
    monkeypatch.setattr(repo, "write_audit", audit)


async def test_local_chat_persists_both_turns_without_breaker(monkeypatch):
    added: list = []
    _patch_common(monkeypatch, added)

    breaker_called = {"check": False}

    async def check(conn, uid):
        breaker_called["check"] = True

    monkeypatch.setattr(breaker, "check_can_spend_cloud", check)

    outcome = await Orchestrator(_Router(_Adapter(is_cloud=False))).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="hai", privacy_tier="internal", model_preference="local", trace_id=None,
    )

    assert outcome.response == "halo Bob"
    assert ("user", "hai") in added
    assert ("assistant", "halo Bob") in added
    assert breaker_called["check"] is False  # local never gates cost


async def test_cloud_chat_gates_and_debits(monkeypatch):
    added: list = []
    _patch_common(monkeypatch, added)

    calls = {"check": 0, "debit": 0}

    async def check(conn, uid):
        calls["check"] += 1
        return breaker.CeilingCheck(
            ceiling_id=uuid.uuid4(), ceiling_amount=5.0, spend_today=0.0
        )

    async def debit(conn, *, check, model_run_id, amount):
        calls["debit"] += 1
        return amount, False

    monkeypatch.setattr(breaker, "check_can_spend_cloud", check)
    monkeypatch.setattr(breaker, "debit", debit)

    await Orchestrator(_Router(_Adapter(is_cloud=True))).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="hai", privacy_tier="internal", model_preference="cloud", trace_id=None,
    )

    assert calls["check"] == 1
    assert calls["debit"] == 1
