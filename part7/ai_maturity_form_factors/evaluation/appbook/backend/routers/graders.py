"""The graders: try one check on every grader, and read a validation run back."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.core import db, evidence, graders, llm, suites
from backend.schemas import TryCheck

router = APIRouter(prefix="/api/graders", tags=["graders"])


@router.post("/try")
async def try_check(body: TryCheck):
    """Ask every available grader the same check; return P(yes), latency and the judge's reason."""
    fields = {k: v for k, v in body.model_dump().items() if k != "kind" and v is not None}
    needed = graders.CHECKS[body.kind][1] + (("fact",) if body.kind == "states_fact" else ())
    missing = [k for k in needed if not fields.get(k)]
    if missing:
        raise HTTPException(422, f"This check needs: {', '.join(missing)}")
    state, question = graders.check_request(body.kind, fields)
    choice = graders.chosen()

    def run_all():
        out = []
        for name in graders.available():
            with llm.meter() as meter:
                try:
                    answer = graders.ask(name, body.kind, fields)
                    out.append({"grader": name, "p": answer["p"], "ms": round(1000 * answer["seconds"]),
                                "reason": answer.get("reason"), "cost_usd": meter.totals()["cost_usd"],
                                "chosen": choice[body.kind]["grader"] == name})
                except Exception as exc:  # noqa: BLE001 — one grader failing should not hide the others
                    out.append({"grader": name, "error": f"{type(exc).__name__}: {exc}"[:200]})
        return out

    return {"kind": body.kind, "state": state, "question": question, "answers": await run_in_threadpool(run_all),
            "chosen": choice[body.kind]}


@router.get("/chosen")
def chosen():
    return {"chosen": graders.chosen()}


@router.get("/report")
def report(run_id: str | None = None):
    """The scoreboard, choices, reliability and blind spots of a validation run (the latest by default)."""
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    run_id = run_id or evidence.latest_run_with("graders")
    if not run_id:
        return {"run_id": None}
    rows = graders.check_rows(run_id)
    return {"run_id": run_id, "checks": len(rows), **suites.graders_report(rows)}
