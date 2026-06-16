"""Form Factor 1 — The Chatbot.

A stateless LLM made multi-turn by *resending the whole conversation* each call.
The "memory" is literally the growing message list. Replies stream token-by-token.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.anthropic_client import MAX_TOKENS, MODEL, async_client
from backend.core.sse import sse_response
from backend.schemas import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chatbot"])

SYSTEM = "You are a helpful assistant."

# claude-opus-4-8 context window (tokens) — drives the UI's utilised-vs-free meter.
CONTEXT_WINDOW = 200_000

# Conversation memory: session_id -> list[{"role","content"}]. In-process only.
_sessions: dict[str, list[dict]] = {}


async def _context_tokens(history: list[dict]) -> int:
    """Tokens the *next* turn will send = system + full history. Accurate via the
    count_tokens API; falls back to a ~4-chars/token estimate if it's unavailable."""
    try:
        ct = await async_client.messages.count_tokens(model=MODEL, system=SYSTEM, messages=history)
        return int(ct.input_tokens)
    except Exception:  # noqa: BLE001
        chars = len(SYSTEM) + sum(len(m.get("content", "")) for m in history)
        return max(1, chars // 4)


@router.post("/message")
async def message(req: ChatRequest):
    history = _sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": req.message})

    async def events():
        parts: list[str] = []
        async with async_client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=history,
        ) as stream:
            async for text in stream.text_stream:
                parts.append(text)
                yield {"type": "delta", "text": text}
        reply = "".join(parts)
        history.append({"role": "assistant", "content": reply})
        # turns = how many messages we now resend every call — the teachable bit.
        tokens = await _context_tokens(history)
        yield {
            "type": "done",
            "turns": len(history),
            "context_tokens": tokens,
            "context_window": CONTEXT_WINDOW,
        }

    return sse_response(events())


@router.get("/history")
def history(session_id: str) -> dict:
    return {"history": _sessions.get(session_id, [])}


@router.post("/reset")
def reset(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return {"ok": True}
