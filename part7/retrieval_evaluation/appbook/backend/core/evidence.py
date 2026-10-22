"""The stored run, read back: runs, best configurations, per-query results, the leaderboard and its statistics.

Every number is recomputed from BEIR7_RESULTS rows with the notebook's own functions and seed, so the leaderboard
reproduces the notebook's §9.2 and §9.5.
"""
from __future__ import annotations

import hashlib
import json
import threading

import numpy as np

from backend.config import DATASETS, METRICS, STRATEGIES, settings
from backend.core import db, metrics

_cache: dict = {}
_lock = threading.Lock()


def runs() -> list[dict]:
    rows = db.sql("""
        SELECT r.run_id, r.started_at, r.minutes, JSON_SERIALIZE(r.settings) AS settings,
               (SELECT COUNT(*) FROM beir7_results x WHERE x.run_id = r.run_id) AS results,
               (SELECT COUNT(*) FROM beir7_results x WHERE x.run_id = r.run_id AND x.split = 'test') AS test_rows
        FROM   beir7_runs r ORDER BY r.started_at DESC""")
    for r in rows:
        r["started_at"] = r["started_at"].isoformat() if hasattr(r["started_at"], "isoformat") else r["started_at"]
        try:
            r["settings"] = json.loads(r["settings"] or "{}")
        except ValueError:
            r["settings"] = {}
    return rows


def default_run() -> str | None:
    all_runs = runs()
    if settings.run_id and any(r["run_id"] == settings.run_id for r in all_runs):
        return settings.run_id
    with_tests = [r for r in all_runs if r["test_rows"]]
    return (with_tests or all_runs or [{}])[0].get("run_id")


def resolve(run_id: str | None) -> str:
    known = {r["run_id"] for r in runs()}
    if run_id and run_id in known:
        return run_id
    found = default_run()
    if not found:
        raise LookupError("No run in BEIR7_RUNS: run the notebook first.")
    return found


def best_configs(run_id: str) -> dict:
    """Per dataset, the configuration of each strategy carried to the test set (the HNSW side run is listed apart)."""
    out = {ds: {} for ds in DATASETS}
    for r in db.sql("""SELECT DISTINCT dataset, strategy, config FROM beir7_results
                       WHERE run_id = :r AND split = 'test'""", r=run_id):
        if r["dataset"] not in out:
            continue
        key = "vector_hnsw" if "HNSW" in r["config"] else r["strategy"]
        out[r["dataset"]][key] = r["config"]
    return out


def query_order(ds: str, ids: list[str], seed: int) -> list[str]:
    """The notebook's order of a test set: sorted ids, or hash order for ArguAna's hash split."""
    if ds == "arguana":
        return sorted(ids, key=lambda q: hashlib.sha1(f"{seed}:{q}".encode()).hexdigest())
    return sorted(ids)


def per_query(run_id: str, ds: str, strategy: str, config: str, split: str) -> dict[str, dict]:
    rows = db.sql(f"""SELECT query_id, {', '.join(METRICS)}, latency_ms FROM beir7_results
                      WHERE run_id = :r AND dataset = :d AND strategy = :s AND config = :c AND split = :p""",
                  r=run_id, d=ds, s=strategy, c=config, p=split)
    return {r["query_id"]: r for r in rows}


def _seed(run_id: str) -> int:
    for r in runs():
        if r["run_id"] == run_id:
            return int(r["settings"].get("seed", settings.seed))
    return settings.seed


def leaderboard(run_id: str) -> dict:
    with _lock:
        if ("leaderboard", run_id) in _cache:
            return _cache[("leaderboard", run_id)]
    seed = _seed(run_id)
    configs = best_configs(run_id)
    tables, tests, values = {}, [], {}
    for ds, cfgs in configs.items():
        rows = []
        order = None
        for strategy in STRATEGIES:
            if strategy not in cfgs:
                continue
            data = per_query(run_id, ds, strategy, cfgs[strategy], "test")
            order = order or query_order(ds, list(data), seed)
            vals = {m: np.array([data[q][m] for q in order], dtype=float) for m in METRICS}
            values[(ds, strategy)] = vals["ndcg10"]
            lat = np.array([data[q]["latency_ms"] for q in order if data[q]["latency_ms"] is not None], dtype=float)
            rows.append({"strategy": strategy, "config": cfgs[strategy], "queries": len(order),
                         "metrics": {m: {"mean": float(vals[m].mean()), "ci": metrics.bootstrap_ci(vals[m], seed=seed)}
                                     for m in METRICS},
                         "p50_ms": float(np.median(lat)) if len(lat) else None,
                         "p95_ms": float(np.percentile(lat, 95)) if len(lat) else None})
        if "vector_hnsw" in cfgs:
            data = per_query(run_id, ds, "vector", cfgs["vector_hnsw"], "test")
            lat = [r["latency_ms"] for r in data.values() if r["latency_ms"] is not None]
            tables.setdefault("hnsw", {})[ds] = {"config": cfgs["vector_hnsw"],
                                                 "ndcg10": float(np.mean([r["ndcg10"] for r in data.values()])),
                                                 "p50_ms": float(np.median(lat)) if lat else None}
        tables[ds] = rows
        # the notebook's §9.5: the top two, then every other strategy against vector search
        ranked = sorted([r for r in rows], key=lambda r: -r["metrics"]["ndcg10"]["mean"])
        if len(ranked) >= 2:
            pairs = [(ranked[0]["strategy"], ranked[1]["strategy"], "top two")]
            pairs += [(s, "vector", "against vector") for s in STRATEGIES
                      if s != "vector" and (ds, s) in values and {s, "vector"} != set(pairs[0][:2])]
            for a, b, kind in pairs:
                result = metrics.paired_test(values[(ds, a)], values[(ds, b)], seed=seed)
                tests.append({"dataset": ds, "comparison": kind, "a": a, "b": b, "diff": result["mean_diff"],
                              "ci": result["ci"], "p": result["p_value"]})
    for t, adjusted in zip(tests, metrics.holm([t["p"] for t in tests])):
        t["p_holm"] = adjusted
        t["significant"] = adjusted < 0.05
    out = {"run_id": run_id, "datasets": {ds: tables.get(ds, []) for ds in DATASETS}, "hnsw": tables.get("hnsw", {}),
           "tests": tests, "gap": dev_test_gap(run_id), "costs": costs(run_id), "bm25": bm25(tables)}
    with _lock:
        _cache[("leaderboard", run_id)] = out
    return out


def dev_test_gap(run_id: str) -> list[dict]:
    return db.sql("""
        WITH s AS (
            SELECT dataset, strategy, config, split, AVG(ndcg10) AS ndcg10, COUNT(*) AS queries
            FROM   beir7_results WHERE run_id = :r GROUP BY dataset, strategy, config, split)
        SELECT d.dataset, d.strategy, d.config, d.queries AS dev_queries, ROUND(d.ndcg10, 4) AS dev_ndcg10,
               ROUND(t.ndcg10, 4) AS test_ndcg10, ROUND(t.ndcg10 - d.ndcg10, 4) AS test_minus_dev
        FROM   s d JOIN s t ON t.dataset = d.dataset AND t.strategy = d.strategy AND t.config = d.config
        WHERE  d.split = 'dev' AND t.split = 'test'
        ORDER  BY d.dataset, d.strategy""", r=run_id)


def costs(run_id: str) -> list[dict]:
    """Build costs: this run's, or for steps it found cached, the latest run that measured them."""
    return db.sql("""
        SELECT dataset, item, seconds, mb, run_id FROM (
            SELECT c.*, ROW_NUMBER() OVER (PARTITION BY dataset, item
                                           ORDER BY CASE WHEN run_id = :r THEN 0 ELSE 1 END, run_id DESC) AS pick
            FROM beir7_costs c)
        WHERE pick = 1 ORDER BY dataset, item""", r=run_id)


def bm25(tables: dict) -> list[dict]:
    """Oracle Text's test nDCG@10 next to BEIR's published BM25 (full corpora), per dataset."""
    out = []
    for ds, spec in DATASETS.items():
        lexical = next((r for r in tables.get(ds, []) if r["strategy"] == "lexical"), None)
        if lexical:
            out.append({"dataset": ds, "oracle_text": lexical["metrics"]["ndcg10"]["mean"], "bm25": spec["bm25"],
                        "config": lexical["config"]})
    return out


def dev_grid(run_id: str, ds: str) -> dict[str, dict]:
    """Mean dev metrics of every configuration the notebook tried on a dataset, by strategy and label."""
    rows = db.sql("""SELECT strategy, config, COUNT(*) AS queries, AVG(ndcg10) AS ndcg10, AVG(mrr10) AS mrr10,
                            AVG(r100) AS r100
                     FROM beir7_results WHERE run_id = :r AND dataset = :d AND split = 'dev'
                     GROUP BY strategy, config""", r=run_id, d=ds)
    return {f"{r['strategy']}|{r['config']}": r for r in rows}
