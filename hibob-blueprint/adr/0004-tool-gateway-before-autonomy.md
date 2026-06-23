# ADR 0004 - Tool Gateway Before Autonomy

## Status
Accepted for blueprint v0.1

## Context
Hibob will eventually use tools such as Playwright MCP, Activepieces, repo tools, shell commands, and MCP servers. Tool use creates real risk.

## Decision
No advanced autonomy before Tool Gateway, approval workflow, audit logs, and safety evals exist.

## Consequences
Positive: safer path to agent capability.  
Negative: slower initial feature excitement.

## Alternatives considered
- Let agent call tools directly: faster but unsafe.
- Disable all tools forever: safe but limits Hibob's unique value.
