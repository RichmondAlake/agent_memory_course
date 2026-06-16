"""Agent Memory Stack — FastAPI application.

Mounts one router per memory layer, warms the memorizz Memory Core in the
background on startup, and serves the static frontend from the same origin.

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
from backend.routers import conversation, coordination, images, knowledge, meta, procedural, semantic


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the embedding model + memory provider without blocking startup.
    threading.Thread(target=store.initialize, daemon=True).start()
    yield


app = FastAPI(title="Agent Memory Stack", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, conversation.router, semantic.router, knowledge.router,
          procedural.router, coordination.router, images.router):
    app.include_router(r)

# Serve concept-diagram images, then the SPA last (so /api/* + /images win).
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
