"""Central configuration for the zero-to-hero appbook.

The appbook is the interactive companion to
``../notebook/agent_memory_zero_to_hero.ipynb``. It makes the same choices as the
notebook: OpenAI ``gpt-5.5`` (Responses API, reasoning effort ``none``) for both
agents, OpenAI ``text-embedding-3-small`` at 256 dimensions for every vector,
the ``MEMORIZZ`` schema of Oracle AI Database for every table (your
``SCRATCH_*`` tables and MemoRizz's), and TypeSafe Jev for memory routing.
There is no fallback store: when Oracle or the OpenAI key is missing, the API
reports a clear error.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent           # .../appbook
FRONTEND_DIR = APP_DIR / "frontend"

# Process variables always win; the most specific .env file is read first.
for candidate in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in {"0", "false", "no", "off"}


class Settings:
    """Runtime settings, read once at import."""

    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY") or None
    typesafe_api_key: str | None = os.environ.get("TYPESAFE_API_KEY") or None
    model: str = os.environ.get("MEMO_MODEL") or os.environ.get("AMEM_MODEL") or "gpt-5.5"
    # The LLM judge that grades answers on the Tokenomics page; its cost is reported apart from the agents'.
    judge_model: str = os.environ.get("MEMO_JUDGE_MODEL") or "gpt-5.5"
    embed_model: str = "text-embedding-3-small"
    embed_dimensions: int = 256

    oracle_user: str = os.environ.get("ORACLE_USER", "MEMORIZZ")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "MemorizzPwd_2026")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")

    jev_url: str = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"
    cleanup_on_reset: bool = _flag("MEMO_CLEANUP_ON_RESET", "1")


settings = Settings()
