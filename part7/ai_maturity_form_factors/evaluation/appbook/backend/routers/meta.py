"""Health, runs (notebook and appbook), a run's scorecard and gates."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import settings
from backend.core import db, decision, evidence, graders
from backend.core.tracing import tracing_status

router = APIRouter(prefix="/api", tags=["meta"])
OPEN_MODELS = {"status": "preparing" if settings.open else "off", "error": None}


@router.get("/health")
def health():
    runs = []
    if db.ready():
        try:
            runs = evidence.runs(limit=200)
        except Exception:  # noqa: BLE001 — health must answer even if a query fails
            runs = []
    return {
        "provider": settings.provider, "model": settings.model, "effort": None if settings.open else settings.effort,
        "open_models": {**OPEN_MODELS, "ollama_url": settings.ollama_url},
        "judge": {"provider": settings.judge_provider, "model": settings.judge_model},
        "clef": decision.clef_status(), "jev": {"available": settings.jev, "model": "jev-latest" if settings.jev else None},
        "graders": graders.available(), "oracle": db.status(), "models": db.models_status(),
        "agent_available": settings.claude_cli_path is not None, "tracing": tracing_status(),
        "runs": {"total": len(runs), "notebook": sum(r["source"] == "notebook" for r in runs),
                 "appbook": sum(r["source"] == "appbook" for r in runs)},
    }


def _ready():
    if not db.ready():
        raise HTTPException(503, f"Oracle AI Database is not ready: {db.status().get('error') or 'still starting'}")


@router.get("/runs")
def list_runs(limit: int = 60):
    _ready()
    return {"runs": evidence.runs(limit=min(max(limit, 1), 200))}


@router.get("/runs/{run_id}")
def run_summary(run_id: str):
    _ready()
    found = [r for r in evidence.runs(limit=200) if r["run_id"] == run_id]
    if not found:
        raise HTTPException(404, "No such run")
    summary = evidence.summarize(run_id)
    gates = evidence.evaluate_gates(summary)
    return {"run": found[0], "summary": summary, "gates": gates, "readiness": evidence.readiness(gates)}


@router.get("/runs/{run_id}/results")
def run_results(run_id: str, form_factor: str | None = None, limit: int = 500):
    _ready()
    rows = evidence.results(run_id, form_factor)
    return {"run_id": run_id, "rows": rows[: min(max(limit, 1), 2000)], "total": len(rows)}
