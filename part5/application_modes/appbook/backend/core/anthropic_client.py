"""Shared Anthropic client + helpers used by all three modes."""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from backend.config import settings

# Placeholder when the key is unset so the app still imports and serves the
# frontend. API calls then fail with a clear 401 instead of failing at import.
_api_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
client = anthropic.Anthropic(api_key=_api_key)
async_client = anthropic.AsyncAnthropic(api_key=_api_key)
MODEL = settings.model
MAX_TOKENS = settings.max_tokens


def text_of(response) -> str:
    """Concatenate the text blocks of a Claude response into a single string."""
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text")


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _loads_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^json\s*", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJ.search(text)
        if match:
            return json.loads(match.group(0))
        raise


def structured_json(*, system: str, user: str, schema: dict[str, Any], max_tokens: int = 512) -> dict[str, Any]:
    """Return validated JSON from Claude using output_config, with a text fallback."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        return _loads_loose(text_of(response))
    except Exception:  # noqa: BLE001 — fall back to instruction-guided JSON
        guided = (
            f"{system}\n\nRespond with ONLY a JSON object matching this schema "
            f"(no prose, no code fences):\n{json.dumps(schema)}"
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=guided,
            messages=[{"role": "user", "content": user}],
        )
        return _loads_loose(text_of(response))


def summarize(text: str, *, instruction: str, max_tokens: int = 320) -> str:
    """One-shot summarize helper (used by the in-memory memory fallback)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=instruction,
        messages=[{"role": "user", "content": text}],
    )
    return text_of(response)
