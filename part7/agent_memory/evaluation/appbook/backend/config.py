"""Settings for the agent memory evaluation studio: the agents' models, the graders and Oracle.

The same switches as the evaluation notebook: OpenAI (gpt-6.1-sol answers, gpt-6-luna does background work,
text-embedding-3-small at 256 dimensions) with an OpenAI key, or Gemma 4 and nomic-embed-text through Ollama
(MEMO_PROVIDER=ollama, or no OpenAI key). The LLM judge comes from another model family when it can:
claude-sonnet-5-5 with an Anthropic key, otherwise gpt-6.1-sol; Gemma on open models. Clef-Flash runs in this
process on Apple silicon, or at CLEF_URL. Jev is optional (TYPESAFE_API_KEY).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent           # .../agent_memory/evaluation/appbook
FRONTEND_DIR = APP_DIR / "frontend"
DEFAULT_PORT = 8715

# Most specific first; process variables always win.
for candidate in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env",
                  APP_DIR.parent.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def resolve_models(env: dict) -> dict:
    """The agents' models, the embeddings and the judge, from the environment (the notebook's rules)."""
    provider = (env.get("MEMO_PROVIDER") or ("openai" if env.get("OPENAI_API_KEY") else "ollama")).strip().lower()
    if provider == "ollama":
        url = (env.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        base = env.get("MEMO_OPEN_MODEL") or "gemma4"
        model = f"{base.replace(':', '-')}-32k"
        return {"provider": "ollama", "ollama_url": url, "open_model": base, "model": model, "cheap_model": model,
                "model_effort": "none", "cheap_effort": "none", "embed_model": "nomic-embed-text",
                "openai_base_url": f"{url}/v1", "openai_api_key": "ollama",
                "judge_provider": "ollama", "judge_model": model}
    judge = (("anthropic", env.get("MEMO_EVAL_JUDGE_MODEL") or "claude-sonnet-5-5") if env.get("ANTHROPIC_API_KEY")
             else ("openai", env.get("MEMO_EVAL_JUDGE_MODEL") or "gpt-6.1-sol"))
    return {"provider": "openai", "ollama_url": None, "open_model": None,
            "model": env.get("MEMO_MODEL") or "gpt-6.1-sol", "cheap_model": env.get("MEMO_CHEAP_MODEL") or "gpt-6-luna",
            "model_effort": "low", "cheap_effort": "none", "embed_model": "text-embedding-3-small",
            "openai_base_url": None, "openai_api_key": env.get("OPENAI_API_KEY"),
            "judge_provider": judge[0], "judge_model": judge[1]}


_models = resolve_models(dict(os.environ))


class Settings:
    provider: str = _models["provider"]
    open: bool = provider == "ollama"
    ollama_url: str | None = _models["ollama_url"]
    open_model: str | None = _models["open_model"]
    open_context: int = 32768
    model: str = _models["model"]
    cheap_model: str = _models["cheap_model"]
    model_effort: str = _models["model_effort"]
    cheap_effort: str = _models["cheap_effort"]
    embed_model: str = _models["embed_model"]
    dimensions: int = 256
    openai_base_url: str | None = _models["openai_base_url"]
    openai_api_key: str | None = _models["openai_api_key"]
    judge_provider: str = _models["judge_provider"]
    judge_model: str = _models["judge_model"]
    request_timeout: float = float(os.environ.get("MEMEVAL_TIMEOUT", "180"))   # every model call: fail, never hang
    cleanup: bool = os.environ.get("MEMO_CLEANUP") == "1"   # delete what a suite run wrote; kept by default (MemoRizz UI)

    clef_url: str = os.environ.get("CLEF_URL", "").rstrip("/")
    clef_repo: str = os.environ.get("CLEF_REPO", "mlx-community/clef-flash-4bit")
    clef_revision: str = os.environ.get("CLEF_REVISION", "b5adbe2c3a95200d4bf04a0727c8ec457157d5e1")
    jev: bool = bool(os.environ.get("TYPESAFE_API_KEY"))

    oracle_user: str = os.environ.get("ORACLE_USER", "MEMORIZZ")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "MemorizzPwd_2026")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "3"))


settings = Settings()

# The OpenAI SDK, and MemoRizz's OpenAI client built on it, read these (Ollama serves the same API on open models).
if settings.open:
    os.environ.update(OPENAI_BASE_URL=settings.openai_base_url, OPENAI_API_KEY="ollama")
for name, value in (("ORACLE_USER", settings.oracle_user), ("ORACLE_PASSWORD", settings.oracle_password),
                    ("ORACLE_DSN", settings.oracle_dsn)):
    os.environ.setdefault(name, value)   # MemoRizz's OracleProvider.from_env() reads them
