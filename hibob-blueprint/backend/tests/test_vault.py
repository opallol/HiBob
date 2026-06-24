"""Credential Vault store/resolve (ADR 0014). Fake (identity) sealer - no crypto dep in tests."""

import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.vault import repository as repo
from hibob_core.vault import service

USER = core_repo.BOB_USER_ID


class _FakeSealer:
    key_ref = "env:TEST"

    def seal(self, plaintext: str) -> bytes:
        return ("sealed:" + plaintext).encode()

    def open(self, ciphertext: bytes) -> str:
        return bytes(ciphertext).decode().removeprefix("sealed:")


async def test_store_returns_non_secret_view_and_marks_critical(monkeypatch):
    captured = {}

    async def store(conn, **k):
        captured.update(k)
        return uuid.uuid4()

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "store", store)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    out = await service.store_credential(
        None, _FakeSealer(), user_id=USER, label="gmail", credential_type="email",
        account_identifier="bob@example.com", secret="hunter2",
    )
    assert out["risk_tier"] == "critical"
    assert "secret" not in out and "hunter2" not in str(out)
    assert captured["secret_ciphertext"] == b"sealed:hunter2"  # stored sealed, never plaintext


async def test_resolve_requires_sandbox(monkeypatch):
    with pytest.raises(service.VaultError):
        await service.resolve(None, _FakeSealer(), credential_ref=uuid.uuid4(),
                              tool_run_id=None, purpose="login", in_sandbox=False)


async def test_resolve_in_sandbox_returns_secret_and_logs_use(monkeypatch):
    uses = {"n": 0}
    cid = uuid.uuid4()

    async def get_row(conn, credential_id):
        return {"secret_ciphertext": b"sealed:hunter2"}

    async def record_use(conn, **k):
        uses["n"] += 1

    async def touch_used(conn, credential_id):
        return None

    async def audit(conn, **k):
        return None

    monkeypatch.setattr(repo, "get_row", get_row)
    monkeypatch.setattr(repo, "record_use", record_use)
    monkeypatch.setattr(repo, "touch_used", touch_used)
    monkeypatch.setattr(core_repo, "write_audit", audit)

    secret = await service.resolve(None, _FakeSealer(), credential_ref=cid,
                                   tool_run_id=uuid.uuid4(), purpose="login", in_sandbox=True)
    assert secret == "hunter2"     # decrypted for immediate use
    assert uses["n"] == 1          # the use was logged (that it happened, not the value)
