# ADR 0014 - Operational Credential Vault for Tool-Use Login/Send Actions

## Status
Accepted for blueprint v0.1 (storage layer only - no credential-using tool is enabled until its own phase gate, see Consequences)

## Context
Bob holds real operational credentials (personal email, government SSO, digital signature, messaging) that he wants Hibob to eventually use to act on his behalf - logging into a portal, sending an email, sending a message - not merely to "know about" as a memory fact. This is categorically different from a `secret`-tier memory (doc 08 §3): a memory fact describes the world, a vault credential *is* live authentication material for accounts where misuse has real-world consequences (a government SSO/digital-signature credential can be used to act in Bob's official capacity).

The existing `memories` table and its `sensitivity: secret` tier (ERD doc 03 §4) are the wrong home for this: memory rows are designed to be retrieved into prompts and embedded into Qdrant, which is exactly what must never happen to a live credential (doc 08 §3, §10). A plain document under `docs/` is also the wrong home, independent of git: this workspace lives inside a OneDrive-synced folder, so any plaintext file here already replicates to cloud storage outside Hibob's control regardless of `.gitignore`.

`00_EXECUTIVE_BLUEPRINT.md` §6 excludes "email/calendar/write action" from v0.1 scope. That exclusion stays - this ADR only defines where and how credentials are stored so the capability can be added later without retrofitting storage, not when the first credential-using tool goes live.

## Decision
Introduce a `credential_vault` table, separate from `memories`, holding: `label`, `credential_type` (email/sso/digital_signature/messaging/other), a non-secret `account_identifier`, a `secret_ciphertext` sealed with a key referenced by `encryption_key_ref` and held outside the database (OS keystore/DPAPI or an external key file outside any synced folder - never alongside the ciphertext), and `risk_tier` hard-defaulted to `critical`.

Any tool that needs a credential receives a `credential_ref` (the vault row id), never the decrypted value. The Tool Gateway resolves the secret server-side, inside the Ephemeral Sandbox (ADR 0011), at the moment of execution; the decrypted value never enters `tool_runs.input_json`/`output_json`, never enters a prompt, never enters a Phoenix trace, and is never written to `memories` or a Qdrant payload. Every resolution is logged to a `credential_uses` row (credential id, tool_run id, purpose) - the audit trail records *that* a credential was used and for what, never the value itself, matching doc 08 §10's "references/IDs instead of full secret content" rule.

`credential_vault` rows are always `risk_tier = critical`. Per ADR 0005 §3.8 and the non-negotiable refusal list (doc 08 §15), trust-score escalation never applies to critical-risk actions - a credential-using tool is `ask` (or `deny` pre-Phase-7) on every single run, forever, regardless of how many times it has succeeded before.

## Consequences
Positive: the storage and resolution pattern exists ahead of need, so the eventual login/send-message tools are built on a vault designed for this from day one, not retrofitted onto memory or document storage. The decrypted value's blast radius is bounded to the single sandboxed tool-run that needed it.

Negative: adds a new subsystem (key management, sealed storage, resolution path) before any tool actually uses it - justified here only because Bob explicitly wants this capability later (this ADR), unlike speculative scope.

Phase gate: `credential_vault` storage and resolution land in Phase 4 alongside the Sandbox Runtime (ADR 0011), since both are prerequisites for any high-risk tool. No credential-using tool (login, send email, send message) is enabled until Phase 7 (Controlled Browser & Automation) at the earliest, and only behind: Tool Gateway + Sandbox + per-action approval with no auto-escalation. `00_EXECUTIVE_BLUEPRINT.md` §6's v0.1 exclusion of "email/calendar/write action" is unaffected by this ADR.

Immediate, non-deferrable action regardless of phase: the existing plaintext `docs/credential_bob.md` predates this ADR, was never the vault, and was exposed twice already - once by living unencrypted in a OneDrive-synced folder, once by being read into a cloud LLM session for this design discussion. Bob should rotate at minimum the Gmail and Kemenkeu/digital-signature credentials in that file independent of when the vault itself gets built, and the raw file should be migrated into the vault (or deleted after rotation) rather than left as a standing plaintext copy.

## Alternatives considered
- Keep credentials as `secret`-tier memory rows: rejected - memory is designed for retrieval into prompts/vectors, which is the one thing a live credential must never do.
- Encrypt the markdown file in place (e.g. age/gpg) and leave it under `docs/`: rejected as the long-term answer - still couples credential storage to the documentation tree and to a synced folder; acceptable only as a stopgap, not the vault.
- Defer all storage design until a credential-using tool is actually being built (Phase 7): rejected - storage/encryption design done under deadline pressure right before shipping a critical-risk tool is exactly how secrets end up mishandled; doing it now, unhurried, costs little since no code exists yet.
