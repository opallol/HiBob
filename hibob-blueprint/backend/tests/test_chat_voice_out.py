"""Chat voice-out (Phase 9, ADR 0015): respond_voice -> audio artifact. Faked."""

import uuid

from hibob_core.cost import breaker
from hibob_core.db import repositories as repo
from hibob_core.identity import persona
from hibob_core.models.base import GenerateResult
from hibob_core.multimodal import tts


class _Adapter:
    is_cloud = False
    provider = "ollama"

    async def generate_text(self, *, system, messages, model=None):
        return GenerateResult(text="halo Bob", provider="ollama", model="m",
                              input_tokens=1, output_tokens=1, cost_estimate=0.0)


class _Router:
    def route(self, *, privacy_tier, model_preference):
        return _Adapter()


def _patch(monkeypatch):
    async def add_message(conn, **k):
        return uuid.uuid4()

    async def assemble(conn, uid):
        return "SYSTEM"

    async def history(conn, cid):
        return [{"role": "user", "content": "hai"}]

    async def record_run(conn, **k):
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    async def check(conn, uid):
        return None

    monkeypatch.setattr(repo, "add_message", add_message)
    monkeypatch.setattr(persona, "assemble_system_prompt", assemble)
    monkeypatch.setattr(repo, "get_history", history)
    monkeypatch.setattr(repo, "record_model_run", record_run)
    monkeypatch.setattr(repo, "write_audit", audit)
    monkeypatch.setattr(breaker, "check_can_spend_cloud", check)


async def test_respond_voice_adds_audio_artifact(monkeypatch):
    from hibob_core.agents.orchestrator import Orchestrator
    _patch(monkeypatch)
    monkeypatch.setattr(tts, "synthesize", lambda text: {"type": "audio", "ref": "aud-x"})

    outcome = await Orchestrator(_Router()).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="hai", privacy_tier="internal", model_preference="local", trace_id=None,
        respond_voice=True,
    )
    assert len(outcome.artifacts) == 1
    assert outcome.artifacts[0]["type"] == "audio"


async def test_no_voice_means_no_artifacts(monkeypatch):
    from hibob_core.agents.orchestrator import Orchestrator
    _patch(monkeypatch)
    outcome = await Orchestrator(_Router()).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="hai", privacy_tier="internal", model_preference="local", trace_id=None,
    )
    assert outcome.artifacts == []
