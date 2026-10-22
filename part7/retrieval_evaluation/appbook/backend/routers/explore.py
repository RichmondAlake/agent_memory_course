"""The query explorer: pick a stored query or type one, and see all five strategies' top 10 side by side."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from backend.core import evidence, explore
from backend.routers.meta import ready
from backend.schemas import Dataset, ExploreRequest

router = APIRouter(prefix="/api/explore", tags=["explore"])


@router.get("/queries")
def queries(dataset: Dataset, split: Literal["test", "dev"] = "test"):
    ready()
    return {"dataset": dataset, "split": split, "queries": explore.queries(dataset, split)}


@router.post("/run")
def run(body: ExploreRequest):
    ready()
    if not body.query_id and not (body.text or "").strip():
        raise HTTPException(400, "Pick a query or type one.")
    try:
        return explore.run(body.dataset, evidence.resolve(body.run_id), body.query_id, body.text)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
