"""Self-build tool handlers + seed (Phase 5, ADR 0013).

All draft-only: they NEVER write files, push, or merge. Each proposal is a `tool_run` evaluated by
the Policy Engine; the gateway raises risk for sensitive paths (selfbuild.classifier) so security/
policy/schema changes are always high (never auto). draft_patch already ships from Phase 4.
"""

from __future__ import annotations

import asyncpg

from hibob_core.selfbuild import classifier
from hibob_core.selfbuild.gate import MergeGate, evaluate

SELF_BUILD_TOOLS = {"propose_blueprint_update", "draft_patch", "create_github_issue_draft"}


async def _propose_blueprint_update(conn: asyncpg.Connection, inp: dict) -> dict:
    paths = inp.get("paths", [])
    risk, reasons = classifier.effective_risk("medium", paths)
    touches_logic = any(
        seg in p for p in paths for seg in ("policy", "retrieval", "prompt", "persona")
    )
    return {
        "draft": True,
        "summary": inp.get("summary", ""),
        "touched_paths": paths,
        "risk": risk,
        "risk_reasons": reasons,
        "merge_gate": evaluate(MergeGate(), touches_logic=touches_logic),
        "note": "proposal only - no file written, no merge (ADR 0013)",
    }


async def _create_github_issue_draft(conn: asyncpg.Connection, inp: dict) -> dict:
    return {
        "draft": True,
        "issue_title": inp.get("title", "Hibob: proposed change"),
        "issue_body": inp.get("body", ""),
        "labels": inp.get("labels", []),
        "note": "draft only - not posted to GitHub (ADR 0013)",
    }


HANDLERS = {
    "propose_blueprint_update": _propose_blueprint_update,
    "create_github_issue_draft": _create_github_issue_draft,
}

SEED_TOOLS = [
    {"name": "propose_blueprint_update",
     "description": "Draft a blueprint/doc update proposal (review-only; risk rises for sensitive files).",
     "tool_type": "internal", "risk_level": "medium", "default_permission": "ask", "enabled": True,
     "input_schema": {"summary": "string", "paths": "array"}, "output_schema": {"draft": "bool"}},
    {"name": "create_github_issue_draft",
     "description": "Draft a GitHub issue (never posted automatically).",
     "tool_type": "internal", "risk_level": "medium", "default_permission": "ask", "enabled": True,
     "input_schema": {"title": "string", "body": "string"}, "output_schema": {"issue_body": "string"}},
]
