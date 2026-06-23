# Hibob Development Workflow

Status: Draft matang v0.1 - self-building loop gate implemented (Phase 5 ✅, ADR 0013): proposal
self-build = `tool_run` lewat Policy Engine, risk dinamis berbasis file + merge gate
tests→eval→docs→approval. Lihat `../backend/hibob_core/selfbuild/`. CI/DeepEval/Replay = Phase 6.

## 1. Development philosophy

Hibob should be built through a disciplined self-building loop:

```text
conversation -> decision -> docs -> issue -> branch -> implementation -> tests/evals -> review -> merge -> memory update
```

## 2. Git workflow

- `main` must stay stable.
- Work happens on feature branches.
- Every behavior change updates docs/evals.
- Every architecture decision creates ADR.
- No direct AI auto-commit to main.

Branch naming:

```text
feat/memory-core
feat/tool-gateway
fix/rag-source-citation
docs/prd-v0-1
adr/model-router
```

## 3. Roles in development

### Bob

- final product owner,
- approves memory decisions,
- approves high-risk tool actions,
- decides trade-offs.

### Hibob

- proposes architecture,
- challenges assumptions,
- creates draft docs/tasks,
- reviews consistency,
- suggests evals.

### Cline/Aider

- implementation assistant,
- writes code/docs under scoped tasks,
- runs tests with approval,
- drafts patches.

## 4. Issue format

Each issue should include:

```markdown
## Goal

## Why now

## Scope

## Non-goals

## Acceptance criteria

## Risk level

## Docs to update

## Evals to add/update
```

## 5. Pull request format

```markdown
## Summary

## Changed files

## Behavioral changes

## Tests

## Evals

## Security/privacy impact

## Docs updated

## Rollback plan

## Policy risk classification (high if security/policy/schema files touched)

## Replay batch result (required if prompt/retrieval/policy logic changed)
```

## 6. Definition of done

A task is done when:

- code works locally,
- unit tests pass,
- relevant evals pass,
- docs updated,
- audit/security implications checked,
- Bob approves if high-risk,
- ADR added if architecture decision.

For self-build proposals (Hibob-authored patches/doc updates, §11), "done" additionally requires going through the merge gate in §11a (ADR 0013) - there is no separate, lighter-weight path for changes Hibob made about itself.

## 7. Documentation-driven development

Before coding a core feature:

1. Update blueprint/architecture section.
2. Define API contract.
3. Define data model.
4. Define eval cases.
5. Implement.
6. Validate against docs.

This prevents Hibob from becoming random tool glue.

## 8. AI coding agent rules

### Cline

Good for:

- multi-file edits,
- IDE context,
- command-assisted debugging,
- feature implementation.

Rules:

- require approval for file writes/commands,
- keep task scope narrow,
- inspect diff manually.

### Aider

Good for:

- terminal-driven edits,
- git-aware patching,
- docs refactors,
- quick implementation.

Rules:

- start with clean git status,
- commit manually or reviewed,
- avoid simultaneous edits with Cline.

## 9. Local environment workflow

Recommended:

```text
WSL2 Ubuntu
Docker Desktop WSL2 backend
repo in WSL filesystem
Docker Compose for services
Python venv for Hibob Core
Node optional for UI
```

## 10. Commit conventions

```text
feat: add memory candidate extraction
fix: enforce approval for high-risk tools
docs: update PRD scope
adr: choose Qdrant for vector store
test: add memory conflict evals
chore: update docker compose
```

## 11. Self-building loop v0.1

At the end of a design conversation:

1. Hibob creates session summary.
2. Hibob extracts decisions.
3. Hibob proposes memory candidates.
4. Hibob proposes doc changes.
5. Bob approves.
6. Hibob drafts issues.
7. Cline/Aider implements.
8. Tests/evals run.
9. Results become improvement log.

Steps 4, 6, and "Cline/Aider implements" each correspond to a concrete tool call (`propose_blueprint_update`, `create_github_issue_draft`, `draft_patch`) - none of them is a special, implicitly-trusted action. See §11a for the gate they all go through.

## 11a. Self-building loop safety gate (ADR 0013)

Until this ADR, "Hibob helps build Hibob" was specified only as the step sequence above, with no explicit gate ensuring Hibob cannot propose or merge an unsafe change to its own rules. The gate:

1. `propose_blueprint_update`, `draft_patch`, and `create_github_issue_draft` are `tool_run`s like any other, evaluated by the Policy Engine (doc 05 §6a).
2. **Risk classification by file touched, not diff size.** A one-line change to a security policy, tool permission, or memory-schema file is classified high risk exactly the same as a hundred-line one.
3. **No trust-tier escalation for those files.** `tool_trust_scores` (doc 05 §6a) can move ordinary doc edits from `ask` to `auto` over time; it never does so for security/policy/schema files, regardless of how clean the run history is.
4. **Merge requires, in order:** unit tests passing -> relevant DeepEval suite passing -> docs updated in the same change -> Bob's explicit approval recorded as an `approval_request`.
5. **Replay Harness gate.** If the change touches prompt, retrieval, or policy logic, the Replay Harness (ADR 0008, doc 09 §5 `replay_migration_eval`) must run against the affected eval suites before merge, and the PR must cite the replay batch result.

This is intentionally slower than an ungated self-build loop would be - the trade is deliberate: Hibob does not get to modify its own safety rails with less scrutiny than any other high-risk tool action.

## 12. CI/CD v0.1

Initial CI:

- lint backend,
- unit tests,
- schema validation,
- DeepEval core suite optional/manual first,
- markdown link/format checks optional.

Deployment is not v0.1 priority.

## 13. Release versioning

```text
v0.1 Blueprint Guardian + Memory Core
v0.2 Knowledge Base + RAG
v0.3 Tool Gateway + limited tools
v0.4 Dev Partner + repo workflow
v0.5 Self-testing agent loop
v1.0 Personal AI OS beta
```

## 14. Anti-patterns

Do not:

- code before requirement is stable,
- use AI agent to patch broad areas without scope,
- skip evals for prompt changes,
- add new tools just because possible,
- hide failed experiments,
- let docs drift from implementation,
- let a self-build proposal (§11a) skip Policy Engine evaluation because Hibob authored it,
- let trust-tier escalation apply to security/policy/memory-schema file changes regardless of how clean prior runs were,
- merge a prompt/retrieval/policy change without citing a Replay Harness batch result.
