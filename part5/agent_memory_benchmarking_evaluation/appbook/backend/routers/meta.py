"""/api/health — model + Oracle Agent Memory status for the sidebar."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.conversation import MAX_TURNS
from backend.memory_core import store

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "agent_model": settings.agent_model,
        "small_model": settings.small_model,
        "embed_model": settings.embed_model,
        "context_window": settings.context_window,
        "benchmark_turns": min(settings.benchmark_turns, MAX_TURNS),  # default run length
        "max_turns": MAX_TURNS,                                       # the real ceiling
        "memory": store.status(),
    }
