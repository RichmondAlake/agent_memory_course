"""Health + capability + suite-catalog endpoints that drive the UI."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.agent_eval import AGENT_METRICS, AGENT_SCENARIOS, FF5_METRICS
from backend.core.agent_runtime import AGENT_AVAILABLE
from backend.core.beir import DATASETS as BEIR_DATASETS, bench
from backend.core.evaluation import SUITES
from backend.core.metric_defs import catalog
from backend.core.retrieval import store

router = APIRouter(prefix="/api", tags=["meta"])

# Cache the one-time LangSmith auth check so /health (polled by the UI) never re-pings.
_ls_ok: bool | None = None


def _langsmith_ok() -> bool:
    """True only if a LangSmith key is present AND actually authenticates."""
    global _ls_ok
    if _ls_ok is not None:
        return _ls_ok
    if not settings.langsmith_enabled:
        _ls_ok = False
        return False
    try:
        from langsmith import Client
        list(Client().list_datasets(limit=1))
        _ls_ok = True
    except Exception:  # noqa: BLE001 — present but rejected key → degrade to local-only
        _ls_ok = False
    return _ls_ok


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "retrieval": store.status(),
        "beir": bench.status(),
        "agent_available": AGENT_AVAILABLE,
        "oracle_enabled": settings.oracle_enabled,
        "api_key_set": bool(settings.anthropic_api_key),
        "langsmith_key_set": settings.langsmith_enabled,
        "langsmith_ok": _langsmith_ok(),     # key present AND authenticates
        "langsmith_project": settings.langsmith_project if _langsmith_ok() else None,
    }


@router.get("/suites")
def suites() -> dict:
    """Catalog the evaluations the UI offers, grouped by form factor."""
    ff_suites: dict[str, list] = {}
    for sid, s in SUITES.items():
        ff_suites.setdefault(s["ff"], []).append({
            "id": sid, "title": s["title"], "lens": s["lens"], "blurb": s["blurb"],
            "metrics": s["metrics"], "n": len(s["dataset"]),
        })
    return {
        "suites": ff_suites,
        "agent": {"scenarios": [{"id": s["id"], "prompt": s["prompt"],
                                 "expected": s["expected_tools"], "forbidden": s["forbidden_tools"]}
                                for s in AGENT_SCENARIOS],
                  "metrics": AGENT_METRICS},
        "builder": {"metrics": FF5_METRICS},
        "beir": {"n_queries": settings.beir_n_queries,
                 "datasets": [{"id": k, "label": v["label"], "blurb": v["blurb"]} for k, v in BEIR_DATASETS.items()]},
        "catalog": catalog(),
        "models": {
            "default": settings.model,
            "options": [
                {"id": settings.model, "label": settings.model + " (default)"},
                {"id": "claude-haiku-4-5", "label": "claude-haiku-4-5 (weaker)"},
                {"id": "claude-sonnet-4-6", "label": "claude-sonnet-4-6 (mid)"},
            ],
        },
    }
