"""Tool Gateway (Phase 4, ADR 0005): validate -> provenance -> policy -> approve -> execute -> audit.

The Policy Engine (deterministic) owns the allow/ask/deny decision; the model only requests. Trust
accrues on successful, non-flagged runs and may auto-allow medium-risk tools, never high/critical
(risk ceiling). shell/browser/mcp tools are default-deny until a sandbox exists (sandbox_available
is always False in v0.1).
"""

from __future__ import annotations

import json
import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.policy import engine, provenance
from hibob_core.tools import repository as repo
from hibob_core.tools.builtins import HANDLERS

_SANDBOX_AVAILABLE = False  # no ephemeral runtime in v0.1 (ADR 0011 deferred)


class GatewayError(Exception):
    pass


async def _execute(conn: asyncpg.Connection, tool: dict, tool_run_id: uuid.UUID, inp: dict) -> dict:
    handler = HANDLERS.get(tool["name"])
    await repo.set_tool_run(conn, tool_run_id=tool_run_id, status="running", mark_started=True)
    if handler is None:
        await repo.set_tool_run(conn, tool_run_id=tool_run_id, status="failed",
                                output_json={"error": "no handler"}, mark_finished=True)
        raise GatewayError(f"tool '{tool['name']}' has no executable handler")
    try:
        out = await handler(conn, inp)
    except Exception as e:
        await repo.set_tool_run(conn, tool_run_id=tool_run_id, status="failed",
                                output_json={"error": str(e)}, mark_finished=True)
        raise
    await repo.set_tool_run(conn, tool_run_id=tool_run_id, status="succeeded",
                            output_json=out, mark_finished=True)
    return out


async def request_tool(
    conn: asyncpg.Connection,
    *,
    name: str,
    input: dict,
    reason: str,
    context: str = "chat",
    conversation_id: uuid.UUID | None = None,
    requested_by: str = "assistant",
    trace_id: str | None = None,
) -> dict:
    tool = await repo.get_tool_by_name(conn, name)
    if tool is None or not tool["enabled"]:
        raise GatewayError(f"tool '{name}' not found or not enabled")
    tool = dict(tool)
    risk = tool["risk_level"]

    # Injection defense (ADR 0005 #3): scan the request text; a hit forces at least `ask`.
    suspected, score = provenance.classify(f"{reason} {json.dumps(input)}")
    if suspected and conversation_id is not None:
        await provenance.tag(
            conn, source_type="message", source_id=conversation_id, provenance="user",
            suspected=True, score=score, trace_id=trace_id,
        )

    trust = await repo.get_trust(conn, tool_id=tool["id"], context=context)
    decision = engine.decide(
        risk_level=risk, tool_type=tool["tool_type"], trust_score=trust,
        sandbox_available=_SANDBOX_AVAILABLE, provenance_flagged=suspected,
    )

    await core_repo.write_audit(
        conn, actor_type=requested_by, actor_id=None, event_type="tool.requested",
        target_type="tool", target_id=name,
        metadata={"decision": decision.decision, "reason": decision.reason, "risk": risk},
    )

    result = {"tool_run_id": None, "status": None, "approval_request_id": None,
              "risk_level": risk, "trust_score": trust, "sandbox_run_id": None}

    if decision.decision == "deny":
        run_id = await repo.create_tool_run(
            conn, tool_id=tool["id"], requested_by=requested_by, input_json=input,
            risk_level=risk, status="denied", trace_id=trace_id,
        )
        result.update(tool_run_id=str(run_id), status="denied")
        return result

    if decision.decision == "ask":
        appr_id = await repo.create_approval(
            conn, user_id=core_repo.BOB_USER_ID, request_type="tool_run",
            summary=f"{name}: {reason}",
            payload={"name": name, "input": input, "reason": reason, "context": context},
            ttl_hours=settings.tool_approval_ttl_hours,
        )
        run_id = await repo.create_tool_run(
            conn, tool_id=tool["id"], requested_by=requested_by, input_json=input,
            risk_level=risk, status="pending_approval", approval_request_id=appr_id,
            trace_id=trace_id,
        )
        result.update(tool_run_id=str(run_id), status="pending_approval",
                      approval_request_id=str(appr_id))
        return result

    # allow -> execute now
    run_id = await repo.create_tool_run(
        conn, tool_id=tool["id"], requested_by=requested_by, input_json=input,
        risk_level=risk, status="requested", trace_id=trace_id,
    )
    try:
        await _execute(conn, tool, run_id, input)
        new_trust = await repo.bump_trust(
            conn, tool_id=tool["id"], context=context, increment=settings.trust_increment
        )
        result.update(tool_run_id=str(run_id), status="succeeded", trust_score=new_trust)
    except Exception:
        result.update(tool_run_id=str(run_id), status="failed")
    return result


async def approve_run(
    conn: asyncpg.Connection, *, approval_id: uuid.UUID, decision: str
) -> dict:
    if decision not in ("approve", "deny"):
        raise GatewayError("decision must be 'approve' or 'deny'")
    appr = await repo.get_approval(conn, approval_id)
    if appr is None:
        raise GatewayError("approval request not found")
    if appr["status"] != "pending":
        raise GatewayError(f"approval already {appr['status']}")

    payload = appr["payload_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    run = await repo.get_run_by_approval(conn, approval_id)

    if decision == "deny":
        await repo.decide_approval(conn, approval_id=approval_id, status="denied")
        if run:
            await repo.set_tool_run(conn, tool_run_id=run["id"], status="denied", mark_finished=True)
        await core_repo.write_audit(
            conn, actor_type="user", actor_id=str(core_repo.BOB_USER_ID),
            event_type="approval.denied", target_type="approval", target_id=str(approval_id),
        )
        return {"tool_run_id": str(run["id"]) if run else None, "status": "denied"}

    await repo.decide_approval(conn, approval_id=approval_id, status="approved")
    tool = dict(await repo.get_tool_by_name(conn, payload["name"]))
    status = "succeeded"
    try:
        await _execute(conn, tool, run["id"], payload["input"])
        await repo.bump_trust(
            conn, tool_id=tool["id"], context=payload.get("context", "chat"),
            increment=settings.trust_increment,
        )
    except Exception:
        status = "failed"
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(core_repo.BOB_USER_ID),
        event_type="approval.approved", target_type="approval", target_id=str(approval_id),
        metadata={"tool": payload["name"], "status": status},
    )
    return {"tool_run_id": str(run["id"]), "status": status}
