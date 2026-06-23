"""Policy Engine (Phase 4, ADR 0005) - deterministic allow/ask/deny. Pure functions.

The model NEVER adjudicates its own permission; it only requests. Decisions are a function of
risk_level, tool_type, accumulated trust_score, sandbox availability, and provenance flags - all
version-controlled and unit-testable (ADR 0005 #1).

Invariants:
  - low      -> allow
  - medium   -> ask, but auto-allow once trust crosses the threshold (ADR 0005 #2)
  - high     -> ask, NEVER auto (risk ceiling)
  - critical -> deny, always
  - shell/browser/mcp without a live sandbox -> deny (ADR 0011 guard)
  - any injection-suspected provenance -> force at least ask (never auto)
"""

from __future__ import annotations

from dataclasses import dataclass

from hibob_core.config import settings

_SANDBOX_TOOL_TYPES = {"shell", "browser", "mcp"}
_AUTO_ELIGIBLE = {"low", "medium"}  # risk tiers that may ever reach auto-allow


@dataclass(frozen=True)
class Decision:
    decision: str  # "allow" | "ask" | "deny"
    reason: str


def decide(
    *,
    risk_level: str,
    tool_type: str,
    trust_score: float = 0.0,
    sandbox_available: bool = False,
    provenance_flagged: bool = False,
) -> Decision:
    # Hard sandbox guard first (ADR 0011): these tool types cannot run without a sandbox.
    if tool_type in _SANDBOX_TOOL_TYPES and not sandbox_available:
        return Decision("deny", f"{tool_type} tools require an ephemeral sandbox (not yet available)")

    if risk_level == "critical":
        return Decision("deny", "critical-risk tools are default-deny (ADR 0005)")

    if risk_level == "low":
        # Even low risk: a suspected-injection context should be reviewed, not auto-run.
        if provenance_flagged:
            return Decision("ask", "low risk but injection-suspected content in context")
        return Decision("allow", "low risk")

    if risk_level == "medium":
        if provenance_flagged:
            return Decision("ask", "medium risk with injection-suspected content")
        if trust_score >= settings.trust_auto_threshold:
            return Decision("allow", f"medium risk auto-allowed by trust {trust_score:.2f}")
        return Decision("ask", "medium risk below trust threshold")

    if risk_level == "high":
        # High risk never auto-escalates regardless of trust (risk ceiling).
        return Decision("ask", "high risk always requires approval")

    return Decision("deny", f"unknown risk_level '{risk_level}' -> fail closed")


def can_auto_escalate(risk_level: str) -> bool:
    """Whether trust may ever move this risk tier to auto (used by GET trust-score ceiling)."""
    return risk_level in _AUTO_ELIGIBLE
