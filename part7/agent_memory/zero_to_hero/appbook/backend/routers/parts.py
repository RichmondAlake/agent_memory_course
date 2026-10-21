"""Each notebook Part as a page: its tables, one message to both agents, and its actions."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.core.memorizz_memo import runtime
from backend.core.session import PAGE_TABLES, sessions
from backend.core.sse import sse_response
from backend.schemas import ActionRequest, ChatRequest

router = APIRouter(prefix="/api/parts", tags=["parts"])
ACTIONS: dict[int, list[str]] = {
    1: ["baseline"], 2: ["restore"], 3: ["evolve"], 5: ["search"], 6: ["preview"], 9: ["propose", "approve"],
    11: ["compact"], 12: ["invalidate"], 13: ["review"], 14: ["scores", "suppress", "restore"],
    15: ["route", "file"], 16: ["save_restore", "compare", "observability"],
}


def _part(part: int) -> int:
    if part not in PAGE_TABLES:
        raise HTTPException(404, "Unknown Part")
    return part


def unavailable_reason(part: int, needs_jev: bool = False) -> str | None:
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is not set. Copy .env.example to .env, add the key and restart."
    if runtime.initialize() is None:
        return runtime.error
    if needs_jev and not settings.typesafe_api_key:
        return "TYPESAFE_API_KEY is not set: add it to appbook/.env to route memories with Jev."
    return None


@router.get("/{part}")
def page(part: int) -> dict[str, Any]:
    _part(part)
    data = sessions.current.page(part)
    data["actions"] = ACTIONS.get(part, [])
    data["unavailable"] = unavailable_reason(part, needs_jev=part == 15) if not runtime.ready or part == 15 else None
    return data


@router.post("/{part}/chat")
async def chat(part: int, body: ChatRequest):
    _part(part)

    async def events():
        reason = await run_in_threadpool(unavailable_reason, part)
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
                sessions.current.chat(part, body.message, body.thread, body.context(), body.budget, emit)
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
        yield {"type": "done", "session": sessions.current.snapshot()}

    return sse_response(events())


@router.post("/{part}/actions/{name}")
async def action(part: int, name: str, body: ActionRequest) -> dict[str, Any]:
    _part(part)
    if name not in ACTIONS.get(part, []):
        raise HTTPException(404, f"Part {part} has no action {name!r}")
    reason = await run_in_threadpool(unavailable_reason, part, part == 15)
    if reason:
        raise HTTPException(503, reason)
    try:
        return await run_in_threadpool(sessions.current.action, part, name, body.params)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the page
        raise HTTPException(500, f"{type(exc).__name__}: {exc}"[:500]) from exc
