"""Form Factor 3 — The underwriting workflow, with Clef as the decision model.

A fixed, code-orchestrated pipeline, as in the notebook: extract → measure ‖ ground → decide (Clef) →
gate → explain → review → record. Every step streams an event so the UI draws the pipeline and the
decision tree live. ``/batch`` runs several applications as parallel lanes: the language steps overlap,
while the decision model (one GPU) serves them one at a time, so lanes visibly queue for it.
A referral pauses for a human underwriter (``/underwriter``).
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.core import db
from backend.core import underwriting as uw
from backend.core.sse import sse_response
from backend.schemas import UnderwriterRequest, WorkflowBatchRequest, WorkflowRequest

router = APIRouter(prefix="/api/workflow", tags=["workflow"])
_clef_turn = asyncio.Lock()  # one decision model: lanes take turns, and the wait is reported as 'queued'


def _require_db() -> None:
    if not db.ready():
        raise HTTPException(503, f"Oracle AI Database is not ready: {db.status()['error'] or 'still starting'}")


async def run_lane(lane: str, email: str, emit, max_revisions: int = 1) -> dict:
    """One application through the whole pipeline; every step is reported through ``emit``."""
    started = time.perf_counter()

    async def step(name: str, status: str, **data):
        await emit({"lane": lane, "type": "step", "step": name, "status": status,
                    "t": round(time.perf_counter() - started, 2), **({"data": data} if data else {})})

    try:
        await step("extract", "running")
        app = await asyncio.to_thread(uw.extract_application, email)
        await step("extract", "done", application=app)

        # ② measure and ③ ground do not depend on each other, so they run side by side.
        await step("measure", "running")
        await step("ground", "running")
        rules, versions = await asyncio.to_thread(uw.current_policy)
        ratios, policy_text = await asyncio.gather(asyncio.to_thread(uw.measure, app, rules),
                                                   asyncio.to_thread(uw.decision_policy_text))
        use = app["property_use"]
        await step("measure", "done", ratios=ratios,
                   limits={"max_dti": rules["max_dti"], "max_ltv": rules["max_ltv"][use],
                           "min_reserve_months": rules["min_reserve_months"][use],
                           "min_credit_score": rules["min_credit_score"]})
        await step("ground", "done", sections=[{"doc_id": d, "version": versions[d]} for d in uw.DECISION_SECTIONS])

        if _clef_turn.locked():
            await step("decide", "queued")
        async with _clef_turn:
            clef = uw.clef_status()
            await step("decide", "loading" if clef["status"] in ("not loaded", "loading") else "running")
            decision = await asyncio.to_thread(uw.decide, app, ratios, rules, policy_text)
        answers = decision["answers"]
        await step("decide", "done", answers=answers, latency_ms=decision["latency_ms"], usage=decision["usage"],
                   request=decision["request"])

        outcome, review_reasons = uw.gate(answers, app, ratios, rules)
        tree = uw.decision_tree(answers, app, ratios, rules, outcome)
        await step("gate", "done", outcome=outcome, review_reasons=review_reasons, tree=tree)

        reasons = uw.principal_reasons(answers, app, ratios, rules) if outcome == "decline" else []
        await step("explain", "running")
        letter = await asyncio.to_thread(uw.draft_letter, app, outcome, reasons)
        await step("explain", "done", letter=letter, attempt=1)
        verdict = None
        for attempt in range(1, max_revisions + 2):
            await step("review", "running", attempt=attempt)
            verdict = await asyncio.to_thread(uw.review_letter, outcome, reasons, letter)
            await step("review", "done", attempt=attempt, **verdict)
            if verdict["approved"] or attempt > max_revisions:
                break
            await step("explain", "running", attempt=attempt + 1, feedback=verdict["feedback"])
            letter = await asyncio.to_thread(uw.draft_letter, app, outcome, reasons, verdict["feedback"])
            await step("explain", "done", letter=letter, attempt=attempt + 1)

        await step("record", "running")
        application_id = await asyncio.to_thread(uw.save_application, app, email)
        decision_id = await asyncio.to_thread(uw.save_decision, application_id, outcome, answers, ratios, reasons,
                                              review_reasons, versions, f"workflow · {uw.clef_id()}", letter)
        await step("record", "done", application_id=application_id, decision_id=decision_id)
        summary = {"lane": lane, "type": "lane_done", "applicant": app["applicant"], "outcome": outcome,
                   "confidence": answers["decision"]["confidence"], "reasons": reasons + review_reasons,
                   "application_id": application_id, "decision_id": decision_id,
                   "seconds": round(time.perf_counter() - started, 1)}
        await emit(summary)
        if outcome == "refer":
            await emit({"lane": lane, "type": "handoff", "application_id": application_id,
                        "applicant": app["applicant"], "reasons": review_reasons})
        return summary
    except Exception as exc:  # noqa: BLE001 — the lane fails visibly; other lanes continue
        await emit({"lane": lane, "type": "error", "message": f"{type(exc).__name__}: {exc}"[:400]})
        return {"lane": lane, "error": str(exc)}


def _stream(lanes: dict[str, str], max_revisions: int = 1):
    async def events():
        queue: asyncio.Queue = asyncio.Queue()
        yield {"type": "start", "lanes": [{"lane": key, "applicant": uw.SAMPLE_APPLICATIONS.get(key, (key,))[0]}
                                         for key in lanes]}
        tasks = [asyncio.create_task(run_lane(key, email, queue.put, max_revisions)) for key, email in lanes.items()]
        pending = set(tasks)
        while pending:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(pending | {getter}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield getter.result()
            else:
                getter.cancel()
            pending -= {t for t in done if t is not getter}
        while not queue.empty():
            yield queue.get_nowait()
        yield {"type": "all_done", "results": [t.result() for t in tasks]}

    return sse_response(events())


@router.get("/samples")
def samples() -> dict:
    return {"samples": uw.sample_list()}


@router.post("/run")
async def run(req: WorkflowRequest):
    _require_db()
    return _stream({"single": req.email}, req.max_revisions)


@router.post("/batch")
async def batch(req: WorkflowBatchRequest):
    """Several applications at once, as parallel lanes."""
    _require_db()
    unknown = [s for s in req.samples if s not in uw.SAMPLE_APPLICATIONS]
    if unknown:
        raise HTTPException(400, f"Unknown samples: {unknown}")
    return _stream({key: uw.SAMPLE_APPLICATIONS[key][2] for key in dict.fromkeys(req.samples)})


@router.post("/underwriter")
async def underwriter(req: UnderwriterRequest) -> dict:
    """A human underwriter resolves a referral: a decision row and a case note are appended."""
    _require_db()
    return await run_in_threadpool(uw.record_human_decision, req.application_id, req.outcome, req.note)


@router.get("/decisions")
async def decisions() -> dict:
    _require_db()
    return {"decisions": await run_in_threadpool(uw.recent_decisions)}
