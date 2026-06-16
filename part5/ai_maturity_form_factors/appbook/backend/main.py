"""AI Maturity Ladder — FastAPI application.

Mounts one router per form factor, warms the retriever in the background on
startup, and serves the static frontend from the same origin.

Run from the `app/` directory:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR, IMAGES_DIR
from backend.core.automations import automation_store
from backend.core.retrieval import store
from backend.routers import agent, builder, chat, images, meta, rag, workflow


async def _scheduler_loop() -> None:
    """Fire any due automations roughly every 15s — Form Factor 5's in-app scheduler."""
    while True:
        await asyncio.sleep(15)
        try:
            await run_in_threadpool(automation_store.tick)
        except Exception:  # noqa: BLE001 — never let the scheduler crash the app
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the embedding model + Oracle connection without blocking startup.
    threading.Thread(target=store.initialize, daemon=True).start()
    scheduler = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        scheduler.cancel()


app = FastAPI(title="AI Maturity Ladder", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, chat.router, rag.router, workflow.router, agent.router, builder.router, images.router):
    app.include_router(r)

# Serve the concept-diagram images, then the SPA last (mounted after so /api/* + /images win).
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
