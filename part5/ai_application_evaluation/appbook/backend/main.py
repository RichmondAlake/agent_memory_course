"""AI Application Evaluation — FastAPI application.

A companion to the AI Maturity Ladder app: instead of *building* the five form
factors, it **evaluates** them — chatbot, RAG, workflow, agent, autonomous agent —
each with the metric that fits how it fails, streamed live to the browser.

Run from the `appbook/` directory:
    uvicorn backend.main:app --reload --port 8003
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR, IMAGES_DIR
from backend.core.retrieval import store
from backend.routers import agentff, benchmark, images, meta, suites


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the embedding model + Oracle connection without blocking startup.
    threading.Thread(target=store.initialize, daemon=True).start()
    yield


app = FastAPI(title="AI Application Evaluation", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Register specific /api/eval/* routes (beir, agent, builder) BEFORE the catch-all
# /api/eval/{suite_id} in suites.router, so they aren't shadowed.
for r in (meta.router, benchmark.router, agentff.router, suites.router, images.router):
    app.include_router(r)

if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8003, reload=False)
