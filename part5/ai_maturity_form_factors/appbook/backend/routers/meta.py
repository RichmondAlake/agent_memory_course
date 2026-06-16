"""Health / capability endpoint — drives the UI's backend-status badge."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.agent_runtime import AGENT_AVAILABLE
from backend.core.retrieval import store

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "retrieval": store.status(),
        "agent_available": AGENT_AVAILABLE,
        "oracle_enabled": settings.oracle_enabled,
        "api_key_set": bool(settings.anthropic_api_key),
    }
