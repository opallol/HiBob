"""Deterministic Replay Harness (Phase 6, ADR 0008). Pure diff/compare + recording.

A model/provider migration must cite a replay batch as evidence: re-run a past assembled prompt
against a candidate model and diff the outcome against the same eval metrics. v0.1 ships the diff +
recording; executing the candidate through the Model Router's dry-run mode is the next seam (needs
the assembled-prompt store + a no-side-effect adapter mode).
"""

from __future__ import annotations

import json
import uuid

import asyncpg


def diff_outputs(baseline: str, candidate: str) -> dict:
    """Shallow text diff between two model outputs."""
    changed = (baseline or "") != (candidate or "")
    return {
        "changed": changed,
        "baseline_len": len(baseline or ""),
        "candidate_len": len(candidate or ""),
    }


def compare_eval(baseline_results: dict, candidate_results: dict) -> dict:
    """Compare two {metric: pass_rate} maps. Candidate must not regress any metric."""
    regressions = [
        m for m, base in baseline_results.items()
        if candidate_results.get(m, 0.0) < base
    ]
    improved = [
        m for m, base in baseline_results.items()
        if candidate_results.get(m, 0.0) > base
    ]
    return {"regressions": regressions, "improved": improved, "net_ok": not regressions}


async def record_replay(
    conn: asyncpg.Connection,
    *,
    source_model_run_id: uuid.UUID | None,
    candidate_provider: str,
    candidate_model: str,
    assembled_input_ref: str,
    diff_summary: dict,
    eval_comparison: dict,
    decision: str,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO replay_runs
            (source_model_run_id, candidate_provider, candidate_model, assembled_input_ref,
             status, diff_summary_json, eval_comparison_json, decision, finished_at)
        VALUES ($1,$2,$3,$4,'succeeded',$5,$6,$7, now()) RETURNING id
        """,
        source_model_run_id, candidate_provider, candidate_model, assembled_input_ref,
        json.dumps(diff_summary), json.dumps(eval_comparison), decision,
    )
    return row["id"]
