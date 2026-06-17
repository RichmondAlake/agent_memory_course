"""FF4 (agent) + FF5 (autonomous agent) streaming evaluation."""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.agent_eval import stream_agent_eval, stream_builder_eval
from backend.core.sse import sse_response

router = APIRouter(prefix="/api/eval", tags=["agent-eval"])


@router.post("/agent")
async def agent():
    """FF4 — run each scenario live and score final response / trajectory / single step."""
    return sse_response(stream_agent_eval())


@router.post("/builder")
async def builder():
    """FF5 — build a CLI, run it on two batches, score functional correctness + code quality."""
    return sse_response(stream_builder_eval())
