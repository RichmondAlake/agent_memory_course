"""Model calls: the agents' chat model, the embeddings, the LLM judge, and the open models on Ollama.

Every call has a timeout (MEMEVAL_TIMEOUT, 180 s by default), so a stalled request fails instead of hanging a run.
`SPEND` adds up tokens and dollars per purpose for the whole process; a suite reports the difference over its run.
"""
from __future__ import annotations

import array
import json
import threading
import time
from collections import Counter

import requests

from backend.config import settings
from backend.core.tracing import io, set_output, set_tokens, traced

PRICES = {  # USD per 1M tokens: (input, cached input, output)
    "gpt-6.1-sol": (2.00, 0.10, 10.00), "gpt-6-luna": (0.10, 0.01, 0.50),
    "claude-sonnet-5-5": (2.00, 0.10, 10.00), "claude-haiku-5-5": (0.10, 0.01, 0.50),
    "text-embedding-3-small": (0.02, 0.02, 0.0),
    "jev-latest": (0.042, 0.042, 0.0),   # the rate MemoRizz's Jev client uses
}
SPEND: Counter = Counter()          # f"{purpose}:{field}" → total, for the whole process
_spend_lock = threading.Lock()
_client = None
_judge_client = None
_client_lock = threading.Lock()


def cost(model: str, input_tokens: int = 0, cached_tokens: int = 0, output_tokens: int = 0) -> float:
    """Dollars for one call: input includes the cached part, which is billed at the cached rate."""
    if settings.open or model not in PRICES:
        return 0.0
    p_in, p_cached, p_out = PRICES[model]
    return ((input_tokens - cached_tokens) * p_in + cached_tokens * p_cached + output_tokens * p_out) / 1e6


def spend(purpose: str, **values) -> None:
    with _spend_lock:
        for key, value in values.items():
            SPEND[f"{purpose}:{key}"] += value or 0


def spent_since(before: dict) -> dict:
    """Dollars per purpose since a snapshot of SPEND."""
    with _spend_lock:
        now = dict(SPEND)
    out = {}
    for key, value in now.items():
        purpose, field = key.split(":", 1)
        if field == "cost_usd":
            out[purpose] = round(value - before.get(key, 0), 6)
    return {k: v for k, v in out.items() if v}


def snapshot() -> dict:
    with _spend_lock:
        return dict(SPEND)


def client():
    """The OpenAI SDK client (OpenAI, or Ollama's copy of its API on open models)."""
    global _client
    with _client_lock:
        if _client is None:
            from openai import OpenAI

            _client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url,
                             timeout=settings.request_timeout, max_retries=3)
    return _client


def usage_of(response, model: str) -> dict:
    cached = getattr(response.usage.input_tokens_details, "cached_tokens", 0) or 0
    return {"input_tokens": response.usage.input_tokens, "cached_tokens": cached,
            "output_tokens": response.usage.output_tokens,
            "cost_usd": cost(model, response.usage.input_tokens, cached, response.usage.output_tokens)}


def chat(instructions: str, messages, cheap: bool = False, purpose: str = "agents", **options):
    """One model call through the Responses API; cheap=True for background work. Returns (response, usage)."""
    model, effort = (settings.cheap_model, settings.cheap_effort) if cheap else (settings.model, settings.model_effort)
    response = client().responses.create(model=model, instructions=instructions, input=messages,
                                         reasoning={"effort": effort}, **options)
    if settings.open and not response.output_text.strip():   # a small open model sometimes ends a turn without a word
        nudge = [*messages, {"role": "user", "content": "Answer now."}] if isinstance(messages, list) else f"{messages}\n\nAnswer now."
        response = client().responses.create(model=model, instructions=instructions, input=nudge,
                                             reasoning={"effort": effort}, **options)
    used = usage_of(response, model)
    spend(purpose, **used)
    return response, used


def embed(texts, purpose: str = "embeddings", batch: int = 256) -> list[array.array]:
    """Embed texts as 256-d float32 vectors, ready to bind to a VECTOR column."""
    texts, vectors = [str(t)[:8000] or " " for t in texts], []
    for start in range(0, len(texts), batch):
        response = client().embeddings.create(model=settings.embed_model, input=texts[start:start + batch],
                                              dimensions=settings.dimensions)
        spend(purpose, input_tokens=response.usage.total_tokens,
              cost_usd=cost(settings.embed_model, response.usage.total_tokens))
        vectors += [array.array("f", item.embedding) for item in response.data]
    return vectors


# ── the judge ─────────────────────────────────────────────────────────────────────────────────────────────────
def judge_json(system: str, prompt: str, schema: dict, name: str = "verdict") -> tuple[dict, dict]:
    """One typed verdict from the judge; returns (verdict dict, usage dict with seconds)."""
    global _judge_client
    started = time.perf_counter()
    if settings.judge_provider == "anthropic":
        with _client_lock:
            if _judge_client is None:
                import anthropic

                _judge_client = anthropic.Anthropic(timeout=settings.request_timeout, max_retries=3)
        response = _judge_client.messages.create(
            model=settings.judge_model, max_tokens=1024, system=system, messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}})
        text = "".join(block.text for block in response.content if block.type == "text")
        cached = response.usage.cache_read_input_tokens or 0
        used = (response.usage.input_tokens + cached, cached, response.usage.output_tokens)
    elif settings.judge_provider == "openai":
        response = client().responses.create(model=settings.judge_model, reasoning={"effort": "low"}, instructions=system,
                                             input=prompt, text={"format": {"type": "json_schema", "name": name,
                                                                            "schema": schema, "strict": True}})
        text = response.output_text
        used = (response.usage.input_tokens, getattr(response.usage.input_tokens_details, "cached_tokens", 0) or 0,
                response.usage.output_tokens)
    else:   # Ollama's own chat API constrains the output to the schema
        response = ollama("/api/chat", model=settings.judge_model, think=False, format=schema,
                          messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        text = response["message"]["content"]
        used = (response.get("prompt_eval_count", 0), 0, response.get("eval_count", 0))
    usage = {"input_tokens": used[0], "cached_tokens": used[1], "output_tokens": used[2],
             "cost_usd": cost(settings.judge_model, *used)}
    spend("judge", **usage)
    return json.loads(text), {**usage, "seconds": time.perf_counter() - started}


# ── open models ───────────────────────────────────────────────────────────────────────────────────────────────
def ollama(path: str, **body) -> dict:
    """One call to Ollama's own API: pull a model, chat, or create a variant of one."""
    if path != "/api/chat":
        response = requests.post(f"{settings.ollama_url}{path}", json={**body, "stream": False}, timeout=3600)
        response.raise_for_status()
        return response.json()
    with traced("ollama chat", "LLM", **{"llm.model_name": str(body.get("model")), "llm.provider": "ollama"},
                **io(body.get("messages"))) as span:
        response = requests.post(f"{settings.ollama_url}{path}", json={**body, "stream": False}, timeout=3600)
        response.raise_for_status()
        reply = response.json()
        set_output(span, (reply.get("message") or {}).get("content", ""))
        set_tokens(span, reply.get("prompt_eval_count"), reply.get("eval_count"))
        return reply


def prepare_open_models() -> None:
    """Pull Gemma 4 and nomic-embed-text if missing, and create the 32k-context variant the agents use."""
    installed = {m["name"] for m in requests.get(f"{settings.ollama_url}/api/tags", timeout=10).json()["models"]}
    for name in (settings.open_model, settings.embed_model):
        if name not in installed and f"{name}:latest" not in installed:
            ollama("/api/pull", model=name)
    ollama("/api/create", model=settings.model, parameters={"num_ctx": settings.open_context}, **{"from": settings.open_model})
