"""Form Factor 1 — The Chatbot.

A stateless LLM made multi-turn by *resending the whole conversation* every call: the memory is the
growing message list. Replies stream token by token, and each turn reports how many tokens that memory
now costs to resend.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.anthropic_client import MAX_TOKENS, MODEL, OUTPUT_CONFIG, async_client
from backend.core.sse import sse_response
from backend.schemas import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chatbot"])

SYSTEM = "You are a helpful mortgage assistant. Keep answers under 80 words."
CONTEXT_WINDOW = 1_000_000  # Claude Haiku 5.5

# Conversation memory: session_id -> list[{"role","content"}]. In-process only, lost on restart.
_sessions: dict[str, list[dict]] = {}


async def _context_tokens(history: list[dict]) -> int:
    """Tokens the *next* turn will send: system + full history (count_tokens, or a 4-chars/token estimate)."""
    try:
        counted = await async_client.messages.count_tokens(model=MODEL, system=SYSTEM, messages=history)
        return int(counted.input_tokens)
    except Exception:  # noqa: BLE001
        return max(1, (len(SYSTEM) + sum(len(m.get("content", "")) for m in history)) // 4)


@router.post("/message")
async def message(req: ChatRequest):
    history = _sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": req.message})

    async def events():
        parts: list[str] = []
        async with async_client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, output_config=OUTPUT_CONFIG,
                                                system=SYSTEM, messages=history) as stream:
            async for text in stream.text_stream:
                parts.append(text)
                yield {"type": "delta", "text": text}
            final = await stream.get_final_message()
        reply = "".join(parts)
        history.append({"role": "assistant", "content": reply})  # the memory grows here
        yield {"type": "done", "turns": len(history), "input_tokens": final.usage.input_tokens,
               "context_tokens": await _context_tokens(history), "context_window": CONTEXT_WINDOW}

    return sse_response(events())


@router.get("/history")
def history(session_id: str) -> dict:
    return {"history": _sessions.get(session_id, []), "system": SYSTEM}


@router.post("/reset")
def reset(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return {"ok": True}
