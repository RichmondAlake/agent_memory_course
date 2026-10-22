"""The decision models: Clef-Flash (in this process, or at CLEF_URL) and Jev (hosted, optional).

Both take the same SystemOne request: a state, and typed questions; both return a probability per answer.
Clef plays two roles here: it decides mortgage applications (the workflow under test) and it grades answers.
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time

import requests

from backend.config import settings
from backend.core.tracing import as_json, llm_usage, traced

JEV_URL = "https://api.typesafe.ai/v1/systemone"
APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"
_clef = {"model": None, "status": "remote" if settings.clef_url else "on first use", "error": None, "load_seconds": None}
_load_lock = threading.Lock()
_run_lock = threading.Lock()   # one local model: one request at a time


def clef_id() -> str:
    return f"clef-flash via {settings.clef_url}" if settings.clef_url else f"{settings.clef_repo}@{settings.clef_revision[:7]}"


def clef_status() -> dict:
    return {"status": _clef["status"], "error": _clef["error"], "load_seconds": _clef["load_seconds"], "id": clef_id(),
            "busy": _run_lock.locked()}


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
            from huggingface_hub.utils import disable_progress_bars

            disable_progress_bars()
            path = snapshot_download(settings.clef_repo, revision=settings.clef_revision,
                                     ignore_patterns=["__pycache__/*", "*.pyc", ".eval_results/*"])
            if path not in sys.path:
                sys.path.insert(0, path)
            import clef_mlx

            started = time.perf_counter()
            _clef["model"] = clef_mlx.load(path)
            _clef.update(status="ready", load_seconds=round(time.perf_counter() - started, 1), error=None)
        except Exception as exc:  # noqa: BLE001 — reported by /api/health
            _clef.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
    return _clef["model"]


def _llm_span(name: str, model: str, provider: str, request: dict):
    return traced(name, "LLM", **{"llm.model_name": model, "llm.provider": provider, "input.value": as_json(request),
                                  "input.mime_type": "application/json"})


def _record_reply(span, reply: dict) -> None:
    if span:
        span.set_attributes({"output.value": as_json(reply.get("answers")), "output.mime_type": "application/json",
                             **llm_usage(reply.get("usage"))})


def systemone(request: dict) -> dict:
    """One SystemOne request to Clef-Flash."""
    with _llm_span("clef-flash", clef_id(), "local", request) as span:
        if settings.clef_url:
            response = requests.post(f"{settings.clef_url}/v1/systemone", json=request, timeout=180)
            response.raise_for_status()
            reply = response.json()
        else:
            model = _load_clef()
            with _run_lock:
                reply = model.systemone(request)
        _record_reply(span, reply)
    return reply


def jev(request: dict) -> dict:
    """One SystemOne request to Jev (needs TYPESAFE_API_KEY)."""
    with _llm_span("jev", "jev-latest", "typesafe", request) as span:
        response = requests.post(JEV_URL, headers={"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"},
                                 json={**request, "model": "jev-latest"}, timeout=60)
        response.raise_for_status()
        reply = response.json()
        _record_reply(span, reply)
    return reply
