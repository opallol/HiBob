-- Hibob Phase 7 (Controlled Browser & Automation) - Credential Vault (ADR 0014).
-- Tables copied from ../../../database/schema.sql - DO NOT diverge.
-- sandbox_runs already created in 0007_phase4.sql (seam, now actually used).
-- The decrypted value NEVER lands here: only the sealed ciphertext + a key REFERENCE (the key
-- itself lives in an OS keystore / external file outside the DB and any synced folder).
--
-- Apply manually: docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0009_phase7.sql

CREATE TABLE IF NOT EXISTS credential_vault (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    label TEXT NOT NULL,
    credential_type TEXT NOT NULL,      -- email | sso | digital_signature | messaging | other
    account_identifier TEXT,            -- non-secret (email/username) - safe to display
    secret_ciphertext BYTEA NOT NULL,   -- sealed; the key is NOT stored here
    encryption_key_ref TEXT NOT NULL,   -- pointer to OS keystore/external key file, never the key
    risk_tier TEXT NOT NULL DEFAULT 'critical',
    last_rotated_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credential_vault_user ON credential_vault(user_id);

CREATE TABLE IF NOT EXISTS credential_uses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id UUID REFERENCES credential_vault(id),
    tool_run_id UUID REFERENCES tool_runs(id),
    purpose TEXT NOT NULL,              -- records THAT a credential was used + for what, never the value
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credential_uses_credential ON credential_uses(credential_id);
