"""The agent memory evaluation studio: FastAPI backend and static frontend on one origin.

Run from the `appbook/` directory:
    ./run.sh            # http://127.0.0.1:8715
"""
from __future__ import annotations

from backend.core.tracing import setup_tracing

setup_tracing()   # first: instrument OpenAI and Anthropic before any module creates a client (off without Arize keys)

import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.config import DEFAULT_PORT, FRONTEND_DIR, settings  # noqa: E402
from backend.core import db  # noqa: E402
from backend.routers import data_explorer, graders, meta, suites  # noqa: E402


def _warm_up() -> None:
    """Open models first (Gemma 4 and nomic-embed-text through Ollama), then Oracle (pool and tables)."""
    if settings.open:
        from backend.core import llm

        try:
            llm.prepare_open_models()
            meta.OPEN_MODELS.update(status="ready", error=None)
        except Exception as exc:  # noqa: BLE001 — shown on the status card
            meta.OPEN_MODELS.update(status="error", error=f"Ollama at {settings.ollama_url}: {exc}"[:300])
    db.bootstrap()


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Agent Memory Evaluation Studio", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def database_unavailable(request, exc):
    """A lost or restarting database is a 503 with the driver's message, not a bare 500."""
    from fastapi.responses import JSONResponse

    message = f"{type(exc).__name__}: {exc}".splitlines()[0][:300]
    status = 503 if type(exc).__module__.startswith("oracledb") or "Oracle" in message else 500
    return JSONResponse({"detail": message}, status_code=status)


@app.middleware("http")
async def revalidate_frontend(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


for r in (meta.router, graders.router, suites.router, data_explorer.router):
    app.include_router(r)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
