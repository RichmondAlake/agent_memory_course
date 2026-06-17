"""Central configuration for the AI Application Evaluation app.

Loads environment variables (Anthropic key — required; LangSmith key — optional;
Oracle credentials — optional) and exposes a single ``settings`` object. Mirrors
the AI Maturity Ladder app so the two share their Oracle + fastembed + agent
plumbing; this one adds the LangSmith + BEIR-seed knobs the evaluation needs.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent.parent           # .../appbook
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_DIR = APP_DIR / "frontend"
# FF5 autonomous-agent workspace. Default to a NEUTRAL temp path (no project-like
# ancestor dirs) so the builder agent can't mistake a parent for "the project" and
# wander off with a mangled absolute path — it just works in its current directory.
SANDBOX_DIR = Path(os.environ.get("AIEVAL_SANDBOX", "/tmp/aieval-ff5-workspace"))
IMAGES_DIR = APP_DIR.parent / "images"                     # concept diagrams shown in the UI
# The precomputed BEIR scifact corpus + 768-dim nomic vectors (skips the ~11-min embed).
SEED_PATH = APP_DIR.parent / "notebook" / "data" / "beir_scifact_seed.npz"

# Load .env files in priority order (workshop root → app-local override).
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
    """Runtime settings, read once at import."""

    # Anthropic / model — the system under test AND the LLM-as-judge.
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    model: str = os.environ.get("AIEVAL_MODEL", "claude-opus-4-8")
    max_tokens: int = int(os.environ.get("AIEVAL_MAX_TOKENS", "1024"))

    # LangSmith (optional). When a key is present, experiments upload to the platform;
    # otherwise every metric is still computed locally and the upload is skipped.
    langsmith_api_key: str | None = os.environ.get("LANGSMITH_API_KEY")
    langsmith_enabled: bool = bool(os.environ.get("LANGSMITH_API_KEY"))
    langsmith_project: str = os.environ.get("LANGSMITH_PROJECT", "ai-maturity-evaluation")

    # Embeddings (torch-free ONNX via fastembed) — same model as the notebook (768-dim).
    embed_model: str = os.environ.get("AIEVAL_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    # Oracle AI Database (optional). If unreachable, retrieval falls back to in-memory NumPy.
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_enabled: bool = os.environ.get("ORACLE_ENABLED", "1") not in {"0", "false", "False"}
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "1"))
    oracle_connect_delay: float = float(os.environ.get("ORACLE_CONNECT_DELAY", "3"))

    # BEIR benchmark
    seed_path: Path = SEED_PATH
    beir_n_queries: int = int(os.environ.get("AIEVAL_BEIR_QUERIES", "50"))

    # Agent runtime (FF4 & FF5)
    claude_cli_path: str | None = _find_claude_cli()
    sandbox_dir: Path = SANDBOX_DIR


settings = Settings()
