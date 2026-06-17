"""Agent Memory Benchmarks — FastAPI application.

Warms the Oracle Agent Memory client in the background on startup, mounts one
router per stop of the journey, and serves the static SPA from the same origin.

Run from the appbook/ directory:
    uvicorn backend.main:app --port 8004
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR
from backend.memory_core import store
from backend.routers import benchmark, memory, meta, naive


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Loading the embedder + connecting to Oracle can take a few seconds; do it off
    # the event loop so the frontend serves immediately and shows a "warming" status.
    threading.Thread(target=store.initialize, daemon=True).start()
    yield


app = FastAPI(title="Agent Memory Benchmarks", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, naive.router, memory.router, benchmark.router):
    app.include_router(r)

# Serve the SPA last so /api/* wins.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8004, reload=False)
