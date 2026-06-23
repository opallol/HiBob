"""Agent Orchestrator (doc 02 §3.7) - chat loop + the Hermes seam.

The loop is deliberately small and grows by phase:
  Phase 1: assemble persona -> route model -> (cost gate if cloud) -> generate -> persist.
  Phase 2: memory recall is folded into context assembly (doc 04 §8).
  Phase 2.5: memories actually used are fed back as `used` calibration signals (ADR 0007).
  Phase 3: document chunks are recalled too, with source references (doc 06 §9/§10).
No tools / no multi-step agent loop yet - that arrives with the Tool Gateway (Phase 4).

THE HERMES SEAM
---------------
This is the single extension point where Hermes plugs in later (Phase 5) WITHOUT
touching Core. The future shape:
  - an `AgentBackend` ABC (separate from models.ModelAdapter) defines `run_agent(...)`;
  - Hermes is registered as ONE tool of tool_type='agent' in the Tool Gateway (tools/),
    governed by the Policy Engine (policy/, ADR 0005) and executed in the ephemeral
    Sandbox (ADR 0011), with secrets resolved via the Credential Vault (ADR 0014);
  - Core keeps identity/memory/policy/canonical DB. We read hermes-agent for patterns
    (sandbox backends, curator loop, footprint ladder) but never import it (ADR 0014,
    doc 07 §5.13). No Hibob safety mechanism may depend on Hermes's release cycle.
Phase 1 does NOT build any of this - it just keeps the boundary clean so it can.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

import asyncpg

from hibob_core.cost import breaker
from hibob_core.db import repositories as repo
from hibob_core.identity import persona
from hibob_core.knowledge import retrieval as doc_retrieval
from hibob_core.memory import calibration, retrieval
from hibob_core.models.router import ModelRouter
from hibob_core.multimodal import attachments as mm, stt, vision


@dataclass
class ChatOutcome:
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    response: str
    trace_id: str | None
    used_memory_ids: list[str] = field(default_factory=list)          # populated since Phase 2
    used_document_chunk_ids: list[str] = field(default_factory=list)  # populated since Phase 3 (RAG)
    tool_run_ids: list[str] = field(default_factory=list)             # empty until Phase 4 (tools)


class Orchestrator:
    def __init__(self, router: ModelRouter):
        self.router = router

    async def chat(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_message: str,
        privacy_tier: str,
        model_preference: str,
        trace_id: str | None,
        attachments: list | None = None,
    ) -> ChatOutcome:
        # Multimodal input (Phase 3.7): validate + split. AttachmentError propagates -> HTTP 400.
        images, audios = mm.split(attachments or [])

        # Audio -> transcript (always local). Fold into the text message so the whole downstream
        # path (memory/doc recall, persistence) is unchanged. Degrade gracefully if STT is absent.
        for att in audios:
            try:
                raw = mm.get_bytes(att)
                transcript = await asyncio.to_thread(stt.transcribe, raw, media_type=att.media_type)
                if transcript:
                    user_message = (user_message + "\n" + transcript).strip()
            except Exception:
                pass

        # Persist the user's turn first (text incl. any transcript; raw media is never persisted).
        await repo.add_message(
            conn, conversation_id=conversation_id, role="user",
            content=user_message, trace_id=trace_id,
        )

        system = await persona.assemble_system_prompt(conn, user_id)

        # Memory recall (Phase 2): retrieve relevant approved memories and add as context
        # (doc 04 §8). Privacy containment + conflict suppression handled inside retrieve().
        # Degrade gracefully: a retrieval failure must not break chat.
        used_memory_ids: list[str] = []
        try:
            memories = await retrieval.retrieve(
                conn, self.router, query=user_message, privacy_tier=privacy_tier
            )
            if memories:
                system = system + "\n\n" + retrieval.render_for_prompt(memories)
                used_memory_ids = [m["id"] for m in memories]
        except Exception:
            memories = []

        # Knowledge recall (Phase 3): retrieve relevant document chunks and add as context with
        # source references (doc 06 §9/§10). Same privacy containment as memory; degrade gracefully.
        used_document_chunk_ids: list[str] = []
        try:
            chunks = await doc_retrieval.retrieve(
                conn, self.router, query=user_message, privacy_tier=privacy_tier
            )
            if chunks:
                system = system + "\n\n" + doc_retrieval.render_for_prompt(chunks)
                used_document_chunk_ids = [c["chunk_id"] for c in chunks]
        except Exception:
            pass

        history = await repo.get_history(conn, conversation_id)  # includes the new user turn

        # Image input (Phase 3.7): rebuild the final user turn as multimodal blocks. The model
        # router still gates by privacy_tier, so a private/secret image can never go to cloud.
        if images and history:
            history = history[:-1] + [
                {"role": "user", "content": vision.build_user_blocks(user_message, images)}
            ]

        adapter = self.router.route(privacy_tier=privacy_tier, model_preference=model_preference)

        # Cost circuit breaker (ADR 0012): gate BEFORE any cloud call.
        check = None
        if adapter.is_cloud:
            check = await breaker.check_can_spend_cloud(conn, user_id)  # raises if over ceiling

        started = time.perf_counter()
        result = await adapter.generate_text(system=system, messages=history)
        latency_ms = int((time.perf_counter() - started) * 1000)

        model_run_id = await repo.record_model_run(
            conn,
            provider=result.provider,
            model=result.model,
            task_type="chat",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=latency_ms,
            cost_estimate=result.cost_estimate,
            trace_id=trace_id,
        )

        # Debit the ledger for cloud spend (ADR 0012).
        if adapter.is_cloud and check is not None:
            await breaker.debit(
                conn, check=check, model_run_id=model_run_id, amount=result.cost_estimate
            )

        message_id = await repo.add_message(
            conn, conversation_id=conversation_id, role="assistant",
            content=result.text, model_run_id=model_run_id, trace_id=trace_id,
        )

        # Calibration signal (Phase 2.5, ADR 0007): a memory that was recalled and used in an
        # answer without correction is weak positive evidence -> nudge its confidence up.
        # Degrade gracefully: a calibration failure must never break the chat response.
        for mem_id in used_memory_ids:
            try:
                await calibration.record_feedback(
                    conn, memory_id=uuid.UUID(mem_id), conversation_id=conversation_id,
                    event_type="used", actor_user_id=user_id,
                )
            except Exception:
                pass

        await repo.write_audit(
            conn, actor_type="assistant", actor_id=str(user_id),
            event_type="chat.responded", target_type="conversation",
            target_id=str(conversation_id),
            metadata={"provider": result.provider, "model": result.model,
                      "cost_estimate": result.cost_estimate,
                      "n_images": len(images), "n_audio": len(audios)},
        )

        return ChatOutcome(
            conversation_id=conversation_id,
            message_id=message_id,
            response=result.text,
            trace_id=trace_id,
            used_memory_ids=used_memory_ids,
            used_document_chunk_ids=used_document_chunk_ids,
        )
