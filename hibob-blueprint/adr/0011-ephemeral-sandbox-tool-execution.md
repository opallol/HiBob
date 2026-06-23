# ADR 0011 - Ephemeral OS-Level Sandbox for Tool Execution

## Status
Accepted for blueprint v0.1

## Context
Shell, browser, and third-party MCP governance (doc 08 §6-8) is enforced at the policy/prompt level: allowed commands, allowed hosts, approval requirements. If that policy layer is ever bypassed — through a prompt injection that slips past ADR 0005's classifier, or a bug in the policy engine itself — there is no physical containment layer beneath it. Policy is necessary but, alone, is a single point of failure.

## Decision
High-risk tool types (`shell`, `browser`, third-party `mcp`) execute inside an ephemeral, per-run Docker container: no network access by default, read-only filesystem except an explicitly scoped workdir, destroyed immediately after the run completes. Network or write exceptions are explicit allowlist entries recorded on the tool's registry definition (`tools.input_schema_json`/constraints), never an ambient default. Every sandboxed execution is recorded in a `sandbox_runs` table linked to its `tool_run`.

## Consequences
Positive: true defense-in-depth — even a successful policy bypass cannot exfiltrate data or persist changes, because the execution environment itself is isolated and disposable regardless of what the policy layer decided.
Negative: adds container orchestration overhead and slightly increases tool-call latency; requires the local Docker/WSL2 stack (already part of doc 07) to support fast ephemeral container spin-up.

## Alternatives considered
- Policy-only enforcement with no physical isolation (status quo): rejected, single point of failure identified in review finding 2.9.
- Full VM-level isolation (Firecracker/gVisor) from day one: deferred — disproportionate infrastructure for personal-scale v0.1; ephemeral Docker containers capture most of the safety value at a fraction of the operational cost. Revisit if Hibob moves toward multi-user or production use (doc 11 Phase 8+).
