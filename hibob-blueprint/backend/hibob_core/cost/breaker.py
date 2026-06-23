"""Cost circuit breaker (ADR 0012) - hard daily ceiling on cloud spend.

Checked BEFORE every cloud model call: if today's spend already meets/exceeds the
ceiling, the call is refused (Phase 1) and an audit row is written. Local (Ollama)
calls never touch this path. After a permitted cloud call, the actual cost is debited
to cost_ledger. A precise pre-call cost is impossible (output tokens unknown), so the
gate is "are we already at the ceiling?" - simple and safe at personal scale.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import asyncpg

from hibob_core.db import repositories as repo


class BudgetExceeded(Exception):
    def __init__(self, spend: float, ceiling: float):
        self.spend = spend
        self.ceiling = ceiling
        super().__init__(
            f"Daily cloud budget ceiling reached: spent ${spend:.4f} of ${ceiling:.4f}. "
            f"Cloud call paused - approval required (Phase 1: use model_preference=local, "
            f"or raise the ceiling)."
        )


@dataclass
class CeilingCheck:
    ceiling_id: uuid.UUID
    ceiling_amount: float
    spend_today: float


async def check_can_spend_cloud(conn: asyncpg.Connection, user_id: uuid.UUID) -> CeilingCheck:
    """Raise BudgetExceeded if already at/over the daily ceiling. Writes an audit row on breach."""
    ceiling = await repo.get_daily_ceiling(conn, user_id)
    if ceiling is None:
        # No ceiling configured = no cloud spend allowed (fail closed, ADR 0012 spirit).
        await repo.write_audit(
            conn, actor_type="system", actor_id=str(user_id),
            event_type="cost.no_ceiling_configured",
        )
        raise BudgetExceeded(0.0, 0.0)

    ceiling_id = ceiling["id"]
    ceiling_amount = float(ceiling["ceiling_amount"])
    spend = await repo.get_spend_today(conn, ceiling_id)

    if spend >= ceiling_amount:
        await repo.write_audit(
            conn, actor_type="system", actor_id=str(user_id),
            event_type="cost.ceiling_breached_blocked",
            metadata={"spend_today": spend, "ceiling": ceiling_amount},
        )
        raise BudgetExceeded(spend, ceiling_amount)

    return CeilingCheck(ceiling_id=ceiling_id, ceiling_amount=ceiling_amount, spend_today=spend)


async def debit(
    conn: asyncpg.Connection,
    *,
    check: CeilingCheck,
    model_run_id: uuid.UUID,
    amount: float,
) -> tuple[float, bool]:
    """Record a cloud cost against the ceiling. Returns (running_total, breached_after)."""
    running_total = check.spend_today + amount
    breached = running_total >= check.ceiling_amount
    await repo.record_cost(
        conn,
        model_run_id=model_run_id,
        budget_ceiling_id=check.ceiling_id,
        amount=amount,
        running_total=running_total,
        ceiling_breached=breached,
    )
    return running_total, breached
