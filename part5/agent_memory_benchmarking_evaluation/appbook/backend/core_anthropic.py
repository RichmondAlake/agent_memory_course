"""Shared Anthropic client + helpers (mirrors the notebook's call_claude).

Both a sync client (used inside threadpool workers alongside OAMP's sync API) and
an async client (used for token-streaming chat) are provided, each with generous
retries so transient 429/5xx/overloaded responses don't break a long benchmark run.
"""
from __future__ import annotations

import random
import time
from typing import Any

import anthropic

from backend.config import settings

_api_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
sync_client = anthropic.Anthropic(api_key=_api_key, max_retries=8)
async_client = anthropic.AsyncAnthropic(api_key=_api_key, max_retries=8)

AGENT_MODEL = settings.agent_model
SMALL_MODEL = settings.small_model
SYSTEM_PROMPT = "You are a concise research assistant. Answer in 1-3 sentences."


def text_of(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def prompt_tokens(usage) -> int:
    """Total input tokens for a request = uncached + cache-write + cache-read."""
    return (usage.input_tokens
            + getattr(usage, "cache_creation_input_tokens", 0)
            + getattr(usage, "cache_read_input_tokens", 0))


def _payload(messages: list[dict], cache: bool) -> list[dict]:
    """Render messages; when caching, mark the last block with cache_control so
    Anthropic stores the conversation prefix (re-read at ~0.1x cost next turn)."""
    if not cache:
        return messages
    out = []
    for i, m in enumerate(messages):
        block: dict[str, Any] = {"type": "text", "text": m["content"]}
        if i == len(messages) - 1:
            block["cache_control"] = {"type": "ephemeral"}
        out.append({"role": m["role"], "content": [block]})
    return out


def call_claude(messages: list[dict], *, model: str = AGENT_MODEL, system: str = SYSTEM_PROMPT,
                cache: bool = False, max_tokens: int | None = None):
    """Sync Messages API call → (text, usage). Retries transient failures."""
    max_tokens = max_tokens or settings.max_answer_tokens
    payload = _payload(messages, cache)
    last_err = None
    for attempt in range(7):
        try:
            resp = sync_client.messages.create(
                model=model, max_tokens=max_tokens, system=system, messages=payload,
            )
            return text_of(resp), resp.usage
        except anthropic.APIStatusError as err:
            status = getattr(err, "status_code", 0) or 0
            if status in (408, 409, 429) or status >= 500:
                last_err = err
                time.sleep(min(3 * 2 ** attempt + random.random(), 60))
                continue
            raise
        except anthropic.APIConnectionError as err:
            last_err = err
            time.sleep(min(3 * 2 ** attempt + random.random(), 60))
    raise last_err
