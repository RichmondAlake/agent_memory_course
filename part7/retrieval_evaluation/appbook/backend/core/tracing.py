"""Optional tracing to Arize AX (OpenInference spans over OpenTelemetry).

On only when both ARIZE_SPACE_ID and ARIZE_API_KEY are set (environment, ~/.ppa_workshop/keys.env, or a .env next to
the app); ARIZE_PROJECT_NAME overrides the project. Off otherwise: no provider, no exporter, no spans.

This app calls no LLM, so nothing is instrumented automatically. The spans are written by hand, and only for the
query explorer: one CHAIN per request (`traced_request`), the query embedding, each strategy's retrieval and the
reranker. The playground's recomputations and the leaderboard send none: `traced()` yields a span only inside a
`traced_request()` block.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

DEFAULT_PROJECT = "beir-retrieval-benchmark-appbook"
APP_DIR = Path(__file__).resolve().parents[2]
_state: dict = {"ready": False, "tracer": None, "project": DEFAULT_PROJECT}
_in_request: ContextVar[bool] = ContextVar("beir7app_traced_request", default=False)


def _keys() -> dict:
    """ARIZE_* values: keys.env, then the .env files (most specific last), then the process environment."""
    values: dict = {}
    try:
        from dotenv import dotenv_values

        for path in (Path.home() / ".ppa_workshop" / "keys.env", APP_DIR.parent.parent / ".env",
                     APP_DIR.parent / ".env", APP_DIR / ".env"):
            if path.exists():
                values.update({k: v for k, v in dotenv_values(path).items() if k.startswith("ARIZE_") and v})
    except Exception:  # noqa: BLE001 — a missing or unreadable file just means no keys from it
        pass
    values.update({k: os.environ[k] for k in ("ARIZE_SPACE_ID", "ARIZE_API_KEY", "ARIZE_PROJECT_NAME") if os.environ.get(k)})
    return values


def setup_tracing() -> str:
    """Register the Arize AX tracer provider once, if the keys are present. Returns the status."""
    if _state["ready"]:
        return tracing_status()
    keys = _keys()
    _state["project"] = keys.get("ARIZE_PROJECT_NAME") or DEFAULT_PROJECT
    if keys.get("ARIZE_SPACE_ID") and keys.get("ARIZE_API_KEY"):
        from arize.otel import register

        provider = register(space_id=keys["ARIZE_SPACE_ID"], api_key=keys["ARIZE_API_KEY"],
                            project_name=_state["project"], set_global_tracer_provider=False, verbose=False)
        _state["tracer"] = provider.get_tracer(_state["project"])
    _state["ready"] = True
    return tracing_status()


def tracing_status() -> str:
    return f"arize-ax:{_state['project']}" if _state["tracer"] is not None else "off"


@contextmanager
def traced(name: str, kind: str, **attributes):
    """A span for a step the instrumentors cannot see. Yields the span, or None when tracing is off (or outside a
    traced request)."""
    tracer = _state["tracer"]
    if tracer is None or not _in_request.get():
        yield None
        return
    with tracer.start_as_current_span(name, attributes={"openinference.span.kind": kind, **attributes}) as span:
        yield span


@contextmanager
def traced_request(name: str, **attributes):
    """The CHAIN span of one explorer request; the spans opened inside it are sent, spans elsewhere are not."""
    token = _in_request.set(True)
    try:
        with traced(name, "CHAIN", **attributes) as span:
            yield span
    finally:
        _in_request.reset(token)


def active() -> bool:
    """True when a span opened now would be sent (so callers can skip building its attributes)."""
    return _state["tracer"] is not None and _in_request.get()


def set_documents(span, prefix: str, ranked: list[tuple], texts: dict[str, str] | None = None) -> None:
    """Up to ten (doc_id, score) pairs as OpenInference document attributes, with the first 300 characters."""
    if span is None:
        return
    for i, (doc, score) in enumerate(ranked[:10]):
        span.set_attribute(f"{prefix}.{i}.document.id", str(doc))
        span.set_attribute(f"{prefix}.{i}.document.score", float(score))
        if texts is not None:
            span.set_attribute(f"{prefix}.{i}.document.content", (texts.get(doc) or "")[:300])
