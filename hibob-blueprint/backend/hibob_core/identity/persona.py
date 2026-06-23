"""Persona/system-prompt assembly (doc 02 §3.3).

Phase 1: persona is the ordered set of active persona_rules from the DB, joined into a
system prompt. Not "just a long prompt" - it is backed by editable, audited DB rows
(persona_rules), which is the seam memory/policy will hook into in later phases.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.db import repositories as repo


async def assemble_system_prompt(conn: asyncpg.Connection, user_id: uuid.UUID) -> str:
    rules = await repo.get_active_persona_rules(conn, user_id)
    if not rules:
        # Fail-safe identity if the DB has no rules yet.
        return "Kamu adalah Hibob, saudara digital Bob. Jujur, kritis, dan tidak mengarang."
    return "\n\n".join(rules)
