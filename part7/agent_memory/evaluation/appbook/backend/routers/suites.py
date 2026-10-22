"""Run a suite in the background, stream its events, stop it, and read the last stored run of a suite."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from backend.core import db, evidence, graders, suites
from backend.schemas import SuiteStart

router = APIRouter(prefix="/api/suites", tags=["suites"])
PART = {"longmemeval": "5-longmemeval", "factconsolidation": "6-factconsolidation", "operations": "7-operations"}


def _kind(kind: str) -> str:
    if kind not in suites.KINDS:
        raise HTTPException(404, f"Unknown suite {kind!r}; one of {', '.join(suites.KINDS)}")
    return kind


@router.get("")
def all_status():
    return {"suites": {kind: (suites.JOBS[kind].info() if kind in suites.JOBS else None) for kind in suites.KINDS}}


@router.post("/{kind}/start")
def start(kind: str, body: SuiteStart):
    _kind(kind)
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    try:
        job = suites.start(kind, body.size, body.model_dump(exclude_none=True, exclude={"size"}))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job.info()


@router.post("/{kind}/stop")
def stop(kind: str):
    job = suites.JOBS.get(_kind(kind))
    if not job or job.status != "running":
        return {"stopping": False}
    job.stop()
    return {"stopping": True}


@router.get("/{kind}/status")
def status(kind: str):
    job = suites.JOBS.get(_kind(kind))
    return job.info() if job else {"kind": kind, "status": "idle"}


@router.get("/{kind}/stream")
async def stream(kind: str, request: Request, since: int = 0):
    """Server-sent events: every event of the current (or last) job from `since`, then new ones until it ends."""
    job = suites.JOBS.get(_kind(kind))
    if not job:
        raise HTTPException(404, "No run of this suite yet.")

    async def events():
        index = max(0, since)
        while True:
            if await request.is_disconnected():
                return
            batch = job.events[index:]
            for event in batch:
                yield {"data": json.dumps(event, default=str)}
            index += len(batch)
            if job.status != "running" and index >= len(job.events):
                yield {"event": "end", "data": "{}"}
                return
            await asyncio.sleep(0.25)

    return EventSourceResponse(events())


@router.get("/{kind}/last")
def last(kind: str, run_id: str | None = None):
    """The latest stored run of this suite (notebook or appbook), or the one asked for: its summary, gates and rows."""
    _kind(kind)
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    if kind == "graders":
        run_id = run_id or graders.latest_validation_run()
        if not run_id:
            return {"run_id": None}
        return {"run_id": run_id, "analysis": graders.analyse(graders.validation_rows(run_id)), "policy": graders.policy()}
    run_id = run_id or evidence.latest_run_with(PART[kind])
    if not run_id:
        return {"run_id": None}
    parts = (PART[kind], "7-writes") if kind == "operations" else (PART[kind],)
    rows = evidence.results(run_id, parts)
    run = next((r for r in evidence.runs(limit=200) if r["run_id"] == run_id), {"run_id": run_id})
    summary = evidence.summarize(run_id)
    return {"run_id": run_id, "run": run, "summary": summary.get(kind, {}),
            "gates": [g for g in evidence.evaluate_gates(summary) if g["value"] is not None], "rows": rows[:1500]}
