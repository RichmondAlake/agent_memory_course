"""Stop 3 — the head-to-head benchmark. We run a short scripted conversation
through BOTH agents (naive + OAMP), streaming per-turn token & latency metrics so
the frontend can draw the divergence live, then run an LLM-as-judge quality pass.

The script is a compact, self-contained version of the notebook's design: a few
declarative turns that load facts, then recall probes that force retrieval."""
from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.conversation import SCRIPT
from backend.core_anthropic import AGENT_MODEL, SYSTEM_PROMPT, call_claude, prompt_tokens
from backend.memory_core import store
from backend.schemas import BenchmarkRequest
from backend.sse import sse_response

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])

# The benchmark runs under its OWN OAMP identity (separate from the /memory chat's
# app-user/app-agent) so each run can be reset to a pristine, empty memory store
# without disturbing the interactive chat's stored memories.
BENCH_USER = "bench-user"
BENCH_AGENT = "bench-agent"

_JUDGE_PROMPT = """You are an impartial judge comparing two AI assistant responses to a user query.

User query:
{query}

Response A:
{a}

Response B:
{b}

Judge on accuracy, completeness, relevance, and coherence. Return ONLY this JSON:
{{"winner": "A" or "B" or "Tie", "reason": "one short sentence"}}"""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = re.sub(r"^json\s*", "", raw, flags=re.IGNORECASE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"winner": "Tie", "reason": "(unparsed)"}


def _naive_call(history: list[dict]) -> dict:
    """One naive turn: re-send the full history (prompt-cached). Returns metrics."""
    t0 = time.perf_counter()
    answer, usage = call_claude(history, model=AGENT_MODEL, system=SYSTEM_PROMPT, cache=True)
    return {
        "answer": answer,
        "tokens": prompt_tokens(usage),
        "cache_read": getattr(usage, "cache_read_input_tokens", 0),
        "latency": round(time.perf_counter() - t0, 3),
    }


def _judge(query: str, a: str, b: str) -> str:
    text, _ = call_claude(
        [{"role": "user", "content": _JUDGE_PROMPT.format(query=query, a=a, b=b)}],
        system="You are an impartial evaluation judge. Output only the requested JSON.",
        max_tokens=160,
    )
    w = _extract_json(text).get("winner", "Tie")
    return {"A": "oamp", "B": "naive"}.get(w, "tie")


@router.get("/script")
def script() -> dict:
    return {"turns": SCRIPT, "default_turns": settings.benchmark_turns}


# Only one benchmark may run at a time — the OAMP connection is a single,
# lock-serialised resource, so concurrent runs would starve each other. A second
# request returns immediately instead of stacking up behind the active run.
_run_active = False


@router.post("/run")
async def run(req: BenchmarkRequest):
    n = max(2, min(req.turns or settings.benchmark_turns, len(SCRIPT)))
    turns = SCRIPT[:n]

    async def events():
        global _run_active
        if not store.ready:
            yield {"type": "error", "message": store.error or "Oracle Agent Memory is still warming up — try again shortly."}
            return
        if _run_active:
            yield {"type": "error", "message": "A benchmark is already running — let it finish, or reload the page and try again."}
            return

        _run_active = True
        tid = None
        try:
            yield {"type": "starting", "total": len(turns)}   # instant feedback
            # PRISTINE RUN: wipe any memories left by a previous benchmark run so recall is
            # measured from an empty store (the appbook analogue of schema_policy='recreate').
            await run_in_threadpool(store.reset_identity, BENCH_USER, BENCH_AGENT)
            tid = await run_in_threadpool(store.create_thread, BENCH_USER, BENCH_AGENT)

            naive_history: list[dict] = []
            oamp_answers: list[str] = []
            naive_answers: list[str] = []
            for i, q in enumerate(turns, 1):
                yield {"type": "turn", "turn": i, "total": len(turns), "query": q}

                oamp = await run_in_threadpool(store.step, tid, q, user_id=BENCH_USER, agent_id=BENCH_AGENT)
                oamp_answers.append(oamp["answer"])

                naive_history.append({"role": "user", "content": q})
                naive = await run_in_threadpool(_naive_call, naive_history)
                naive_history.append({"role": "assistant", "content": naive["answer"]})
                naive_answers.append(naive["answer"])

                yield {
                    "type": "metric", "turn": i,
                    "oamp": {"tokens": oamp["input_tokens"], "latency": oamp["total_s"], "answer": oamp["answer"]},
                    "naive": {"tokens": naive["tokens"], "latency": naive["latency"], "cache_read": naive["cache_read"], "answer": naive["answer"]},
                }

            if req.judge:
                wins = {"oamp": 0, "naive": 0, "tie": 0}
                for i, (q, a, b) in enumerate(zip(turns, oamp_answers, naive_answers), 1):
                    winner = await run_in_threadpool(_judge, q, a, b)
                    wins[winner] += 1
                    yield {"type": "judge", "turn": i, "winner": winner}
                yield {"type": "judge_done", "wins": wins}

            yield {"type": "done"}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
        finally:
            _run_active = False                                # release the gate (also on client disconnect)
            if tid:
                await run_in_threadpool(store.delete_thread, tid)

    return sse_response(events())
