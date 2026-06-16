"""Layer 5 — Shared memory: multi-agent coordination (observable).

A Lead delegates to a Researcher and a Reviewer, then synthesizes one
recommendation. The hand-offs are mediated by a `SharedMemory` blackboard and
streamed as `flow` events so the UI can render the live agentic data flow; each
agent's context window is streamed as `agent_context` for the hover view.

memorizz also ships `MultiAgentOrchestrator`, which runs this exact pattern
opaquely over shared memory — here we drive it explicitly so every instruction
and report passing between agents is observable in real time.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.memory import (
    compute_context_segments,
    error_stream,
    pseudo_stream,
    run_agent,
    store,
    unavailable_reason,
)
from backend.core.sse import sse_response
from backend.schemas import CoordinationRequest

router = APIRouter(prefix="/api/coordination", tags=["coordination"])

_lock = threading.Lock()
_team: dict = {"lead": None, "researcher": None, "reviewer": None, "shared": None}

ROLES = {
    "lead": "You are the lead engineer. Decompose the question, weigh the specialists' input, "
            "and synthesize one clear, decisive recommendation.",
    "researcher": "You research technical options and lay out concrete trade-offs "
                  "(cost, quality, risk). Be specific and brief.",
    "reviewer": "You critique a proposal for correctness, security, and operational risk, "
                "then give a clear verdict. Be specific and brief.",
}

# The static architecture / data-flow graph the UI renders.
ARCHITECTURE = {
    "agents": [
        {"id": "lead", "name": "Lead", "role": "root",
         "desc": "Decomposes the task, delegates to specialists, and synthesizes the answer."},
        {"id": "researcher", "name": "Researcher", "role": "delegate",
         "desc": "Gathers options and lays out trade-offs (cost, quality, risk)."},
        {"id": "reviewer", "name": "Reviewer", "role": "delegate",
         "desc": "Critiques the proposal for correctness, security, and operational risk."},
        {"id": "output", "name": "Recommendation", "role": "output",
         "desc": "The synthesized recommendation returned to you."},
    ],
    "edges": [
        {"src": "lead", "dst": "researcher", "label": "research task"},
        {"src": "researcher", "dst": "lead", "label": "findings"},
        {"src": "lead", "dst": "reviewer", "label": "review request"},
        {"src": "reviewer", "dst": "lead", "label": "verdict"},
        {"src": "lead", "dst": "output", "label": "recommendation"},
    ],
}


def _build_team() -> dict:
    with _lock:
        if _team["lead"] is not None:
            return _team
    lead = store.build_agent(ROLES["lead"], name="Lead")
    researcher = store.build_agent(ROLES["researcher"], name="Researcher")
    reviewer = store.build_agent(ROLES["reviewer"], name="Reviewer")
    for a in (lead, researcher, reviewer):
        a.save()
    shared = None
    try:
        from memorizz import SharedMemory

        sm = SharedMemory(store.require())
        memory_id = sm.create_shared_session(
            root_agent_id=lead.agent_id,
            delegate_agent_ids=[researcher.agent_id, reviewer.agent_id],
        )
        shared = {"sm": sm, "memory_id": memory_id}
    except Exception:
        shared = None  # blackboard is best-effort; the flow still streams
    with _lock:
        _team.update(lead=lead, researcher=researcher, reviewer=reviewer, shared=shared)
    return _team


def _post(team: dict, agent_id: str, content: str, entry_type: str) -> None:
    """Best-effort write of an inter-agent message onto the shared blackboard."""
    sh = team.get("shared")
    if not sh:
        return
    try:
        sh["sm"].add_blackboard_entry(
            memory_id=sh["memory_id"], agent_id=agent_id, content=content, entry_type=entry_type
        )
    except Exception:
        pass


@router.post("/run")
async def run(req: CoordinationRequest):
    reason = unavailable_reason()
    if reason:
        return sse_response(error_stream(reason))

    async def events():
        # 0) hand the UI the architecture graph to draw IMMEDIATELY (no LLM/DB needed),
        #    so the data-flow renders even while the specialists are still thinking.
        yield {"type": "architecture", **ARCHITECTURE, "shared_memory": True}
        team = await run_in_threadpool(_build_team)
        lead, researcher, reviewer = team["lead"], team["researcher"], team["reviewer"]

        async def emit_ctx(agent_id: str, agent, query: str):
            win, segs = await run_in_threadpool(compute_context_segments, agent, query)
            yield {"type": "agent_context", "agent": agent_id, "window": win,
                   "used": sum(s["tokens"] for s in segs), "segments": segs}

        try:
            # 1) Lead → Researcher
            r_instr = ("Research this decision and lay out concrete options with their trade-offs "
                       f"(cost, quality, risk):\n\n{req.prompt}")
            yield {"type": "flow", "id": "f1", "src": "lead", "dst": "researcher",
                   "kind": "instruction", "status": "active", "content": r_instr}
            await run_in_threadpool(_post, team, lead.agent_id, r_instr, "command")
            findings = await run_agent(lambda: researcher.run(r_instr))
            await run_in_threadpool(_post, team, researcher.agent_id, findings, "report")
            async for e in emit_ctx("researcher", researcher, r_instr):
                yield e
            yield {"type": "flow", "id": "f1", "src": "lead", "dst": "researcher",
                   "kind": "instruction", "status": "done", "content": r_instr}
            yield {"type": "flow", "id": "f2", "src": "researcher", "dst": "lead",
                   "kind": "report", "status": "done", "content": findings}

            # 2) Lead → Reviewer
            v_instr = ("Critique this proposal for correctness, security, and operational risk, "
                       f"then give a verdict.\n\nDecision:\n{req.prompt}\n\nResearcher findings:\n{findings}")
            yield {"type": "flow", "id": "f3", "src": "lead", "dst": "reviewer",
                   "kind": "instruction", "status": "active", "content": v_instr}
            await run_in_threadpool(_post, team, lead.agent_id, v_instr, "command")
            verdict = await run_agent(lambda: reviewer.run(v_instr))
            await run_in_threadpool(_post, team, reviewer.agent_id, verdict, "report")
            async for e in emit_ctx("reviewer", reviewer, v_instr):
                yield e
            yield {"type": "flow", "id": "f3", "src": "lead", "dst": "reviewer",
                   "kind": "instruction", "status": "done", "content": v_instr}
            yield {"type": "flow", "id": "f4", "src": "reviewer", "dst": "lead",
                   "kind": "report", "status": "done", "content": verdict}

            # 3) Lead synthesizes
            s_instr = ("Synthesize ONE clear, decisive recommendation, using the findings and the "
                       f"review.\n\nDecision:\n{req.prompt}\n\nResearcher findings:\n{findings}\n\n"
                       f"Reviewer verdict:\n{verdict}")
            yield {"type": "flow", "id": "f5", "src": "lead", "dst": "output",
                   "kind": "output", "status": "active", "content": ""}
            final = await run_agent(lambda: lead.run(s_instr))
            await run_in_threadpool(_post, team, lead.agent_id, final, "synthesis")
            async for e in emit_ctx("lead", lead, s_instr):
                yield e
            yield {"type": "flow", "id": "f5", "src": "lead", "dst": "output",
                   "kind": "output", "status": "done", "content": final}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error",
                   "message": f"Multi-agent run failed ({type(exc).__name__}). It makes several "
                              f"LLM calls — check your key/quota. {exc}"}
            return

        async for ev in pseudo_stream(final):
            yield ev
        yield {"type": "final", "reply": final, "backend": store.backend}

    return sse_response(events())
