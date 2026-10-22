"""Optional tracing to Arize AX: every LLM and agent call (auto-instrumented), plus spans for the steps the
instrumentors cannot see (the decision models, the graders, Oracle retrieval and the reranker).

On only when ARIZE_SPACE_ID and ARIZE_API_KEY are both set, in the environment or the appbook's .env. Otherwise no
tracer provider or exporter is created and every `traced()` block is a no-op. ARIZE_PROJECT_NAME overrides the project.
The key is never printed, logged or put in a span.
"""
from __future__ import annotations

import importlib
import json
import os
import threading
from contextlib import contextmanager

DEFAULT_PROJECT = "ai-maturity-evaluation-appbook"
_state = {"configured": False, "tracer": None, "provider": None, "project": None}
_lock = threading.Lock()


def _register(**kwargs):
    """Arize AX's OpenTelemetry setup (the contract tests swap in an in-memory provider)."""
    from arize.otel import register

    return register(**kwargs)


def _instrumentors() -> list:
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor

    return [AnthropicInstrumentor(), OpenAIInstrumentor(), ClaudeAgentSDKInstrumentor()]


def setup_tracing() -> None:
    """Register the exporter and the instrumentors once. Call it before `claude_agent_sdk` is imported anywhere."""
    with _lock:
        if _state["configured"]:
            return
        _state["configured"] = True
        importlib.import_module("backend.config")   # loads the appbook's .env files first

        space_id, api_key = os.environ.get("ARIZE_SPACE_ID", "").strip(), os.environ.get("ARIZE_API_KEY", "").strip()
        if not (space_id and api_key):
            return
        project = os.environ.get("ARIZE_PROJECT_NAME", "").strip() or DEFAULT_PROJECT
        # Not the global provider: the Anthropic SDK emits its own span through the global one, which would duplicate
        # OpenInference's LLM span.
        provider = _register(space_id=space_id, api_key=api_key, project_name=project, set_global_tracer_provider=False,
                             verbose=False)
        for instrumentor in _instrumentors():
            instrumentor.instrument(tracer_provider=provider)
        _state.update(provider=provider, tracer=provider.get_tracer(project), project=project)


def tracing_status() -> str:
    return f"arize-ax:{_state['project']}" if _state["tracer"] is not None else "off"


def as_json(value) -> str:
    return json.dumps(value, default=str)[:2000]


def _attribute(value):
    """Numbers and booleans as they are; text truncated; anything else as JSON."""
    if isinstance(value, (bool, int, float)):
        return value
    return (value if isinstance(value, str) else as_json(value))[:2000]


@contextmanager
def traced(name: str, kind: str, **attributes):
    """A span for a step the instrumentors cannot see. Yields the span, or None when tracing is off."""
    tracer = _state["tracer"]
    if tracer is None:
        yield None
        return
    clean = {key: _attribute(value) for key, value in attributes.items() if value is not None}
    with tracer.start_as_current_span(name, attributes={"openinference.span.kind": kind, **clean}) as span:
        yield span


def documents(prefix: str, ids: list, texts=None, scores=None) -> dict:
    """OpenInference attributes for a ranked list of documents: ids, short content and scores when known."""
    attributes = {}
    for i, doc_id in enumerate(ids):
        attributes[f"{prefix}.{i}.document.id"] = str(doc_id)
        text = texts.get(doc_id) if isinstance(texts, dict) else (texts[i] if texts is not None else None)
        if text:
            attributes[f"{prefix}.{i}.document.content"] = str(text)[:300]
        if scores is not None:
            attributes[f"{prefix}.{i}.document.score"] = float(scores[i])
    return attributes


def llm_usage(usage: dict | None) -> dict:
    """Token counts from a SystemOne or Ollama reply, as OpenInference attributes."""
    usage = usage or {}
    prompt, completion = usage.get("input_tokens") or usage.get("prompt_eval_count"), usage.get("output_tokens") or usage.get("eval_count")
    counts = {"llm.token_count.prompt": prompt, "llm.token_count.completion": completion}
    if prompt is not None or completion is not None:
        counts["llm.token_count.total"] = (prompt or 0) + (completion or 0)
    return {k: int(v) for k, v in counts.items() if v is not None}
