"""Shared runtime for the agent form factors (4 and 5).

Wraps ``claude_agent_sdk.query`` and turns its message stream into small JSON events for the browser:

    {"type": "session",     "session_id": ...}                 the run's session (resumable)
    {"type": "text",        "text": ...}
    {"type": "tool_use",    "id": ..., "name": ..., "input": {...}}
    {"type": "tool_result", "id": ..., "text": ..., "is_error": bool}
    {"type": "hook",        "tool": ..., "decision": "allow" | "deny", "path": ..., "reason": ...}
    {"type": "result",      "session_id": ..., "subtype": ..., "cost_usd": ..., "num_turns": ..., "duration_ms": ...}
    {"type": "error",       "message": ...}

Hooks can push their own events into ``RunContext.events``; they are flushed between SDK messages.
"""
from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from backend.config import settings

AGENT_AVAILABLE = settings.claude_cli_path is not None

# SDK plumbing the CLI uses to load MCP tool schemas; hidden from the trajectory.
_HIDDEN_TOOLS = {"ToolSearch"}


class RunContext:
    """Per-run scratch space shared by the stream and the hooks."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []


def agent_env() -> dict[str, str]:
    """Environment for the spawned `claude` CLI: ours, the API key, and this Python first on PATH, so `python`
    inside the sandbox is the interpreter that has matplotlib and pandas."""
    env = {k: v for k, v in os.environ.items() if v is not None}
    if settings.anthropic_api_key:
        env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    python_bin = str(Path(sys.executable).parent)
    env["PATH"] = os.pathsep.join([python_bin, env.get("PATH", "")])
    env.setdefault("MPLBACKEND", "Agg")
    env.setdefault("MPLCONFIGDIR", str(settings.sandbox_dir / ".mplconfig"))  # writable inside the OS sandbox
    return env


def cli_stderr(line: str) -> None:
    """Forward the bundled CLI's stderr, minus its notice that claude.ai connectors are off under an API key."""
    if "connectors are disabled" not in line:
        print(line, file=sys.stderr)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join((item.get("text", "") or "") if isinstance(item, dict) else str(getattr(item, "text", item))
                       for item in value)
    return str(value)


async def run_agent_events(prompt: str, options, context: RunContext | None = None) -> AsyncIterator[dict[str, Any]]:
    """Run one agent query and yield normalized events. Never raises: errors are events."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, UserMessage, query

    context = context or RunContext()
    announced = False
    result_seen = False
    try:
        async for message in query(prompt=prompt, options=options):
            while context.events:
                yield context.events.pop(0)
            session_id = getattr(message, "session_id", None) or (
                message.data.get("session_id") if isinstance(message, SystemMessage) and isinstance(message.data, dict) else None)
            if session_id and not announced:
                announced = True
                yield {"type": "session", "session_id": session_id}
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if getattr(block, "text", None) is not None and not hasattr(block, "name"):
                        if block.text.strip():
                            yield {"type": "text", "text": block.text}
                    elif hasattr(block, "name") and hasattr(block, "input"):
                        if block.name in _HIDDEN_TOOLS:
                            continue
                        yield {"type": "tool_use", "id": getattr(block, "id", None), "name": block.name,
                               "input": dict(block.input) if block.input else {}}
            elif isinstance(message, UserMessage):
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "tool_use_id"):
                            yield {"type": "tool_result", "id": block.tool_use_id,
                                   "text": _stringify(getattr(block, "content", ""))[:6000],
                                   "is_error": bool(getattr(block, "is_error", False))}
            elif isinstance(message, ResultMessage):
                result_seen = True
                yield {"type": "result", "session_id": message.session_id, "subtype": message.subtype,
                       "cost_usd": message.total_cost_usd, "num_turns": message.num_turns,
                       "duration_ms": message.duration_ms}
        while context.events:
            yield context.events.pop(0)
    except Exception as exc:  # noqa: BLE001 — a single-shot query raises after an error result
        while context.events:
            yield context.events.pop(0)
        if not result_seen:
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
