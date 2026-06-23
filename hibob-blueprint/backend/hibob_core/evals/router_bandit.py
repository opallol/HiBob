"""Learned router bias (Phase 6, ADR 0012). Pure epsilon-greedy over ALLOWED candidates only.

The static privacy/cost router (models/router.py) still decides what is *allowed*; this only biases
the choice among already-permitted candidates using router_policy_feedback. epsilon=0 (default) is
pure exploit = deterministic, so it never changes live behavior until explicitly enabled.
"""

from __future__ import annotations

import random


def select(candidates: list[dict], *, epsilon: float = 0.0, rng: random.Random | None = None) -> dict:
    """Pick a candidate {provider, model, avg_eval_score}. Explore w.p. epsilon, else best score."""
    if not candidates:
        raise ValueError("no candidates to select from")
    r = rng or random
    if epsilon > 0.0 and r.random() < epsilon:
        return r.choice(candidates)
    return max(candidates, key=lambda c: c.get("avg_eval_score") or 0.0)
