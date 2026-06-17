"""Benchmark endpoint: stream the 3-way ACID / concurrency race over SSE."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from backend.core import concurrency
from backend.core.sse import sse_response

router = APIRouter(prefix="/api/benchmark")


@router.get("/concurrency")
async def concurrency_stream(
    writers: int = Query(8, ge=2, le=16),
    per: int = Query(40, ge=10, le=200),
):
    """Run naive-FS, locked-FS, and ACID-DB writers and stream each result as it lands."""
    expected = writers * per
    legs = [
        ("Filesystem (no lock)", concurrency.run_naive_fs),
        ("Filesystem (flock)", concurrency.run_locked_fs),
        ("Database (ACID)", concurrency.run_database),
    ]

    async def events():
        yield {"phase": "config", "writers": writers, "per_writer": per, "expected": expected}
        for label, fn in legs:
            yield {"phase": "start", "approach": label}
            result = await asyncio.to_thread(fn, writers, per)
            yield {"phase": "result", "result": result}
        yield {"phase": "done"}

    return sse_response(events())
