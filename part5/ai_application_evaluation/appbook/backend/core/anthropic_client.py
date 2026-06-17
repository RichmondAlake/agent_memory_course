"""Shared Anthropic client + helpers used by Form Factors 1-3.

Mirrors the notebook's ``text_of`` helper and adds a small ``structured_json``
wrapper around the Messages API's ``output_config`` JSON-schema feature, with a
graceful fall back to plain-text JSON parsing if the schema call is rejected.
"""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from backend.config import settings

# Use a placeholder when the key is unset so the app still imports and serves the
# frontend in a fresh Codespace. API calls then fail with a clear 401 instead of
# the whole server failing to start at import time.
_api_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
client = anthropic.Anthropic(api_key=_api_key)
async_client = anthropic.AsyncAnthropic(api_key=_api_key)
MODEL = settings.model
MAX_TOKENS = settings.max_tokens


def text_of(response) -> str:
    """Concatenate the text blocks of a Claude response into a single string."""
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _loads_loose(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, tolerating ```json fences / prose."""
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


def structured_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 512,
    model: str | None = None,
) -> dict[str, Any]:
    """Return validated JSON from Claude using output_config, with a text fallback.
    `model` overrides the default (e.g. to run the system under test on a weaker model);
    the LLM-as-judge leaves it None so it always grades with the strong default model."""
    use_model = model or MODEL
    try:
        response = client.messages.create(
            model=use_model,
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
            model=use_model,
            max_tokens=max_tokens,
            system=guided,
            messages=[{"role": "user", "content": user}],
        )
        return _loads_loose(text_of(response))
