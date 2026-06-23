"""Confidence calibration (ADR 0007): Beta posterior moves confidence, never status."""

import uuid

import pytest

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.memory import calibration
from hibob_core.memory import repository as repo

MID = uuid.uuid4()


def test_posterior_mean_neutral_prior():
    # Beta(1,1) with no feedback -> mean 0.5.
    assert calibration._posterior_mean({}) == pytest.approx(0.5)


def test_used_raises_corrected_drops_sharply():
    used = calibration._posterior_mean({"used": 5})
    corrected = calibration._posterior_mean({"corrected": 5})
    assert used > 0.5
    assert corrected < 0.5
    # A single correction outweighs a passive use (correction_weight applies to beta).
    one_each = calibration._posterior_mean({"used": 1, "corrected": 1})
    assert one_each < 0.5


def test_posterior_mean_is_clamped():
    assert calibration._posterior_mean({"used": 10_000}) <= settings.calib_cap
    assert calibration._posterior_mean({"corrected": 10_000}) >= settings.calib_floor


async def test_record_feedback_rejects_unknown_event():
    async def get(conn, mid):
        return {"id": mid, "confidence": 0.9, "status": "approved"}
    import pytest as _pytest
    # get isn't even reached for a bad event, but patch anyway for safety
    with _pytest.raises(calibration.MemoryError):
        await calibration.record_feedback(
            None, memory_id=MID, conversation_id=None, event_type="bogus"
        )


async def test_record_feedback_updates_confidence_not_status(monkeypatch):
    captured = {"confidence": None, "set_status_called": False}

    async def get(conn, mid):
        return {"id": mid, "confidence": 0.9, "status": "approved"}

    async def add_usage_feedback(conn, **k):
        return uuid.uuid4()

    async def feedback_tallies(conn, mid):
        return {"corrected": 6}  # heavy negative evidence -> confidence should drop low

    async def set_confidence(conn, mid, confidence):
        captured["confidence"] = confidence

    def _set_status(*a, **k):
        captured["set_status_called"] = True

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get", get)
    monkeypatch.setattr(repo, "add_usage_feedback", add_usage_feedback)
    monkeypatch.setattr(repo, "feedback_tallies", feedback_tallies)
    monkeypatch.setattr(repo, "set_confidence", set_confidence)
    monkeypatch.setattr(repo, "set_status", _set_status)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await calibration.record_feedback(
        None, memory_id=MID, conversation_id=None, event_type="corrected"
    )
    assert out["status"] == "approved"            # status echoed, unchanged
    assert captured["set_status_called"] is False  # calibration NEVER touches status
    assert out["confidence"] < 0.9                 # dropped from the correction
    assert out["confidence"] == captured["confidence"]
    assert out["review_needed"] is True            # below the review threshold
