"""AI Maturity Ladder — FastAPI application (Acme Home Loans).

Mounts one router per form factor, bootstraps Oracle (pool, schema, seed) and the sandbox in the
background on startup, runs the automation scheduler, and serves the static frontend from the same origin.

Run from the `appbook/` directory:
    ./run.sh            # or: uvicorn backend.main:app --reload --port 8700
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from backend.config import DEFAULT_PORT, FRONTEND_DIR
from backend.core import db, sandbox
from backend.core.activity import activity, operations_for
from backend.core.automations import automation_store
from backend.routers import agent, builder, chat, data_explorer, meta, rag, workflow


async def _scheduler_loop() -> None:
    """Fire any due automations roughly every 15s — Form Factor 5's in-app scheduler."""
    while True:
        await asyncio.sleep(15)
        try:
            await run_in_threadpool(automation_store.tick)
        except Exception:  # noqa: BLE001 — never let the scheduler crash the app
            pass


def _warm_up() -> None:
    """Oracle first (pool, legacy clean-up, schema, seed), then the sandbox with a fresh policy export."""
    db.bootstrap()
    sandbox.seed_if_empty()
    if db.ready() and not (sandbox.SANDBOX / "policy.json").exists():
        from backend.core.underwriting import current_policy

        sandbox.export_policy(*current_policy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    scheduler = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        scheduler.cancel()


app = FastAPI(title="AI Maturity Ladder", version="2.0.0", lifespan=lifespan)

# No CORS middleware on purpose: the SPA is served from this origin, and Form
# Factor 5 runs code, so other websites must not be able to call this API.


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
    try:
        response = await call_next(request)
        status = "committed" if response.status_code < 400 else "rolled_back"
        return response
    except Exception:
        status = "rolled_back"
        raise
    finally:
        detail = f"{(perf_counter() - started) * 1000:.1f} ms"
        for item in operations:
            await activity.publish(transaction_id=transaction_id, status=status, route=path, detail=detail, **item)


@app.middleware("http")
async def revalidate_frontend(request, call_next):
    """The page and its scripts change with the app: browsers must revalidate them (ETag), not reuse a stale copy."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


for r in (meta.router, data_explorer.router, chat.router, rag.router, workflow.router, agent.router, builder.router):
    app.include_router(r)

# Serve the SPA last so the API routes win.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
