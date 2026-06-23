"""Model Router (doc 02 §3.6) - picks an adapter by privacy tier + preference.

Phase 1 is a static router (ADR 0003): a small deterministic policy, not a learned
bandit (that is Phase 6, ADR 0012). The privacy rule is non-negotiable and lives here
so it can never be bypassed by model choice (doc 08 §4): `secret`/`private` tiers never
route to a cloud provider.
"""

from __future__ import annotations

from hibob_core.models.anthropic_adapter import AnthropicAdapter
from hibob_core.models.base import ModelAdapter
from hibob_core.models.ollama_adapter import OllamaAdapter

_LOCAL_ONLY_TIERS = {"secret", "private"}


class PrivacyViolation(Exception):
    """Raised when a request would send private/secret context to a cloud model."""


class CloudUnavailable(Exception):
    """Raised when a cloud model is requested but no provider is configured (no API key)."""


class ModelRouter:
    def __init__(
        self, ollama: OllamaAdapter | None = None, anthropic: AnthropicAdapter | None = None
    ):
        self.ollama = ollama or OllamaAdapter()
        self.anthropic = anthropic or AnthropicAdapter()

    def route(self, *, privacy_tier: str, model_preference: str) -> ModelAdapter:
        """Return the adapter to use. May raise PrivacyViolation.

        model_preference: 'auto' | 'local' | 'cloud'.
        - private/secret tier -> always local; 'cloud' here is a hard error.
        - 'local' -> Ollama; 'cloud' -> Anthropic; 'auto' -> local (Private Mode default,
          cheapest + most private; cloud is opt-in until a learned router exists).
        """
        wants_cloud = model_preference == "cloud"

        if privacy_tier in _LOCAL_ONLY_TIERS:
            if wants_cloud:
                raise PrivacyViolation(
                    f"privacy_tier='{privacy_tier}' cannot use a cloud model (doc 08 §4). "
                    f"Use model_preference=local."
                )
            return self.ollama

        if wants_cloud:
            if not self.anthropic.available:
                raise CloudUnavailable(
                    "model_preference=cloud requested but no Anthropic API key is configured "
                    "(set HIBOB_ANTHROPIC_API_KEY). Use model_preference=local."
                )
            return self.anthropic

        # 'local' or 'auto' -> local
        return self.ollama

    def embed_adapter(self) -> ModelAdapter:
        """Embeddings are always local in Phase 2 (private/secret memory never leaves the box)."""
        return self.ollama
