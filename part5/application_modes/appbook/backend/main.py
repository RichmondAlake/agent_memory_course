"""Application Modes — FastAPI application.

Three operational modes of memory-backed agents (Assistant, Workflow, Deep
Research), each streamed to the browser over Server-Sent Events. Warms the
Oracle AI Agent Memory store in the background on startup and serves the SPA
from the same origin.

Run from the `appbook/` directory:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR, IMAGES_DIR
from backend.core.memory import store
from backend.routers import assistant, images, meta, research, workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the memory backend (Oracle connect + embedder) without blocking startup.
    threading.Thread(target=store.initialize, daemon=True).start()
    yield


app = FastAPI(title="Application Modes", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, assistant.router, workflow.router, research.router, images.router):
    app.include_router(r)

# Serve concept-diagram images, then the SPA last (so /api/* + /images win).
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
