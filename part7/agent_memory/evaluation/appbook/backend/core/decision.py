"""The two decision models: Clef-Flash (in this process, or at CLEF_URL) and Jev (hosted, optional).

Both answer the same SystemOne request: {"model", "state", "questions"}. A local Clef is loaded on first use and serves
one request at a time; CLEF_URL lets several apps share one copy.
"""
from __future__ import annotations

import platform
import sys
import threading
import time

import requests

from backend.config import settings
from backend.core import llm
from backend.core.tracing import io, set_output, set_tokens, traced

_clef = {"model": None, "status": "remote" if settings.clef_url else "on first use", "error": None}
_load_lock = threading.Lock()
_run_lock = threading.Lock()
APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"


def clef_status() -> dict:
    if settings.clef_url:
        return {"status": "remote", "endpoint": settings.clef_url}
    return {"status": _clef["status"], "error": _clef["error"], "model": f"{settings.clef_repo}@{settings.clef_revision[:7]}"}


def clef_id() -> str:
    return f"clef via {settings.clef_url}" if settings.clef_url else f"{settings.clef_repo}@{settings.clef_revision[:7]}"


def available() -> list[str]:
    return ["clef", "jev"] if settings.jev else ["clef"]


def _load_clef():
    if _clef["model"] is not None:
        return _clef["model"]
    with _load_lock:
        if _clef["model"] is not None:
            return _clef["model"]
        if not APPLE_SILICON:
            raise RuntimeError("Clef-Flash runs in-process on Apple silicon only here; set CLEF_URL to a SystemOne endpoint.")
        _clef["status"] = "loading"
        try:
            from huggingface_hub import snapshot_download

            path = snapshot_download(settings.clef_repo, revision=settings.clef_revision,
                                     ignore_patterns=["__pycache__/*", "*.pyc", ".eval_results/*"])
            if path not in sys.path:
                sys.path.insert(0, path)
            import clef_mlx

            _clef["model"] = clef_mlx.load(path)
            _clef.update(status="ready", error=None)
        except Exception as exc:  # noqa: BLE001 — shown by /api/health
            _clef.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
    return _clef["model"]


def systemone(model: str, state: dict, questions: dict) -> tuple[dict, float, dict]:
    """One SystemOne request to Clef or Jev; returns (answers, seconds, usage with cost_usd)."""
    started = time.perf_counter()
    request = {"model": "jev-latest" if model == "jev" else "clef-flash", "state": state, "questions": questions}
    with traced(f"systemone {request['model']}", "LLM", **{"llm.model_name": request["model"],
                "llm.provider": "typesafe" if model == "jev" else "local"}, **io({"state": state, "questions": questions})) as span:
        if model == "jev":
            import os

            response = requests.post("https://api.typesafe.ai/v1/systemone", json=request, timeout=120,
                                     headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"})
            response.raise_for_status()
            body = response.json()
        elif settings.clef_url:
            response = requests.post(f"{settings.clef_url}/v1/systemone", json=request, timeout=300)
            response.raise_for_status()
            body = response.json()
        else:
            clef = _load_clef()
            with _run_lock:
                body = clef.systemone(request)
        set_output(span, body.get("answers"))
        set_tokens(span, (body.get("usage") or {}).get("input_tokens"), (body.get("usage") or {}).get("output_tokens"))
    usage = dict(body.get("usage") or {})
    usage["cost_usd"] = llm.cost("jev-latest", usage.get("input_tokens", 0)) if model == "jev" else 0.0
    llm.spend(model, cost_usd=usage["cost_usd"], input_tokens=usage.get("input_tokens", 0))
    return body["answers"], time.perf_counter() - started, usage
