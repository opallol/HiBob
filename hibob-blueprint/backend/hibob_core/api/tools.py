"""Tool & Policy API (doc 13 §6/§6a): list/request tools, trust scores, approvals, policy rules."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from hibob_core.config import settings
from hibob_core.db.pool import get_pool
from hibob_core.policy import engine
from hibob_core.tools import gateway, repository as repo

router = APIRouter()


class ToolRequest(BaseModel):
    input: dict = Field(default_factory=dict)
    reason: str = ""
    context: str = "chat"
    conversation_id: uuid.UUID | None = None


class DecideRequest(BaseModel):
    decision: str  # approve | deny


@router.get("/tools")
async def list_tools() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        tools = await repo.list_tools(conn)
    return {"tools": tools, "count": len(tools)}


@router.post("/tools/{name}/request")
async def request_tool(name: str, req: ToolRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await gateway.request_tool(
                    conn, name=name, input=req.input, reason=req.reason,
                    context=req.context, conversation_id=req.conversation_id,
                )
            except gateway.GatewayError as e:
                raise HTTPException(status_code=404, detail=str(e))


@router.get("/tools/{name}/trust-score")
async def trust_score(name: str, context: str = "chat") -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        tool = await repo.get_tool_by_name(conn, name)
        if tool is None:
            raise HTTPException(status_code=404, detail="tool not found")
        score = await repo.get_trust(conn, tool_id=tool["id"], context=context)
    return {
        "tool": name,
        "context": context,
        "trust_score": score,
        "risk_level": tool["risk_level"],
        "can_auto_escalate": engine.can_auto_escalate(tool["risk_level"]),
        "trust_auto_threshold": settings.trust_auto_threshold,
    }


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(approval_id: uuid.UUID, req: DecideRequest) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                return await gateway.approve_run(
                    conn, approval_id=approval_id, decision=req.decision
                )
            except gateway.GatewayError as e:
                raise HTTPException(status_code=400, detail=str(e))


@router.get("/policy/rules")
async def policy_rules() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        ver = await conn.fetchrow(
            "SELECT policy_name, version, status FROM policy_versions "
            "WHERE policy_name='tool_policy' AND status='active' ORDER BY created_at DESC LIMIT 1"
        )
    # Effective rules are encoded in the deterministic engine (ADR 0005).
    rules = [
        {"risk_level": "low", "decision": "allow"},
        {"risk_level": "medium", "decision": "ask (auto-allow once trust >= threshold)"},
        {"risk_level": "high", "decision": "ask (never auto)"},
        {"risk_level": "critical", "decision": "deny"},
        {"rule": "tool_type in shell|browser|mcp without sandbox", "decision": "deny"},
        {"rule": "injection-suspected provenance", "decision": "force ask (never auto)"},
    ]
    return {"version": dict(ver) if ver else None, "rules": rules}
