"""Deterministic eval metrics (Phase 6). Pure."""

from hibob_core.evals import metrics


def test_policy_metric_matches_engine():
    assert metrics.policy_metric({"risk_level": "low", "tool_type": "internal"}, "allow")[0]
    assert metrics.policy_metric({"risk_level": "critical", "tool_type": "internal"}, "deny")[0]
    assert metrics.policy_metric(
        {"risk_level": "medium", "tool_type": "internal", "trust_score": 0.95}, "allow")[0]
    # mismatch fails
    passed, score, _ = metrics.policy_metric({"risk_level": "high", "tool_type": "internal"}, "allow")
    assert not passed and score == 0.0


def test_substring_metric():
    assert metrics.substring_metric("Bob, ini saudara digital", "saudara", None)[0]
    assert not metrics.substring_metric("halo", "saudara", None)[0]
    assert not metrics.substring_metric("ini rahasia", None, "rahasia")[0]


def test_evaluate_case_dispatch():
    case = {"input_json": {"risk_level": "low", "tool_type": "internal"},
            "expected_behavior": "allow", "metric_config_json": {"metric": "policy"}}
    assert metrics.evaluate_case(case)[0]
    assert metrics.evaluate_case({**case, "metric_config_json": {"metric": "nope"}})[0] is False
