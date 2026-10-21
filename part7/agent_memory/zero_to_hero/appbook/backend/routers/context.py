"""Context window: what each agent sent to the model, call by call, for every measured turn."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.core.session import sessions

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("")
def turns() -> dict[str, Any]:
    return {"turns": sessions.current.context_turns()}


@router.get("/{turn}")
def turn(turn: int) -> dict[str, Any]:
    record = sessions.current.context(turn)
    if record is None:
        raise HTTPException(404, "No context window was recorded for this turn.")
    return record
