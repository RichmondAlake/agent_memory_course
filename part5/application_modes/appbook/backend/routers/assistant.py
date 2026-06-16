"""Assistant mode — conversational, reactive, relationship-driven.

A turn-by-turn logistics ops assistant. Each turn it RECALLS the operator's
durable preferences and operational notes from Oracle AI Agent Memory, answers
with that context, then WRITES the turn back to memory. Memory profile:
short-term context (the thread) + long-term preference retrieval.
"""
from __future__ import annotations

import threading

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.anthropic_client import MAX_TOKENS, MODEL, async_client
from backend.core.contextwin import block as ctx_block
from backend.core.contextwin import count_tokens as ctx_count
from backend.core.contextwin import window as ctx_window
from backend.core.memory import store
from backend.core.sse import sse_response
from backend.schemas import AssistantRequest

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

USER_ID = "operator-morgan"
AGENT_ID = "supply-assistant"

PREFERENCES = [
    "Acme Industrial prefers proactive delay notifications by phone, not email.",
    "Belden Foods requires a temperature-controlled handling note on every shipment update.",
    "Operator Morgan likes shipment rundowns grouped by customer, most urgent first.",
]
SEED_NOTES = [
    "Shipment SHP-1003 for Acme Industrial is delayed to May 14 due to port congestion.",
    "Shipment SHP-1001 for Acme Industrial is in transit, ETA May 2, currently on track.",
    "Shipment SHP-1002 for Belden Foods is at the Newark port, ETA Apr 28.",
]

SYSTEM = (
    "You are a logistics operations assistant for the West Coast desk. Use the operator's "
    "stored PREFERENCES and OPERATIONAL NOTES below to answer. Honour preferences (e.g. a "
    "customer's preferred contact channel). Be concise and concrete; interpret the notes "
    "rather than repeating them verbatim.\n\n"
    "PREFERENCES:\n{prefs}\n\nOPERATIONAL NOTES:\n{notes}"
)

_sessions: dict[str, list[dict]] = {}
_seed_lock = threading.Lock()
_seeded = False


def _ensure_seeded() -> None:
    global _seeded
    if _seeded:
        return
    with _seed_lock:
        if _seeded:
            return
        store.ensure_scope(USER_ID, AGENT_ID)
        already = store.search("Acme phone notification preference", user_id=USER_ID,
                               agent_id=AGENT_ID, record_types=["preference"], max_results=1)
        if not already:
            store.add_typed(PREFERENCES, "preference", user_id=USER_ID, agent_id=AGENT_ID,
                            metadata={"kind": "seed"})
            for note in SEED_NOTES:
                store.add_memory(note, user_id=USER_ID, agent_id=AGENT_ID,
                                 metadata={"kind": "seed"})
        _seeded = True


@router.post("/message")
async def message(req: AssistantRequest):
    _ensure_seeded()
    store.thread_create(req.session_id, user_id=USER_ID, agent_id=AGENT_ID)
    history = _sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": req.message})

    async def events():
        # ① RECALL — long-term preferences + operational notes relevant to the turn
        prefs = store.search(req.message, user_id=USER_ID, agent_id=AGENT_ID,
                             record_types=["preference"], max_results=3)
        notes = store.search(req.message, user_id=USER_ID, agent_id=AGENT_ID,
                             record_types=["memory"], max_results=3)
        yield {"type": "memory_recall", "scope": "preference", "hits": prefs}
        yield {"type": "memory_recall", "scope": "memory", "hits": notes}

        system = SYSTEM.format(
            prefs="\n".join(h["formatted_content"] for h in prefs) or "(none on file)",
            notes="\n".join(h["formatted_content"] for h in notes) or "(none on file)",
        )

        # CONTEXT WINDOW — exactly what we're about to send to the model this turn.
        # Memory enters the window via the system prompt; the conversation is the messages array.
        def _blocks(hist):
            b = [ctx_block("system", "System prompt · instructions + recalled memory", system)]
            for i, m in enumerate(hist, 1):
                b.append(ctx_block(m["role"], f"Message {i} · {m['role']}", m["content"]))
            return b
        measured = await run_in_threadpool(ctx_count, system, history)
        yield {"type": "context", "window": ctx_window(_blocks(history), measured=measured,
                                                       note="No tools in this call — the whole window is system prompt + messages.")}

        # ② RESPOND — stream the reply, with the running conversation as short-term memory
        parts: list[str] = []
        async with async_client.messages.stream(
            model=MODEL, max_tokens=MAX_TOKENS, system=system, messages=history,
        ) as stream:
            async for text in stream.text_stream:
                parts.append(text)
                yield {"type": "delta", "text": text}
        reply = "".join(parts)
        history.append({"role": "assistant", "content": reply})

        # ③ WRITE — persist the turn (working memory) + a durable operational note
        store.thread_add(req.session_id, "user", req.message, user_id=USER_ID, agent_id=AGENT_ID)
        store.thread_add(req.session_id, "assistant", reply, user_id=USER_ID, agent_id=AGENT_ID)
        note = f"Operator asked about: {req.message.strip()[:160]}"
        store.add_memory(note, user_id=USER_ID, agent_id=AGENT_ID,
                         thread_id=req.session_id, metadata={"kind": "turn"})
        yield {"type": "memory_write",
               "record": {"content": note, "record_type": "memory"}}

        # Context window now includes the model's reply (it becomes input next turn)
        measured2 = await run_in_threadpool(ctx_count, system, history)
        yield {"type": "context", "window": ctx_window(_blocks(history), measured=measured2,
                                                       note="The reply is now part of the window — it's resent as input on the next turn.")}
        # CONTEXT CARD — OAMP's consolidated working-memory block for this thread
        card = store.thread_context_card(req.session_id, user_id=USER_ID, agent_id=AGENT_ID)
        if card:
            yield {"type": "context_card", "card": card}

        yield {"type": "done", "thread_len": store.thread_len(req.session_id)}

    return sse_response(events())


@router.get("/state")
def state(session_id: str) -> dict:
    _ensure_seeded()
    prefs = store.search("preferences for customers and the operator", user_id=USER_ID,
                         agent_id=AGENT_ID, record_types=["preference"], max_results=10)
    summary = store.thread_summary(session_id, user_id=USER_ID, agent_id=AGENT_ID)
    return {
        "preferences": prefs,
        "summary": summary,
        "thread_len": store.thread_len(session_id),
        "backend": store.status().get("backend"),
    }


@router.post("/reset")
def reset(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return {"ok": True}
