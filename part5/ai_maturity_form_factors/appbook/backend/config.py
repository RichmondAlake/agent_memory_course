"""Central configuration for the AI Maturity Ladder app.

Loads environment variables (Anthropic key, optional Oracle credentials) and
exposes a single ``settings`` object the rest of the backend imports. Also makes
the bundled ``claude`` CLI discoverable so the agent form factors (4 & 5) work
when the server is launched from uvicorn / a conda env.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent.parent           # .../app
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
SANDBOX_DIR = BACKEND_DIR / "sandbox"                       # Form Factor 5 workspace
IMAGES_DIR = APP_DIR.parent / "images"                     # concept diagrams shown in the UI gallery

# Load .env files in priority order. The workshop already ships a .env two levels
# up (with ANTHROPIC_API_KEY); an app-local .env overrides it if present.
for candidate in (APP_DIR.parent.parent / ".env", APP_DIR.parent / ".env", APP_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=True)


def _augment_path() -> None:
    """Ensure common user-bin locations are on PATH so `claude` is findable."""
    extra = [str(Path.home() / ".local" / "bin"), "/usr/local/bin", "/opt/homebrew/bin"]
    current = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join([*current, *[p for p in extra if p not in current]])


def _find_claude_cli() -> str | None:
    _augment_path()
    found = shutil.which("claude")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "claude"
    return str(fallback) if fallback.exists() else None


class Settings:
    """Immutable-ish runtime settings, read once at import."""

    # Anthropic / model — one model string used everywhere, mirroring the notebook.
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    model: str = os.environ.get("AIML_MODEL", "claude-opus-4-8")
    max_tokens: int = int(os.environ.get("AIML_MAX_TOKENS", "1024"))

    # Embeddings (torch-free ONNX via fastembed) — same model as the notebook.
    embed_model: str = os.environ.get("AIML_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    # Oracle AI Database (optional). If unreachable, RAG falls back to in-memory.
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_enabled: bool = os.environ.get("ORACLE_ENABLED", "1") not in {"0", "false", "False"}
    # Retry the first Oracle connect — useful in Codespaces where the DB warms up
    # alongside the app. Defaults to 1 (no retry) so local fallback stays instant.
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "1"))
    oracle_connect_delay: float = float(os.environ.get("ORACLE_CONNECT_DELAY", "3"))

    # Agent runtime (Form Factors 4 & 5)
    claude_cli_path: str | None = _find_claude_cli()
    sandbox_dir: Path = SANDBOX_DIR


settings = Settings()
