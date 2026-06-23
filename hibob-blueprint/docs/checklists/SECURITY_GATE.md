# Security Gate Checklist

Before enabling any new tool or automation, confirm:

- [ ] Tool has owner.
- [ ] Tool has input/output schema.
- [ ] Risk level assigned.
- [ ] Permission mode assigned.
- [ ] Audit logging enabled.
- [ ] Secret redaction tested.
- [ ] Prompt injection handling considered.
- [ ] Rollback plan exists for write/destructive actions.
- [ ] Tool is disabled by default until reviewed.
- [ ] DeepEval safety/policy test added.
- [ ] Phoenix trace captures tool run.
- [ ] Tool's allow/ask/deny is covered by a `policy_rules` entry, not left to model judgment (ADR 0005).
- [ ] If the tool type is shell, browser, or third-party MCP, the ephemeral sandbox (no-network/read-only default) has been verified working for it before go-live (ADR 0011).
- [ ] If the tool can trigger a cloud model call, a budget ceiling is configured for it (ADR 0012).
- [ ] Tool's risk ceiling for trust-score escalation is set, and confirmed to exclude critical actions (ADR 0005).

Critical actions must remain denied in v0.1 unless Bob manually overrides outside automated flow.
