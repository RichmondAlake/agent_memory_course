"""The graders: ask one check of every grader, read a validation run back, and the policy the suites use."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.core import db, decision, graders, stats
from backend.schemas import TryCheck

router = APIRouter(prefix="/api/graders", tags=["graders"])


@router.post("/try")
async def try_check(body: TryCheck):
    """Ask every available grader the same check; return P(yes), latency, cost and the judge's reason."""
    if body.check == "states_fact" and not body.fact:
        raise HTTPException(422, "states_fact needs a fact")
    if body.check == "uses_old_value" and not body.old:
        raise HTTPException(422, "uses_old_value needs the outdated value")
    plan = graders.policy()[body.check]

    def run_all():
        out = []
        for name in decision.available():
            try:
                p, seconds, usage = graders.dm_check(name, body.question, body.answer, body.fact, body.old, checks=(body.check,))
                low, high = plan["band"] or stats.escalation_band(plan["threshold"])
                out.append({"grader": name, "p": p[body.check], "ms": round(1000 * seconds), "cost_usd": usage["cost_usd"],
                            "chosen": plan["grader"] == name, "escalates": plan["grader"] == name and low < p[body.check] < high})
            except Exception as exc:  # noqa: BLE001 — one grader failing should not hide the others
                out.append({"grader": name, "error": f"{type(exc).__name__}: {exc}"[:200]})
        try:
            verdict, used = graders.judge_checks(body.question, body.answer, body.fact, body.old)
            out.append({"grader": "judge", "p": float(verdict[body.check]), "ms": round(1000 * used["seconds"]),
                        "cost_usd": used["cost_usd"], "reason": verdict.get("reason"), "chosen": plan["grader"] == "judge"})
        except Exception as exc:  # noqa: BLE001
            out.append({"grader": "judge", "error": f"{type(exc).__name__}: {exc}"[:200]})
        return out

    question = graders.CHECKS[body.check].format(fact=body.fact, old=body.old)
    return {"check": body.check, "question": question, "answers": await run_in_threadpool(run_all), "policy": plan}


@router.get("/policy")
def policy(refresh: bool = False):
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    return {"policy": graders.policy(refresh=refresh)}
