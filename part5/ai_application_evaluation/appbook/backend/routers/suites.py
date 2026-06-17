"""Streaming evaluation for FF1–FF3 suites (chatbot, RAG, workflow).

POST /api/eval/{suite_id} runs the suite's target + evaluators over its dataset and
streams one SSE event per example as it completes, then an aggregate summary — the
same dataset → target → evaluators loop the notebook runs, made live.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.core.evaluation import CURRENT_MODEL, SUITES, run_example
from backend.core.retrieval import store
from backend.core.sse import sse_response
from backend.schemas import EvalRequest

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

_CONCURRENCY = 4


@router.post("/{suite_id}")
async def evaluate_suite(suite_id: str, req: EvalRequest | None = None):
    if suite_id not in SUITES:
        raise HTTPException(404, f"unknown suite '{suite_id}'")
    suite = SUITES[suite_id]
    model = (req.model if req else None) or settings.model

    async def events():
        CURRENT_MODEL.set(model)            # system-under-test model (judge stays on the default)
        if suite["ff"] in ("rag", "workflow"):
            store.initialize()  # warm the retriever before retrieval/RAG suites
        ds = suite["dataset"]
        yield {"type": "start", "suite": suite_id, "title": suite["title"], "lens": suite["lens"],
               "metrics": suite["metrics"], "total": len(ds), "model": model}

        sem = asyncio.Semaphore(_CONCURRENCY)
        totals = {m: 0.0 for m in suite["metrics"]}

        async def run(i, ex):
            async with sem:
                return i, await asyncio.to_thread(run_example, suite_id, ex)

        done = 0
        for fut in asyncio.as_completed([asyncio.create_task(run(i, ex)) for i, ex in enumerate(ds)]):
            i, row = await fut
            for m in suite["metrics"]:
                totals[m] += row["scores"].get(m, 0.0)
            done += 1
            yield {"type": "example", "index": i, "done": done, "total": len(ds), **row}

        n = len(ds) or 1
        yield {"type": "summary", "aggregate": {m: round(totals[m] / n, 3) for m in suite["metrics"]}}

    return sse_response(events())
