"""Central configuration for the Application Modes app.

Loads environment variables (Anthropic key for the agents, OpenAI key for the
Oracle AI Agent Memory embedder, optional Tavily key for web research, optional
Oracle credentials) and exposes a single ``settings`` object the rest of the
backend imports.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent.parent           # .../appbook
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
IMAGES_DIR = APP_DIR.parent / "images"   # concept diagrams for the UI gallery

# Load .env files in priority order. The course already ships a .env a couple of
# levels up; an app-local .env overrides it if present.
for candidate in (APP_DIR.parent.parent / ".env", APP_DIR.parent / ".env", APP_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=True)


class Settings:
    """Runtime settings, read once at import."""

    # Anthropic / model — runs the conversational + research synthesis.
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    model: str = os.environ.get("APPMODES_MODEL", "claude-opus-4-8")
    max_tokens: int = int(os.environ.get("APPMODES_MAX_TOKENS", "1024"))
    # The model's context-window capacity (tokens), shown in the context-window pane.
    # claude-opus-4-8 has a 1M-token window on the Claude API.
    context_capacity: int = int(os.environ.get("APPMODES_CONTEXT_CAPACITY", "1000000"))

    # Oracle AI Agent Memory: local open-source embeddings (nomic-embed-text-v1.5
    # via fastembed — no key, no network) + Claude Sonnet 4.6 as the
    # extraction/summary helper. No OpenAI key is needed anywhere in the app.
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")  # retained but unused
    embed_model: str = os.environ.get("APPMODES_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
    extract_model: str = os.environ.get("APPMODES_EXTRACT_MODEL", "anthropic/claude-sonnet-4-6")

    # Tavily — web search for the Deep Research mode. Optional; research degrades
    # to model-only if unset.
    tavily_api_key: str | None = os.environ.get("TAVILY_API_KEY")

    # Oracle AI Database (optional). If unreachable / no OpenAI key, memory falls
    # back to an in-process store and the app still runs fully.
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_enabled: bool = os.environ.get("ORACLE_ENABLED", "1") not in {"0", "false", "False"}
    table_name_prefix: str = os.environ.get("APPMODES_TABLE_PREFIX", "appmodes_")


settings = Settings()
