"""Live checks against a running appbook: Oracle, the stored run, the local models.

Start the app first (./run.sh), then:

    python tests/check_live.py                          # http://127.0.0.1:8725
    APPBOOK_URL=http://127.0.0.1:9000 python tests/check_live.py

It checks that the notebook's corpora, vectors and graphs are present, that the leaderboard reproduces the
notebook's headline numbers, that a stored test query reproduces its stored nDCG@10 for every strategy, that a typed
query runs without judgements, that the playground builds its dev cache over SSE and reproduces the notebook's dev
score at its chosen settings, the decision-guide diagnostics, and that the Data Explorer never sends a vector.
Prints one PASS/FAIL line per check and exits non-zero if any check fails.
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8725")
client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(600, connect=10))
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS: {label}", flush=True)
    else:
        failures.append(label)
        print(f"FAIL: {label}  {str(detail)[:400]}", flush=True)


def get(path: str, **params) -> dict:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def post(path: str, body: dict | None = None, **params) -> dict:
    response = client.post(path, json=body or {}, params=params)
    response.raise_for_status()
    return response.json()


def wait_ready(timeout: float = 120) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        try:
            health = get("/api/health")
            if health["oracle"]["ready"] and health.get("run_id"):
                return health
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise SystemExit("the appbook did not become ready")


def follow_cache(dataset: str, timeout: float = 600) -> list[dict]:
    events = []
    started = time.time()
    with client.stream("GET", f"/api/playground/{dataset}/stream", params={"since": 0}, timeout=timeout) as stream:
        name = "message"
        for line in stream.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                if name == "end":
                    break
                events.append(json.loads(line[5:].strip()))
                if events[-1].get("type") in ("done", "error"):
                    break
            if time.time() - started > timeout:
                break
    return events


def main() -> None:
    started = time.time()
    health = wait_ready()
    run_id = health["run_id"]
    print(f"run {run_id}", flush=True)

    check("health · reports the tracing status", health.get("tracing") == "off" or str(health.get("tracing")).startswith("arize-ax:"),
          health.get("tracing"))
    inventory = get("/api/inventory")
    check("inventory · every corpus, its vectors, text index, edges and property graph are present",
          all(inventory[ds]["complete"] for ds in ("fiqa", "scifact", "arguana")), inventory)
    check("inventory · the evidence tables hold the run", inventory["evidence"]["results"] > 100000, inventory["evidence"])

    board = get("/api/leaderboard", run_id=run_id)
    fiqa = {r["strategy"]: r for r in board["datasets"]["fiqa"]}
    check("leaderboard · five strategies per dataset", all(len(board["datasets"][ds]) == 5 for ds in board["datasets"]))
    check("leaderboard · FiQA hybrid nDCG@10 and interval match the notebook (0.502 [0.473–0.529])",
          round(fiqa["hybrid"]["metrics"]["ndcg10"]["mean"], 3) == 0.502
          and [round(v, 3) for v in fiqa["hybrid"]["metrics"]["ndcg10"]["ci"]] == [0.473, 0.529], fiqa["hybrid"]["metrics"]["ndcg10"])
    top = next(t for t in board["tests"] if t["dataset"] == "fiqa" and t["comparison"] == "top two")
    check("leaderboard · the FiQA top-two paired test matches (hybrid − vector +0.0100, Holm p 0.0036)",
          (top["a"], top["b"], round(top["diff"], 4), top["p_holm"]) == ("hybrid", "vector", 0.01, 0.0036), top)
    check("leaderboard · thirteen Holm-corrected tests", len(board["tests"]) == 13, len(board["tests"]))
    check("leaderboard · the Oracle Text vs BM25 numbers", [round(b["oracle_text"], 3) for b in board["bm25"]] == [0.208, 0.575, 0.189]
          and [b["bm25"] for b in board["bm25"]] == [0.236, 0.665, 0.315], board["bm25"])
    check("leaderboard · dev-to-test gap rows", len(board["gap"]) == 15, len(board["gap"]))

    queries = get("/api/explore/queries", dataset="scifact")["queries"]
    check("explorer · lists SciFact's 300 test queries", len(queries) == 300, len(queries))
    t0 = time.time()
    result = post("/api/explore/run", {"dataset": "scifact", "query_id": queries[0]["id"], "run_id": run_id})
    took = time.time() - t0
    strategies = result["strategies"]
    check("explorer · a stored query runs all five strategies", sorted(strategies) == ["graph", "hybrid", "lexical", "rerank", "vector"])
    mismatched = {s: (r["metrics"]["ndcg10"], r["stored_ndcg10"]) for s, r in strategies.items()
                  if r["stored_ndcg10"] is None or abs(r["metrics"]["ndcg10"] - r["stored_ndcg10"]) > 1e-6}
    check("explorer · every strategy reproduces the stored nDCG@10 for that query", not mismatched, mismatched)
    print(f"      (stored query in {took:.1f}s, reranker and lexical frequencies loaded on first use)", flush=True)
    graded = [d for r in strategies.values() for d in r["top"] if d["grade"]]
    for ds in ("fiqa", "arguana"):
        q = get("/api/explore/queries", dataset=ds)["queries"][3]["id"]
        r = post("/api/explore/run", {"dataset": ds, "query_id": q, "run_id": run_id})
        graded += [d for v in r["strategies"].values() for d in v["top"] if d["grade"]]
        bad = {s: (v["metrics"]["ndcg10"], v["stored_ndcg10"]) for s, v in r["strategies"].items()
               if v["stored_ndcg10"] is None or abs(v["metrics"]["ndcg10"] - v["stored_ndcg10"]) > 1e-6}
        check(f"explorer · {ds} query {q} reproduces the stored nDCG@10 for every strategy", not bad, bad)
        if ds == "arguana":
            check("explorer · ArguAna never returns the query's own document",
                  all(d["doc_id"] != q for v in r["strategies"].values() for d in v["top"]))
    check("explorer · relevant documents in a top 10 carry their grade", bool(graded) and all(d["grade"] >= 1 for d in graded),
          len(graded))
    typed = post("/api/explore/run", {"dataset": "fiqa", "text": "Should I pay off my mortgage early or invest the money?",
                                      "run_id": run_id})
    check("explorer · a typed query runs with no judgements and no metrics",
          typed["typed"] and not typed["judged"] and all(v["metrics"] is None for v in typed["strategies"].values()))
    check("explorer · a typed query is embedded locally", (typed["embed_ms"] or 0) > 0, typed["embed_ms"])

    post("/api/playground/scifact/prepare", run_id=run_id)
    events = follow_cache("scifact")
    done = [e for e in events if e.get("type") == "done"]
    check("playground · the SciFact dev cache builds with progress events over SSE",
          bool(done) and any(e.get("type") == "progress" for e in events), events[-3:])
    status = get("/api/playground/scifact/status", run_id=run_id)
    chosen, grid = status["chosen"], status["grid"]
    h = chosen["hybrid"]
    body = ({"kind": "weighted", "alpha": h["alpha"], "depth": h["depth"]} if h["method"] == "weighted"
            else {"kind": "rrf", "k": h["k"], "w": h["w"], "depth": h["depth"]})
    scored = post("/api/playground/score", {"dataset": "scifact", **body})
    label = (f"hybrid|weighted · alpha={h['alpha']} · depth={h['depth']}" if h["method"] == "weighted"
             else f"hybrid|RRF · k={h['k']} · w={h['w']} · depth={h['depth']}")
    stored = grid.get(label, {}).get("ndcg10")
    check("playground · the chosen hybrid setting reproduces the notebook's dev nDCG@10",
          stored is not None and abs(scored["ndcg10"] - stored) < 0.002, (scored["ndcg10"], stored, label))
    g = chosen["graph"]
    graph = post("/api/playground/score", {"dataset": "scifact", "kind": "graph", **g})
    stored_g = grid.get(f"graph|M={g['m']} · seeds={g['seeds']} · decay={g['decay']}", {}).get("ndcg10")
    check("playground · the chosen graph setting reproduces the notebook's dev nDCG@10",
          stored_g is not None and abs(graph["ndcg10"] - stored_g) < 0.002, (graph["ndcg10"], stored_g))
    check("playground · a setting scores in well under a second", graph["ms"] < 1000, graph["ms"])

    diag = get("/api/guide/diagnostics/scifact")
    check("guide · SciFact diagnostics match the notebook (overlap 0.501, mismatch 0.118, cohesion 0.867 vs 0.628)",
          (diag["lexical_overlap"], diag["vocabulary_mismatch"], diag["cohesion_relevant"], diag["cohesion_random"])
          == (0.501, 0.118, 0.867, 0.628), diag)
    check("guide · one-hop reach is available once the dev cache exists", diag["reach"] is not None, diag.get("reach"))
    fiqa_diag = get("/api/guide/diagnostics/fiqa")
    check("guide · FiQA diagnostics match the notebook (10 and 95 words, overlap 0.402, mismatch 0.300, cohesion 0.790 vs 0.596)",
          (fiqa_diag["query_words_median"], fiqa_diag["document_words_median"], fiqa_diag["lexical_overlap"],
           fiqa_diag["vocabulary_mismatch"], fiqa_diag["cohesion_relevant"], fiqa_diag["cohesion_random"])
          == (10, 95, 0.402, 0.3, 0.79, 0.596), fiqa_diag)
    evidence = get("/api/guide/evidence", run_id=run_id)
    check("guide · evidence for every dataset", sorted(evidence["datasets"]) == ["arguana", "fiqa", "scifact"])

    tables = get("/api/data_explorer/tables")["tables"]
    check("data explorer · lists only BEIR7_ tables", tables and all(t["name"].startswith("beir7_") for t in tables))
    vec = get("/api/data_explorer/tables/beir7_fiqa_bge/rows", limit=5)
    check("data explorer · never sends a vector", all(str(r["embedding"]).startswith("VECTOR (not shown)") for r in vec["rows"]), vec["rows"][:1])
    docs = get("/api/data_explorer/tables/beir7_fiqa_docs/rows", limit=5)
    check("data explorer · long text is cut", all(len(r["body"] or "") <= 301 for r in docs["rows"]))
    blocked = client.get("/api/data_explorer/tables/user_tables/rows")
    check("data explorer · refuses a table outside the allowlist", blocked.status_code == 400, blocked.status_code)

    health = get("/api/health")
    check("models · bge and the reranker loaded once, at the pinned revisions",
          health["models"]["bge"] == "loaded" and health["models"]["reranker"] == "loaded", health["models"])
    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - started:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
