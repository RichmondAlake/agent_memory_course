"""Layer 4 — Procedural memory: tools + workflows + skillbox.

Procedural memory is *how to act*. This layer shows three flavours from the
notebook (§6–§8): callable **tools** the agent can invoke, a stored **workflow**
(runbook) recalled by intent, and a **skillbox** of how-to guides retrieved as an
always-on manifest. The pipeline streams each piece, then the agent answers.
"""
from __future__ import annotations

import threading

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
from backend.schemas import ProceduralRequest

router = APIRouter(prefix="/api/procedural", tags=["procedural"])

SKILL_NS = "appbook-skills"

SKILLS = [
    {"name": "vector/index-rebuild",
     "description": "Rebuild an Oracle AI Vector Search index safely in production.",
     "body": "Enter maintenance mode; build the new index alongside the old one; wait for row "
             "counts to match; flip the read alias; watch p99 for 15 min; drop the old index."},
    {"name": "ops/incident-triage",
     "description": "Triage a production retrieval outage (SEV1) calmly and in order.",
     "body": "Acknowledge within 5 minutes; check service health and recent deploys first; if error "
             "rate > 5% roll back before debugging; post status every 30 minutes; file a postmortem."},
    {"name": "rag/chunking-strategy",
     "description": "Choose a chunking strategy when ingesting a new corpus.",
     "body": "Start with paragraph chunking + a 1000-char cap; use semantic chunking when topics "
             "drift; keep tables whole; re-embed the whole corpus if the model/dimension changes."},
]

_lock = threading.Lock()
_seeded = {"done": False, "skill_ids": {}}


# ── tools (procedural memory: how to act) ────────────────────────────────────
def check_service_health(service_name: str) -> dict:
    """Return the current health status for a named internal service."""
    return {"service": service_name, "status": "healthy", "p99_latency_ms": 240}


def estimate_monthly_cost(num_requests: int, tokens_per_request: int,
                          usd_per_million_tokens: float = 0.15) -> float:
    """Estimate monthly LLM token cost (USD) from request volume and average tokens per request."""
    return round(num_requests * tokens_per_request / 1_000_000 * usd_per_million_tokens, 2)


TOOLS = [check_service_health, estimate_monthly_cost]
TOOL_INFO = [
    {"name": "check_service_health", "desc": "Health status for a named service."},
    {"name": "estimate_monthly_cost", "desc": "Monthly LLM token-cost estimate."},
]


def _seed():
    """Store a workflow + a small skillbox once (idempotent, cached)."""
    with _lock:
        if _seeded["done"]:
            return
    provider = store.require()
    # Workflow (runbook)
    try:
        from memorizz.long_term.procedural.workflow.workflow import Workflow

        wf = Workflow(name="incident_response",
                      description="Standard procedure for responding to a production incident.")
        wf.add_step("acknowledge", {"action": "Acknowledge the SEV page within 5 minutes"})
        wf.add_step("triage", {"action": "Run check_service_health on affected services"})
        wf.add_step("mitigate", {"action": "Roll back to last good deploy if error rate > 5%"})
        wf.add_step("communicate", {"action": "Post status to #incidents every 30 minutes"})
        wf.store_workflow(provider)
    except Exception:
        pass
    # Skillbox (how-to guides) — a KnowledgeBase namespace, like notebook §8
    skill_ids: dict[str, dict] = {}
    try:
        from memorizz import KnowledgeBase

        kb = KnowledgeBase(provider)
        try:
            prior = kb.retrieve_knowledge_by_query("skill", namespace=SKILL_NS, limit=50)
            for kid in {h.get("knowledge_base_id") for h in prior if h.get("knowledge_base_id")}:
                kb.delete_knowledge(kid)
        except Exception:
            pass
        for s in SKILLS:
            kid = kb.ingest_knowledge(corpus=s["body"], namespace=SKILL_NS, chunking_strategy="none")
            skill_ids[kid] = s
    except Exception:
        pass
    with _lock:
        _seeded.update(done=True, skill_ids=skill_ids)


def _recall_workflow(message: str) -> dict | None:
    try:
        from memorizz.long_term.procedural.workflow.workflow import Workflow

        matches = Workflow.retrieve_workflows_by_query(message, store.require(), limit=1)
        if matches:
            w = matches[0]
            steps = list((w.to_dict().get("steps") or {}).keys())
            return {"name": getattr(w, "name", "workflow"), "steps": steps}
    except Exception:
        pass
    return None


def _recall_skill(message: str) -> dict | None:
    try:
        from memorizz import KnowledgeBase

        kb = KnowledgeBase(store.require())
        hits = kb.retrieve_knowledge_by_query(message, namespace=SKILL_NS, limit=1)
        for h in hits:
            s = _seeded["skill_ids"].get(h.get("knowledge_base_id"))
            if s:
                return {"name": s["name"], "description": s["description"]}
    except Exception:
        pass
    return None


@router.post("/run")
async def run(req: ProceduralRequest):
    reason = unavailable_reason()
    if reason:
        return sse_response(error_stream(reason))
    await run_in_threadpool(_seed)

    async def events():
        # ① tools the agent can call
        yield {"type": "step", "step": "tools", "status": "done", "data": {"tools": TOOL_INFO}}

        # ② workflow recalled by intent
        yield {"type": "step", "step": "workflow", "status": "running"}
        wf = await run_in_threadpool(_recall_workflow, req.message)
        yield {"type": "step", "step": "workflow", "status": "done", "data": {"workflow": wf}}

        # ③ skillbox manifest
        yield {"type": "step", "step": "skill", "status": "running"}
        sk = await run_in_threadpool(_recall_skill, req.message)
        yield {"type": "step", "step": "skill", "status": "done", "data": {"skill": sk}}

        # ④ the agent answers, using its tools as needed
        yield {"type": "step", "step": "answer", "status": "running"}
        instruction = (
            "You are Memo, an engineering copilot. Use your tools when a question needs a live "
            "value or a calculation. Be concise."
        )
        agent = store.build_agent(instruction, name="Procedural", tools=TOOLS)
        tools_text = " ".join(f"{t['name']}: {t['desc']}" for t in TOOL_INFO)
        win, segs = await run_in_threadpool(
            compute_context_segments, agent, req.message, tools_text=tools_text
        )
        async for ev in prefill_context_events(win, segs):
            yield ev
        result = await run_agent(lambda: agent.run(req.message))
        yield final_context_event(agent, win, segs)
        async for ev in pseudo_stream(result):
            yield ev
        yield {"type": "final", "reply": result}

    return sse_response(events())
