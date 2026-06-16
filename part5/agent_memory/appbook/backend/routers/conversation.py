"""Layer 1 — Episodic conversation memory.

A MemAgent backed by the shared Memory Core. It remembers across turns AND across
a process restart: ``/reload`` reconstructs the agent from storage by its
``agent_id`` (via ``MemAgent.load``) and asks it to recall — the notebook's §2
"killer demo," made interactive.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.memory import (
    compute_context_segments,
    error_stream,
    final_context_event,
    prefill_context_events,
    pseudo_stream,
    run_agent,
    store,
    unavailable_reason,
)
from backend.core.sse import sse_response
from backend.schemas import ConversationRequest

router = APIRouter(prefix="/api/conversation", tags=["conversation"])

INSTRUCTION = (
    "You are Memo, an engineering copilot with persistent memory. Be concise and concrete. "
    "Remember what the user tells you about themselves and their work, and use it on later turns."
)

# session_id -> {"agent", "agent_id", "turns"}. The agent's *content* lives in the
# Memory Core (Oracle / filesystem); this dict is just the in-process handle.
_sessions: dict[str, dict] = {}


def _session(session_id: str) -> dict:
    s = _sessions.get(session_id)
    if s is None:
        agent = store.build_agent(INSTRUCTION, name="Memo")
        agent.save()  # persist config to the MEMAGENT store so it can be reloaded
        s = {"agent": agent, "agent_id": agent.agent_id, "turns": 0}
        _sessions[session_id] = s
    return s


@router.post("/message")
async def message(req: ConversationRequest):
    reason = unavailable_reason()
    if reason:
        return sse_response(error_stream(reason))
    s = _session(req.session_id)
    agent = s["agent"]

    async def events():
        s["turns"] += 1
        win, segs = await run_in_threadpool(
            compute_context_segments, agent, req.message, history_memory_id=s.get("memory_id")
        )
        async for ev in prefill_context_events(win, segs):
            yield ev
        answer = await run_agent(lambda: agent.run(req.message))
        # Remember the conversation scope so a reloaded agent can resume this exact thread.
        s["memory_id"] = agent.get_current_memory_id()
        s["thread_id"] = agent.get_current_thread_id()
        yield final_context_event(agent, win, segs)
        async for ev in pseudo_stream(answer):
            yield ev
        yield {"type": "done", "turns": s["turns"], "agent_id": s["agent_id"], "backend": store.backend}

    return sse_response(events())


@router.post("/reload")
async def reload(req: ConversationRequest):
    """Simulate a restart: load the agent fresh from storage by id, then recall."""
    reason = unavailable_reason()
    if reason:
        return sse_response(error_stream(reason))
    s = _sessions.get(req.session_id)
    if not s:
        async def none():
            yield {"type": "error", "message": "No conversation yet — send a message first."}
        return sse_response(none())

    agent_id = s["agent_id"]

    async def events():
        from memorizz.memagent import MemAgent

        reloaded = await run_in_threadpool(
            lambda: MemAgent.load(agent_id, memory_provider=store.require())
        )
        query = (req.message or "").strip() or (
            "Based only on our earlier conversation, what is my name and what am I working on?"
        )
        yield {"type": "reloaded", "agent_id": agent_id, "backend": store.backend}
        # Resume the same conversation scope the live agent used, so the freshly
        # loaded agent reads the persisted history instead of starting blank.
        answer = await run_agent(
            lambda: reloaded.run(query, memory_id=s.get("memory_id"), thread_id=s.get("thread_id"))
        )
        async for ev in pseudo_stream(answer):
            yield ev
        yield {"type": "done", "reloaded": True, "agent_id": agent_id, "backend": store.backend}

    return sse_response(events())


@router.post("/reset")
def reset(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return {"ok": True}
