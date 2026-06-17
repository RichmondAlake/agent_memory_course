"""Stop 2 — Oracle Agent Memory: the same model, but each turn persists into
Oracle AI Database, extracts durable facts, and retrieves a small context card
instead of replaying the whole history. We surface the card and the stored
memories so you can see what the agent actually remembered."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.memory_core import store
from backend.schemas import ChatRequest, SessionRef
from backend.sse import sse_response

router = APIRouter(prefix="/api/memory", tags=["memory"])

# session_id -> OAMP thread_id
_threads: dict[str, str] = {}


@router.post("/message")
async def message(req: ChatRequest):
    async def events():
        if not store.ready:
            yield {"type": "error", "message": store.error or "Oracle Agent Memory is still warming up — try again in a moment."}
            return

        tid = _threads.get(req.session_id)
        if tid is None:
            try:
                tid = await run_in_threadpool(store.create_thread)
            except Exception as exc:  # noqa: BLE001
                yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
                return
            _threads[req.session_id] = tid

        yield {"type": "working", "stage": "persist + retrieve context card from Oracle…"}
        try:
            result = await run_in_threadpool(store.step, tid, req.message)
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            return

        yield {"type": "answer", "text": result["answer"]}
        yield {
            "type": "done",
            "context_card": result["context_card"],
            "memories": result["memories"],
            "input_tokens": result["input_tokens"],
            "retrieval_s": result["retrieval_s"],
            "total_s": result["total_s"],
        }

    return sse_response(events())


@router.post("/reset")
async def reset(ref: SessionRef) -> dict:
    tid = _threads.pop(ref.session_id, None)
    if tid:
        await run_in_threadpool(store.delete_thread, tid)
    return {"ok": True}
