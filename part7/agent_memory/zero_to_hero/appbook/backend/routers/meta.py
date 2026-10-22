"""Health and session endpoints: drive the sidebar status card and the overview."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.core.memorizz_memo import runtime
from backend.core.session import sessions
from backend.core.tracing import tracing_status

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "provider": settings.provider,
        "ollama_url": settings.ollama_url,
        "embed_model": settings.embed_model,
        "memory": runtime.status(),
        "api_key_set": bool(settings.openai_api_key),
        "jev_key_set": bool(settings.typesafe_api_key),
        "tracing": tracing_status(),
    }


@router.get("/session")
def session() -> dict:
    return sessions.current.snapshot()


@router.post("/session/reset")
async def reset() -> dict:
    report = await run_in_threadpool(sessions.reset)
    return {"cleanup": report, **sessions.current.snapshot()}
