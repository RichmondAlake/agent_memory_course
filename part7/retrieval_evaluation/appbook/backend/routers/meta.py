"""Health, the runs in BEIR7_RUNS, and what the stored run left in Oracle."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import DATASETS, settings
from backend.core import db, diagnostics, evidence, models, playground, text, tracing

router = APIRouter(prefix="/api", tags=["meta"])
INVENTORY: dict = {}


def ready() -> None:
    if not db.ready():
        raise HTTPException(503, f"Oracle AI Database is not ready: {db.status().get('error') or 'still starting'}")


@router.get("/health")
def health():
    out = {"oracle": db.status(), "models": models.status(), "inventory": INVENTORY or None,
           "run_id": None, "runs": 0, "datasets": {ds: spec["name"] for ds, spec in DATASETS.items()},
           "playground": {ds: playground.status(ds) for ds in DATASETS},
           "document_frequencies": dict(text.DF_SECONDS), "diagnostics": sorted(diagnostics._cache),
           "dsn": settings.oracle_dsn, "tracing": tracing.tracing_status()}
    if db.ready():
        try:
            all_runs = evidence.runs()
            out.update(runs=len(all_runs), run_id=evidence.default_run())
        except Exception as exc:  # noqa: BLE001 — health must answer
            out["error"] = str(exc).splitlines()[0][:200]
    return out


@router.get("/runs")
def runs():
    ready()
    return {"runs": evidence.runs(), "default": evidence.default_run()}


@router.get("/inventory")
def inventory():
    ready()
    INVENTORY.update(db.inventory())
    return INVENTORY


@router.get("/runs/{run_id}/configs")
def configs(run_id: str):
    ready()
    try:
        run_id = evidence.resolve(run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"run_id": run_id, "configs": evidence.best_configs(run_id)}
