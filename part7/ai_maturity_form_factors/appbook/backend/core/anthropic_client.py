"""Shared Anthropic client and helpers for Form Factors 1-3, mirroring the notebook.

Claude Haiku 5.5 thinks before it answers, so a response can open with a ``thinking`` block:
``text_of`` reads text blocks by type. ``structured_json`` constrains output to a JSON Schema with
``output_config.format`` and retries once with a bigger budget if the answer was truncated.

On open models the same client talks to Ollama's Messages API (Gemma 4, thinking off so a laptop stays quick),
and ``structured_json`` uses Ollama's own chat API, whose ``format`` constrains the output to the schema (its
Messages API ignores ``output_config.format``).
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from backend.config import settings
from backend.core.tracing import as_json, llm_usage, traced

# Use a placeholder when the key is unset so the app still imports and serves the frontend;
# API calls then fail with a clear 401 instead of the server failing to start.
_api_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
client = anthropic.Anthropic(api_key=_api_key, base_url=settings.anthropic_base_url)
async_client = anthropic.AsyncAnthropic(api_key=_api_key, base_url=settings.anthropic_base_url)
MODEL = settings.model
MAX_TOKENS = settings.max_tokens
EFFORT = settings.effort
OUTPUT_CONFIG = {"effort": EFFORT}
THINKING = {"thinking": {"type": "disabled"}} if settings.open else {}   # pass with every request


def _ollama(path: str, **body: Any) -> dict:
    """One call to Ollama's own API."""
    import requests
    from contextlib import nullcontext

    with (traced("ollama chat", "LLM", **{"llm.model_name": body.get("model"), "input.value": as_json(body.get("messages"))})
          if path == "/api/chat" else nullcontext()) as span:
        response = requests.post(f"{settings.ollama_url}{path}", json={**body, "stream": False}, timeout=3600)
        response.raise_for_status()
        reply = response.json()
        if span:
            span.set_attributes({"output.value": as_json((reply.get("message") or {}).get("content")), **llm_usage(reply)})
    return reply


def prepare_open_models() -> None:
    """Open models: pull Gemma 4 if Ollama lacks it, then make the 32k-context variant every call uses.

    Ollama's default context window is 4,096 tokens; the agents' requests (the Claude Code runtime's own
    instructions and tools first) are far longer, and a cut request fails without an error.
    """
    import requests

    tags = requests.get(f"{settings.ollama_url}/api/tags", timeout=10)
    tags.raise_for_status()
    installed = {model["name"] for model in tags.json().get("models", [])}
    if settings.open_model not in installed and f"{settings.open_model}:latest" not in installed:
        _ollama("/api/pull", model=settings.open_model)
    _ollama("/api/create", model=MODEL, parameters={"num_ctx": 32768}, **{"from": settings.open_model})


def text_of(response) -> str:
    """Join the text blocks of a Claude response (it can also hold thinking and tool-use blocks)."""
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


def ask(system: str, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    response = client.messages.create(model=MODEL, max_tokens=max_tokens, output_config=OUTPUT_CONFIG, **THINKING,
                                      system=system, messages=[{"role": "user", "content": prompt}])
    return text_of(response)


def structured_json(*, schema: dict[str, Any], system: str, prompt: str, initial_tokens: int = 2048) -> dict:
    """Request schema-constrained JSON and retry once with a bigger budget if the output is truncated."""
    if settings.open:
        reply = _ollama("/api/chat", model=MODEL, think=False, format=schema,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return json.loads(reply["message"]["content"])
    budgets = tuple(dict.fromkeys((initial_tokens, max(4096, MAX_TOKENS))))
    last_reason = None
    for budget in budgets:
        response = client.messages.create(
            model=MODEL,
            max_tokens=budget,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={**OUTPUT_CONFIG, "format": {"type": "json_schema", "schema": schema}},
        )
        last_reason = response.stop_reason
        if last_reason == "max_tokens":
            continue
        if last_reason not in {"end_turn", "stop_sequence"}:
            raise RuntimeError(f"Structured response stopped with {last_reason!r}.")
        return json.loads(text_of(response))
    raise RuntimeError(f"Structured response stayed truncated after budgets {budgets}; last stop_reason={last_reason!r}.")
