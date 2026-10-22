"""The five strategies, as the notebook runs them live (§4.3, §5.1, §6.5, §7.6, §8.1), with their best configurations
parsed from the stored run.

Table names are formatted from the fixed dataset keys only; everything that comes from a query is a bind variable.
"""
from __future__ import annotations

import array
import re

from backend.config import DATASETS, EXCLUDE_SELF
import json

from backend.core import db, models, text, tracing

LEXICAL_SQL = """
SELECT doc_id, SCORE(1) AS score
FROM   beir7_{ds}_docs
WHERE  CONTAINS(body, :query, 1) > 0
ORDER  BY SCORE(1) DESC, doc_id
FETCH  FIRST :k ROWS ONLY"""

VECTOR_SQL = """
SELECT doc_id, VECTOR_DISTANCE(embedding, :qv, COSINE) AS distance
FROM   beir7_{ds}_bge
ORDER  BY VECTOR_DISTANCE(embedding, :qv, COSINE)
FETCH  EXACT FIRST :k ROWS ONLY"""

HYBRID_SQL = {
    "RRF": """
WITH lex AS (
    SELECT doc_id, ROW_NUMBER() OVER (ORDER BY s DESC, doc_id) AS rnk
    FROM  (SELECT doc_id, SCORE(1) AS s
           FROM   beir7_{ds}_docs
           WHERE  CONTAINS(body, :query, 1) > 0 AND doc_id <> :exclude
           ORDER  BY SCORE(1) DESC, doc_id
           FETCH  FIRST :depth ROWS ONLY)),
vec AS (
    SELECT doc_id, ROW_NUMBER() OVER (ORDER BY distance) AS rnk
    FROM  (SELECT doc_id, VECTOR_DISTANCE(embedding, :qv, COSINE) AS distance
           FROM   beir7_{ds}_bge
           WHERE  doc_id <> :exclude
           ORDER  BY VECTOR_DISTANCE(embedding, :qv, COSINE)
           FETCH  EXACT FIRST :depth ROWS ONLY))
SELECT doc_id, SUM(w / (:k + rnk)) AS score
FROM   (SELECT doc_id, rnk, 1 - :w AS w FROM lex UNION ALL SELECT doc_id, rnk, :w FROM vec)
GROUP  BY doc_id
ORDER  BY score DESC, doc_id
FETCH  FIRST 100 ROWS ONLY""",
    "weighted": """
WITH lex AS (
    SELECT doc_id, SCORE(1) AS s
    FROM   beir7_{ds}_docs
    WHERE  CONTAINS(body, :query, 1) > 0 AND doc_id <> :exclude
    ORDER  BY SCORE(1) DESC, doc_id
    FETCH  FIRST :depth ROWS ONLY),
vec AS (
    SELECT doc_id, 1 - VECTOR_DISTANCE(embedding, :qv, COSINE) AS s
    FROM   beir7_{ds}_bge
    WHERE  doc_id <> :exclude
    ORDER  BY VECTOR_DISTANCE(embedding, :qv, COSINE)
    FETCH  EXACT FIRST :depth ROWS ONLY),
both AS (
    SELECT doc_id, 'lexical' AS source, s FROM lex
    UNION ALL
    SELECT doc_id, 'vector', s FROM vec),
norm AS (
    SELECT doc_id, source,
           NVL((s - MIN(s) OVER (PARTITION BY source))
               / NULLIF(MAX(s) OVER (PARTITION BY source) - MIN(s) OVER (PARTITION BY source), 0), 1) AS s
    FROM   both)
SELECT doc_id, SUM(CASE source WHEN 'vector' THEN :alpha ELSE 1 - :alpha END * s) AS score
FROM   norm
GROUP  BY doc_id
ORDER  BY score DESC, doc_id
FETCH  FIRST 100 ROWS ONLY""",
}

GRAPH_SQL = """
WITH hits AS (
    SELECT doc_id, VECTOR_DISTANCE(embedding, :qv, COSINE) AS distance
    FROM   beir7_{ds}_bge
    WHERE  doc_id <> :exclude
    ORDER  BY VECTOR_DISTANCE(embedding, :qv, COSINE)
    FETCH  EXACT FIRST 100 ROWS ONLY),
ranked AS (
    SELECT doc_id, 1 - distance AS sim, ROW_NUMBER() OVER (ORDER BY distance) AS rnk
    FROM   hits),
spread AS (
    SELECT g.dst AS doc_id, SUM(r.sim * g.edge_sim) AS support
    FROM   ranked r
    JOIN   GRAPH_TABLE (beir7_{ds}_graph
               MATCH (a IS doc) -[e IS similar_to]-> (b IS doc)
               WHERE e.rnk <= :m
               COLUMNS (a.doc_id AS src, b.doc_id AS dst, e.sim AS edge_sim)) g
           ON g.src = r.doc_id
    WHERE  r.rnk <= :seeds AND g.dst <> :exclude
    GROUP  BY g.dst)
SELECT doc_id, NVL(r.sim, 0) + :decay * NVL(s.support, 0) AS score
FROM   ranked r FULL OUTER JOIN spread s USING (doc_id)
ORDER  BY score DESC, doc_id
FETCH  FIRST 100 ROWS ONLY"""


# ── configurations: the stored labels, parsed ────────────────────────────────────────────────────────────────────
def parse_config(strategy: str, label: str) -> dict:
    """Turn a stored configuration label into parameters, e.g. 'weighted · alpha=0.8 · depth=50'."""
    parts = [p.strip() for p in label.split("·")]
    if strategy == "lexical":
        return {"op": parts[0], "stem": parts[1] == "stem", "keep": int(parts[2].split()[1]) if parts[2].startswith("rarest") else None}
    if strategy == "vector":
        return {"model": parts[0], "exact": "exact" in label}
    values = dict(re.findall(r"(\w+)=([\d.]+)", label))
    if strategy == "hybrid":
        if parts[0] == "RRF":
            return {"method": "RRF", "k": int(values["k"]), "w": float(values["w"]), "depth": int(values["depth"])}
        return {"method": "weighted", "alpha": float(values["alpha"]), "depth": int(values["depth"])}
    if strategy == "graph":
        return {"m": int(values["M"]), "seeds": int(values["seeds"]), "decay": float(values["decay"])}
    if strategy == "rerank":
        match = re.match(r"(\w+) \+ cross-encoder top (\d+)", label)
        return {"first_stage": match.group(1), "depth": int(match.group(2))}
    raise ValueError(f"unknown strategy {strategy}")


def _check(ds: str) -> None:
    if ds not in DATASETS:
        raise ValueError(f"unknown dataset {ds}")


def _exclude(ds: str, qid: str | None) -> str:
    return qid if (qid and ds in EXCLUDE_SELF) else "#none#"


def _retrieval(name: str, ds: str, query_text: str, qid: str | None, **config):
    """A RETRIEVER span (only inside a traced explorer request)."""
    attributes = {}
    if tracing.active():
        attributes = {"input.value": query_text[:2000],
                      "metadata": json.dumps({"dataset": ds, "query_id": qid, **config}, default=str)}
    return tracing.traced(name, "RETRIEVER", **attributes)


def _documents(span, ds: str, ranked: list[tuple]) -> None:
    if span is not None:
        tracing.set_documents(span, "retrieval.documents", ranked, bodies(ds, [d for d, _ in ranked[:10]]))


def _drop_self(ds: str, qid: str | None, rows: list[tuple], k: int = 100) -> list[tuple]:
    if qid and ds in EXCLUDE_SELF:
        rows = [r for r in rows if r[0] != qid]
    return rows[:k]


# ── the strategies ───────────────────────────────────────────────────────────────────────────────────────────────
def lexical(ds: str, query_text: str, cfg: dict, qid: str | None = None, k: int = 100) -> tuple[list[tuple], float]:
    _check(ds)
    query = text.text_query(ds, query_text, cfg["op"], cfg["stem"], cfg["keep"])
    if not query:
        return [], 0.0
    with _retrieval("lexical search", ds, query_text, qid, contains=query) as span:
        rows, ms = db.timed(LEXICAL_SQL.format(ds=ds), query=text.template(query), k=k + 1)
        ranked = _drop_self(ds, qid, [(d, float(s)) for d, s in rows], k)
        _documents(span, ds, ranked)
    return ranked, ms


def vector(ds: str, qv: array.array, qid: str | None = None, k: int = 100,
           query_text: str = "") -> tuple[list[tuple], float]:
    _check(ds)
    with _retrieval("vector search", ds, query_text, qid, model="bge-small-en-v1.5", search="exact") as span:
        rows, ms = db.timed(VECTOR_SQL.format(ds=ds), qv=qv, k=k + 1)
        ranked = _drop_self(ds, qid, [(d, 1 - float(dist)) for d, dist in rows], k)
        _documents(span, ds, ranked)
    return ranked, ms


def hybrid(ds: str, query_text: str, qv: array.array, cfg: dict, lex_cfg: dict, qid: str | None = None):
    _check(ds)
    query = text.text_query(ds, query_text, lex_cfg["op"], lex_cfg["stem"], lex_cfg["keep"])
    binds = {"query": text.template(query), "qv": qv, "depth": cfg["depth"], "exclude": _exclude(ds, qid)}
    binds.update({"k": cfg["k"], "w": cfg["w"]} if cfg["method"] == "RRF" else {"alpha": cfg["alpha"]})
    with _retrieval("hybrid search", ds, query_text, qid, **cfg) as span:
        rows, ms = db.timed(HYBRID_SQL[cfg["method"]].format(ds=ds), **binds)
        ranked = [(d, float(s)) for d, s in rows]
        _documents(span, ds, ranked)
    return ranked, ms


def graph(ds: str, qv: array.array, cfg: dict, qid: str | None = None, query_text: str = ""):
    _check(ds)
    with _retrieval("graph search", ds, query_text, qid, **cfg) as span:
        rows, ms = db.timed(GRAPH_SQL.format(ds=ds), qv=qv, m=cfg["m"], seeds=cfg["seeds"], decay=cfg["decay"],
                            exclude=_exclude(ds, qid))
        ranked = [(d, float(s)) for d, s in rows]
        _documents(span, ds, ranked)
    return ranked, ms


def bodies(ds: str, doc_ids: list[str]) -> dict[str, str]:
    """Document texts for a handful of ids (bind variables, at most 200)."""
    _check(ds)
    ids = list(dict.fromkeys(doc_ids))[:200]
    if not ids:
        return {}
    binds = {f"d{i}": d for i, d in enumerate(ids)}
    rows = db.rows(f"SELECT doc_id, body FROM beir7_{ds}_docs WHERE doc_id IN ({', '.join(':' + b for b in binds)})",
                   **binds)
    return {d: (b or "") for d, b in rows}


def rerank(ds: str, query_text: str, ranked: list[tuple], depth: int) -> tuple[list[tuple], float]:
    head = list(ranked[:depth])
    texts = bodies(ds, [d for d, _ in head])
    attributes = ({"reranker.query": query_text[:2000], "reranker.model_name": models.PIN["reranker"][0],
                   "reranker.top_k": depth} if tracing.active() else {})
    with tracing.traced("rerank", "RERANKER", **attributes) as span:
        scores, ms = models.rerank_scores(query_text, [texts.get(d, "") for d, _ in head])
        order = sorted(range(len(head)), key=lambda i: -scores[i])
        tracing.set_documents(span, "reranker.output_documents", [(head[i][0], scores[i]) for i in order], texts)
    return [(head[i][0], scores[i]) for i in order] + list(ranked[depth:]), ms
