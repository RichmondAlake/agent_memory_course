"""Context-window helpers — what each agent is actually holding in its context.

A ``window`` is a list of typed blocks (system / memory / user / assistant /
state / web) plus a token budget. We report a MEASURED token count from
Anthropic's ``messages.count_tokens`` endpoint when we have the real API payload
(accurate, includes system + tools), and fall back to a ~4-chars/token estimate
for blocks that never become an API call (e.g. a deterministic workflow's
working state). The UI labels which is which.
"""
from __future__ import annotations

from typing import Any

from backend.config import settings

CAPACITY = settings.context_capacity


def approx_tokens(text: str | None) -> int:
    return max(1, round(len(text or "") / 4))


def block(role: str, label: str, content: str) -> dict[str, Any]:
    return {"role": role, "label": label, "content": content, "tokens": approx_tokens(content)}


def count_tokens(system: str | None, messages: list[dict[str, Any]], tools=None) -> int | None:
    """Real input-token count for an actual Claude payload (free endpoint).

    Returns None on any failure so callers fall back to the estimate.
    """
    from backend.core.anthropic_client import MODEL, client
    try:
        kwargs: dict[str, Any] = {"model": MODEL, "messages": messages}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        return int(client.messages.count_tokens(**kwargs).input_tokens)
    except Exception:  # noqa: BLE001
        return None


def window(blocks: list[dict[str, Any]], *, measured: int | None = None, note: str | None = None) -> dict[str, Any]:
    est = sum(b["tokens"] for b in blocks)
    used = measured if measured is not None else est
    return {
        "capacity": CAPACITY,
        "used": used,
        "free": max(0, CAPACITY - used),
        "measured": measured is not None,
        "blocks": blocks,
        "note": note,
    }
