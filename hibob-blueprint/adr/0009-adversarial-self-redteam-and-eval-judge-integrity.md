# ADR 0009 - Adversarial Self-Red-Team Loop and Eval Judge Integrity

## Status
Accepted for blueprint v0.1

## Context
The Security Skeptic Agent (doc 05 §3.5) evaluates risk reactively, only when an action is actually requested. Separately, DeepEval suites lean heavily on LLM-as-judge metrics (faithfulness, persona consistency) with no fixed anchor — if the judge model changes or drifts, eval scores can move without Hibob's actual behavior changing, and doc 09 §12 already flags this risk without offering a mechanism to prevent it.

## Decision
1. **Self-red-team loop.** The Security Skeptic Agent gains a scheduled mode that generates adversarial inputs against a sandboxed Hibob instance: forged documents with injected instructions, tool-permission persuasion attempts, persona social-engineering probes. Every attempt logged in `redteam_attempts`. Any attempt that succeeds (bypasses policy, leaks sensitivity-tagged content, or breaks persona) is automatically converted into a permanent regression case in `tool_policy_eval` or `persona_eval`.
2. **Eval judge integrity.** Maintain a small, human-authored golden dataset with fixed expected answers that are checked by exact/structural match, not by LLM judgment. Pin the specific judge model/version used for LLM-as-judge metrics in `eval_runs`; whenever the judge model changes, re-validate judge agreement against the golden set before trusting new scores.

## Consequences
Positive: security regression coverage grows automatically and runs ahead of Bob discovering a bug manually; eval scores stop being graded on a drifting curve, restoring confidence that a "pass" means the same thing over time.
Negative: red-team runs consume compute/time on a schedule; golden dataset curation is manual work and must be kept deliberately small to stay maintainable.

## Alternatives considered
- Manual security review only, no scheduled adversarial generation: rejected, doesn't scale and leaves Hibob's defenses static while threats evolve.
- Trust LLM-as-judge exclusively with no golden anchor: rejected, this is explicitly listed as an anti-pattern in doc 09 §12 ("let model judge all evals without spot-checking").
