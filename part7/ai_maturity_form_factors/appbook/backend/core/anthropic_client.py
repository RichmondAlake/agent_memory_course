"""Shared Anthropic client and helpers for Form Factors 1-3, mirroring the notebook.

Claude Haiku 5.5 thinks before it answers, so a response can open with a ``thinking`` block:
``text_of`` reads text blocks by type. ``structured_json`` constrains output to a JSON Schema with
``output_config.format`` and retries once with a bigger budget if the answer was truncated.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from backend.config import settings

# Use a placeholder when the key is unset so the app still imports and serves the frontend;
# API calls then fail with a clear 401 instead of the server failing to start.
_api_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
client = anthropic.Anthropic(api_key=_api_key)
async_client = anthropic.AsyncAnthropic(api_key=_api_key)
MODEL = settings.model
MAX_TOKENS = settings.max_tokens
EFFORT = settings.effort
OUTPUT_CONFIG = {"effort": EFFORT}


def text_of(response) -> str:
    """Join the text blocks of a Claude response (it can also hold thinking and tool-use blocks)."""
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


def ask(system: str, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    response = client.messages.create(model=MODEL, max_tokens=max_tokens, output_config=OUTPUT_CONFIG,
                                      system=system, messages=[{"role": "user", "content": prompt}])
    return text_of(response)


def structured_json(*, schema: dict[str, Any], system: str, prompt: str, initial_tokens: int = 2048) -> dict:
    """Request schema-constrained JSON and retry once with a bigger budget if the output is truncated."""
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
