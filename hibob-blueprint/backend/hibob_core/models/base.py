"""Model adapter contract (ADR 0001: core-and-adapters, ADR 0003: model-agnostic routing).

Design template: hermes-agent/agent/anthropic_adapter.py, bedrock_adapter.py,
gemini_native_adapter.py - one interface, many providers, no lock-in (doc 02 §3.6).
Read those for patterns; do NOT import Hermes as a dependency (ADR 0014).

Phase 1 implements `generate_text` only. `embed_text` (Phase 2 memory/RAG) and
`judge` (Phase 6 eval) are declared here as the seam but intentionally unimplemented.
The future `AgentBackend` ABC (where Hermes plugs in as a sandboxed tool, Phase 5)
lives separately - see agents/orchestrator.py - so adding it never touches this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerateResult:
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_estimate: float  # USD; 0.0 for local models


class ModelAdapter(ABC):
    """A single model provider behind one interface."""

    provider: str
    is_cloud: bool  # router consults this to gate the cost breaker (ADR 0012)

    @abstractmethod
    async def generate_text(
        self, *, system: str, messages: list[dict], model: str | None = None
    ) -> GenerateResult:
        """messages: [{'role': 'user'|'assistant', 'content': str}, ...]."""
        ...

    # --- Seam for later phases (not implemented in Phase 1) ---
    async def embed_text(self, texts: list[str], model: str | None = None):  # Phase 2
        raise NotImplementedError("embed_text lands with Memory Core (Phase 2)")

    async def judge(self, *, system: str, messages: list[dict], model: str | None = None):  # Phase 6
        raise NotImplementedError("judge lands with Observability/Eval (Phase 6)")
