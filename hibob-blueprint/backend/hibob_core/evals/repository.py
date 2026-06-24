"""DB access for the eval harness (Phase 6)."""

from __future__ import annotations

import json
import uuid

import asyncpg


def _loads(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


async def get_suite_by_name(conn: asyncpg.Connection, name: str) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM eval_suites WHERE name = $1", name)


async def list_suites(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch("SELECT id, name, description FROM eval_suites ORDER BY name")
    return [{**dict(r), "id": str(r["id"])} for r in rows]


async def list_cases(conn: asyncpg.Connection, suite_id: uuid.UUID) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, name, input_json, expected_behavior, prohibited_behavior, metric_config_json "
        "FROM eval_cases WHERE suite_id = $1 AND enabled = true ORDER BY created_at",
        suite_id,
    )
    cases = []
    for r in rows:
        c = dict(r)
        c["input_json"] = _loads(c["input_json"])
        c["metric_config_json"] = _loads(c["metric_config_json"])
        cases.append(c)
    return cases


async def create_run(
    conn: asyncpg.Connection, *, suite_id: uuid.UUID, target_version: str | None
) -> uuid.UUID:
    row = await conn.fetchrow(
        "INSERT INTO eval_runs (suite_id, target_version) VALUES ($1,$2) RETURNING id",
        suite_id, target_version,
    )
    return row["id"]


async def add_result(
    conn: asyncpg.Connection,
    *,
    eval_run_id: uuid.UUID,
    eval_case_id: uuid.UUID,
    score: float,
    passed: bool,
    explanation: str,
) -> None:
    await conn.execute(
        "INSERT INTO eval_results (eval_run_id, eval_case_id, score, passed, explanation) "
        "VALUES ($1,$2,$3,$4,$5)",
        eval_run_id, eval_case_id, score, passed, explanation,
    )


async def finish_run(conn: asyncpg.Connection, *, run_id: uuid.UUID, status: str) -> None:
    await conn.execute(
        "UPDATE eval_runs SET status=$2, finished_at=now() WHERE id=$1", run_id, status
    )


async def run_summary(conn: asyncpg.Connection, run_id: uuid.UUID) -> dict:
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE passed) AS passed "
        "FROM eval_results WHERE eval_run_id = $1",
        run_id,
    )
    total = row["total"] or 0
    passed = row["passed"] or 0
    return {"total": total, "passed": passed,
            "pass_rate": round(passed / total, 4) if total else 0.0}


async def get_results(conn: asyncpg.Connection, run_id: uuid.UUID) -> list[dict]:
    rows = await conn.fetch(
        "SELECT eval_case_id, score, passed, explanation FROM eval_results WHERE eval_run_id=$1",
        run_id,
    )
    return [{**dict(r), "eval_case_id": str(r["eval_case_id"]), "score": float(r["score"] or 0)}
            for r in rows]


async def get_active_judge(conn: asyncpg.Connection) -> dict | None:
    row = await conn.fetchrow(
        "SELECT judge_provider, judge_model, judge_version, golden_set_agreement_score, status "
        "FROM eval_judge_versions WHERE status='active' ORDER BY created_at DESC LIMIT 1"
    )
    if row is None:
        return None
    d = dict(row)
    if d.get("golden_set_agreement_score") is not None:
        d["golden_set_agreement_score"] = float(d["golden_set_agreement_score"])
    return d
