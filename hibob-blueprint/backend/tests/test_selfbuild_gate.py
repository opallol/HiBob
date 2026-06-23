"""Self-build merge gate ordering (ADR 0013). Pure."""

from hibob_core.selfbuild.gate import MergeGate, evaluate


def test_empty_gate_blocks_on_tests_first():
    out = evaluate(MergeGate())
    assert out["ready"] is False
    assert out["next"] == "tests_passed"
    assert out["missing"] == ["tests_passed", "eval_passed", "docs_updated", "approved"]


def test_approval_alone_is_not_enough():
    out = evaluate(MergeGate(approved=True))
    assert out["ready"] is False
    assert "tests_passed" in out["missing"]


def test_all_satisfied_is_ready():
    out = evaluate(MergeGate(tests_passed=True, eval_passed=True, docs_updated=True, approved=True))
    assert out["ready"] is True
    assert out["missing"] == []


def test_touches_logic_requires_replay():
    full = MergeGate(tests_passed=True, eval_passed=True, docs_updated=True, approved=True)
    out = evaluate(full, touches_logic=True)
    assert out["ready"] is False
    assert "replay_checked" in out["missing"]
    full.replay_checked = True
    assert evaluate(full, touches_logic=True)["ready"] is True
