"""Central configuration for the Memory Substrate Evaluation app.

Loads environment variables (Anthropic key — optional, only for the "synthesise an
answer" payoff; Oracle credentials — optional, retrieval falls back to in-memory)
and exposes a single ``settings`` object. Mirrors the other Part 5 appbooks so the
whole course shares its Oracle + fastembed plumbing.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent.parent           # .../appbook
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
IMAGES_DIR = APP_DIR.parent / "images"                     # concept diagrams (optional)
WORKSPACE_DIR = BACKEND_DIR / "workspace"                  # filesystem substrate root

# Load .env files in priority order (workshop root → notebook folder → app-local).
for candidate in (APP_DIR.parent.parent / ".env", APP_DIR.parent / ".env", APP_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=True)


class Settings:
    """Runtime settings, read once at import."""

    # Anthropic / model — OPTIONAL. Only used by the "synthesise an answer from the
    # retrieved context" payoff that closes the retrieval lesson. The substrate
    # comparison + benchmarks run fully without a key.
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    model: str = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
    max_tokens: int = int(os.environ.get("SUBSTRATE_MAX_TOKENS", "600"))

    # Embeddings (torch-free ONNX via fastembed) — same nomic model as the notebook.
    embed_model: str = os.environ.get("SUBSTRATE_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    # Oracle AI Database (optional). If unreachable, the DB substrate falls back to
    # an in-memory NumPy cosine index so the whole app still runs on a laptop. The
    # active backend is reported to the UI via /api/health.
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "127.0.0.1:1521/FREEPDB1")
    oracle_enabled: bool = os.environ.get("ORACLE_ENABLED", "1") not in {"0", "false", "False"}

    # Filesystem substrate workspace.
    workspace_dir: Path = WORKSPACE_DIR

    # Table name for the Oracle vector substrate.
    db_table: str = os.environ.get("SUBSTRATE_DB_TABLE", "SUBSTRATE_DOCS")


settings = Settings()
