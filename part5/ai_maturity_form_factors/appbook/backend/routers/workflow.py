"""Form Factor 3 — The LLM-Driven Workflow.

A fixed, code-orchestrated pipeline: classify → route → retrieve → draft →
**human handoff** (approve / decline-with-reason). Each stage streams a `step`
event so the UI renders the pipeline live; at the draft it pauses for a human
verdict (`/start` → handoff → `/decision`). *Your code* owns the control flow.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.anthropic_client import MAX_TOKENS, MODEL, client, structured_json, text_of
from backend.core.retrieval import store
from backend.core.sse import sse_response
from backend.schemas import WorkflowDecisionRequest, WorkflowRequest

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string",
                     "enum": ["billing", "technical", "account", "feature_request", "other"]},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string", "description": "One-line summary of the request."},
    },
    "required": ["category", "urgency", "summary"],
    "additionalProperties": False,
}

def _classify(message: str) -> dict:
    return structured_json(
        system="Classify the incoming Acme Cloud support message.",
        user=message,
        schema=CLASSIFY_SCHEMA,
    )


def _draft_reply(message: str, context: str) -> str:
    system = (
        "You are an Acme Cloud support agent. Write a friendly, accurate reply using ONLY "
        "the provided context. Cite facts with [n]. Keep it under 120 words."
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": f"Customer message:\n{message}\n\nContext:\n{context}"}],
    )
    return text_of(response)


def _route(info: dict) -> dict:
    escalate = info.get("category") == "billing" and info.get("urgency") == "high"
    return {
        "escalated": escalate,
        "reason": "Urgent billing → flag for a human" if escalate
                  else "Handled by the automated pipeline",
    }


# Workflows paused awaiting a human verdict: workflow_id -> state. In-process only.
_pending: dict[str, dict] = {}


@router.post("/start")
async def start(req: WorkflowRequest):
    """Run classify → route → retrieve → draft, then pause for a HUMAN handoff."""
    async def events():
        # ① classify (LLM)
        yield {"type": "step", "step": "classify", "status": "running"}
        info = await run_in_threadpool(_classify, req.message)
        yield {"type": "step", "step": "classify", "status": "done", "data": info}

        # ② route (your code)
        route = _route(info)
        yield {"type": "step", "step": "route", "status": "done", "data": route}

        # ③ retrieve (RAG, reused from FF2)
        yield {"type": "step", "step": "retrieve", "status": "running"}
        hits = await run_in_threadpool(store.search, req.message, "vector", 3)
        context = "\n".join(f"[{i + 1}] {h.content}" for i, h in enumerate(hits))
        yield {"type": "step", "step": "retrieve", "status": "done",
               "data": {"hits": [h.as_dict() for h in hits], "backend": store.backend}}

        # ④ draft (LLM)
        yield {"type": "step", "step": "draft", "status": "running"}
        draft = await run_in_threadpool(_draft_reply, req.message, context)
        yield {"type": "step", "step": "draft", "status": "done", "data": {"draft": draft, "attempt": 1}}

        # ⑤ HANDOFF — pause for a human to approve or decline (the review step is now a person)
        wid = uuid.uuid4().hex[:12]
        _pending[wid] = {"message": req.message, "context": context,
                         "classification": info, "route": route, "draft": draft, "attempt": 1}
        yield {"type": "handoff", "workflow_id": wid, "draft": draft, "attempt": 1,
               "classification": info, "escalated": route["escalated"]}

    return sse_response(events())


@router.post("/decision")
async def decision(req: WorkflowDecisionRequest):
    """The human's verdict on the current draft: approve → finalize; decline →
    redraft using the reason, then hand off the new draft again."""
    st = _pending.get(req.workflow_id)

    async def events():
        if not st:
            yield {"type": "error", "message": "This handoff has expired — run the pipeline again."}
            return

        if req.approved:
            yield {"type": "final", "classification": st["classification"],
                   "escalated": st["route"]["escalated"], "reply": st["draft"], "approved": True}
            _pending.pop(req.workflow_id, None)
            return

        # Declined → redraft using the human's reason, then hand off the new draft.
        attempt = st["attempt"] + 1
        yield {"type": "step", "step": "draft", "status": "running",
               "data": {"attempt": attempt, "revising": True, "reason": req.reason}}
        feedback = (req.reason or "").strip() or "Please improve the reply."
        new_context = st["context"] + f"\n\nReviewer (human) feedback to address: {feedback}"
        draft = await run_in_threadpool(_draft_reply, st["message"], new_context)
        st["draft"], st["attempt"] = draft, attempt
        yield {"type": "step", "step": "draft", "status": "done", "data": {"draft": draft, "attempt": attempt}}
        yield {"type": "handoff", "workflow_id": req.workflow_id, "draft": draft, "attempt": attempt,
               "classification": st["classification"], "escalated": st["route"]["escalated"]}

    return sse_response(events())
