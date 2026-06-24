"""Credential Vault API (Phase 7, ADR 0014).

Store accepts a secret and returns ONLY a non-secret view (id/label). There is deliberately NO
endpoint that returns a decrypted secret - resolution happens server-side inside the sandbox during
a tool run, never over the API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hibob_core.db import repositories as core_repo
from hibob_core.db.pool import get_pool
from hibob_core.vault import repository as repo, service
from hibob_core.vault.sealer import VaultUnavailable, default_sealer

router = APIRouter()


class StoreCredentialRequest(BaseModel):
    label: str
    credential_type: str          # email | sso | digital_signature | messaging | other
    account_identifier: str | None = None
    secret: str


@router.post("/vault/credentials")
async def store_credential(req: StoreCredentialRequest) -> dict:
    try:
        sealer = default_sealer()
    except VaultUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.store_credential(
                conn, sealer, user_id=core_repo.BOB_USER_ID, label=req.label,
                credential_type=req.credential_type, account_identifier=req.account_identifier,
                secret=req.secret,
            )


@router.get("/vault/credentials")
async def list_credentials() -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        creds = await repo.list_labels(conn, core_repo.BOB_USER_ID)
    return {"credentials": creds, "count": len(creds)}
