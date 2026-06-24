"""Learned-router epsilon-greedy (ADR 0012). Pure + seeded RNG."""

import random

import pytest

from hibob_core.evals import router_bandit

CANDS = [
    {"provider": "ollama", "model": "a", "avg_eval_score": 0.7},
    {"provider": "anthropic", "model": "b", "avg_eval_score": 0.9},
]


def test_epsilon_zero_exploits_best():
    assert router_bandit.select(CANDS, epsilon=0.0)["model"] == "b"


def test_epsilon_one_explores_with_seed():
    rng = random.Random(0)
    # epsilon=1 always explores -> uses rng.choice; just assert it returns a valid candidate
    choice = router_bandit.select(CANDS, epsilon=1.0, rng=rng)
    assert choice in CANDS


def test_empty_raises():
    with pytest.raises(ValueError):
        router_bandit.select([], epsilon=0.0)
