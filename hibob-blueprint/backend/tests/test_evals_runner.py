"""Eval runner records results and computes pass_rate (Phase 6). Repo faked."""

import uuid

import pytest

from hibob_core.evals import repository as repo
from hibob_core.evals import runner

SUITE_ID = uuid.uuid4()


async def test_run_suite_scores_cases(monkeypatch):
    recorded = []

    async def get_suite_by_name(conn, name):
        return {"id": SUITE_ID, "name": name}

    async def list_cases(conn, suite_id):
        return [
            {"id": uuid.uuid4(), "input_json": {"risk_level": "low", "tool_type": "internal"},
             "expected_behavior": "allow", "prohibited_behavior": None,
             "metric_config_json": {"metric": "policy"}},
            {"id": uuid.uuid4(), "input_json": {"risk_level": "high", "tool_type": "internal"},
             "expected_behavior": "allow", "prohibited_behavior": None,  # WRONG on purpose -> fails
             "metric_config_json": {"metric": "policy"}},
        ]

    async def create_run(conn, *, suite_id, target_version):
        return uuid.uuid4()

    async def add_result(conn, *, eval_run_id, eval_case_id, score, passed, explanation):
        recorded.append(passed)

    async def run_summary(conn, run_id):
        return {"total": 2, "passed": sum(recorded), "pass_rate": round(sum(recorded) / 2, 4)}

    async def finish_run(conn, *, run_id, status):
        return None

    monkeypatch.setattr(repo, "get_suite_by_name", get_suite_by_name)
    monkeypatch.setattr(repo, "list_cases", list_cases)
    monkeypatch.setattr(repo, "create_run", create_run)
    monkeypatch.setattr(repo, "add_result", add_result)
    monkeypatch.setattr(repo, "run_summary", run_summary)
    monkeypatch.setattr(repo, "finish_run", finish_run)

    out = await runner.run_suite(None, suite_name="tool_policy_eval")
    assert out["total"] == 2
    assert out["passed"] == 1          # only the correct case passed
    assert out["pass_rate"] == 0.5
    assert recorded == [True, False]


async def test_unknown_suite_raises(monkeypatch):
    async def get_suite_by_name(conn, name):
        return None
    monkeypatch.setattr(repo, "get_suite_by_name", get_suite_by_name)
    with pytest.raises(runner.EvalError):
        await runner.run_suite(None, suite_name="missing")
