"""Settings for the evaluation studio: the application under test, the graders and Oracle.

The same switches as the evaluation notebook: Claude Haiku 5.5 with an Anthropic key, or Gemma 4 through Ollama
(AIML_PROVIDER=ollama, or no Anthropic key). The LLM judge comes from another model family when it can: gpt-6.1-sol
with an OpenAI key, otherwise claude-sonnet-5-5; Gemma on open models. Clef-Flash runs in this process on Apple
silicon, or at CLEF_URL. Jev is optional (TYPESAFE_API_KEY).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent           # .../evaluation/appbook
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
DEFAULT_PORT = 8705

# Most specific first; process variables always win.
for candidate in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env",
                  APP_DIR.parent.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def _bundled_claude_cli() -> str | None:
    spec = importlib.util.find_spec("claude_agent_sdk")
    if spec is None or not spec.origin:
        return None
    binary = Path(spec.origin).parent / "_bundled" / ("claude.exe" if os.name == "nt" else "claude")
    return str(binary) if binary.exists() else None


def _find_claude_cli() -> str | None:
    bundled = _bundled_claude_cli()
    if bundled:
        return bundled
    extra = [str(Path.home() / ".local" / "bin"), "/usr/local/bin", "/opt/homebrew/bin"]
    current = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join([*current, *[p for p in extra if p not in current]])
    return shutil.which("claude")


def resolve_models(env: dict) -> dict:
    """The application under test and the judge, from the environment (the notebook's rules)."""
    provider = (env.get("AIML_PROVIDER") or ("anthropic" if env.get("ANTHROPIC_API_KEY") else "ollama")).strip().lower()
    if provider == "ollama":
        url = (env.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        base = env.get("AIML_OPEN_MODEL") or "gemma4"
        model = f"{base.replace(':', '-')}-32k"
        return {"provider": "ollama", "ollama_url": url, "open_model": base, "model": model,
                "anthropic_api_key": "ollama", "anthropic_base_url": url,
                "judge_provider": "ollama", "judge_model": model}
    judge_provider, judge_model = (("openai", env.get("EVAL_JUDGE_MODEL") or "gpt-6.1-sol") if env.get("OPENAI_API_KEY")
                                   else ("anthropic", env.get("EVAL_JUDGE_MODEL") or "claude-sonnet-5-5"))
    return {"provider": "anthropic", "ollama_url": None, "open_model": None,
            "model": env.get("AIML_MODEL") or "claude-haiku-5-5",
            "anthropic_api_key": env.get("ANTHROPIC_API_KEY"), "anthropic_base_url": None,
            "judge_provider": judge_provider, "judge_model": judge_model}


_models = resolve_models(dict(os.environ))


class Settings:
    provider: str = _models["provider"]
    open: bool = provider == "ollama"
    ollama_url: str | None = _models["ollama_url"]
    open_model: str | None = _models["open_model"]
    model: str = _models["model"]
    anthropic_api_key: str | None = _models["anthropic_api_key"]
    anthropic_base_url: str | None = _models["anthropic_base_url"]
    judge_provider: str = _models["judge_provider"]
    judge_model: str = _models["judge_model"]
    max_tokens: int = int(os.environ.get("AIML_MAX_TOKENS", "2048"))
    effort: str = os.environ.get("AIML_EFFORT", "low")

    clef_url: str = os.environ.get("CLEF_URL", "").rstrip("/")
    clef_repo: str = os.environ.get("CLEF_REPO", "mlx-community/clef-flash-4bit")
    clef_revision: str = os.environ.get("CLEF_REVISION", "b5adbe2c3a95200d4bf04a0727c8ec457157d5e1")
    jev: bool = bool(os.environ.get("TYPESAFE_API_KEY"))

    embed_model: str = os.environ.get("AIML_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
    reranker_model: str = os.environ.get("AIML_RERANKER", "BAAI/bge-reranker-v2-m3-int8")

    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "3"))

    claude_cli_path: str | None = _find_claude_cli()
    agent_dir: Path = BACKEND_DIR / "agent_work"       # the agent's working folder (its sessions live under ~/.claude)
    sandbox_dir: Path = BACKEND_DIR / "sandbox"        # the autonomous agent's sandbox
    hidden_dir: Path = BACKEND_DIR / "hidden"          # hidden tests, never visible to the agent


settings = Settings()

if settings.open:   # both Anthropic SDKs and the agents' Claude Code runtime read these
    os.environ.update(ANTHROPIC_BASE_URL=settings.ollama_url, ANTHROPIC_API_KEY="ollama",
                      ANTHROPIC_DEFAULT_HAIKU_MODEL=settings.model, ANTHROPIC_DEFAULT_SONNET_MODEL=settings.model,
                      ANTHROPIC_DEFAULT_OPUS_MODEL=settings.model)
