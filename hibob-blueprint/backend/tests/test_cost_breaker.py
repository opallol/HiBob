"""Cost breaker (ADR 0012): no cloud call passes once the daily ceiling is met."""

import uuid

import pytest

from hibob_core.cost import breaker
from hibob_core.db import repositories as repo

CID = uuid.UUID("00000000-0000-0000-0000-0000000000c1")


async def test_blocks_when_at_or_over_ceiling(monkeypatch):
    async def ceiling(conn, uid):
        return {"id": CID, "ceiling_amount": 5.0}

    async def spend(conn, cid):
        return 5.0  # exactly at ceiling -> blocked

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_daily_ceiling", ceiling)
    monkeypatch.setattr(repo, "get_spend_today", spend)
    monkeypatch.setattr(repo, "write_audit", audit)

    with pytest.raises(breaker.BudgetExceeded):
        await breaker.check_can_spend_cloud(None, uuid.uuid4())


async def test_allows_when_under_ceiling(monkeypatch):
    async def ceiling(conn, uid):
        return {"id": CID, "ceiling_amount": 5.0}

    async def spend(conn, cid):
        return 1.0

    monkeypatch.setattr(repo, "get_daily_ceiling", ceiling)
    monkeypatch.setattr(repo, "get_spend_today", spend)

    check = await breaker.check_can_spend_cloud(None, uuid.uuid4())
    assert check.spend_today == 1.0
    assert check.ceiling_amount == 5.0


async def test_missing_ceiling_fails_closed(monkeypatch):
    async def ceiling(conn, uid):
        return None

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_daily_ceiling", ceiling)
    monkeypatch.setattr(repo, "write_audit", audit)

    with pytest.raises(breaker.BudgetExceeded):
        await breaker.check_can_spend_cloud(None, uuid.uuid4())


async def test_debit_flags_breach(monkeypatch):
    async def record(conn, **k):
        return None

    monkeypatch.setattr(repo, "record_cost", record)

    check = breaker.CeilingCheck(ceiling_id=CID, ceiling_amount=5.0, spend_today=4.9)
    total, breached = await breaker.debit(
        None, check=check, model_run_id=uuid.uuid4(), amount=0.2
    )
    assert breached is True
    assert round(total, 4) == 5.1
