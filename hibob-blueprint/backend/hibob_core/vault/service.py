"""Credential Vault service (Phase 7, ADR 0014).

Store: seal the secret, persist ciphertext + a key REFERENCE (never the key). risk_tier is always
critical. Resolve: only ever called server-side, INSIDE a sandboxed tool-run; the decrypted value is
returned to the caller for immediate use and is NEVER written to tool_runs/prompt/trace/memory. Every
resolution is logged to credential_uses (that it was used + for what, never the value).
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.db import repositories as core_repo
from hibob_core.vault import repository as repo
from hibob_core.vault.sealer import Sealer


class VaultError(Exception):
    pass


async def store_credential(
    conn: asyncpg.Connection,
    sealer: Sealer,
    *,
    user_id: uuid.UUID,
    label: str,
    credential_type: str,
    account_identifier: str | None,
    secret: str,
) -> dict:
    cred_id = await repo.store(
        conn, user_id=user_id, label=label, credential_type=credential_type,
        account_identifier=account_identifier, secret_ciphertext=sealer.seal(secret),
        encryption_key_ref=sealer.key_ref,
    )
    await core_repo.write_audit(
        conn, actor_type="user", actor_id=str(user_id), event_type="credential.stored",
        target_type="credential", target_id=str(cred_id),
        metadata={"label": label, "credential_type": credential_type},  # no secret
    )
    # Return non-secret view only.
    return {"id": str(cred_id), "label": label, "credential_type": credential_type,
            "risk_tier": "critical"}


async def resolve(
    conn: asyncpg.Connection,
    sealer: Sealer,
    *,
    credential_ref: uuid.UUID,
    tool_run_id: uuid.UUID | None,
    purpose: str,
    in_sandbox: bool,
) -> str:
    """Decrypt a credential for immediate sandboxed use. Returns the secret; logs the use only."""
    if not in_sandbox:
        raise VaultError("credentials may only be resolved inside the ephemeral sandbox (ADR 0014)")
    row = await repo.get_row(conn, credential_ref)
    if row is None:
        raise VaultError("credential not found")
    secret = sealer.open(row["secret_ciphertext"])
    await repo.record_use(conn, credential_id=credential_ref, tool_run_id=tool_run_id, purpose=purpose)
    await repo.touch_used(conn, credential_ref)
    await core_repo.write_audit(
        conn, actor_type="system", actor_id=None, event_type="credential.used",
        target_type="credential", target_id=str(credential_ref),
        metadata={"purpose": purpose, "tool_run_id": str(tool_run_id) if tool_run_id else None},
    )
    return secret  # caller uses it in-flight; never persisted
