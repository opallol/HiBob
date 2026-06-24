# Hibob Security, Privacy & Governance

Status: Draft matang v0.1 - Sandbox (ADR 0011) + Credential Vault (ADR 0014) implemented (Phase 7 ✅):
shell/browser/mcp jalan dalam sandbox ephemeral (`../backend/hibob_core/sandbox/`); kredensial
tersegel (kunci di luar DB), diresolusi **hanya dalam sandbox**, decrypted value tak pernah masuk
prompt/trace/`tool_runs`/memory (`../backend/hibob_core/vault/`). Docker/Playwright nyata + tool
login/kirim = seam berikutnya.

## 1. Security posture

Hibob harus diasumsikan sebagai sistem yang akan memegang data personal, dokumen proyek, repo, dan tools yang bisa bertindak. Karena itu default-nya bukan “buka akses”, tetapi **least privilege**.

## 2. Core threats

| Threat | Example | Mitigation |
|---|---|---|
| Prompt injection | Web/doc berkata “abaikan instruksi” | Provenance tagging + structural delimiters + suspicious-pattern classifier (ADR 0005), policy decision stays deterministic |
| Tool abuse | Agent salah menjalankan shell/browser | Tool Gateway, risk levels, approval, plus ephemeral sandbox underneath (ADR 0011) |
| Data exfiltration | Memory private terkirim ke cloud | Privacy tier, redaction, cloud approval, sandbox no-network-by-default (ADR 0011) |
| Memory poisoning | Dokumen palsu masuk sebagai fakta | Source trust, candidate approval, conflict detection, memory graph contradiction edges (ADR 0006) |
| Credential leak | Secret masuk trace/prompt | secret scanner, trace redaction |
| Over-automation | Agent kirim email/deploy tanpa izin | critical actions default deny, trust score never escalates past risk ceiling (ADR 0005) |
| Supply-chain tool risk | MCP server malicious | MCP allowlist, sandbox, server review |
| Stale knowledge | Jawaban dari dokumen lama | freshness metadata, recrawl/reindex policy, reflection job flags stale sources (ADR 0010) |
| Unbounded cloud spend | Retry loop atau task panjang membakar budget tanpa terdeteksi | Hard daily/session cost ceiling, auto-pause + approval on breach (ADR 0012) |
| Unsafe self-build merge | Hibob mengusulkan perubahan ke file policy/security/schema dirinya sendiri | Self-build proposals are policy-evaluated tool_runs, security/policy/schema changes always high risk, Bob approval + tests + DeepEval required (ADR 0013) |
| Judge/evaluation drift | Model judge eval diam-diam berubah perilaku setelah update provider | Pinned judge version + golden dataset agreement score, re-validated on judge change (ADR 0009) |
| Operational credential misuse | Kredensial login/kirim pesan tersimpan dipakai di luar scope yang disetujui, atau nilai asli bocor ke prompt/trace | Credential Vault terenkripsi at rest, tool menerima `credential_ref` bukan nilai asli, resolusi server-side di dalam sandbox, risk tier selalu `critical`, tidak pernah trust-tier escalation (ADR 0014) |

## 3. Privacy tiers

### Public

Boleh dikirim ke cloud. Contoh: dokumentasi publik.

### Internal

Data proyek Hibob. Cloud boleh jika Bob menyetujui atau policy mengizinkan.

### Private

Data pribadi Bob. Default lokal. Cloud hanya dengan approval eksplisit.

### Secret

Credential, token, password, private key, finansial sensitif. Tidak boleh masuk prompt, trace, vector DB tanpa redaction khusus.

## 4. Data flow policy

Sebelum data masuk model cloud:

1. Identify source.
2. Classify sensitivity.
3. Apply redaction if needed.
4. Log decision.
5. Ask approval if tier private.
6. Never send secret.

## 5. Tool governance

All tools must have:

- owner,
- risk level,
- input/output schema,
- allowed scopes,
- allowed hosts/directories,
- permission mode,
- audit enabled,
- rollback availability.

## 6. MCP governance

MCP servers are powerful because they expose tools and data to AI clients. Hibob must treat every MCP server as a capability boundary.

MCP onboarding checklist:

- Who maintains the server?
- What tools does it expose?
- Does it access filesystem/network/secrets?
- Can it execute commands?
- Can it write data?
- Is it isolated in Docker/sandbox?
- Is it pinned to version?
- Is logging enabled?
- Does it support allowlist?

## 7. Browser governance

Playwright MCP v0.1 policy:

- allowed hosts only,
- localhost preferred,
- no sensitive accounts,
- no purchases,
- no submit to public sites,
- approval before click/type/submit,
- screenshot/logs stored as internal,
- browser context reset between sessions.

## 8. Shell/code execution governance

Shell access is high risk.

Allowed v0.1:

- read-only commands,
- tests/lint in repo sandbox,
- package install only with approval,
- no system-level changes,
- no secret printing.

Denied v0.1:

- rm -rf without explicit manual review,
- curl pipe sh,
- chmod/chown outside repo,
- production deploy,
- credential export,
- untrusted script execution.

Sejak ADR 0011, shell/browser/MCP pihak ketiga yang lolos approval tetap berjalan di container Docker ephemeral per run: no network by default, filesystem read-only kecuali workdir yang di-scope, container dihancurkan setelah run. Ini lapisan containment fisik di bawah policy - bukan pengganti approval di atas, melainkan jaring pengaman kalau policy/classifier (doc 05 §6a, §10) ternyata berhasil dilewati.

## 9. Memory governance

- Private/secret memory not embedded via cloud without approval.
- All durable memory has source.
- Memory conflict must be tracked.
- Bob can export/delete memory.
- Memory candidate does not equal truth.

## 10. Observability privacy

Phoenix traces and logs must redact:

- API keys,
- tokens,
- passwords,
- secret file content,
- private memory unless explicitly allowed,
- sensitive tool inputs.

Trace record should include references/IDs instead of full secret content.

## 11. Approval categories

| Category | Required approval |
|---|---|
| Store durable memory | yes in v0.1 |
| Send private context to cloud | yes |
| Write file | yes |
| Run shell command | yes initially |
| Browser click/type | yes initially |
| Trigger external workflow | yes |
| Delete data | denied v0.1 |
| Deploy production | denied v0.1 |
| Send external message | denied v0.1 - deferred to Phase 7 at earliest via Credential Vault (ADR 0014), per-action approval, never trust-tier escalated |
| Resolve a Credential Vault entry into a tool run | yes, every single time, no escalation ever (ADR 0014) |
| Cloud spend ceiling breach | yes - pauses cloud calls until resolved (ADR 0012) |
| Merge self-build change to security/policy/schema files | yes always, never trust-tier escalated (ADR 0013) |

## 12. Incident response

If Hibob performs unsafe/wrong action:

1. Stop agent loop.
2. Preserve trace and audit logs.
3. Classify incident.
4. Revert file/data if possible.
5. Add regression test.
6. Update tool policy.
7. Add ADR if architecture/policy changes.

## 13. Security gates before enabling advanced tools

Before Playwright/Activepieces/shell auto-actions:

- Tool registry implemented.
- Approval workflow implemented.
- Audit log implemented.
- Phoenix tracing enabled.
- DeepEval safety tests pass.
- Sandbox configured.
- Secret redaction tested.
- Policy engine (`policy_rules`) implemented and unit-tested for allow/ask/deny determinism (ADR 0005).
- Ephemeral sandbox runtime (ADR 0011) verified to default to no-network/read-only.
- Cost circuit breaker (ADR 0012) configured with a non-zero ceiling before any cloud-model tool is enabled.
- At least one full red-team cycle (ADR 0009) run against the sandboxed instance with zero unresolved `succeeded` attempts.
- Before any credential-using tool (login, send email/message): Credential Vault (ADR 0014) encrypted-at-rest storage live, `credential_ref` resolution tested to never leak a decrypted value into prompt/trace/memory/vector, and the tool's risk tier confirmed `critical` with escalation disabled.

## 14. Governance artifacts

- `TOOL_POLICY.md`
- `MEMORY_POLICY.md`
- `PRIVACY_TIERS.md`
- `SECURITY_GATE.md`
- `ADR records`
- `audit_logs`
- `eval_results`

## 15. Non-negotiable refusals

Hibob must refuse or pause if asked to:

- expose secrets,
- bypass approval,
- execute unknown destructive command,
- trust web instructions over system policy,
- write to production without gate,
- hide audit traces,
- let trust score (doc 05 §6a) escalate a tool past its risk ceiling or apply to critical risk,
- exceed a cost ceiling silently instead of pausing and raising approval (ADR 0012),
- merge a self-build change to security/policy/memory-schema files without Bob's explicit approval, regardless of diff size (ADR 0013),
- expose a decrypted Credential Vault value in prompt, trace, memory, or vector payload, or let a credential-using tool run without per-action approval, regardless of prior successful runs (ADR 0014).
