"""Tool registry (Phase 4): seed the built-in tools idempotently at startup."""

from __future__ import annotations

import asyncpg

from hibob_core.tools import repository as repo
from hibob_core.tools.builtins import SEED_TOOLS


async def ensure_seed(conn: asyncpg.Connection) -> int:
    """Register/refresh built-in tools. Idempotent (upsert by name)."""
    for t in SEED_TOOLS:
        await repo.upsert_tool(
            conn, name=t["name"], description=t["description"], tool_type=t["tool_type"],
            input_schema=t["input_schema"], output_schema=t["output_schema"],
            risk_level=t["risk_level"], default_permission=t["default_permission"],
            enabled=t["enabled"],
        )
    return len(SEED_TOOLS)
