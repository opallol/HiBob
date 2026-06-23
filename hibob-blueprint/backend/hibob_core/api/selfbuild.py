"""Self-building loop API (Phase 5, ADR 0013).

Proposals themselves go through the existing Tool Gateway (POST /v1/tools/{name}/request) so they
inherit the Policy Engine + approval flow. This endpoint exposes the merge gate: no patch is
mergeable until tests -> eval -> docs -> approval are all satisfied (CI/DeepEval live in Phase 6).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from hibob_core.selfbuild.gate import MergeGate, evaluate

router = APIRouter()


class GateRequest(BaseModel):
    tests_passed: bool = False
    eval_passed: bool = False
    docs_updated: bool = False
    approved: bool = False
    replay_checked: bool = False
    touches_logic: bool = False


@router.post("/selfbuild/check-merge")
async def check_merge(req: GateRequest) -> dict:
    gate = MergeGate(
        tests_passed=req.tests_passed, eval_passed=req.eval_passed,
        docs_updated=req.docs_updated, approved=req.approved, replay_checked=req.replay_checked,
    )
    return evaluate(gate, touches_logic=req.touches_logic)
