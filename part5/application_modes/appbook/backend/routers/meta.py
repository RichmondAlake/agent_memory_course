"""Health / capability endpoint — drives the UI's status badge."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.memory import store
from backend.core.websearch import WEB_AVAILABLE

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "memory": store.status(),
        "web_search": WEB_AVAILABLE,
        "oracle_enabled": settings.oracle_enabled,
        "api_key_set": bool(settings.anthropic_api_key),
    }
