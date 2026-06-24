"""Replay diff/compare (ADR 0008). Pure."""

from hibob_core.evals import replay


def test_diff_outputs_detects_change():
    assert replay.diff_outputs("a", "b")["changed"] is True
    assert replay.diff_outputs("same", "same")["changed"] is False


def test_compare_eval_flags_regression():
    out = replay.compare_eval({"policy": 1.0, "persona": 0.9}, {"policy": 0.8, "persona": 0.95})
    assert out["regressions"] == ["policy"]
    assert out["improved"] == ["persona"]
    assert out["net_ok"] is False


def test_compare_eval_net_ok_when_no_regression():
    out = replay.compare_eval({"policy": 0.9}, {"policy": 0.9})
    assert out["net_ok"] is True and out["regressions"] == []
