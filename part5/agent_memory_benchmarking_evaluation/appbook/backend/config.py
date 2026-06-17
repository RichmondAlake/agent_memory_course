"""Central configuration for the Agent Memory Benchmarks app.

Loads the Anthropic key and Oracle credentials, and exposes one ``settings``
object the rest of the backend imports. Mirrors the companion notebook's stack:
two Claude tiers + a local fastembed embedder + Oracle AI Database.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent        # .../appbook
FRONTEND_DIR = APP_DIR / "frontend"

# Load .env files in priority order (app-local wins; fall back to the workshop's).
for candidate in (APP_DIR.parent.parent / ".env", APP_DIR.parent / ".env", APP_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=True)


class Settings:
    # Anthropic — two tiers, exactly like the notebook.
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    agent_model: str = os.environ.get("BENCH_AGENT_MODEL", "claude-opus-4-8")   # agents + judge
    small_model: str = os.environ.get("BENCH_SMALL_MODEL", "claude-haiku-4-5")  # extraction / compaction
    max_answer_tokens: int = int(os.environ.get("BENCH_MAX_TOKENS", "512"))
    context_window: int = int(os.environ.get("BENCH_CONTEXT_WINDOW", "200000"))

    # Local open-source embedder (Anthropic has no embeddings API).
    embed_model: str = os.environ.get("BENCH_EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")

    # Oracle AI Database.
    oracle_user: str = os.environ.get("DB_USER", "VECTOR")
    oracle_password: str = os.environ.get("DB_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("DB_CONNECT_STRING", "localhost:1521/FREEPDB1")
    oamp_prefix: str = os.environ.get("BENCH_OAMP_PREFIX", "oamp_app")

    # How many scripted turns the live head-to-head benchmark runs. The default live SCRIPT
    # is a compact, recall-dense conversation (~7 declarative + 5 recall probes), so the
    # default runs the whole thing — short enough to finish in a couple of minutes, yet it
    # actually exercises recall so the LLM-judge is meaningful. (Set BENCH_USE_NOTEBOOK_SCRIPT=1
    # to run the notebook's full 80-turn script instead, where a much higher count is apt.)
    benchmark_turns: int = int(os.environ.get("BENCH_LIVE_TURNS", "12"))


settings = Settings()
