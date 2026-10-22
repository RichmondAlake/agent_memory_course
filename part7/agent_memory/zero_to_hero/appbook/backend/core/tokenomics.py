"""Tokenomics: latency by phase, tokens and list-price cost for every turn of every agent.

Scratch Memo and MemoRizz Memo answer every measured turn; the memory workload adds a naive
baseline (``scratch.NaiveMemo``) that appends the whole thread to each request and nothing else.
Every agent is measured the same way and priced with the same rate card
(MemoRizz's ``DEFAULT_PRICING``, OpenAI list prices):

- **model**: time inside model calls, and their input, prompt-cached and output tokens;
- **memory**: memory reads and writes (SQL, embeddings, the Jev router) outside model calls;
- **tools**: time inside tool executions;
- **other**: everything else in the turn (orchestration, persistence).

The scratch and naive agents are metered by hooks in ``scratch.chat``, ``scratch.tool_loop`` and
``ScratchMemo.run``. The MemoRizz agent reports the same phases through its own trace
events (``model_result``, ``memory_retrieval``, ``tool_result``) and ``get_last_run_usage()``.
Embedding tokens are excluded on both sides.
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Iterator

from memorizz.observability.pricing import DEFAULT_PRICING

from backend.config import settings

_local = threading.local()

# Golden questions: each reference uses only what both agents are given by the setup of the Parts
# (persona, runbook, platform tools, the authored rebuild skill), so it does not depend on chat history.
CACHE_POLICY = {"cache_domain": "runbook", "data_version": "2026-10-17"}
GOLDEN = {
    "Who are you, and how do you answer?":
        "Memo, an engineering copilot for platform engineers; answers concisely, in numbered steps.",
    "When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?":
        "Only in the Tuesday maintenance window, 02:00-04:00 UTC; a change ticket with the ORAMNT prefix, "
        "approved by the on-call lead.",
    "What ticket prefix do Oracle maintenance changes need?": "The ORAMNT prefix.",
    "Which ticket prefix is required for Oracle maintenance changes?": "The ORAMNT prefix.",
    "Check the health of docs_hnsw and how much of the vector pool is free.":
        "docs_hnsw is ready with 30 checks passed; the vector memory pool has 27.5 percent free.",
    "Who owns the embedding-worker service?": "Lin.",
    "Plan the retrieval-api index rebuild for me.":
        "Rebuild only in the Tuesday 02:00-04:00 UTC window; an ORAMNT change ticket with on-call lead approval; "
        "run index_health and confirm at least 20 percent free vector memory pool; take a schema snapshot; after "
        "the rebuild, check golden-set recall is at least 0.95; keep the old index for 24 hours.",
    "Who do I page if the rebuild fails?":
        "#platform-oncall first; if nobody answers within 15 minutes, the database team.",
}
# The memory workload: 30 turns in a fresh memory scope at the full stack. Turns where Ada tells Memo something
# are unscored; every other turn carries the reference the LLM judge grades against. Each scored turn tests one
# way memory can fail, and later turns refer back to earlier ones.
TESTS = {
    "grounding": "Answered from what both agents are given: persona, runbook, tools, the rebuild skill.",
    "recall": "A fact Ada told Memo earlier in the conversation.",
    "update": "A fact that changed later: only the new value is correct.",
    "back-reference": "Refers to an earlier question or answer.",
    "tool recall": "A result from an earlier tool call.",
    "cache": "A paraphrase of an earlier cacheable question.",
    "abstention": "Never told, or a false premise: inventing an answer is wrong.",
    "preference": "A standing instruction Ada gave earlier.",
    "cross-thread": "Asked in a new thread, so only long-term memory carries it over.",
    "told": "Ada tells Memo something to remember (unscored).",
}
MAIN_THREAD, NEW_THREAD = "tokenomics", "standup"
COMPACT_AFTER = 20      # after this turn both memory agents summarise the main thread, keeping its 4 newest messages
AGENTS = ("scratch", "memorizz", "naive")


def _turn(question: str, test: str, reference: str | None = None, *, thread: str = MAIN_THREAD,
          context: dict | None = None) -> dict:
    return {"question": question, "test": test, "reference": reference, "thread": thread, "context": context}


WORKLOAD = [
    _turn("Who are you, and how do you answer?", "grounding", GOLDEN["Who are you, and how do you answer?"]),
    _turn("Some context before we start: I'm Ada, I lead the migration of our RAG stack from Pinecone to Oracle "
          "AI Database, and the cutover is planned for 14 November.", "told"),
    _turn("When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?", "grounding",
          GOLDEN["When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?"]),
    _turn("Two teammates you should know: Priya is our DBA, and Kemi owns the evaluation harness.", "told"),
    _turn("Check the health of docs_hnsw and how much of the vector pool is free.", "grounding",
          GOLDEN["Check the health of docs_hnsw and how much of the vector pool is free."]),
    _turn("Which vector store are we migrating away from, and when is the cutover?", "recall",
          "Pinecone; the cutover is planned for 14 November."),
    _turn("What ticket prefix do Oracle maintenance changes need?", "grounding", "The ORAMNT prefix.",
          context=CACHE_POLICY),
    _turn("Without running the check again: how much of the vector pool was free when you looked?", "tool recall",
          "27.5 percent free."),
    _turn("Which ticket prefix is required for Oracle maintenance changes?", "cache", "The ORAMNT prefix.",
          context=CACHE_POLICY),
    _turn("Who owns the embedding-worker service?", "grounding", "Lin."),
    _turn("Change of plan: Priya is on leave until 3 November, so Tomasz covers database questions until then.",
          "told"),
    _turn("I have a database question. Who should I ask right now?", "update",
          "Tomasz."),
    _turn("Plan the retrieval-api index rebuild for me.", "grounding",
          GOLDEN["Plan the retrieval-api index rebuild for me."]),
    _turn("In that plan, what recall do we need after the rebuild, and how long do we keep the old index?",
          "back-reference", "Golden-set recall of at least 0.95; keep the old index for 24 hours."),
    _turn("Who do I page if the rebuild fails?", "grounding", GOLDEN["Who do I page if the rebuild fails?"]),
    _turn("Update: the cutover has moved from 14 November to 21 November.", "told"),
    _turn("Rebuilds are fine on Friday afternoons, right?", "abstention",
          "No: rebuilds run only in the Tuesday 02:00-04:00 UTC maintenance window."),
    _turn("What's the name of my manager?", "abstention",
          "Says it does not know or was never told who Ada's manager is; it must not call anyone her manager."),
    _turn("From now on, end every answer with a one-line TL;DR.", "told"),
    _turn("When is the cutover now?", "update",
          "21 November. Giving 14 November as the current date is wrong."),
    _turn("What was the very first thing I asked you today?", "back-reference",
          "\"Who are you, and how do you answer?\", in these or other words."),
    _turn("List the teammates I've told you about and what each one does.", "recall",
          "Priya: the DBA, on leave until 3 November; Kemi: owns the evaluation harness; Tomasz: covers database "
          "questions while Priya is away. Also naming a service owner from the tools, such as Lin, is fine."),
    _turn("Earlier you checked docs_hnsw. What was its status, and how many checks passed?", "tool recall",
          "Ready, with 30 checks passed."),
    _turn("What version of retrieval-api is deployed, and when was it deployed?", "grounding",
          "Version 2026.10.3, deployed on 14 October 2026 at 09:12 UTC."),
    _turn("Who owns the ingestion-pipeline service?", "preference",
          "Grace, and the answer ends with a one-line TL;DR."),
    _turn("New chat. What's our cutover date, and which vector store are we leaving?", "cross-thread",
          "21 November; Pinecone.", thread=NEW_THREAD),
    _turn("Who covers database questions while Priya is away, and until when?", "cross-thread",
          "Tomasz, until 3 November.", thread=NEW_THREAD),
    _turn("What did we decide about the Redis cache last week?", "abstention",
          "There is no record of any Redis cache decision; it says so instead of inventing one.", thread=NEW_THREAD),
    _turn("Remind me what Kemi does.", "cross-thread", "Kemi owns the evaluation harness.", thread=NEW_THREAD),
    _turn("Summarise where the migration stands: the cutover date, who takes database questions right now, and "
          "the rebuild rules.", "recall",
          "Cutover on 21 November; Tomasz takes database questions while Priya is on leave until 3 November; "
          "rebuilds only in the Tuesday 02:00-04:00 UTC window, with an ORAMNT change ticket approved by the "
          "on-call lead."),
]


def reference_for(question: str) -> str | None:
    """The golden reference for a question, matched on its words (case and punctuation ignored)."""
    key = " ".join(question.lower().replace("?", " ").replace(".", " ").split())
    for golden, reference in GOLDEN.items():
        if " ".join(golden.lower().replace("?", " ").replace(".", " ").split()) == key:
            return reference
    return None


class Meter:
    """Accumulates one scratch turn's model, tool and memory work."""

    def __init__(self) -> None:
        self.model_ms = self.model_ms_in_layers = self.tools_ms = self.layer_ms = 0.0
        self.calls = self.input_tokens = self.cached_tokens = self.output_tokens = 0
        self.in_layer = False
        self.layer: str | None = None
        self.requests: list[dict] = []     # what each model call sent, for the Context window page


def current() -> Meter | None:
    return getattr(_local, "meter", None)


@contextmanager
def metering() -> Iterator[Meter]:
    meter = Meter()
    _local.meter = meter
    try:
        yield meter
    finally:
        _local.meter = None


def _plain(value: Any) -> Any:
    """A JSON copy of a request, so later changes to the message list do not alter what was sent."""
    return json.loads(json.dumps(value, default=lambda item: item.model_dump(exclude_none=True)
                                 if hasattr(item, "model_dump") else str(item)))


def record_model(response: Any, elapsed_ms: float, request: dict | None = None) -> None:
    meter = current()
    if meter is None:
        return
    usage = response.usage
    details = getattr(usage, "input_tokens_details", None)
    inputs, outputs = int(usage.input_tokens or 0), int(usage.output_tokens or 0)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    meter.calls += 1
    meter.model_ms += elapsed_ms
    if meter.in_layer:
        meter.model_ms_in_layers += elapsed_ms
    meter.input_tokens += inputs
    meter.cached_tokens += cached
    meter.output_tokens += outputs
    if request is not None:
        meter.requests.append({"request": _plain(request), "layer": meter.layer if meter.in_layer else None,
                               "input_tokens": inputs, "cached_tokens": cached, "output_tokens": outputs})


def record_tool(elapsed_ms: float) -> None:
    meter = current()
    if meter is not None:
        meter.tools_ms += elapsed_ms


@contextmanager
def layer_work(label: str | None = None) -> Iterator[None]:
    """Time a layer's read or write; model calls inside it are counted as model time."""
    meter = current()
    if meter is None:
        yield
        return
    meter.in_layer, meter.layer, started = True, label, time.perf_counter()
    try:
        yield
    finally:
        meter.layer_ms += (time.perf_counter() - started) * 1000
        meter.in_layer, meter.layer = False, None


def price(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> tuple[float | None, str]:
    if settings.open:
        return 0.0, f"Open model on this machine ({model} through Ollama): no API cost"
    quote = DEFAULT_PRICING.quote({"provider": "openai", "model": model, "input_tokens": input_tokens,
                                   "cached_tokens": cached_tokens, "output_tokens": output_tokens})
    if quote.get("cost_status") != "calculated":
        return None, quote.get("cost_reason") or "No rate card"
    return float(Decimal(quote["cost_usd"])), f"OpenAI list price ({quote.get('pricing_version')})"


def _record(*, turn: int, part: int, thread: str, question: str, agent: str, model: str, total_ms: float,
            model_ms: float, memory_ms: float, tools_ms: float, calls: int, input_tokens: int,
            cached_tokens: int, output_tokens: int, cost: float | None, cost_note: str, tool_calls: list,
            cache_hit: bool, test: str | None = None) -> dict:
    model_ms, memory_ms, tools_ms = (max(0.0, value) for value in (model_ms, memory_ms, tools_ms))
    return {
        "turn": turn, "run_id": f"t{turn}", "part": part, "thread": thread, "question": question,
        "test": test, "agent": agent, "model": model,
        "latency": {"total_ms": round(total_ms, 1), "model_ms": round(model_ms, 1),
                    "memory_ms": round(memory_ms, 1), "tools_ms": round(tools_ms, 1),
                    "other_ms": round(max(0.0, total_ms - model_ms - memory_ms - tools_ms), 1)},
        "usage": {"model_calls": calls, "input_tokens": input_tokens, "cached_input_tokens": cached_tokens,
                  "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens},
        "cost_usd": None if cost is None else round(cost, 8), "cost_note": cost_note,
        "tool_calls": list(tool_calls), "cache_hit": bool(cache_hit),
        "accuracy": {"score": None, "verdict": "unscored", "reason": "Not a golden question.", "missing": [],
                     "method": None},
    }


def scratch_record(meter: Meter, *, turn: int, part: int, thread: str, question: str, model: str,
                   total_ms: float, tool_calls: list, cache_hit: bool, test: str | None = None,
                   agent: str = "scratch") -> dict:
    """A metered turn of an agent built on ``scratch.chat``: scratch Memo, or the naive baseline."""
    cost, note = price(model, meter.input_tokens, meter.cached_tokens, meter.output_tokens)
    return _record(turn=turn, part=part, thread=thread, question=question, agent=agent, model=model,
                   total_ms=total_ms, model_ms=meter.model_ms,
                   memory_ms=meter.layer_ms - meter.model_ms_in_layers, tools_ms=meter.tools_ms,
                   calls=meter.calls, input_tokens=meter.input_tokens, cached_tokens=meter.cached_tokens,
                   output_tokens=meter.output_tokens, cost=cost, cost_note=note, tool_calls=tool_calls,
                   cache_hit=cache_hit, test=test)


def _union(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for begin, finish in sorted(intervals):
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], finish)
        else:
            merged.append([begin, finish])
    return [(a, b) for a, b in merged]


def _minus(spans: list[tuple[float, float]], taken: list[tuple[float, float]]) -> float:
    """Length of ``spans`` not already covered by ``taken`` (both merged interval lists)."""
    total = 0.0
    for begin, finish in spans:
        length = finish - begin
        for a, b in taken:
            length -= max(0.0, min(finish, b) - max(begin, a))
        total += max(0.0, length)
    return total


class TraceCollector:
    """Collects a MemoRizz run's phase timings from its stream events.

    MemoRizz reports each model call, memory read and tool call with its duration when it
    finishes. Some reads run concurrently and some happen inside a tool (``knowledge_base_lookup``),
    so durations cannot simply be added. Each event becomes a wall-clock interval, and every
    millisecond of the turn is attributed once, in priority order: model, then tools, then memory.
    """

    PHASES = {"model_result": "model", "tool_result": "tools", "memory_retrieval": "memory"}

    def __init__(self) -> None:
        self.intervals: dict[str, list[tuple[float, float]]] = {"model": [], "tools": [], "memory": []}
        self.window = (time.perf_counter(), None)
        self.calls: dict[str, dict] = {}       # model span id → its context snapshot id and its tokens

    def __call__(self, event: Any = None, *args: Any, **kwargs: Any) -> None:
        if not isinstance(event, dict) or event.get("type") != "trace":
            return
        kind = event.get("trace_kind")
        if kind in ("context_snapshot", "model_result") and event.get("span_id"):
            call = self.calls.setdefault(str(event["span_id"]), {})
            if kind == "context_snapshot":
                call["snapshot_id"] = event.get("snapshot_id")
            else:
                call.update({key: event.get(key) for key in ("stage", "iteration", "input_tokens", "cached_tokens",
                                                             "output_tokens")})
        phase = self.PHASES.get(kind)
        if phase:
            finish = time.perf_counter()
            self.intervals[phase].append((finish - float(event.get("duration_ms") or 0) / 1000, finish))

    def stop(self) -> None:
        self.window = (self.window[0], time.perf_counter())

    def phases(self) -> dict[str, float]:
        begin, finish = self.window[0], self.window[1] or time.perf_counter()
        clip = lambda spans: _union([(max(a, begin), min(b, finish)) for a, b in spans if b > begin and a < finish])
        model, tools, memory = (clip(self.intervals[name]) for name in ("model", "tools", "memory"))
        taken = _union(model + tools)
        return {"model_ms": _minus(model, []) * 1000, "tools_ms": _minus(tools, model) * 1000,
                "memory_ms": _minus(memory, taken) * 1000}


def memorizz_record(collector: TraceCollector, usage: dict, *, turn: int, part: int, thread: str,
                    question: str, model: str, total_ms: float, tool_calls: list, cache_hit: bool,
                    test: str | None = None) -> dict:
    inputs, cached, outputs = (int(usage.get(key) or 0) for key in ("input_tokens", "cached_tokens", "output_tokens"))
    cost = usage.get("cost_usd")
    note = "MemoRizz usage: OpenAI list price"
    if cost is None:
        cost, note = price(model, inputs, cached, outputs) if usage else (0.0, "No model call")
    phases = collector.phases()
    return _record(turn=turn, part=part, thread=thread, question=question, agent="memorizz", model=model,
                   total_ms=total_ms, model_ms=phases["model_ms"], memory_ms=phases["memory_ms"],
                   tools_ms=phases["tools_ms"], calls=int(usage.get("calls") or 0), input_tokens=inputs,
                   cached_tokens=cached, output_tokens=outputs, cost=float(cost), cost_note=note,
                   tool_calls=tool_calls, cache_hit=cache_hit, test=test)


def raw_record(response: Any, elapsed_ms: float, *, turn: int, part: int, thread: str, question: str,
               model: str, test: str | None = None) -> dict:
    """Part 1's right-hand column is a raw model call with no memory at all."""
    details = getattr(response.usage, "input_tokens_details", None)
    inputs, outputs = int(response.usage.input_tokens or 0), int(response.usage.output_tokens or 0)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    cost, note = price(model, inputs, cached, outputs)
    return _record(turn=turn, part=part, thread=thread, question=question, agent="memorizz", model=model,
                   total_ms=elapsed_ms, model_ms=elapsed_ms, memory_ms=0, tools_ms=0, calls=1,
                   input_tokens=inputs, cached_tokens=cached, output_tokens=outputs, cost=cost,
                   cost_note=note + " · raw model call (Part 1)", tool_calls=[], cache_hit=False, test=test)


def summary(turns: list[dict]) -> dict:
    out = {}
    for agent in AGENTS:
        rows = [r for r in turns if r["agent"] == agent]
        latencies = sorted(r["latency"]["total_ms"] for r in rows)
        inputs = sum(r["usage"]["input_tokens"] for r in rows)
        cached = sum(r["usage"]["cached_input_tokens"] for r in rows)
        out[agent] = {
            "turns": len(rows),
            "total_tokens": sum(r["usage"]["total_tokens"] for r in rows),
            "input_tokens": inputs, "cached_input_tokens": cached,
            "cached_share": round(cached / inputs, 3) if inputs else 0.0,
            "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
            "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 6),
            "avg_latency_s": round(sum(latencies) / len(latencies) / 1000, 2) if latencies else 0.0,
            "max_latency_s": round(latencies[-1] / 1000, 2) if latencies else 0.0,
            "model_calls": sum(r["usage"]["model_calls"] for r in rows),
            "tool_calls": sum(len(r["tool_calls"]) for r in rows),
            "cache_hits": sum(1 for r in rows if r["cache_hit"]),
            "scored": sum(1 for r in rows if r["accuracy"]["score"] is not None),
            "correct": sum(r["accuracy"]["score"] or 0 for r in rows),
            "judge_cost_usd": round(sum(r["accuracy"].get("judge_cost_usd") or 0 for r in rows), 6),
        }
        out[agent]["accuracy"] = (round(out[agent]["correct"] / out[agent]["scored"], 3)
                                  if out[agent]["scored"] else None)
        by_test: dict[str, dict] = {}
        for r in rows:
            if r["accuracy"]["score"] is not None:
                cell = by_test.setdefault(r.get("test") or "golden question", {"scored": 0, "correct": 0})
                cell["scored"] += 1
                cell["correct"] += r["accuracy"]["score"]
        out[agent]["by_test"] = by_test
    return out
