"""Orchestrator multimodal path (Phase 3.7): audio->transcript, image->multimodal message. Faked."""

import base64
import uuid

from hibob_core.agents import orchestrator as orch_mod
from hibob_core.agents.orchestrator import Orchestrator
from hibob_core.cost import breaker
from hibob_core.db import repositories as repo
from hibob_core.identity import persona
from hibob_core.models.base import GenerateResult
from hibob_core.multimodal.attachments import Attachment

_IMG = base64.b64encode(b"img").decode()
_AUD = base64.b64encode(b"aud").decode()


class _Adapter:
    is_cloud = False
    provider = "ollama"

    def __init__(self):
        self.seen_messages = None

    async def generate_text(self, *, system, messages, model=None):
        self.seen_messages = messages
        return GenerateResult(text="ok", provider="ollama", model="m",
                              input_tokens=1, output_tokens=1, cost_estimate=0.0)


class _Router:
    def __init__(self, adapter):
        self._a = adapter

    def route(self, *, privacy_tier, model_preference):
        return self._a


def _patch(monkeypatch, added):
    async def add_message(conn, *, conversation_id, role, content, model_run_id=None, trace_id=None):
        added.append((role, content))
        return uuid.uuid4()

    async def assemble(conn, uid):
        return "SYSTEM"

    async def history(conn, cid):
        # mimic get_history: returns the just-persisted user turn as the last item
        return [{"role": "user", "content": added[-1][1] if added else "hai"}]

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


async def test_audio_is_transcribed_into_the_message(monkeypatch):
    added: list = []
    _patch(monkeypatch, added)
    monkeypatch.setattr(orch_mod.stt, "transcribe", lambda raw, media_type=None: "halo dari suara")

    await Orchestrator(_Router(_Adapter())).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="dengar ini", privacy_tier="internal", model_preference="local", trace_id=None,
        attachments=[Attachment(type="audio", media_type="audio/wav", data=_AUD)],
    )
    user_turn = next(c for r, c in added if r == "user")
    assert "halo dari suara" in user_turn


async def test_image_becomes_multimodal_final_message(monkeypatch):
    added: list = []
    _patch(monkeypatch, added)
    adapter = _Adapter()

    await Orchestrator(_Router(adapter)).chat(
        None, user_id=repo.BOB_USER_ID, conversation_id=uuid.uuid4(),
        user_message="apa ini?", privacy_tier="internal", model_preference="local", trace_id=None,
        attachments=[Attachment(type="image", media_type="image/png", data=_IMG)],
    )
    last = adapter.seen_messages[-1]
    assert isinstance(last["content"], list)
    assert any(b.get("type") == "image" and b["data"] == _IMG for b in last["content"])
