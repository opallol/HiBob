"""Policy Engine decision matrix (ADR 0005). Pure - the model never adjudicates."""

from hibob_core.config import settings
from hibob_core.policy import engine

HI = settings.trust_auto_threshold  # at/above -> medium may auto


def d(**k):
    k.setdefault("tool_type", "internal")
    return engine.decide(**k).decision


def test_risk_tier_defaults():
    assert d(risk_level="low") == "allow"
    assert d(risk_level="medium") == "ask"
    assert d(risk_level="high") == "ask"
    assert d(risk_level="critical") == "deny"
    assert d(risk_level="weird") == "deny"  # fail closed


def test_medium_auto_allows_only_above_trust():
    assert d(risk_level="medium", trust_score=HI - 0.01) == "ask"
    assert d(risk_level="medium", trust_score=HI) == "allow"


def test_high_and_critical_never_auto():
    assert d(risk_level="high", trust_score=1.0) == "ask"
    assert d(risk_level="critical", trust_score=1.0) == "deny"


def test_sandbox_guard_denies_shell_browser_mcp():
    for tt in ("shell", "browser", "mcp"):
        assert d(risk_level="low", tool_type=tt, sandbox_available=False) == "deny"
        # with a sandbox it falls back to the normal risk decision
        assert d(risk_level="low", tool_type=tt, sandbox_available=True) == "allow"


def test_injection_forces_at_least_ask():
    assert d(risk_level="low", provenance_flagged=True) == "ask"
    assert d(risk_level="medium", trust_score=1.0, provenance_flagged=True) == "ask"


def test_can_auto_escalate_ceiling():
    assert engine.can_auto_escalate("low") and engine.can_auto_escalate("medium")
    assert not engine.can_auto_escalate("high")
    assert not engine.can_auto_escalate("critical")
