"""The tuning playground: build the dev candidate cache (progress over SSE), then score any fusion or graph setting."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.core import evidence, playground
from backend.routers.meta import ready
from backend.schemas import Dataset, ScoreRequest

router = APIRouter(prefix="/api/playground", tags=["playground"])


@router.get("/{dataset}/status")
def status(dataset: Dataset, run_id: str | None = None):
    ready()
    run = evidence.resolve(run_id)
    return {**playground.status(dataset), "chosen": playground.chosen(run, dataset), "run_id": run,
            "grid": evidence.dev_grid(run, dataset)}


@router.post("/{dataset}/prepare")
def prepare(dataset: Dataset, run_id: str | None = None):
    ready()
    playground.prepare(dataset, evidence.resolve(run_id))
    return playground.status(dataset)


@router.get("/{dataset}/stream")
async def stream(dataset: Dataset, since: int = 0):
    async def events():
        sent = since
        while True:
            batch, state = playground.events(dataset, sent)
            for event in batch:
                sent += 1
                yield {"data": json.dumps(event)}
            if state in ("ready", "error", "empty"):
                yield {"event": "end", "data": json.dumps({"state": state})}
                return
            await asyncio.sleep(0.4)

    return EventSourceResponse(events())


@router.post("/score")
def score(body: ScoreRequest):
    ready()
    params = ({"alpha": body.alpha, "depth": body.depth} if body.kind == "weighted"
              else {"k": body.k, "w": body.w, "depth": body.depth} if body.kind == "rrf"
              else {"m": body.m, "seeds": body.seeds, "decay": body.decay})
    try:
        return playground.score(body.dataset, body.kind, params)
    except LookupError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{dataset}/reach")
def reach(dataset: Dataset):
    ready()
    try:
        return {"dataset": dataset, **playground.reach(dataset)}
    except LookupError as exc:
        raise HTTPException(409, str(exc)) from exc
