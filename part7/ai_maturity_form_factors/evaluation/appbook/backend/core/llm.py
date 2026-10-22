"""Model calls, counted: the application under test (Claude Haiku 5.5 or Gemma 4) and the LLM judge.

Every call writes a row to the current meter (a context variable), so a suite can report the tokens, seconds and
dollars of each case, split into what the application spent and what grading it cost. `pmap` runs work in a
thread pool and carries the meter into each thread.
"""
from __future__ import annotations

import contextvars
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext

import anthropic
import requests

from backend.config import settings
from backend.core.tracing import as_json, llm_usage, traced

PRICES = {  # USD per 1M tokens: input, cached input, output (list prices, October 2026)
    "claude-haiku-5-5": (0.10, 0.01, 0.50), "claude-sonnet-5-5": (2.00, 0.10, 10.00),
    "claude-opus-5-5": (4.00, 0.20, 20.00), "gpt-6.1-sol": (2.00, 0.10, 10.00), "gpt-6-luna": (0.10, 0.01, 0.50),
    "jev-latest": (0.042, 0.042, 0.042),   # the per-token rate MemoRizz's Jev client uses
}
_meter: contextvars.ContextVar[tuple] = contextvars.ContextVar("meter", default=())   # nested meters, outermost first

client = anthropic.Anthropic(api_key=settings.anthropic_api_key or "missing",
                             **({"base_url": settings.anthropic_base_url} if settings.anthropic_base_url else {}))
_openai = None


def cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    if model not in PRICES:
        return 0.0
    price_in, price_cached, price_out = PRICES[model]
    return ((input_tokens - cached_tokens) * price_in + cached_tokens * price_cached + output_tokens * price_out) / 1e6


def log_call(purpose: str, model: str, input_tokens: int, output_tokens: int, seconds: float, cached_tokens: int = 0,
             cost: float | None = None) -> None:
    row = None
    for calls in _meter.get():
        row = row or {"purpose": purpose, "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
                      "seconds": round(seconds, 3),
                      "cost_usd": cost_usd(model, input_tokens, output_tokens, cached_tokens) if cost is None else cost}
        calls.append(row)


class Meter:
    def __init__(self, calls: list):
        self.calls = calls

    def totals(self, grading: bool | None = None) -> dict:
        rows = [c for c in self.calls if grading is None or c["purpose"].startswith("grader") == grading]
        return {"calls": len(rows), "cost_usd": round(sum(c["cost_usd"] for c in rows), 6),
                "seconds": round(sum(c["seconds"] for c in rows), 3),
                "input_tokens": sum(c["input_tokens"] for c in rows), "output_tokens": sum(c["output_tokens"] for c in rows)}


@contextmanager
def meter():
    calls: list = []
    token = _meter.set(_meter.get() + (calls,))
    try:
        yield Meter(calls)
    finally:
        _meter.reset(token)


def pmap(function, items, workers: int = 8) -> list:
    """map() over a thread pool, with the caller's meter in every thread."""
    items = list(items)
    with ThreadPoolExecutor(max(1, min(workers, len(items) or 1))) as pool:
        futures = [pool.submit(contextvars.copy_context().run, function, item) for item in items]
        return [f.result() for f in futures]


def text_of(response) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def ollama(path: str, **body) -> dict:
    chat = path == "/api/chat"
    with (traced("ollama chat", "LLM", **{"llm.model_name": body.get("model"), "input.value": as_json(body.get("messages"))})
          if chat else nullcontext()) as span:
        response = requests.post(f"{settings.ollama_url}{path}", json={**body, "stream": False}, timeout=3600)
        response.raise_for_status()
        reply = response.json()
        if span:
            span.set_attributes({"output.value": as_json((reply.get("message") or {}).get("content")), **llm_usage(reply)})
    return reply


def prepare_open_models() -> None:
    """Pull Gemma 4 the first time and create the 32k-context variant (open models only)."""
    installed = {m["name"] for m in requests.get(f"{settings.ollama_url}/api/tags", timeout=10).json()["models"]}
    if settings.open_model not in installed and f"{settings.open_model}:latest" not in installed:
        ollama("/api/pull", model=settings.open_model)
    ollama("/api/create", model=settings.model, parameters={"num_ctx": 32768}, **{"from": settings.open_model})


def claude(purpose: str, system: str, messages: list, max_tokens: int | None = None, **extra):
    """One call to the application's model, metered."""
    started = time.perf_counter()
    options = ({"thinking": {"type": "disabled"}} if settings.open
               else {"output_config": {"effort": settings.effort, **extra.pop("output_config", {})}})
    response = client.messages.create(model=settings.model, max_tokens=max_tokens or settings.max_tokens, system=system,
                                      messages=messages, **options, **extra)
    usage = response.usage
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    log_call(purpose, settings.model, usage.input_tokens + cached, usage.output_tokens, time.perf_counter() - started,
             cached_tokens=cached)
    return response


def structured_json(purpose: str, *, schema: dict, system: str, prompt: str) -> dict:
    """Schema-constrained JSON from the application's model (Ollama's own API constrains Gemma's output)."""
    if settings.open:
        started = time.perf_counter()
        reply = ollama("/api/chat", model=settings.model, think=False, format=schema,
                       messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        log_call(purpose, settings.model, reply.get("prompt_eval_count", 0), reply.get("eval_count", 0),
                 time.perf_counter() - started)
        return json.loads(reply["message"]["content"])
    response = claude(purpose, system, [{"role": "user", "content": prompt}], max_tokens=4096,
                      output_config={"format": {"type": "json_schema", "schema": schema}})
    return json.loads(text_of(response))


def judge(purpose: str, system: str, prompt: str, schema: dict) -> dict:
    """A typed verdict from the LLM judge, on whichever provider runs JUDGE_MODEL."""
    global _openai
    started = time.perf_counter()
    if settings.judge_provider == "openai":
        if _openai is None:
            from openai import OpenAI

            _openai = OpenAI()
        response = _openai.responses.create(
            model=settings.judge_model, reasoning={"effort": "low"}, instructions=system, input=prompt,
            text={"format": {"type": "json_schema", "name": "verdict", "schema": schema, "strict": True}})
        usage = response.usage
        log_call(purpose, settings.judge_model, usage.input_tokens, usage.output_tokens, time.perf_counter() - started,
                 cached_tokens=getattr(usage.input_tokens_details, "cached_tokens", 0) or 0)
        return json.loads(response.output_text)
    if settings.judge_provider == "anthropic":
        response = client.messages.create(model=settings.judge_model, max_tokens=1024, system=system,
                                          messages=[{"role": "user", "content": prompt}],
                                          output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
        log_call(purpose, settings.judge_model, response.usage.input_tokens, response.usage.output_tokens,
                 time.perf_counter() - started)
        return json.loads(text_of(response))
    reply = ollama("/api/chat", model=settings.judge_model, think=False, format=schema,
                   messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    log_call(purpose, settings.judge_model, reply.get("prompt_eval_count", 0), reply.get("eval_count", 0),
             time.perf_counter() - started)
    return json.loads(reply["message"]["content"])
