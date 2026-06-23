"""Local model adapter -> ai-stack Ollama (localhost:11435). Cost is always 0 (local)."""

from __future__ import annotations

import httpx

from hibob_core.config import settings
from hibob_core.models.base import GenerateResult, ModelAdapter


class OllamaAdapter(ModelAdapter):
    provider = "ollama"
    is_cloud = False

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        embed_model: str | None = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_default_model
        self.embed_model = embed_model or settings.embed_model

    async def generate_text(
        self, *, system: str, messages: list[dict], model: str | None = None
    ) -> GenerateResult:
        model = model or self.default_model
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data.get("message", {}).get("content", "")
        return GenerateResult(
            text=text,
            provider=self.provider,
            model=model,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            cost_estimate=0.0,
        )

    async def embed_text(
        self, texts: list[str], model: str | None = None
    ) -> list[list[float]]:
        """Local embeddings via Ollama /api/embed. Always free, always local."""
        model = model or self.embed_model
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/embed", json={"model": model, "input": texts}
            )
            resp.raise_for_status()
            data = resp.json()
        return data["embeddings"]
