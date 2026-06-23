"""Deterministic eval metrics (Phase 6, doc 09 §4/§5). Pure - no LLM, no DeepEval dependency.

v0.1 metrics are rule-based so they are a real, repeatable regression boundary (an LLM judge is a
separate, pinned seam - see judge.py). The dispatch key lives in each case's metric_config_json.
"""

from __future__ import annotations

from hibob_core.policy import engine


def policy_metric(input_json: dict, expected_behavior: str) -> tuple[bool, float, str]:
    """Validate the Policy Engine: decide(**input) must equal the expected allow/ask/deny."""
    got = engine.decide(
        risk_level=input_json.get("risk_level", "low"),
        tool_type=input_json.get("tool_type", "internal"),
        trust_score=float(input_json.get("trust_score", 0.0)),
        sandbox_available=bool(input_json.get("sandbox_available", False)),
        provenance_flagged=bool(input_json.get("provenance_flagged", False)),
    ).decision
    passed = got == expected_behavior
    return passed, (1.0 if passed else 0.0), f"expected={expected_behavior} got={got}"


def substring_metric(
    output: str, expected: str | None, prohibited: str | None
) -> tuple[bool, float, str]:
    """Persona/refusal style check (doc 09 §4): expected present AND prohibited absent."""
    text = output or ""
    ok_expected = (not expected) or (expected.lower() in text.lower())
    ok_prohibited = (not prohibited) or (prohibited.lower() not in text.lower())
    passed = ok_expected and ok_prohibited
    return passed, (1.0 if passed else 0.0), f"expected_ok={ok_expected} prohibited_ok={ok_prohibited}"


def evaluate_case(case: dict) -> tuple[bool, float, str]:
    """Dispatch a case to its metric. `case` carries input_json, expected/prohibited, metric_config."""
    metric = (case.get("metric_config_json") or {}).get("metric", "policy")
    if metric == "policy":
        return policy_metric(case["input_json"], case["expected_behavior"])
    if metric == "substring":
        return substring_metric(
            (case["input_json"] or {}).get("output", ""),
            case.get("expected_behavior"), case.get("prohibited_behavior"),
        )
    return False, 0.0, f"unknown metric '{metric}'"
