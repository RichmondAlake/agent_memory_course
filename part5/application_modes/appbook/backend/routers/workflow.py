"""Workflow mode — multi-step, goal-oriented, stateful process execution.

A mortgage-approval pipeline: identity -> credit -> income -> DTI -> decide.
The earlier stages are DETERMINISTIC CODE — they have no LLM call and therefore
no system prompt; what they carry is *working state*. The decision NODE is the
one place an LLM runs (mirroring "the LLM reasons inside nodes"): there a real
system prompt (underwriter instructions + recalled policy) + the assembled
working state form an actual context window, measured with count_tokens.
Memory profile: working state + tool outputs (the audit trail).
"""
from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.anthropic_client import MODEL, client, text_of
from backend.core.contextwin import block as ctx_block
from backend.core.contextwin import count_tokens as ctx_count
from backend.core.contextwin import window as ctx_window
from backend.core.memory import store
from backend.core.sse import sse_response
from backend.schemas import WorkflowRequest

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

USER_ID = "underwriter-alex"
AGENT_ID = "mortgage-workflow-v1"

POLICY_FACTS = [
    "Minimum acceptable credit score for conventional loans is 620.",
    "Maximum acceptable debt-to-income ratio is 43%.",
    "Loans above $1.5M require manual senior-underwriter review regardless of the automated decision.",
]
POLICY_GUIDELINES = [
    "If identity verification fails, deny the application without assessing credit or income.",
    "Never approve an application whose debt-to-income ratio exceeds the documented maximum.",
]

DECIDE_SYSTEM = (
    "You are a senior mortgage underwriter. The automated gates have ALREADY decided the "
    "outcome — do not change it. Using the applicant's working state and the policy in "
    "context, write a concise 1-2 sentence rationale explaining the decision and citing the "
    "relevant policy."
)

# Preset applicant fixtures (in production these come from KYC / bureau / payroll APIs).
APPLICANTS = {
    "A-001": {"name": "J. Patel", "identity": True, "credit": 742, "income": 11_500, "debt": 2_100, "loan": 480_000},
    "A-002": {"name": "M. Johansson", "identity": True, "credit": 598, "income": 6_800, "debt": 3_400, "loan": 320_000},
    "A-003": {"name": "R. Okafor", "identity": False, "credit": 710, "income": 9_200, "debt": 1_600, "loan": 1_800_000},
    "A-004": {"name": "D. Nguyen", "identity": True, "credit": 705, "income": 10_200, "debt": 2_900, "loan": 1_650_000},
}

WS_NOTE = ("These stages are deterministic code — no LLM, no system prompt. The blocks are the "
           "WORKING STATE being assembled for the one LLM call at the decision node.")

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
        already = store.search("minimum credit score policy", user_id=USER_ID, agent_id=AGENT_ID,
                               record_types=["fact"], max_results=1)
        if not already:
            store.add_typed(POLICY_FACTS, "fact", user_id=USER_ID, agent_id=AGENT_ID, metadata={"kind": "policy"})
            store.add_typed(POLICY_GUIDELINES, "guideline", user_id=USER_ID, agent_id=AGENT_ID, metadata={"kind": "policy"})
        _seeded = True


def _audit(aid: str, stage: str, outcome: str, rationale: str) -> dict:
    content = f"[{stage}] applicant={aid} outcome={outcome}. {rationale}"
    store.add_memory(content, user_id=USER_ID, agent_id=AGENT_ID,
                     metadata={"applicant_id": aid, "stage": stage, "outcome": outcome})
    return {"content": content, "record_type": "memory"}


@router.get("/applicants")
def applicants() -> dict:
    return {"applicants": [{"id": k, **v} for k, v in APPLICANTS.items()]}


@router.post("/run")
async def run(req: WorkflowRequest):
    _ensure_seeded()
    aid = req.applicant_id if req.applicant_id in APPLICANTS else "A-001"
    a = APPLICANTS[aid]

    async def events():
        wstate: dict = {"applicant_id": aid, "name": a["name"], "loan": a["loan"]}
        ctx = [ctx_block("input", "Working state · applicant record",
                         json.dumps(wstate, indent=2))]
        audit_lines: list[str] = []

        def emit_ctx():
            return {"type": "context", "window": ctx_window(list(ctx), note=WS_NOTE)}

        async def recall(step, query, record_types):
            yield {"type": "step", "step": step, "status": "running"}
            hits = store.search(query, user_id=USER_ID, agent_id=AGENT_ID,
                                record_types=record_types, max_results=2)
            if hits:
                yield {"type": "memory_recall", "step": step, "hits": hits}
                ctx.append(ctx_block("memory", f"Policy recalled · {step}",
                                     "\n".join(h["formatted_content"] for h in hits)))
            await asyncio.sleep(0.12)

        def write_audit(step, outcome, rationale):
            rec = _audit(aid, step, outcome, rationale)
            audit_lines.append(rec["content"])
            ctx.append(ctx_block("state", f"{step} → {outcome}", rec["content"]))
            return rec

        async def decide_node(decision, reason):
            # The one LLM call: recall policy, assemble a real context window, reason.
            yield {"type": "step", "step": "decide", "status": "running"}
            try:
                hits = store.search("underwriting decision thresholds and escalation rules",
                                    user_id=USER_ID, agent_id=AGENT_ID,
                                    record_types=["fact", "guideline"], max_results=4)
            except Exception:  # noqa: BLE001 — a transient embedder/network blip shouldn't blank the run
                hits = []
            if hits:
                yield {"type": "memory_recall", "step": "decide", "hits": hits}
            policy_txt = "\n".join(h["formatted_content"] for h in hits) or "(none)"
            system = f"{DECIDE_SYSTEM}\n\nPOLICY IN CONTEXT:\n{policy_txt}"
            user_msg = ("Applicant working state:\n" + json.dumps(wstate, indent=2)
                        + f"\n\nDeterministic gate result: {decision.upper()} — {reason}")
            msgs = [{"role": "user", "content": user_msg}]
            measured = await run_in_threadpool(ctx_count, system, msgs)
            try:
                resp = await run_in_threadpool(
                    lambda: client.messages.create(model=MODEL, max_tokens=180,
                                                   system=system, messages=msgs))
                rationale = text_of(resp).strip() or reason
            except Exception:  # noqa: BLE001
                rationale = reason
            decide_ctx = [
                ctx_block("system", "System prompt · underwriter instructions + recalled policy", system),
                ctx_block("user", "User message · assembled working state + gate result", user_msg),
                ctx_block("assistant", "Assistant message · decision rationale", rationale),
            ]
            yield {"type": "context", "window": ctx_window(
                decide_ctx, measured=measured,
                note="The decision node is the workflow's one LLM call — so a real system prompt "
                     "enters the context window here. Earlier stages were deterministic code.")}
            rec = write_audit("decision", decision, reason)
            yield {"type": "memory_write", "step": "decide", "record": rec}
            yield {"type": "step", "step": "decide", "status": "done",
                   "data": {"decision": decision, "reason": reason}}
            yield {"type": "final", "applicant": aid, "name": a["name"],
                   "decision": decision, "reason": reason, "rationale": rationale}
            # CONTEXT CARD — consolidate the run into OAMP's working-memory block
            tid = f"workflow-{aid}"
            store.thread_add(tid, "user", f"Review application {aid} ({a['name']}), loan ${a['loan']:,}.",
                             user_id=USER_ID, agent_id=AGENT_ID)
            store.thread_add(tid, "assistant", f"Decision: {decision}. {rationale}\nAudit trail:\n"
                             + "\n".join(audit_lines), user_id=USER_ID, agent_id=AGENT_ID)
            card = store.thread_context_card(tid, user_id=USER_ID, agent_id=AGENT_ID)
            if card:
                yield {"type": "context_card", "card": card}

        # ① identity ────────────────────────────────────────────────────────
        async for ev in recall("identity", "identity verification failure rule", ["guideline"]):
            yield ev
        ok = a["identity"]; wstate["identity_verified"] = ok
        rec = write_audit("identity", "pass" if ok else "fail",
                          "Documents matched." if ok else "Document mismatch — re-submission required.")
        yield {"type": "memory_write", "step": "identity", "record": rec}
        yield {"type": "step", "step": "identity", "status": "done", "data": {"verified": ok}}
        yield emit_ctx()
        if not ok:
            async for ev in decide_node("deny", "Identity not verified."):
                yield ev
            return

        # ② credit ──────────────────────────────────────────────────────────
        async for ev in recall("credit", "minimum acceptable credit score", ["fact"]):
            yield ev
        score = a["credit"]; wstate["credit_score"] = score
        rec = write_audit("credit", f"score={score}", f"Bureau score {score}.")
        yield {"type": "memory_write", "step": "credit", "record": rec}
        yield {"type": "step", "step": "credit", "status": "done", "data": {"score": score}}
        yield emit_ctx()
        if score < 620:
            async for ev in decide_node("deny", f"Credit score {score} below 620 minimum."):
                yield ev
            return

        # ③ income + ④ DTI ──────────────────────────────────────────────────
        async for ev in recall("income", "accepted income documentation", ["fact"]):
            yield ev
        inc, debt = a["income"], a["debt"]
        wstate["monthly_income"] = inc; wstate["monthly_debt"] = debt
        rec = write_audit("income", f"inc={inc},debt={debt}", "Income & obligations verified.")
        yield {"type": "memory_write", "step": "income", "record": rec}
        yield {"type": "step", "step": "income", "status": "done", "data": {"income": inc, "debt": debt}}
        yield emit_ctx()

        async for ev in recall("dti", "maximum acceptable debt to income ratio", ["fact"]):
            yield ev
        dti = (debt / inc) if inc else 1.0
        wstate["dti_ratio"] = round(dti, 3)
        rec = write_audit("dti", f"ratio={dti:.3f}", f"Computed DTI {dti:.1%}.")
        yield {"type": "memory_write", "step": "dti", "record": rec}
        yield {"type": "step", "step": "dti", "status": "done", "data": {"dti": dti}}
        yield emit_ctx()

        if dti > 0.43:
            decision, reason = "deny", f"DTI {dti:.1%} exceeds 43% ceiling."
        elif a["loan"] > 1_500_000:
            decision, reason = "manual_review", f"Loan ${a['loan']:,} above $1.5M jumbo threshold."
        else:
            decision, reason = "approve", f"All gates passed (score {score}, DTI {dti:.1%})."

        async for ev in decide_node(decision, reason):
            yield ev

    return sse_response(events())


@router.get("/audit")
def audit(applicant_id: str = "A-001") -> dict:
    hits = store.search(f"audit trail for applicant {applicant_id}", user_id=USER_ID,
                        agent_id=AGENT_ID, record_types=["memory"], max_results=12)
    return {"trail": hits}
