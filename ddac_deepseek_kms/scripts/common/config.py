"""
Centralized configuration loaded from environment variables (.env).

All scripts should import from here instead of hardcoding credentials.
Loads the .env file located at the project root.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of the scripts/ folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and fill in the values."
        )
    return val


# --- MySQL ---
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "172.16.2.153"),
    "user": _require("DB_USER"),
    "password": _require("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME", "ddac2026"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "charset": "utf8mb4",
}

# --- DeepSeek API (OCR cleaning) ---
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# --- TreasurAI (reasoning) ---
TREASURAI_BASE_URL = os.environ.get(
    "TREASURAI_BASE_URL",
    "https://treasurai-src-treasury-ai-dev.apps.ocpsdc-djpb.kemenkeu.go.id",
)
TREASURAI_API_KEY = os.environ.get("TREASURAI_API_KEY", "")
TREASURAI_DEFAULT_MODEL = os.environ.get("TREASURAI_DEFAULT_MODEL", "oss20b")
TREASURAI_MODELS = {
    "oss20b": "/api/v1/openshift/oss20b/chat",
    "oss120b": "/api/v1/openshift/oss120b/chat",
}

# --- Embeddings ---
# Model aktif: Indonesian fine-tune, lebih akurat untuk
# istilah birokrasi Indonesia. Prefix "query: " wajib saat inference.
EMBEDDING_MODEL = "LazarusNLP/all-indo-e5-small"
EMBEDDING_DIMS = 384

# --- Budget Year (parameterized table names) ---
# Set BUDGET_YEAR=2027 di .env untuk tahun anggaran baru tanpa mengubah script.
BUDGET_YEAR = os.environ.get("BUDGET_YEAR", "2026")

TABLE_PAGU_AKUN      = f"ddac_pagu_akun_{BUDGET_YEAR}"
TABLE_ANOMALY        = f"ddac_anomaly_{BUDGET_YEAR}"
TABLE_COHERENCE      = f"ddac_coherence_{BUDGET_YEAR}"
TABLE_COHERENCE_AKUN = f"ddac_coherence_akun_{BUDGET_YEAR}"
TABLE_KMPNEN         = f"t_kmpnen_{BUDGET_YEAR}"
TABLE_RINGKASAN      = f"ringkasan_pagu_{BUDGET_YEAR}"
