# ADR 0015 - Multimodal Output & Voice Safety

## Status
Accepted for blueprint v0.1

## Context
Phase 3.7 gave Hibob multimodal *input* understanding (image vision + audio STT). Phase 9 adds the
other half: Hibob *producing* non-text output (generated images, synthesized speech) and two-way
voice conversation. Generating and emitting artifacts is categorically more dangerous than reading
them - a generated image could be auto-posted somewhere, a synthesized voice could speak on Bob's
behalf, and "always-listening" voice is a standing privacy hazard. Without an explicit safety
decision, output generation risks becoming an unguarded side-channel that bypasses the Tool Gateway
and privacy rules the rest of the system enforces.

## Decision
1. **Output generation is a tool, not an ambient capability.** Image generation runs through the
   Tool Gateway (ADR 0005) as a registered tool (`image_generate`), risk `high` (always `ask`,
   never auto-escalated). Cloud-backed generation is gated by the cost circuit breaker (ADR 0012).
2. **No auto-publish.** Generated artifacts are returned as drafts (`published: false`) for Bob to
   use; Hibob never posts, sends, or persists them to any external destination on its own.
3. **Privacy containment for artifacts.** A generated artifact inherits the conversation's
   `privacy_tier`; `private`/`secret` generation must stay local and never reach a cloud provider,
   exactly like memory/document/image *input* (doc 08 §4).
4. **Voice is push-to-talk + consent only.** STT input (Phase 3.7) and TTS output compose into
   two-way voice, but only via explicit push-to-talk turns. No always-listening / wake-word capture;
   nothing is recorded silently. TTS is local-first (cost + privacy), like STT.
5. Size limits and provenance watermarking on generated artifacts are seams to harden later.

## Consequences
Positive: output generation and voice are bounded by the same governance (policy, approval, audit,
cost, privacy) as every other action; the most dangerous "act in the world" surface never becomes a
special trusted path. Negative: generation always requires approval and stays draft-only, which is
deliberately slower than auto-emitting - speed traded for not letting Hibob publish or speak
unsupervised.

## Alternatives considered
- Let image generation run as a plain capability outside the gateway: rejected - bypasses policy,
  cost, and audit, and contradicts ADR 0005's "every tool request is adjudicated".
- Auto-publish generated artifacts when the user clearly asked: rejected - the same anti-pattern as
  auto-merge in ADR 0013; the user asking to *generate* is not consent to *publish*.
- Always-listening voice for a smoother experience: rejected for v0.1 - a standing silent-recording
  hazard; revisit only with an explicit, separate consent mechanism (kept in "intentionally delayed").
