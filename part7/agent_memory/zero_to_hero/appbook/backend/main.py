"""Agent Memory, from Scratch to MemoRizz — FastAPI application.

Serves the Part pages (one per notebook Part: both agents, their tables and
actions), the read-only Data Explorer and the static frontend from one origin.
The Oracle runtime warms in the background. On shutdown the lab session's rows
are deleted with exact-scope deletes unless MEMO_CLEANUP_ON_RESET=0.

Run from the ``appbook/`` directory:
    uvicorn backend.main:app --port 8710
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR
from backend.core import scratch
from backend.core.activity import activity, operations_for
from backend.core.memorizz_memo import runtime
from backend.core.session import sessions
from backend.routers import context, data_explorer, meta, parts, tokenomics


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=runtime.initialize, daemon=True).start()
    yield
    sessions.shutdown()
    runtime.close()
    scratch.close_pool()


app = FastAPI(title="Agent Memory, from Scratch to MemoRizz", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def database_activity(request, call_next):
    path = request.url.path
    if path == "/api/data_explorer/activity":
        return await call_next(request)
    operations = operations_for(request.method, path)
    transaction_id = activity.transaction_id()
    started = perf_counter()
    for item in operations:
        await activity.publish(transaction_id=transaction_id, status="active", route=path, **item)
    status = "rolled_back"
    try:
        response = await call_next(request)
        status = "committed" if response.status_code < 400 else "rolled_back"
        return response
    finally:
        detail = f"{(perf_counter() - started) * 1000:.1f} ms"
        for item in operations:
            await activity.publish(transaction_id=transaction_id, status=status, route=path, detail=detail, **item)


for router in (meta.router, data_explorer.router, parts.router, tokenomics.router, context.router):
    app.include_router(router)

# Serve the SPA last so the API routes win.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
