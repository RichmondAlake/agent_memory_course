"""Health / capability endpoint — drives the UI's Memory Core status badge."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.memory import store

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "memory": store.status(),
        "oracle_enabled": settings.oracle_enabled,
        "api_key_set": bool(settings.openai_api_key),
    }
