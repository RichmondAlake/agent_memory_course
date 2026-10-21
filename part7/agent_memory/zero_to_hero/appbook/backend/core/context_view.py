"""Context windows: what each agent sent to the model on every call of a turn, section by section.

- **Scratch**: the request ``scratch.chat`` sent: its instructions (the base instruction, then one block per
  memory layer), the tool schemas, then the input (history, the user's message, tool calls and results).
- **MemoRizz**: the context snapshot MemoRizz stores for each model call when ``capture_context_snapshots`` is
  on: the messages after prompt fitting and the tool schemas. Its per-turn ``<memorizz:context>`` block is split
  at the headers MemoRizz writes (evidence pack items, entity facts, summaries, the tool-output digest).

Sections keep the order the model reads them: the system text, then the tool schemas, then the messages.
OpenAI's prompt cache reuses a prefix of that order, so each call also keeps OpenAI's own counts (input,
prompt-cached, output). Section token counts are tiktoken estimates.
"""
from __future__ import annotations

import json
import re
from typing import Any

from backend.core import scratch

KINDS = {
    "system": "Instructions",
    "tools": "Tool schemas",
    "memory": "Memory",
    "context": "Request context",
    "history": "Conversation history",
    "query": "This turn's message",
    "tool_io": "Tool calls and results",
}
# MemoRizz's per-turn block: each section starts with one of these headers.
VOLATILE_HEADERS = {
    "MEMORIZZ EVIDENCE PACK": "Evidence pack",
    "Relevant memories retrieved for this turn": "Relevant memories",
    "Entity memory facts:": "Entity memory facts",
    "Personalization context for this turn:": "Personalization",
    "Earlier in this conversation (compacted summary):": "Compacted summary",
    "Compressed conversation summaries available via": "Summary references",
    "Recent tool outputs in this thread": "Recent tool outputs (tool-log digest)",
    "REQUEST CONTEXT (ephemeral": "Request context",
}
_HEADER = re.compile("(?:^|(?<=\n\n))(?:" + "|".join(re.escape(h) for h in VOLATILE_HEADERS) + ")")
_EVIDENCE_ITEM = re.compile(r"\n\n(?=\[\d+\] )")


def _text(value: Any) -> tuple[str, str]:
    """(text to show, text to count): JSON is shown indented and counted compact, closer to what the model reads."""
    if value is None:
        return "", ""
    if isinstance(value, str):
        return value, value
    if isinstance(value, list) and value and all(isinstance(part, dict) and "text" in part for part in value):
        text = "\n".join(str(part["text"]) for part in value)          # content parts
        return text, text
    return (json.dumps(value, indent=2, ensure_ascii=False, default=str),
            json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")))


def section(kind: str, label: str, value: Any, **extra: Any) -> dict:
    text, counted = _text(value)
    return {"kind": kind, "label": label, "tokens": scratch.tokens(counted), "text": text, **extra}


def _tools(tools: list) -> dict:
    names = [str(t.get("name") or (t.get("function") or {}).get("name") or "?") for t in tools]
    return section("tools", f"Tool schemas · {len(tools)}", tools, items=names)


def _history(messages: list) -> dict:
    entries = [{"role": str(m.get("role")), "text": _text(m.get("content"))[0]} for m in messages]
    text = "\n\n".join(f"{entry['role']}: {entry['text']}" for entry in entries)
    return section("history", f"Conversation history · {len(entries)} messages", text, messages=entries)


def _call(n: int, stage: str, sections: list[dict], usage: dict) -> dict:
    if any(s["kind"] == "tool_io" for s in sections):
        stage += " · after tool results"
    return {"n": n, "stage": stage, "input_tokens": usage.get("input_tokens"),
            "cached_tokens": usage.get("cached_tokens"), "output_tokens": usage.get("output_tokens"),
            "estimated_tokens": sum(s["tokens"] for s in sections), "sections": sections}


def _last_user(messages: list) -> int | None:
    return max((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "user"), default=None)


# ── scratch ──────────────────────────────────────────────────────────────────
def _scratch_sections(request: dict) -> list[dict]:
    head, *blocks = (request.get("instructions") or "").split("\n\n## ")
    sections = [section("system", "Instruction", head)]
    for block in blocks:                                  # ScratchMemo.instructions: "## label\ntext" per block
        label, _, body = block.partition("\n")
        sections.append(section("context" if label.startswith("Request context") else "memory", label, body))
    if request.get("tools"):
        sections.append(_tools(request["tools"]))
    items = request.get("input")
    if isinstance(items, str):
        return sections + [section("query", "Input", items)]
    items = items or []
    query = _last_user(items)
    if query is None:
        return sections + [section("tool_io", "Input", items)]
    if query:
        sections.append(_history(items[:query]))
    sections.append(section("query", "User message (this turn)", items[query].get("content")))
    names: dict[str, str] = {}
    for item in items[query + 1:]:                        # tool_loop appends the model's calls and their results
        kind = item.get("type")
        if kind == "function_call":
            names[str(item.get("call_id"))] = str(item.get("name"))
            sections.append(section("tool_io", f"Tool call · {item.get('name')}", item.get("arguments")))
        elif kind == "function_call_output":
            sections.append(section("tool_io", f"Tool result · {names.get(str(item.get('call_id')), 'tool')}",
                                    item.get("output")))
        else:
            sections.append(section("tool_io", str(item.get("role") or kind or "item"), item.get("content", item)))
    return sections


def scratch_calls(requests: list[dict]) -> list[dict]:
    """Every model call of a scratch turn: the answer loop's steps, and calls a memory layer made itself."""
    calls, step = [], 0
    for n, item in enumerate(requests, 1):
        if item.get("layer"):
            stage = item["layer"]
        else:
            step += 1
            stage = f"step {step}"
        calls.append(_call(n, stage, _scratch_sections(item["request"]), item))
    return calls


# ── MemoRizz ─────────────────────────────────────────────────────────────────
def _volatile(content: str) -> list[dict]:
    """The final user message: the <memorizz:context> block split at its headers, then the user's message."""
    match = re.match(r"\s*<memorizz:context>\n(.*?)\n</memorizz:context>\n\n(.*)\Z", content, re.S)
    if not match:
        return [section("query", "User message (this turn)", content)]
    block, query = match.groups()
    starts = [m.start() for m in _HEADER.finditer(block)]
    sections, first = [], starts[0] if starts else len(block)
    if block[:first].strip():                            # user-authority skills come before the headed sections
        sections.append(section("memory", "Learned skills", block[:first].strip()))
    for begin, end in zip(starts, starts[1:] + [len(block)]):
        chunk = block[begin:end].strip()
        label = next(name for header, name in VOLATILE_HEADERS.items() if chunk.startswith(header))
        if label == "Evidence pack":
            head, *items = _EVIDENCE_ITEM.split(chunk)
            sections.append(section("memory", "Evidence pack · notice", head))
            for item in items:
                number, _, source = item.split("\n", 1)[0].partition(" ")
                sections.append(section("memory", f"Evidence {number} · {source.split(':', 1)[0]}", item))
        else:
            sections.append(section("context" if label == "Request context" else "memory", label, chunk))
    return sections + [section("query", "User message (this turn)", query)]


def _memorizz_sections(snapshot: dict) -> list[dict]:
    messages, tools = snapshot.get("messages") or [], snapshot.get("tools") or []
    sections, lead = [], 0
    while lead < len(messages) and messages[lead].get("role") == "system":
        sections.append(section("system", "System prompt · framework, instruction, persona",
                                messages[lead].get("content")))
        lead += 1
    if tools:
        sections.append(_tools(tools))
    query = _last_user(messages)
    end = len(messages) if query is None else query
    history: list = []
    for message in messages[lead:end]:
        if message.get("role") == "developer":           # reviewed skills with developer authority
            if history:
                sections.append(_history(history))
                history = []
            sections.append(section("memory", "Approved skills (developer message)", message.get("content")))
        else:
            history.append(message)
    if history:
        sections.append(_history(history))
    if query is None:
        return sections
    sections += _volatile(_text(messages[query].get("content"))[0])
    names: dict[str, str] = {}
    for message in messages[query + 1:]:                 # the tool loop: the model's calls and their results
        if message.get("role") == "tool":
            name = message.get("name") or names.get(str(message.get("tool_call_id")), "tool")
            sections.append(section("tool_io", f"Tool result · {name}", message.get("content")))
            continue
        if message.get("content"):
            sections.append(section("tool_io", str(message.get("role")), message.get("content")))
        for tool_call in message.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            names[str(tool_call.get("id"))] = str(function.get("name"))
            sections.append(section("tool_io", f"Tool call · {function.get('name')}", function.get("arguments")))
    return sections


def memorizz_calls(snapshots: list[tuple[dict, dict]]) -> list[dict]:
    """Every model call of a MemoRizz turn, from its context snapshot and the tokens its trace reported."""
    calls = []
    for n, (snapshot, usage) in enumerate(snapshots, 1):
        stage = usage.get("stage") or snapshot.get("stage")
        iteration = usage.get("iteration") or snapshot.get("iteration") or n
        label = f"step {iteration}" if stage in (None, "agent_run") else f"{stage} · step {iteration}"
        sections = _memorizz_sections(snapshot) if snapshot else [
            section("system", "No context snapshot was stored for this call", "")]
        calls.append(_call(n, label, sections, usage))
    return calls


# ── one turn ─────────────────────────────────────────────────────────────────
def summary(record: dict) -> dict:
    """A turn without its sections, for the turn picker."""
    side = lambda calls: {"calls": len(calls), "input_tokens": sum(c["input_tokens"] or 0 for c in calls),  # noqa: E731
                          "cached_tokens": sum(c["cached_tokens"] or 0 for c in calls)}
    return {key: record[key] for key in ("turn", "part", "thread", "question", "test")} | {
        "scratch": side(record["scratch"]["calls"]), "memorizz": side(record["memorizz"]["calls"])}


def turn(*, turn: int, part: int, thread: str, question: str, test: str | None, scratch: list[dict],
         memorizz: list[dict], memorizz_title: str = "MemoRizz") -> dict:
    side = lambda title, calls: {"title": title, "calls": calls,  # noqa: E731
                                 "note": None if calls else "No model call: the answer came from the semantic cache."}
    return {"turn": turn, "part": part, "thread": thread, "question": question, "test": test, "kinds": KINDS,
            "scratch": side("Scratch", scratch), "memorizz": side(memorizz_title, memorizz)}
