# ADR 0003 - Local-First Hybrid Model Routing

## Status
Accepted for blueprint v0.1

## Context
Hibob should preserve privacy and use local resources, but local models may not always match frontier models for complex reasoning/coding.

## Decision
Use Ollama for local/private tasks and a model adapter layer for optional cloud frontier models. Model selection is based on task type, privacy tier, cost, quality, and availability.

## Consequences
Positive: privacy and quality can both be optimized. Future models can be integrated.  
Negative: routing logic and evaluation become necessary.
