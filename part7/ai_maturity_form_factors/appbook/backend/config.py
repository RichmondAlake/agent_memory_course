"""Central configuration for the AI Maturity Ladder app.

Loads environment variables (Anthropic key, optional Oracle credentials) and
exposes a single ``settings`` object the rest of the backend imports. Also makes
the bundled ``claude`` CLI discoverable so the agent form factors (4 & 5) work
when the server is launched from uvicorn / a conda env.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent.parent           # .../appbook
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
SANDBOX_DIR = BACKEND_DIR / "sandbox"                       # Form Factor 5 workspace
DEFAULT_PORT = 8700                                         # run.sh / __main__ default

# Load the most specific file first. Existing process variables always win, so a
# shell/CI override is never silently replaced by a checked-out .env file.
for candidate in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)


def _augment_path() -> None:
    """Ensure common user-bin locations are on PATH so `claude` is findable."""
    extra = [str(Path.home() / ".local" / "bin"), "/usr/local/bin", "/opt/homebrew/bin"]
    current = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join([*current, *[p for p in extra if p not in current]])


def _bundled_claude_cli() -> str | None:
    """The `claude` binary that ships inside the claude-agent-sdk wheel, if present."""
    spec = importlib.util.find_spec("claude_agent_sdk")
    if spec is None or not spec.origin:
        return None
    binary = Path(spec.origin).parent / "_bundled" / ("claude.exe" if os.name == "nt" else "claude")
    return str(binary) if binary.exists() else None


def _find_claude_cli() -> str | None:
    """Prefer the SDK's bundled CLI (matches the SDK version); fall back to PATH."""
    bundled = _bundled_claude_cli()
    if bundled:
        return bundled
    _augment_path()
    found = shutil.which("claude")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "claude"
    return str(fallback) if fallback.exists() else None


def resolve_models(env: dict) -> dict:
    """Claude with a key, or Gemma 4 through Ollama (AIML_PROVIDER=ollama, or no Anthropic key at all).

    Ollama serves the Anthropic Messages API too, so the open path changes only the base URL and the model name,
    for the anthropic SDK and for the Claude Code runtime behind the agents.
    """
    provider = (env.get("AIML_PROVIDER") or ("anthropic" if env.get("ANTHROPIC_API_KEY") else "ollama")).strip().lower()
    if provider == "ollama":
        url = (env.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
        base = env.get("AIML_OPEN_MODEL") or "gemma4"                      # Gemma 4 E4B
        return {"provider": "ollama", "ollama_url": url, "open_model": base, "anthropic_api_key": "ollama",
                "anthropic_base_url": url, "model": f"{base.replace(':', '-')}-32k"}  # the same weights, a 32k context
    return {"provider": "anthropic", "ollama_url": None, "open_model": None,
            "anthropic_api_key": env.get("ANTHROPIC_API_KEY"), "anthropic_base_url": None,
            "model": env.get("AIML_MODEL", "claude-haiku-5-5")}


_models = resolve_models(dict(os.environ))


class Settings:
    """Immutable-ish runtime settings, read once at import."""

    # Anthropic / model — one model string used everywhere, mirroring the notebook: Claude Haiku 5.5,
    # the latest and lowest-cost Claude model. It thinks before answering; EFFORT keeps that short.
    # Or Gemma 4 on this machine through Ollama: no key, no API cost (AIML_PROVIDER=ollama, or no key).
    provider: str = _models["provider"]
    open: bool = provider == "ollama"
    ollama_url: str | None = _models["ollama_url"]
    open_model: str | None = _models["open_model"]          # the Ollama model the 32k-context variant is made from
    anthropic_api_key: str | None = _models["anthropic_api_key"]
    anthropic_base_url: str | None = _models["anthropic_base_url"]
    model: str = _models["model"]
    max_tokens: int = int(os.environ.get("AIML_MAX_TOKENS", "2048"))
    effort: str = os.environ.get("AIML_EFFORT", "low")

    # The Clef decision model (Form Factors 3 and 4): the pinned 4-bit MLX build of Clef-Flash, loaded
    # in-process on first use, or any SystemOne endpoint when CLEF_URL is set.
    clef_repo: str = os.environ.get("CLEF_REPO", "mlx-community/clef-flash-4bit")
    clef_revision: str = os.environ.get("CLEF_REVISION", "b5adbe2c3a95200d4bf04a0727c8ec457157d5e1")
    clef_url: str = os.environ.get("CLEF_URL", "").rstrip("/")

    # Embeddings (torch-free ONNX via fastembed) — same model as the notebook.
    embed_model: str = os.environ.get("AIML_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    # Oracle AI Database: every form factor from RAG up keeps its memory there.
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    # Retry the first Oracle connect — useful in Codespaces where the DB warms up alongside the app.
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "3"))
    oracle_connect_delay: float = float(os.environ.get("ORACLE_CONNECT_DELAY", "3"))

    # Agent runtime (Form Factors 4 & 5)
    claude_cli_path: str | None = _find_claude_cli()
    sandbox_dir: Path = SANDBOX_DIR


settings = Settings()
