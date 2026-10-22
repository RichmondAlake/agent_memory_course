"""The decision guide: the dataset diagnostics next to the measured evidence behind each branch of the flowchart."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.config import DATASETS
from backend.core import diagnostics, evidence, playground
from backend.routers.meta import ready
from backend.schemas import Dataset

router = APIRouter(prefix="/api/guide", tags=["guide"])


@router.get("/diagnostics/{dataset}")
def diagnostics_for(dataset: Dataset):
    ready()
    out = dict(diagnostics.compute(dataset))
    try:
        out["reach"] = playground.reach(dataset)
    except LookupError:
        out["reach"] = None
    return out


@router.get("/evidence")
def guide_evidence(run_id: str | None = None):
    ready()
    try:
        run = evidence.resolve(run_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    board = evidence.leaderboard(run)
    tests = {(t["dataset"], t["a"], t["b"]): t for t in board["tests"]}
    rows = {}
    for ds in DATASETS:
        by = {r["strategy"]: r for r in board["datasets"].get(ds, [])}
        nd = {s: r["metrics"]["ndcg10"]["mean"] for s, r in by.items()}
        grid = evidence.dev_grid(run, ds)
        model_dev = {key.split("|")[1].split(" · ")[0]: v["ndcg10"] for key, v in grid.items()
                     if key.startswith("vector|") and key.endswith("· exact")}
        plain_rrf = grid.get("hybrid|RRF · k=60 · w=0.5 · depth=100", {}).get("ndcg10")

        def vs(strategy):
            t = tests.get((ds, strategy, "vector")) or tests.get((ds, "vector", strategy))
            if not t:
                return None
            sign = 1 if t["a"] == strategy else -1
            return {"diff": sign * t["diff"], "p_holm": t["p_holm"], "significant": t["significant"]}

        rows[ds] = {"name": DATASETS[ds]["name"], "ndcg10": nd, "model_dev": model_dev,
                    "plain_rrf_dev": plain_rrf, "vector_dev": model_dev.get("bge-small-en-v1.5"),
                    "hybrid_vs_vector": vs("hybrid"), "graph_vs_vector": vs("graph"), "rerank_vs_vector": vs("rerank"),
                    "rerank_p50_ms": by.get("rerank", {}).get("p50_ms"), "vector_p50_ms": by.get("vector", {}).get("p50_ms"),
                    "hnsw": board["hnsw"].get(ds)}
    return {"run_id": run, "datasets": rows}
