"""Tokenomics: latency, cost and token consumption of every measured turn of both agents."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.session import sessions
from backend.core.sse import sse_response
from backend.routers.parts import unavailable_reason

router = APIRouter(prefix="/api/tokenomics", tags=["tokenomics"])


@router.get("")
def measurements() -> dict[str, Any]:
    return sessions.current.tokenomics()


@router.post("/workload")
async def workload():
    """Stream the sample workload: one progress event per question, one turn event per measured pair."""

    async def events():
        session = sessions.current
        reason = await run_in_threadpool(unavailable_reason, session.workload_level())
        if reason:
            yield {"type": "error", "message": reason}
            return
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        def emit(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def work() -> None:
            try:
                session.workload(emit)
            except Exception as exc:  # noqa: BLE001 - reported to the page as an event
                emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"[:500]})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        task = loop.run_in_executor(None, work)
        while True:
            event = await queue.get()
            if event is sentinel:
                break
            yield event
        await task
        yield {"type": "done", **session.tokenomics()}

    return sse_response(events())


@router.get("/status")
def status() -> dict[str, Any]:
    """How far the memory workload is (or how it ended): every page polls this for its run notification."""
    return sessions.current.workload_status()


@router.post("/stop")
def stop() -> dict[str, Any]:
    """Stop run: the workload ends before its next turn (the turn in progress finishes and is measured)."""
    return sessions.current.stop_workload()


@router.post("/clear")
def clear() -> dict[str, Any]:
    return sessions.current.clear_metrics()
