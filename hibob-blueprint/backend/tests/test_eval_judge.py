"""Eval judge agreement scoring (ADR 0009). Pure."""

from hibob_core.evals import judge


def test_full_agreement():
    assert judge.agreement_score([1, 0, 1], [1, 0, 1]) == 1.0


def test_half_agreement():
    assert judge.agreement_score([1, 1, 0, 0], [1, 0, 0, 1]) == 0.5


def test_mismatched_length_or_empty_is_zero():
    assert judge.agreement_score([1], [1, 0]) == 0.0
    assert judge.agreement_score([], []) == 0.0
