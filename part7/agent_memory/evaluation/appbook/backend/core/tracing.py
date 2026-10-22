"""Optional tracing to Arize AX: every OpenAI and Anthropic call (the agents, MemoRizz's model calls, the judge) through
OpenInference's instrumentors, plus manual spans for what they cannot see: SystemOne requests to Clef-Flash and Jev,
Ollama's own chat API, grader verdicts, the scratch Memo's Oracle recall and each MemoRizz turn.

On only when ARIZE_SPACE_ID and ARIZE_API_KEY are set (the environment, ~/.ppa_workshop/keys.env or the appbook's
.env); otherwise there is no tracer provider, no exporter and no span. The key is never printed or stored in a span.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import dotenv_values

DEFAULT_PROJECT = "agent-memory-evaluation-appbook"
_ROOT = Path(__file__).resolve().parents[2]
_state = {"tracer": None, "provider": None, "project": None, "done": False}


def _load_keys() -> None:
    """Read only the ARIZE_* settings from the key files, without touching any other variable. A variable already in
    the environment wins, even when empty: `ARIZE_SPACE_ID= ARIZE_API_KEY= ./run.sh` keeps tracing off."""
    for path in (Path.home() / ".ppa_workshop" / "keys.env", _ROOT / ".env", _ROOT.parent / ".env", _ROOT.parents[2] / ".env"):
        if path.exists():
            for key, value in dotenv_values(path).items():
                if key in ("ARIZE_SPACE_ID", "ARIZE_API_KEY", "ARIZE_PROJECT_NAME") and value and key not in os.environ:
                    os.environ[key] = value


def setup_tracing(register=None) -> str:
    """Register Arize AX and instrument OpenAI and Anthropic, once. `register` is replaceable for tests."""
    if _state["done"]:
        return tracing_status()
    _state["done"] = True
    _load_keys()
    if not (os.getenv("ARIZE_SPACE_ID") and os.getenv("ARIZE_API_KEY")):
        return "off"
    if register is None:
        from arize.otel import register
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    project = os.getenv("ARIZE_PROJECT_NAME") or DEFAULT_PROJECT
    # set_global_tracer_provider=False: the Anthropic SDK also emits its own span through the global provider, which
    # would duplicate OpenInference's LLM span. Every instrumentor gets the provider explicitly instead.
    provider = register(space_id=os.environ["ARIZE_SPACE_ID"], api_key=os.environ["ARIZE_API_KEY"], project_name=project,
                        set_global_tracer_provider=False, verbose=False)
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    AnthropicInstrumentor().instrument(tracer_provider=provider)
    _state.update(tracer=provider.get_tracer(project), provider=provider, project=project)
    return tracing_status()


def tracing_status() -> str:
    return f"arize-ax:{_state['project']}" if _state["tracer"] is not None else "off"


@contextmanager
def traced(name: str, kind: str, **attributes):
    """A span for a step the instrumentors cannot see. Yields the span, or None when tracing is off."""
    tracer = _state["tracer"]
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name, attributes={"openinference.span.kind": kind, **attributes}) as span:
        yield span


def text(value, limit: int = 2000) -> str:
    """A value as span text: JSON when it can be, cut to about `limit` characters."""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            value = str(value)
    return value if len(value) <= limit else value[:limit] + "…"


def io(value) -> dict:
    """input.value (and its mime type) for a span's attributes."""
    out = {"input.value": text(value)}
    if not isinstance(value, str):
        out["input.mime_type"] = "application/json"
    return out


def set_output(span, value) -> None:
    if span is None:
        return
    span.set_attribute("output.value", text(value))
    if not isinstance(value, str):
        span.set_attribute("output.mime_type", "application/json")


def set_documents(span, documents) -> None:
    """documents: (id, content, score) tuples, best first."""
    if span is None:
        return
    for i, (doc_id, content, score) in enumerate(documents):
        span.set_attribute(f"retrieval.documents.{i}.document.id", str(doc_id))
        span.set_attribute(f"retrieval.documents.{i}.document.content", text(content, 300))
        if score is not None:
            span.set_attribute(f"retrieval.documents.{i}.document.score", float(score))


def set_tokens(span, prompt=None, completion=None) -> None:
    if span is None:
        return
    if prompt is not None:
        span.set_attribute("llm.token_count.prompt", int(prompt))
    if completion is not None:
        span.set_attribute("llm.token_count.completion", int(completion))
    if prompt is not None and completion is not None:
        span.set_attribute("llm.token_count.total", int(prompt) + int(completion))
