"""Central configuration for the zero-to-hero appbook.

The appbook is the interactive companion to
``../notebook/agent_memory_zero_to_hero.ipynb``. It makes the same choices as the
notebook: the ``MEMORIZZ`` schema of Oracle AI Database for every table (your
``SCRATCH_*`` tables and MemoRizz's), 256-dimensional vectors, and TypeSafe Jev
for memory routing when a key is set. Two ways to run the models:

- **OpenAI** (``OPENAI_API_KEY``): ``gpt-5.5`` for both agents (Responses API,
  reasoning effort ``none``) and ``text-embedding-3-small``.
- **Open models through Ollama** (``MEMO_PROVIDER=ollama``, or no OpenAI key):
  Gemma 4 for both agents and ``nomic-embed-text`` for the vectors, on this
  machine, with no key and no API cost. Ollama serves the same OpenAI-compatible
  API, so only the base URL and the model names change.

There is no fallback store: when Oracle, the key or Ollama is missing, the API
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


def resolve_models(env: dict) -> dict:
    """OpenAI with a key, or open models through Ollama (MEMO_PROVIDER=ollama, or no OpenAI key at all)."""
    provider = (env.get("MEMO_PROVIDER") or ("openai" if env.get("OPENAI_API_KEY") else "ollama")).strip().lower()
    if provider == "ollama":
        url = (env.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        base = env.get("MEMO_OPEN_MODEL") or "gemma4"                      # Gemma 4 E4B
        model = f"{base.replace(':', '-')}-32k"                            # the same weights, a 32k context window
        return {"provider": "ollama", "ollama_url": url, "open_model": base, "open_context": 32768,
                "openai_api_key": "ollama", "openai_base_url": f"{url}/v1", "model": model,
                "judge_model": env.get("MEMO_JUDGE_MODEL") or model, "embed_model": "nomic-embed-text"}
    return {"provider": "openai", "ollama_url": None, "open_model": None, "open_context": None,
            "openai_api_key": env.get("OPENAI_API_KEY") or None, "openai_base_url": None,
            "model": env.get("MEMO_MODEL") or env.get("AMEM_MODEL") or "gpt-5.5",
            "judge_model": env.get("MEMO_JUDGE_MODEL") or "gpt-5.5", "embed_model": "text-embedding-3-small"}


_models = resolve_models(dict(os.environ))


class Settings:
    """Runtime settings, read once at import."""

    provider: str = _models["provider"]                    # "openai" or "ollama" (open models on this machine)
    open: bool = provider == "ollama"
    ollama_url: str | None = _models["ollama_url"]
    open_model: str | None = _models["open_model"]          # the Ollama model the 32k-context variant is made from
    open_context: int | None = _models["open_context"]
    openai_api_key: str | None = _models["openai_api_key"]
    openai_base_url: str | None = _models["openai_base_url"]  # Ollama's OpenAI-compatible API on the open path
    typesafe_api_key: str | None = os.environ.get("TYPESAFE_API_KEY") or None
    model: str = _models["model"]
    # The LLM judge that grades answers on the Tokenomics page; its cost is reported apart from the agents'.
    judge_model: str = _models["judge_model"]
    embed_model: str = _models["embed_model"]
    embed_dimensions: int = 256

    oracle_user: str = os.environ.get("ORACLE_USER", "MEMORIZZ")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "MemorizzPwd_2026")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")

    jev_url: str = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"
    # A session keeps what it wrote, so its MemoRizz traces appear in the MemoRizz UI. MEMO_CLEANUP=1 (or the
    # older MEMO_CLEANUP_ON_RESET=1) deletes a session's rows on reset, on shutdown and after a Tokenomics run.
    cleanup_on_reset: bool = _flag("MEMO_CLEANUP", os.environ.get("MEMO_CLEANUP_ON_RESET", "0"))


settings = Settings()
