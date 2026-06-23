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
    ollama_vision_model: str = "llava:7b"     # multimodal model for image input (Phase 3.7)

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

    # --- Knowledge base / RAG (Phase 3, doc 06) ---
    documents_collection: str = "hibob_documents"  # separate Qdrant collection (doc 06 §15)
    chunk_target_tokens: int = 700        # within doc 06 §7 range (500-900)
    chunk_overlap_tokens: int = 120       # within doc 06 §7 range (80-150)
    chunk_min_chars: int = 20             # ingestion quality gate (doc 06 §11): skip empty chunks
    doc_retrieval_top_k: int = 6
    doc_retrieval_candidate_k: int = 24   # Qdrant fetch before privacy/metadata filtering
    crawl_allowlist: list[str] = Field(default_factory=list)  # web ingest: allowlist-only (doc 06 §6.2)

    # --- Memory graph & calibration (Phase 2.5, ADR 0006/0007) ---
    graph_max_depth: int = 5            # recursive-CTE traversal cap (doc 04 §9a)
    calib_alpha0: float = 1.0           # Beta prior - positive evidence
    calib_beta0: float = 1.0            # Beta prior - negative evidence
    calib_correction_weight: float = 4.0  # a `corrected` signal weighs 4x a passive `used`
    calib_floor: float = 0.05           # confidence never calibrates below this
    calib_cap: float = 0.99             # ...nor above (can't imply auto-promotion)
    calib_review_threshold: float = 0.30  # below -> flag for weekly review (§11), not archive

    # --- Multimodal input (Phase 3.7) ---
    stt_model: str = "base"               # faster-whisper size (tiny|base|small|...)
    multimodal_max_mb: int = 20           # per-attachment size ceiling
    multimodal_allowed_image_types: list[str] = Field(
        default_factory=lambda: ["image/png", "image/jpeg", "image/webp"]
    )
    multimodal_allowed_audio_types: list[str] = Field(
        default_factory=lambda: ["audio/wav", "audio/mpeg", "audio/webm", "audio/mp4"]
    )

    # --- Reflective sibling (Phase 3.5, ADR 0010) ---
    reflection_low_confidence: float = 0.4  # depends_on target below this = fragile assumption
    reflection_stale_days: int = 30         # web source not recrawled within = stale (doc 06 §13)
    reflection_max_findings: int = 20       # cap per run, anti-noise (ADR 0010)

    # --- Tool Gateway & Policy Engine (Phase 4, ADR 0005) ---
    trust_auto_threshold: float = 0.8   # medium-risk tool auto-allows once trust crosses this
    trust_increment: float = 0.1        # per successful, non-flagged run
    repo_read_root: str = "."           # allowlist root for the read-only repo_read tool
    tool_approval_ttl_hours: int = 24

    # --- Cost circuit breaker (ADR 0012) ---
    # Hard daily ceiling in USD for cloud calls. Breach -> pause + require approval.
    daily_budget_usd: float = 5.00

    # --- Observability (ai-stack Phoenix) ---
    otlp_endpoint: str | None = "http://localhost:4317"  # set to None to disable tracing
    service_name: str = "hibob-core"

    # --- Identity ---
    bob_display_name: str = "Bob"


settings = Settings()
