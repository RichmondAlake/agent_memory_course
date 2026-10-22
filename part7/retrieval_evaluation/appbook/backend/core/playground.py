"""The tuning playground: dev candidate lists cached in memory per dataset, then fusion and graph expansion
recomputed in Python for any setting.

The cache holds, for every dev query, the top 100 of the run's best lexical and vector configurations (with their
scores) and the 20 nearest neighbours of each query's top 20 vector hits. It is built on first use, with progress
events, and lives only in this process. The arithmetic is the notebook's batch SQL (§6.2, §6.3, §7.4) in Python.
"""
from __future__ import annotations

import array
import threading
import time

from backend.config import DATASETS, EXCLUDE_SELF
from backend.core import db, evidence, metrics, search

SEED_MAX, M_MAX = 20, 20
_cache: dict[str, dict] = {}
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def qrels(ds: str, query_ids: list[str] | None = None) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for q, d, g in db.rows(f"SELECT query_id, doc_id, grade FROM beir7_{ds}_qrels"):
        if query_ids is None or q in query_ids:
            out.setdefault(q, {})[d] = int(g)
    return out


def stored_query_vectors(ds: str, query_ids: list[str]) -> dict[str, array.array]:
    wanted = set(query_ids)
    out = {}
    for q, v in db.rows(f"SELECT query_id, embedding FROM beir7_{ds}_bge_q"):
        if q in wanted:
            out[q] = v if isinstance(v, array.array) else array.array("f", list(v))
    return out


def status(ds: str) -> dict:
    job = _jobs.get(ds)
    if ds in _cache:
        c = _cache[ds]
        return {"state": "ready", "seconds": c["seconds"], "queries": len(c["queries"]), "run_id": c["run_id"]}
    if job:
        return {"state": job["state"], "events": len(job["events"]), "error": job.get("error")}
    return {"state": "empty"}


def events(ds: str, since: int = 0) -> tuple[list[dict], str]:
    job = _jobs.get(ds)
    if not job:
        return ([{"type": "done", **status(ds)}] if ds in _cache else []), status(ds)["state"]
    return job["events"][since:], job["state"]


def prepare(ds: str, run_id: str) -> None:
    """Start building a dataset's cache in a background thread (no-op if it exists or is building)."""
    if ds not in DATASETS:
        raise ValueError(ds)
    with _lock:
        if (ds in _cache and _cache[ds]["run_id"] == run_id) or (_jobs.get(ds, {}).get("state") == "building"):
            return
        _jobs[ds] = {"state": "building", "events": []}
    threading.Thread(target=_build, args=(ds, run_id), daemon=True).start()


def _emit(ds: str, **event) -> None:
    _jobs[ds]["events"].append(event)


def _build(ds: str, run_id: str) -> None:
    started = time.perf_counter()
    try:
        cfgs = evidence.best_configs(run_id)[ds]
        lex_cfg = search.parse_config("lexical", cfgs["lexical"])
        query_rows = db.rows(f"SELECT query_id, text FROM beir7_{ds}_queries WHERE split = 'dev' ORDER BY query_id")
        texts = {q: t for q, t in query_rows}
        ids = list(texts)
        judged = qrels(ds, set(ids))
        vectors = stored_query_vectors(ds, ids)
        _emit(ds, type="start", queries=len(ids), lexical=cfgs["lexical"], vector=cfgs["vector"])
        lexical, vector = {}, {}
        for i, q in enumerate(ids, 1):
            lexical[q] = search.lexical(ds, texts[q], lex_cfg, qid=q)[0]
            vector[q] = search.vector(ds, vectors[q], qid=q)[0]
            if i % 25 == 0 or i == len(ids):
                _emit(ds, type="progress", stage="searching dev queries", done=i, total=len(ids),
                      seconds=round(time.perf_counter() - started, 1))
        seeds = sorted({d for q in ids for d, _ in vector[q][:SEED_MAX]})
        edges: dict[str, list[tuple]] = {}
        for start in range(0, len(seeds), 500):
            chunk = seeds[start:start + 500]
            binds = {f"s{i}": s for i, s in enumerate(chunk)}
            for src, dst, sim, rnk in db.rows(
                    f"SELECT src, dst, sim, rnk FROM beir7_{ds}_edges WHERE rnk <= {M_MAX} AND src IN "
                    f"({', '.join(':' + b for b in binds)})", **binds):
                edges.setdefault(src, []).append((dst, float(sim), int(rnk)))
            _emit(ds, type="progress", stage="reading graph edges", done=min(start + 500, len(seeds)), total=len(seeds),
                  seconds=round(time.perf_counter() - started, 1))
        seconds = round(time.perf_counter() - started, 1)
        _cache[ds] = {"run_id": run_id, "queries": ids, "qrels": judged, "lexical": lexical, "vector": vector,
                      "edges": edges, "seconds": seconds, "lexical_config": cfgs["lexical"],
                      "vector_config": cfgs["vector"]}
        _jobs[ds]["state"] = "ready"
        _emit(ds, type="done", seconds=seconds, queries=len(ids), edges=sum(len(v) for v in edges.values()))
    except Exception as exc:  # noqa: BLE001 — reported to the page
        _jobs[ds]["state"] = "error"
        _jobs[ds]["error"] = str(exc).splitlines()[0][:300]
        _emit(ds, type="error", message=_jobs[ds]["error"])


def cache(ds: str) -> dict:
    if ds not in _cache:
        raise LookupError("The dev candidate cache for this dataset is not built yet.")
    return _cache[ds]


def _top(scores: dict[str, float]) -> list[str]:
    return [d for d, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:100]]


def fuse_rrf(lex: list[tuple], vec: list[tuple], k: float, w: float, depth: int) -> list[str]:
    scores: dict[str, float] = {}
    for weight, ranked in ((1 - w, lex), (w, vec)):
        for rank, (doc, _) in enumerate(ranked[:depth], start=1):
            scores[doc] = scores.get(doc, 0.0) + weight / (k + rank)
    return _top(scores)


def fuse_weighted(lex: list[tuple], vec: list[tuple], alpha: float, depth: int) -> list[str]:
    scores: dict[str, float] = {}
    for weight, ranked in ((1 - alpha, lex), (alpha, vec)):
        head = ranked[:depth]
        if not head:
            continue
        values = [s for _, s in head]
        lo, hi = min(values), max(values)
        for doc, s in head:
            norm = (s - lo) / (hi - lo) if hi > lo else 1.0
            scores[doc] = scores.get(doc, 0.0) + weight * norm
    return _top(scores)


def expand(vec: list[tuple], edges: dict, m: int, seeds: int, decay: float, exclude: str | None) -> list[str]:
    scores = {doc: sim for doc, sim in vec}
    support: dict[str, float] = {}
    for doc, sim in vec[:seeds]:
        for dst, edge_sim, rnk in edges.get(doc, ()):
            if rnk <= m and dst != exclude:
                support[dst] = support.get(dst, 0.0) + sim * edge_sim
    for doc, s in support.items():
        scores[doc] = scores.get(doc, 0.0) + decay * s
    return _top(scores)


def score(ds: str, kind: str, params: dict) -> dict:
    """Mean nDCG@10, MRR@10 and R@100 over the dev queries for one setting, with the baselines."""
    c = cache(ds)
    started = time.perf_counter()
    per_query = []
    for q in c["queries"]:
        lex, vec = c["lexical"][q], c["vector"][q]
        if kind == "rrf":
            ranked = fuse_rrf(lex, vec, params["k"], params["w"], params["depth"])
        elif kind == "weighted":
            ranked = fuse_weighted(lex, vec, params["alpha"], params["depth"])
        elif kind == "graph":
            ranked = expand(vec, c["edges"], params["m"], params["seeds"], params["decay"],
                            q if ds in EXCLUDE_SELF else None)
        else:
            raise ValueError(kind)
        per_query.append(metrics.score_ranking(ranked, c["qrels"].get(q, {})))
    result = metrics.mean_metrics(per_query)
    baselines = {name: metrics.mean_metrics([metrics.score_ranking([d for d, _ in c[name][q]], c["qrels"].get(q, {}))
                                             for q in c["queries"]]) for name in ("lexical", "vector")}
    return {"dataset": ds, "kind": kind, "params": params, "queries": len(c["queries"]), **result,
            "baselines": baselines, "ms": round((time.perf_counter() - started) * 1000, 1)}


def reach(ds: str, seeds: int = 10, m: int = 10) -> dict:
    """The notebook's §7.3 on the cached dev lists: can one hop reach what vector search's top 10 missed?"""
    c = cache(ds)
    missed = reachable = hop_relevant = hop_total = tail_relevant = tail_total = 0
    for q in c["queries"]:
        relevant = {d for d, g in c["qrels"].get(q, {}).items() if g > 0}
        top = [d for d, _ in c["vector"][q][:seeds]]
        hop = set()
        for d in top:
            hop.update(dst for dst, _, rnk in c["edges"].get(d, ()) if rnk <= m)
        hop -= set(top) | {q}
        for doc in relevant - set(top):
            missed += 1
            reachable += doc in hop
        hop_relevant += len(hop & relevant)
        hop_total += len(hop)
        tail = [d for d, _ in c["vector"][q][seeds:100]]
        tail_relevant += len(set(tail) & relevant)
        tail_total += len(tail)
    return {"missed": missed, "share_reachable": round(reachable / max(1, missed), 3),
            "hop_precision": round(hop_relevant / max(1, hop_total), 4),
            "tail_precision": round(tail_relevant / max(1, tail_total), 4)}


def chosen(run_id: str, ds: str) -> dict:
    cfgs = evidence.best_configs(run_id)[ds]
    return {"hybrid": search.parse_config("hybrid", cfgs["hybrid"]), "graph": search.parse_config("graph", cfgs["graph"]),
            "lexical": cfgs["lexical"], "vector": cfgs["vector"]}


def memory_mb() -> float:
    """A rough size of the cached lists (for the status line)."""
    n = sum(len(v) for c in _cache.values() for key in ("lexical", "vector") for v in c[key].values())
    e = sum(len(v) for c in _cache.values() for v in c["edges"].values())
    return round((n * 120 + e * 140) / 1e6, 1)

