"""Conversation API (doc 13 §3): POST /v1/chat, GET /v1/conversations/{id}."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hibob_core.agents.orchestrator import Orchestrator
from hibob_core.cost.breaker import BudgetExceeded
from hibob_core.db import repositories as repo
from hibob_core.db.pool import get_pool
from hibob_core.models.router import CloudUnavailable, ModelRouter, PrivacyViolation
from hibob_core.telemetry import start_chat_span

router = APIRouter()
_orchestrator = Orchestrator(ModelRouter())


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str
    mode: str = "chat"                # chat | blueprint | debug | coding
    privacy_tier: str = "internal"    # public | internal | private | secret
    model_preference: str = "auto"    # auto | local | cloud


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    response: str
    trace_id: str | None = None
    used_memory_ids: list[str] = Field(default_factory=list)
    used_document_chunk_ids: list[str] = Field(default_factory=list)
    tool_run_ids: list[str] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    pool = get_pool()
    user_id = repo.BOB_USER_ID

    async with pool.acquire() as conn:
        async with conn.transaction():
            if req.conversation_id is None:
                conversation_id = await repo.create_conversation(
                    conn, user_id=user_id, conversation_type=req.mode,
                    privacy_tier=req.privacy_tier,
                )
            else:
                if not await repo.conversation_exists(conn, req.conversation_id):
                    raise HTTPException(status_code=404, detail="conversation not found")
                conversation_id = req.conversation_id

            with start_chat_span(str(conversation_id)) as span:
                try:
                    outcome = await _orchestrator.chat(
                        conn,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        user_message=req.message,
                        privacy_tier=req.privacy_tier,
                        model_preference=req.model_preference,
                        trace_id=span.trace_id,
                    )
                except PrivacyViolation as e:
                    raise HTTPException(status_code=400, detail=str(e))
                except CloudUnavailable as e:
                    raise HTTPException(status_code=503, detail=str(e))
                except BudgetExceeded as e:
                    # 402 Payment Required: the cost ceiling paused the cloud call (ADR 0012).
                    raise HTTPException(status_code=402, detail=str(e))

    return ChatResponse(
        conversation_id=outcome.conversation_id,
        message_id=outcome.message_id,
        response=outcome.response,
        trace_id=outcome.trace_id,
        used_memory_ids=outcome.used_memory_ids,
        used_document_chunk_ids=outcome.used_document_chunk_ids,
        tool_run_ids=outcome.tool_run_ids,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        data = await repo.get_conversation(conn, conversation_id)
    if data is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return data
