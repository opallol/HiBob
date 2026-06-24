"""Self-calibrating memory confidence (Phase 2.5, ADR 0007, doc 04 §7a).

Confidence stops being frozen at extraction time. Every time a memory is used in an answer
(or Bob explicitly corrects/accepts it) a `memory_usage_feedback` row is recorded, and the
memory's confidence is recomputed as a bounded Beta(alpha, beta) posterior mean.

Hard rules (ADR 0007):
  - calibration ONLY moves `confidence` (and therefore retrieval ranking) - NEVER `status`.
    candidate -> approved still requires Bob (doc 04 §6).
  - a `corrected` signal pushes beta up sharply; `used`/`accepted` nudge alpha up gently.
  - confidence is clamped to [floor, cap]; it can never reach a value that would imply promotion.
  - when confidence drops below the review threshold the memory is flagged for the weekly
    review ritual (§11) via an audit event - it is NOT auto-archived, and no formula resets it.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.memory import repository as repo
from hibob_core.memory.service import MemoryError

# Event types accepted from the feedback endpoint + the chat auto-signal (doc 13 §4a).
EVENT_TYPES = {"used", "corrected", "accepted", "ignored"}


def _posterior_mean(tallies: dict[str, float]) -> float:
    """Beta(alpha, beta) posterior mean from accumulated feedback signal strengths.

    alpha gathers positive evidence (used/accepted); beta gathers negative evidence, with
    `corrected` weighted heavily so a single real correction outweighs many passive uses.
    """
    alpha = settings.calib_alpha0
    beta = settings.calib_beta0
    alpha += tallies.get("used", 0.0) + tallies.get("accepted", 0.0)
    beta += tallies.get("corrected", 0.0) * settings.calib_correction_weight
    beta += tallies.get("ignored", 0.0)
    mean = alpha / (alpha + beta)
    return max(settings.calib_floor, min(settings.calib_cap, mean))


async def record_feedback(
    conn: asyncpg.Connection,
    *,
    memory_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    event_type: str,
    signal_strength: float = 1.0,
    note: str | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> dict:
    """Record one feedback event and recompute confidence. Returns the new confidence."""
    if event_type not in EVENT_TYPES:
        raise MemoryError(
            f"invalid event_type '{event_type}' (allowed: {sorted(EVENT_TYPES)})"
        )
    mem = await repo.get(conn, memory_id)
    if mem is None:
        raise MemoryError("memory not found")
    old_conf = float(mem["confidence"])

    await repo.add_usage_feedback(
        conn, memory_id=memory_id, conversation_id=conversation_id,
        event_type=event_type, signal_strength=signal_strength, note=note,
    )

    tallies = await repo.feedback_tallies(conn, memory_id)
    new_conf = round(_posterior_mean(tallies), 3)
    await repo.set_confidence(conn, memory_id, new_conf)  # status untouched (ADR 0007)

    await core_repo.write_audit(
        conn, actor_type="assistant", actor_id=(str(actor_user_id) if actor_user_id else None),
        event_type="memory.feedback.recorded", target_type="memory", target_id=str(memory_id),
        metadata={"event_type": event_type, "old_confidence": old_conf, "new_confidence": new_conf},
    )

    review_needed = new_conf < settings.calib_review_threshold
    if review_needed:
        # Flag for the weekly review ritual (§11) - NOT an auto-archive.
        await core_repo.write_audit(
            conn, actor_type="system", actor_id=None,
            event_type="memory.calibration.review_needed", target_type="memory",
            target_id=str(memory_id),
            metadata={"confidence": new_conf, "threshold": settings.calib_review_threshold},
        )

    return {
        "id": str(memory_id),
        "event_type": event_type,
        "old_confidence": old_conf,
        "confidence": new_conf,
        "review_needed": review_needed,
        "status": mem["status"],  # echoed to make it explicit calibration never changed it
    }
