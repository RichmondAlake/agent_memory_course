"""The query explorer: one query through all five strategies, with each one's best stored configuration.

A stored query (test or dev) uses its stored vector and its judgements; a typed query is embedded with
bge-small-en-v1.5 and has no judgements, so it gets no relevance marks and no metrics.
"""
from __future__ import annotations

import array
import json

from backend.config import DATASETS, EXCLUDE_SELF
from backend.core import db, evidence, metrics, models, search, tracing


def queries(ds: str, split: str = "test") -> list[dict]:
    rows = db.rows(f"""SELECT q.query_id, DBMS_LOB.SUBSTR(q.text, 220, 1),
                              (SELECT COUNT(*) FROM beir7_{ds}_qrels r WHERE r.query_id = q.query_id)
                       FROM beir7_{ds}_queries q WHERE q.split = :s ORDER BY q.query_id""", s=split)
    return [{"id": q, "text": t, "relevant": int(n)} for q, t, n in rows]


def run(ds: str, run_id: str, query_id: str | None, typed: str | None) -> dict:
    """One explorer request; with tracing on, a CHAIN span holds its embedding, retrieval and reranker spans."""
    metadata = {"metadata": json.dumps({"dataset": ds, "run_id": run_id, "query_id": query_id})}
    with tracing.traced_request(f"explore · {DATASETS[ds]['name']}", **metadata) as chain:
        out = _run(ds, run_id, query_id, typed)
        if chain is not None:
            chain.set_attribute("input.value", out["text"][:2000])
            chain.set_attribute("output.value", json.dumps({s: [d["doc_id"] for d in v["top"]]
                                                            for s, v in out["strategies"].items()}))
            chain.set_attribute("output.mime_type", "application/json")
        return out


def _run(ds: str, run_id: str, query_id: str | None, typed: str | None) -> dict:
    cfgs = evidence.best_configs(run_id)[ds]
    lex_cfg = search.parse_config("lexical", cfgs["lexical"])
    embed_ms = None
    if query_id:
        found = db.rows(f"SELECT text, split FROM beir7_{ds}_queries WHERE query_id = :q", q=query_id)
        if not found:
            raise LookupError("No such query in this dataset.")
        query_text, split = found[0]
        vec = db.rows(f"SELECT embedding FROM beir7_{ds}_bge_q WHERE query_id = :q", q=query_id)[0][0]
        qv = vec if isinstance(vec, array.array) else array.array("f", list(vec))
        judged = {d: int(g) for d, g in db.rows(f"SELECT doc_id, grade FROM beir7_{ds}_qrels WHERE query_id = :q",
                                                q=query_id)}
    else:
        query_text, split, judged = (typed or "").strip(), None, {}
        if not query_text:
            raise ValueError("Type a query or pick one.")
        qv, embed_ms = models.embed_query(query_text)
    qid = query_id

    results = {}
    lexical, ms = search.lexical(ds, query_text, lex_cfg, qid=qid)
    results["lexical"] = (lexical, ms, 0.0)
    vector, ms = search.vector(ds, qv, qid=qid, query_text=query_text)
    results["vector"] = (vector, ms, embed_ms or 0.0)
    hybrid, ms = search.hybrid(ds, query_text, qv, search.parse_config("hybrid", cfgs["hybrid"]), lex_cfg, qid=qid)
    results["hybrid"] = (hybrid, ms, embed_ms or 0.0)
    graph, ms = search.graph(ds, qv, search.parse_config("graph", cfgs["graph"]), qid=qid, query_text=query_text)
    results["graph"] = (graph, ms, embed_ms or 0.0)
    rr = search.parse_config("rerank", cfgs["rerank"])
    first, first_ms, _ = results[rr["first_stage"]]
    reranked, rerank_ms = search.rerank(ds, query_text, first, rr["depth"])
    if qid and ds in EXCLUDE_SELF:
        reranked = [r for r in reranked if r[0] != qid]
    results["rerank"] = (reranked, first_ms + rerank_ms, embed_ms or 0.0)

    stored = {}
    if query_id and split:
        for strategy, label in cfgs.items():
            if strategy == "vector_hnsw":
                continue
            row = db.sql("""SELECT ndcg10 FROM beir7_results WHERE run_id = :r AND dataset = :d AND query_id = :q
                            AND split = :s AND strategy = :st AND config = :c""",
                         r=run_id, d=ds, q=query_id, s=split, st=strategy, c=label)
            if row:
                stored[strategy] = row[0]["ndcg10"]

    shown = {d for ranked, _, _ in results.values() for d, _ in ranked[:10]}
    texts = search.bodies(ds, sorted(shown))
    out = {"dataset": ds, "run_id": run_id, "query_id": query_id, "split": split, "text": query_text,
           "typed": query_id is None, "embed_ms": None if embed_ms is None else round(embed_ms, 1),
           "judged": [{"doc_id": d, "grade": g} for d, g in sorted(judged.items())], "strategies": {}}
    for strategy, (ranked, ms, emb) in results.items():
        docs = [d for d, _ in ranked]
        scored = metrics.score_ranking(docs, judged) if judged else None
        out["strategies"][strategy] = {
            "config": cfgs[strategy], "db_ms": round(ms, 1), "embed_ms": round(emb, 1) if emb else None,
            "metrics": None if scored is None else {k: scored[k] for k in ("ndcg10", "p5", "r10")},
            "stored_ndcg10": stored.get(strategy),
            "top": [{"doc_id": d, "score": round(s, 4), "grade": judged.get(d), "text": texts.get(d, "")[:3000]}
                    for d, s in ranked[:10]],
        }
    return out
