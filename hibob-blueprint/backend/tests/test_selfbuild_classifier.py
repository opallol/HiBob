"""Self-build change-risk classification (ADR 0013). Pure."""

from hibob_core.selfbuild import classifier


def test_sensitive_paths_force_high():
    for p in ["backend/hibob_core/policy/engine.py", "database/schema.sql",
              "backend/hibob_core/db/migrations/0007_phase4.sql", "docs/08_SECURITY.md"]:
        risk, reasons = classifier.effective_risk("medium", [p])
        assert risk == "high", p
        assert reasons


def test_ordinary_paths_keep_base():
    risk, reasons = classifier.effective_risk("medium", ["docs/16_GLOSSARY.md", "README.md"])
    assert risk == "medium"
    assert reasons == []


def test_mixed_paths_escalate():
    risk, _ = classifier.effective_risk("low", ["README.md", "backend/hibob_core/policy/engine.py"])
    assert risk == "high"


def test_never_lowers_risk():
    # base already critical: a non-sensitive change must not drop it
    risk, _ = classifier.effective_risk("critical", ["README.md"])
    assert risk == "critical"
