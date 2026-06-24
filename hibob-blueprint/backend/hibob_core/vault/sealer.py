"""Credential sealing (Phase 7, ADR 0014).

The encryption key lives OUTSIDE the database (env / OS keystore), referenced by `encryption_key_ref`
in the row but never stored beside the ciphertext. FernetSealer is the default; it lazy-imports
`cryptography` (the `vault` extra). A Sealer is injected, so the vault logic is testable with a fake.
"""

from __future__ import annotations

from typing import Protocol


class VaultUnavailable(Exception):
    """Sealing needs a key + the `vault` extra (cryptography)."""


class Sealer(Protocol):
    key_ref: str

    def seal(self, plaintext: str) -> bytes: ...
    def open(self, ciphertext: bytes) -> str: ...


class FernetSealer:
    def __init__(self, key: str | None, key_ref: str):
        if not key:
            raise VaultUnavailable("no vault key configured (set HIBOB_VAULT_KEY)")
        try:
            from cryptography.fernet import Fernet  # lazy (optional `vault` extra)
        except ImportError as e:
            raise VaultUnavailable("vault needs the 'vault' extra: pip install '.[vault]'") from e
        self._f = Fernet(key)
        self.key_ref = key_ref

    def seal(self, plaintext: str) -> bytes:
        return self._f.encrypt(plaintext.encode("utf-8"))

    def open(self, ciphertext: bytes) -> str:
        return self._f.decrypt(bytes(ciphertext)).decode("utf-8")


def default_sealer() -> FernetSealer:
    from hibob_core.config import settings
    return FernetSealer(settings.vault_key, settings.vault_key_ref)
