"""Self-build merge gate (Phase 5, ADR 0013). Pure.

No patch merges without, IN THIS ORDER: unit tests pass -> the relevant DeepEval suite passes ->
docs updated in the same change -> Bob's explicit approval. When a change touches prompt/retrieval/
policy logic, the Replay Harness (ADR 0008) must also have run. The real CI/DeepEval/Replay live
outside (Phase 6); this gate only represents and enforces the ordering. Nothing here auto-merges.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ordered gate steps. `ready` requires every required step satisfied.
_STEPS = ["tests_passed", "eval_passed", "docs_updated", "approved"]


@dataclass
class MergeGate:
    tests_passed: bool = False
    eval_passed: bool = False
    docs_updated: bool = False
    approved: bool = False
    replay_checked: bool = False  # required only when the change touches prompt/retrieval/policy


def evaluate(gate: MergeGate, *, touches_logic: bool = False) -> dict:
    required = list(_STEPS)
    if touches_logic:
        # Replay must run before approval can count (ADR 0008 + 0013).
        required.insert(2, "replay_checked")

    missing = [step for step in required if not getattr(gate, step)]
    return {
        "ready": not missing,
        "missing": missing,
        "next": missing[0] if missing else None,
        "required_order": required,
    }
