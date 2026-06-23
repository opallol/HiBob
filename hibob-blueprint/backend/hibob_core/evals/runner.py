"""Eval suite runner (Phase 6, doc 09 §5/§9). Records eval_runs + eval_results, returns pass_rate.

Every failure here is a regression signal that feeds back into the suites (doc 09 §9). This is what
lets the Phase 5 merge gate's `eval_passed` be filled by a real run instead of a promise.
"""

from __future__ import annotations

import asyncpg

from hibob_core.evals import metrics
from hibob_core.evals import repository as repo


class EvalError(Exception):
    pass


async def run_suite(
    conn: asyncpg.Connection, *, suite_name: str, target_version: str | None = None
) -> dict:
    suite = await repo.get_suite_by_name(conn, suite_name)
    if suite is None:
        raise EvalError(f"eval suite '{suite_name}' not found")

    cases = await repo.list_cases(conn, suite["id"])
    run_id = await repo.create_run(conn, suite_id=suite["id"], target_version=target_version)

    for case in cases:
        passed, score, explanation = metrics.evaluate_case(case)
        await repo.add_result(
            conn, eval_run_id=run_id, eval_case_id=case["id"],
            score=score, passed=passed, explanation=explanation,
        )

    summary = await repo.run_summary(conn, run_id)
    await repo.finish_run(conn, run_id=run_id, status="succeeded")
    return {"run_id": str(run_id), "suite": suite_name, **summary}
