"""Meta endpoints: health + the shared corpus the UI renders."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.anthropic_client import has_key
from backend.core.corpus import CATEGORIES, DOCS, SUGGESTED_QUERIES
from backend.core.db_substrate import db_substrate
from backend.core.fs_substrate import fs_substrate

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {
        "ok": True,
        "embed_model": settings.embed_model,
        "model": settings.model,
        "model_present": has_key(),
        "fs": fs_substrate.stats(),
        "db": db_substrate.status(),
    }


@router.get("/corpus")
def corpus():
    return {
        "docs": DOCS,
        "categories": CATEGORIES,
        "suggested_queries": SUGGESTED_QUERIES,
        "count": len(DOCS),
    }
