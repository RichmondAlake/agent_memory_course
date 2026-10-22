"""The retrieval benchmark appbook: FastAPI backend and static frontend on one origin.

Run from the `appbook/` directory:
    ./run.sh            # http://127.0.0.1:8725
"""
from __future__ import annotations

from backend.core.tracing import setup_tracing

setup_tracing()          # before the other modules are imported: optional Arize AX tracing, off without keys

import threading  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.config import DATASETS, DEFAULT_PORT, FRONTEND_DIR, NOTEBOOK_IMG_DIR  # noqa: E402
from backend.core import db, diagnostics, evidence, text  # noqa: E402
from backend.routers import data_explorer, explore, guide, leaderboard, meta, playground  # noqa: E402


def _warm_up() -> None:
    """Open the pool, check what the stored run left in Oracle, compute the leaderboard, count document frequencies
    once per corpus, and compute the decision guide's diagnostics."""
    db.bootstrap()
    if not db.ready():
        return
    try:
        meta.INVENTORY.update(db.inventory())
        run_id = evidence.default_run()
        if run_id:
            evidence.leaderboard(run_id)          # the landing page: intervals and paired tests, computed once
        for ds in DATASETS:
            if meta.INVENTORY.get(ds, {}).get("documents"):
                text.document_frequency(ds)
        for ds in DATASETS:
            if meta.INVENTORY.get(ds, {}).get("complete"):
                diagnostics.compute(ds)           # the decision guide's diagnostics, so its page opens at once
    except Exception:  # noqa: BLE001 — health reports the inventory; pages say what is missing
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Retrieval Benchmark Appbook", version="1.0.0", lifespan=lifespan)


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


for r in (meta.router, leaderboard.router, explore.router, playground.router, guide.router, data_explorer.router):
    app.include_router(r)
if NOTEBOOK_IMG_DIR.exists():
    app.mount("/img", StaticFiles(directory=str(NOTEBOOK_IMG_DIR)), name="img")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
