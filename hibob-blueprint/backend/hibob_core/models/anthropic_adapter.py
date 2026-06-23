"""Cloud model adapter -> Anthropic Claude (official SDK).

Pricing (USD per 1M tokens, input/output) as of 2026-06; verify via the `claude-api`
skill / Models API when it drifts. Used to populate model_runs.cost_estimate and the
cost ledger (ADR 0012).
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from hibob_core.config import settings
from hibob_core.models.base import GenerateResult, ModelAdapter

# input $/1M, output $/1M
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = _PRICING.get(model, _PRICING["claude-sonnet-4-6"])
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


class AnthropicAdapter(ModelAdapter):
    provider = "anthropic"
    is_cloud = True

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        key = api_key or settings.anthropic_api_key
        self._client = AsyncAnthropic(api_key=key) if key else None
        self.default_model = default_model or settings.cloud_default_model

    @property
    def available(self) -> bool:
        return self._client is not None

    async def generate_text(
        self, *, system: str, messages: list[dict], model: str | None = None
    ) -> GenerateResult:
        if self._client is None:
            raise RuntimeError("Anthropic adapter has no API key (set HIBOB_ANTHROPIC_API_KEY).")
        model = model or self.default_model
        resp = await self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        return GenerateResult(
            text=text,
            provider=self.provider,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_estimate=estimate_cost(model, in_tok, out_tok),
        )
