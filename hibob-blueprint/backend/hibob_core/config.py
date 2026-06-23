"""Runtime configuration (pydantic-settings). All values overridable via env or .env."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HIBOB_", env_file=".env", extra="ignore")

    # --- Database (canonical store) ---
    # Points at the hibob-postgres service added to ai-stack/docker-compose.yml.
    database_dsn: str = "postgresql://hibob:hibob_dev_pw@localhost:5433/hibob"

    # --- Local model runtime (ai-stack Ollama) ---
    ollama_base_url: str = "http://localhost:11435"
    ollama_default_model: str = "qwen3.5:9b"  # fits 8GB VRAM (see ai-stack/README.md)

    # --- Cloud model (Anthropic Claude) ---
    anthropic_api_key: str | None = None
    cloud_default_model: str = "claude-sonnet-4-6"  # default tier; power=opus, utility=haiku

    # --- Embeddings (local, ai-stack Ollama) — Phase 2 ---
    # Local embedding keeps private/secret memory off the cloud (doc 04 §6).
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    # --- Vector store (ai-stack Qdrant) — Phase 2 ---
    qdrant_url: str = "http://localhost:6333"
    memory_collection: str = "hibob_memories"

    # --- Memory retrieval (doc 04 §7) — Phase 2 ---
    retrieval_top_k: int = 6
    retrieval_candidate_k: int = 24  # Qdrant fetch before re-scoring
    w_semantic: float = 0.45
    w_type: float = 0.20
    w_confidence: float = 0.15
    w_recency: float = 0.10
    w_source: float = 0.10

    # --- Cost circuit breaker (ADR 0012) ---
    # Hard daily ceiling in USD for cloud calls. Breach -> pause + require approval.
    daily_budget_usd: float = 5.00

    # --- Observability (ai-stack Phoenix) ---
    otlp_endpoint: str | None = "http://localhost:4317"  # set to None to disable tracing
    service_name: str = "hibob-core"

    # --- Identity ---
    bob_display_name: str = "Bob"


settings = Settings()
