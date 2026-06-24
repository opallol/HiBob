"""Built-in tools (Phase 4): internal, read-only, no sandbox needed. Reuse existing services.

Risk tiers exercise the whole policy matrix without enabling anything dangerous:
  memory_search/document_search -> low  (auto-allow)
  repo_read                     -> medium (ask; auto once trusted)
  draft_patch                   -> high (always ask; produces a draft, never writes)
No shell/browser/mcp tools are registered - those stay default-deny until a sandbox exists.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.knowledge import repository as kn_repo
from hibob_core.memory import repository as mem_repo


class ToolError(Exception):
    pass


async def _memory_search(conn: asyncpg.Connection, inp: dict) -> dict:
    rows = await mem_repo.search_sql(
        conn, user_id=core_repo.BOB_USER_ID, q=inp.get("q"), scope=inp.get("scope"),
        memory_type=inp.get("memory_type"), status=inp.get("status"),
    )
    return {"results": [{**r, "id": str(r["id"]), "confidence": float(r["confidence"])} for r in rows]}


async def _document_search(conn: asyncpg.Connection, inp: dict) -> dict:
    rows = await kn_repo.search_sql(
        conn, user_id=core_repo.BOB_USER_ID, q=inp.get("q"), privacy_tier=inp.get("privacy_tier"),
    )
    return {"results": [
        {"chunk_id": str(r["id"]), "document_id": str(r["document_id"]),
         "text": r["content"], "source": r.get("source_uri") or r["title"]}
        for r in rows
    ]}


async def _repo_read(conn: asyncpg.Connection, inp: dict) -> dict:
    rel = inp.get("path") or ""
    root = os.path.abspath(settings.repo_read_root)
    target = os.path.abspath(os.path.join(root, rel))
    if target != root and not target.startswith(root + os.sep):
        raise ToolError("path is outside the allowlisted repo_read_root")
    if not os.path.isfile(target):
        raise ToolError("not a file")
    with open(target, encoding="utf-8", errors="replace") as f:
        content = f.read(20_000)  # cap output
    return {"path": rel, "content": content}


async def _draft_patch(conn: asyncpg.Connection, inp: dict) -> dict:
    # High-risk by design -> reaches here only after approval. Still does NOT write anything.
    return {
        "applied": False,
        "draft": f"# draft patch for {inp.get('file')}\n# instruction: {inp.get('instruction')}\n"
                 f"# (review-only; the gateway never writes files in Phase 4)",
    }


async def _browser_open(conn: asyncpg.Connection, inp: dict) -> dict:
    # Phase 7 (ADR 0011): runs inside the sandbox (the gateway wraps this). localhost-only allowlist.
    url = inp.get("url", "")
    host = (urlparse(url).hostname or "")
    if host not in settings.browser_allowlist:
        raise ToolError(f"host not in browser allowlist: {host or '(none)'}")
    return {"opened": True, "url": url,
            "note": "browser action governed by sandbox; real Playwright via the docker backend"}


from hibob_core.selfbuild import tools as _selfbuild  # noqa: E402  (avoid import cycle at top)

HANDLERS = {
    "memory_search": _memory_search,
    "document_search": _document_search,
    "repo_read": _repo_read,
    "draft_patch": _draft_patch,
    "browser_open": _browser_open,  # Phase 7: tool_type=browser, runs in the sandbox
    **_selfbuild.HANDLERS,  # Phase 5: propose_blueprint_update, create_github_issue_draft
}

_INTERNAL_SEED = [
    {"name": "memory_search", "description": "Search Bob's memories (read-only).",
     "tool_type": "internal", "risk_level": "low", "default_permission": "allow", "enabled": True,
     "input_schema": {"q": "string"}, "output_schema": {"results": "array"}},
    {"name": "document_search", "description": "Search the knowledge base chunks (read-only).",
     "tool_type": "internal", "risk_level": "low", "default_permission": "allow", "enabled": True,
     "input_schema": {"q": "string"}, "output_schema": {"results": "array"}},
    {"name": "repo_read", "description": "Read a repo file under the allowlisted root (read-only).",
     "tool_type": "internal", "risk_level": "medium", "default_permission": "ask", "enabled": True,
     "input_schema": {"path": "string"}, "output_schema": {"content": "string"}},
    {"name": "draft_patch", "description": "Draft a code patch for review (never writes).",
     "tool_type": "internal", "risk_level": "high", "default_permission": "ask", "enabled": True,
     "input_schema": {"file": "string", "instruction": "string"}, "output_schema": {"draft": "string"}},
    {"name": "browser_open", "description": "Open a localhost URL in a sandboxed browser (Phase 7).",
     "tool_type": "browser", "risk_level": "high", "default_permission": "ask", "enabled": True,
     "input_schema": {"url": "string", "constraints": {"allow_hosts": ["localhost", "127.0.0.1"]}},
     "output_schema": {"opened": "bool"}},
]

# Built-in internal tools + Phase 5 self-build proposal tools (ADR 0013).
SEED_TOOLS = _INTERNAL_SEED + _selfbuild.SEED_TOOLS
