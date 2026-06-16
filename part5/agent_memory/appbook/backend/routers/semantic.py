"""Layer 2 — Semantic memory: persona + entity memory.

The agent carries a stable **persona** (identity/voice) and an **entity memory**:
as you tell it facts ("our on-call tool is PagerPilot, owned by Ada"), it records
them as structured entities it can recall precisely. Notebook §3 + §4.
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
from backend.schemas import SemanticRequest

router = APIRouter(prefix="/api/semantic", tags=["semantic"])

PERSONA = {
    "name": "Memo",
    "role": "TECHNICAL_EXPERT",
    "goals": "Help engineers ship reliable LLM apps; favor correctness first, then clarity.",
    "background": "A staff-level AI platform engineer experienced in retrieval, vector databases, "
                  "evaluation, and running agents in production.",
}

INSTRUCTION = (
    "You are Memo. Answer in character. When the user states a durable fact about a person, "
    "service, or system, record it with your entity-memory tools, and recall such facts precisely "
    "when asked."
)

_sessions: dict[str, dict] = {}


def _build_persona():
    from memorizz import Persona, RoleType

    return Persona(
        name=PERSONA["name"],
        role=getattr(RoleType, PERSONA["role"], RoleType.TECHNICAL_EXPERT),
        goals=PERSONA["goals"],
        background=PERSONA["background"],
    )


def _session(session_id: str) -> dict:
    s = _sessions.get(session_id)
    if s is None:
        agent = store.build_agent(
            INSTRUCTION, name="Memo", persona=_build_persona(), entity_memory=True
        )
        agent.save()
        s = {"agent": agent}
        _sessions[session_id] = s
    return s


def _entities() -> list[dict]:
    """Best-effort list of captured entities, rendered defensively for the UI."""
    try:
        from memorizz.long_term.semantic.entity_memory.entity_memory import EntityMemory

        rows = EntityMemory(store.require()).list_entities() or []
    except Exception:
        return []
    out = []
    for e in rows[:12]:
        if not isinstance(e, dict):
            continue
        attrs = e.get("attributes") or []
        pairs = []
        if isinstance(attrs, list):
            for a in attrs:
                if isinstance(a, dict) and a.get("name") is not None:
                    pairs.append({"name": str(a.get("name")), "value": str(a.get("value", ""))})
        out.append({
            "name": e.get("name") or e.get("entity_id") or "entity",
            "entity_type": e.get("entity_type") or "",
            "attributes": pairs,
        })
    return out


@router.get("/persona")
def persona() -> dict:
    return {"persona": PERSONA}


@router.get("/entities")
def entities() -> dict:
    return {"entities": _entities()}


@router.post("/message")
async def message(req: SemanticRequest):
    reason = unavailable_reason()
    if reason:
        return sse_response(error_stream(reason))
    s = _session(req.session_id)
    agent = s["agent"]

    async def events():
        win, segs = await run_in_threadpool(compute_context_segments, agent, req.message)
        async for ev in prefill_context_events(win, segs):
            yield ev
        answer = await run_agent(lambda: agent.run(req.message))
        yield final_context_event(agent, win, segs)
        async for ev in pseudo_stream(answer):
            yield ev
        ents = await run_in_threadpool(_entities)
        yield {"type": "done", "entities": ents, "backend": store.backend}

    return sse_response(events())
