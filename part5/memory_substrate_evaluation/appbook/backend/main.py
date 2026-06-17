"""Memory Substrate Evaluation — FastAPI application.

Two agent-memory substrates side by side — the filesystem and the Oracle AI
Database — compared through an educational progression: write & ingest latency,
retrieval quality (keyword vs semantic), and ACID concurrency. Serves the SPA from
the same origin.

Run from the `appbook/` directory:
    uvicorn backend.main:app --reload --port 8004
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR, IMAGES_DIR
from backend.core.db_substrate import db_substrate
from backend.routers import benchmark, meta, substrates


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the DB substrate (nomic model download + Oracle connect) off the hot path.
    threading.Thread(target=db_substrate.initialize, daemon=True).start()
    yield


app = FastAPI(title="Memory Substrate Evaluation", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, substrates.router, benchmark.router):
    app.include_router(r)

# Serve concept-diagram images (if any), then the SPA last so /api/* + /images win.
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8004, reload=False)
