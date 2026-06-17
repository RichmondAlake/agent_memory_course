"""Stop 1 — Naive memory: a chatbot whose "memory" is the full message list it
re-sends every turn. Replies stream token-by-token; we report how many input
tokens that growing history now costs."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core_anthropic import AGENT_MODEL, SYSTEM_PROMPT, async_client
from backend.schemas import ChatRequest, SessionRef
from backend.sse import sse_response

router = APIRouter(prefix="/api/naive", tags=["naive"])

# session_id -> append-only [{role, content}] (user/assistant only; system is separate)
_sessions: dict[str, list[dict]] = {}


@router.post("/message")
async def message(req: ChatRequest):
    history = _sessions.setdefault(req.session_id, [])
    history.append({"role": "user", "content": req.message})

    async def events():
        parts: list[str] = []
        try:
            async with async_client.messages.stream(
                model=AGENT_MODEL,
                max_tokens=settings.max_answer_tokens,
                system=SYSTEM_PROMPT,
                messages=history,
            ) as stream:
                async for text in stream.text_stream:
                    parts.append(text)
                    yield {"type": "delta", "text": text}
                final = await stream.get_final_message()
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            return

        reply = "".join(parts)
        history.append({"role": "assistant", "content": reply})
        u = final.usage
        total_in = (u.input_tokens
                    + getattr(u, "cache_creation_input_tokens", 0)
                    + getattr(u, "cache_read_input_tokens", 0))
        yield {
            "type": "done",
            "turns": len(history),            # messages re-sent next turn — the "memory"
            "input_tokens": total_in,          # full prompt this turn (grows every turn)
            "output_tokens": u.output_tokens,
            "context_window": settings.context_window,
        }

    return sse_response(events())


@router.get("/history")
def history(session_id: str) -> dict:
    return {"history": _sessions.get(session_id, [])}


@router.post("/reset")
def reset(ref: SessionRef) -> dict:
    _sessions.pop(ref.session_id, None)
    return {"ok": True}
