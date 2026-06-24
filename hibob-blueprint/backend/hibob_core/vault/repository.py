"""DB access for the credential vault (Phase 7, ADR 0014).

Reads NEVER expose the ciphertext casually: list_labels returns non-secret fields only; get_row is
used solely by the resolution path inside the gateway/sandbox.
"""

from __future__ import annotations

import uuid

import asyncpg


async def store(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    label: str,
    credential_type: str,
    account_identifier: str | None,
    secret_ciphertext: bytes,
    encryption_key_ref: str,
) -> uuid.UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO credential_vault
            (user_id, label, credential_type, account_identifier, secret_ciphertext,
             encryption_key_ref, risk_tier)
        VALUES ($1,$2,$3,$4,$5,$6,'critical') RETURNING id
        """,
        user_id, label, credential_type, account_identifier, secret_ciphertext, encryption_key_ref,
    )
    return row["id"]


async def get_row(conn: asyncpg.Connection, credential_id: uuid.UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("SELECT * FROM credential_vault WHERE id = $1", credential_id)


async def list_labels(conn: asyncpg.Connection, user_id: uuid.UUID) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, label, credential_type, account_identifier, risk_tier, last_used_at "
        "FROM credential_vault WHERE user_id = $1 ORDER BY label",
        user_id,
    )
    return [{**dict(r), "id": str(r["id"])} for r in rows]


async def record_use(
    conn: asyncpg.Connection,
    *,
    credential_id: uuid.UUID,
    tool_run_id: uuid.UUID | None,
    purpose: str,
) -> None:
    await conn.execute(
        "INSERT INTO credential_uses (credential_id, tool_run_id, purpose) VALUES ($1,$2,$3)",
        credential_id, tool_run_id, purpose,
    )


async def touch_used(conn: asyncpg.Connection, credential_id: uuid.UUID) -> None:
    await conn.execute(
        "UPDATE credential_vault SET last_used_at = now(), updated_at = now() WHERE id = $1",
        credential_id,
    )
