"""The leaderboard: per dataset and strategy, the best tuned configuration on the held-out queries, every metric
with its 95% interval, the Holm-corrected paired tests, the dev-to-test gap, latency and build costs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.core import evidence
from backend.routers.meta import ready

router = APIRouter(prefix="/api", tags=["leaderboard"])


@router.get("/leaderboard")
def leaderboard(run_id: str | None = None):
    ready()
    try:
        return evidence.leaderboard(evidence.resolve(run_id))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
