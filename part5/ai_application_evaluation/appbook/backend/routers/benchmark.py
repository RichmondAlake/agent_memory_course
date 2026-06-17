"""FF2 — the BEIR scifact retrieval bake-off (streamed)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from backend.core.beir import get_bench
from backend.core.sse import sse_response
from backend.schemas import BeirRequest

router = APIRouter(prefix="/api/eval", tags=["benchmark"])


@router.post("/beir")
async def beir(req: BeirRequest):
    async def events():
        try:
            # the generator does blocking numpy work — drain it on a thread, one item at a time
            gen = get_bench(req.dataset).run(k=req.k)
            while True:
                item = await asyncio.to_thread(lambda: next(gen, None))
                if item is None:
                    break
                yield item
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}

    return sse_response(events())
