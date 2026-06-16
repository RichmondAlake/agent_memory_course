"""Shared runtime for the agent form factors (4 & 5).

Wraps ``claude_agent_sdk.query`` and normalizes its message stream into small,
JSON-serializable events that the routers relay to the browser over SSE:

    {"type": "text",        "text": ...}
    {"type": "tool_use",    "name": ..., "input": {...}}
    {"type": "tool_result", "text": ...}
    {"type": "result",      "cost_usd": ..., "num_turns": ..., "duration_ms": ...}
    {"type": "error",       "message": ...}
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from backend.config import settings

AGENT_AVAILABLE = settings.claude_cli_path is not None

# Built-in plumbing the agent CLI uses to discover MCP tools — hidden from the
# trajectory so the demo shows only domain-meaningful tool calls.
_HIDDEN_TOOLS = {"ToolSearch"}


def agent_env() -> dict[str, str]:
    """Environment for the spawned `claude` CLI — inherits ours, ensures the key."""
    env = {k: v for k, v in os.environ.items() if v is not None}
    if settings.anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    return env


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(item.get("text", "") or "")
            else:
                parts.append(str(getattr(item, "text", item)))
        return "".join(parts)
    return str(value)


async def run_agent_events(prompt: str, options) -> AsyncIterator[dict[str, Any]]:
    """Run an agent query and yield normalized events. Never raises — errors are events."""
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        UserMessage,
        query,
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text") and getattr(block, "text", None) is not None:
                        yield {"type": "text", "text": block.text}
                    elif hasattr(block, "name") and hasattr(block, "input"):
                        if block.name in _HIDDEN_TOOLS:
                            continue
                        yield {
                            "type": "tool_use",
                            "name": block.name,
                            "input": dict(block.input) if block.input else {},
                        }
            elif isinstance(message, UserMessage):
                # Tool results come back to the model as a UserMessage of tool_result blocks.
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        if getattr(block, "type", None) == "tool_result" or hasattr(block, "tool_use_id"):
                            text = _stringify(getattr(block, "content", ""))
                            if text.strip():
                                yield {"type": "tool_result", "text": text}
            elif isinstance(message, ResultMessage):
                yield {
                    "type": "result",
                    "cost_usd": getattr(message, "total_cost_usd", None),
                    "num_turns": getattr(message, "num_turns", None),
                    "duration_ms": getattr(message, "duration_ms", None),
                }
    except Exception as exc:  # noqa: BLE001 — surface as a stream event, not a 500
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
