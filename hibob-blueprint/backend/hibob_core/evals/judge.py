"""Eval judge integrity (Phase 6, ADR 0009). Pure agreement scoring.

An LLM judge is itself versioned and pinned (`eval_judge_versions`); before use it must agree with a
golden human-labeled set above a threshold, so the judge can't silently drift and quietly pass bad
output. v0.1 ships the agreement math + the pin record; running an actual judge model is the seam.
"""

from __future__ import annotations


def agreement_score(judge_labels: list, golden_labels: list) -> float:
    """Fraction of positions where the judge agrees with the golden labels (0..1)."""
    if not golden_labels or len(judge_labels) != len(golden_labels):
        return 0.0
    agree = sum(1 for j, g in zip(judge_labels, golden_labels) if j == g)
    return round(agree / len(golden_labels), 4)
