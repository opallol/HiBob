"""Self-build change-risk classification (Phase 5, ADR 0013). Pure.

"Hibob helps build Hibob" must not be the one unguarded path. A proposed change's risk is assigned
by WHICH files it touches: anything touching security policy, tool-permission, or schema/migration
files is always high risk regardless of diff size, and (because high never auto-escalates in the
engine) can never be trust-promoted to auto. The classifier only ever RAISES risk, never lowers it.
"""

from __future__ import annotations

import fnmatch

from hibob_core.config import settings

_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _matches(path: str, globs: list[str]) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    return any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(path, g) for g in globs)


def effective_risk(base_risk: str, paths: list[str]) -> tuple[str, list[str]]:
    """Return (risk, reasons). High if any path is sensitive; otherwise base (never lower)."""
    reasons: list[str] = []
    sensitive = [p for p in (paths or []) if _matches(p, settings.selfbuild_sensitive_globs)]
    if sensitive:
        reasons = [f"touches sensitive path: {p}" for p in sensitive]
        # never below high for sensitive files; never lower than base either
        risk = "high" if _ORDER["high"] >= _ORDER.get(base_risk, 1) else base_risk
        return risk, reasons
    return base_risk, reasons
