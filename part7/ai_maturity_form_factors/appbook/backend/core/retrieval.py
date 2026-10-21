"""Retrieval over Acme's lending policy in Oracle AI Database (Form Factor 2, reused by 3 and 4).

Five techniques mirror the notebook (keyword, vector, filtered pre/in/post, hybrid RRF, graph). Each
one also has an ``explain_*`` twin that returns the intermediate data the appbook visualizes: the
terms and postings for keyword search, every distance for vector search, both ranked lists and the
fusion for RRF, and the seeds and traversed edges for the graph. ``space()`` projects the 768-d
embeddings to 2-D/3-D for the latent-space viewer and runs the chosen filter strategy for real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from backend.core import db, policy

_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "do", "does", "i", "my", "for",
         "how", "what", "can", "me", "with", "be", "it", "you", "your", "this", "that", "from", "at", "as", "by",
         "if", "we", "our", "much", "many", "need", "will", "would", "there", "any", "have", "has", "am"}
CATEGORY_EDGE = 0.9  # a shared category is a slightly weaker link than the section itself
FILTER_HINTS = {"pre": "pre_filter_with_join_back", "in": "in_filter_with_join_back",
                "post": "post_filter_without_join_back"}

VECTOR_SQL = """SELECT doc_id, title, category, version, content,
       ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS similarity
FROM policy_docs
ORDER BY similarity DESC
FETCH FIRST {k} ROWS ONLY"""

KEYWORD_SQL = """SELECT doc_id, title, category, version, content, SCORE(1) AS score
FROM policy_docs
WHERE CONTAINS(content, :kw, 1) > 0          -- Oracle Text (CTXSYS.CONTEXT) index
ORDER BY SCORE(1) DESC
FETCH FIRST {k} ROWS ONLY"""

FILTERED_SQL = """SELECT /*+ vector_index_transform(policy_docs policy_vec_idx {hint}) */
       doc_id, title, category, version, content,
       ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS similarity
FROM policy_docs
WHERE category = :cat
ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)
FETCH APPROX FIRST {k} ROWS ONLY WITH TARGET ACCURACY {accuracy}"""

HYBRID_SQL = """WITH
vec AS (                                       -- A) vector ranking
  SELECT doc_id, ROW_NUMBER() OVER (ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)) AS r_vec
  FROM policy_docs ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)
  FETCH FIRST {per_list} ROWS ONLY
),
txt AS (                                       -- B) keyword ranking (Oracle Text)
  SELECT doc_id, ROW_NUMBER() OVER (ORDER BY SCORE(1) DESC) AS r_txt
  FROM policy_docs WHERE CONTAINS(content, :kw, 1) > 0
  ORDER BY SCORE(1) DESC FETCH FIRST {per_list} ROWS ONLY
),
fused AS (
  SELECT COALESCE(v.doc_id, t.doc_id) AS doc_id,
         NVL(v.r_vec, 999999) AS r_vec, NVL(t.r_txt, 999999) AS r_txt
  FROM vec v FULL OUTER JOIN txt t ON t.doc_id = v.doc_id
)
SELECT doc_id, r_vec, r_txt,                   -- C) Reciprocal Rank Fusion
       ROUND(1.0/(:rk + r_vec) + 1.0/(:rk + r_txt), 6) AS rrf_score
FROM fused ORDER BY rrf_score DESC
FETCH FIRST {k} ROWS ONLY"""

GRAPH_SQL = """WITH seed AS (                  -- 1) vector-seed the graph
  -- CAST keeps the UNION ALL below numeric (VECTOR_DISTANCE returns BINARY_DOUBLE)
  SELECT doc_id, CAST(1 - VECTOR_DISTANCE(embedding, :q, COSINE) AS NUMBER) AS seed_score
  FROM policy_docs ORDER BY seed_score DESC
  FETCH FIRST {seed_k} ROWS ONLY
),
seed_hits AS (
  SELECT doc_id AS candidate, seed_score, 'seed' AS rel, 1.0 AS edge_score FROM seed
),
sim_hops AS (                                   -- 2) hop along SIMILAR_TO edges
  SELECT gt.target_doc_id AS candidate, s.seed_score, 'similar_to' AS rel, gt.edge_score
  FROM seed s
  JOIN GRAPH_TABLE(policy_graph
    MATCH (src IS doc)-[e IS similar_to]->(dst IS doc)
    COLUMNS (src.doc_id AS source_doc_id, dst.doc_id AS target_doc_id, e.sim_score AS edge_score)
  ) gt ON gt.source_doc_id = s.doc_id
),
cat_hops AS (                                   -- 3) hop to same-category sections
  SELECT gt.target_doc_id AS candidate, s.seed_score, 'same_category' AS rel, 0.9 AS edge_score
  FROM seed s
  JOIN GRAPH_TABLE(policy_graph
    MATCH (src IS doc)-[IS in_category]->(c IS category)<-[IS in_category]-(dst IS doc)
    COLUMNS (src.doc_id AS source_doc_id, dst.doc_id AS target_doc_id)
  ) gt ON gt.source_doc_id = s.doc_id
  WHERE gt.target_doc_id <> s.doc_id
),
candidates AS (
  SELECT * FROM seed_hits
  UNION ALL SELECT * FROM sim_hops
  UNION ALL SELECT * FROM cat_hops
),
scored AS (                                     -- 4) seed score x edge strength
  SELECT candidate AS doc_id, MAX(seed_score * edge_score) AS graph_score
  FROM candidates GROUP BY candidate
)
SELECT d.doc_id, d.title, d.category, d.version, d.content, ROUND(sc.graph_score, 4) AS graph_score
FROM scored sc JOIN policy_docs d ON d.doc_id = sc.doc_id
ORDER BY graph_score DESC
FETCH FIRST {k} ROWS ONLY"""

SQL_TEMPLATES = {"vector": VECTOR_SQL, "keyword": KEYWORD_SQL, "hybrid": HYBRID_SQL, "graph": GRAPH_SQL,
                 "filtered": FILTERED_SQL}


def sql_for(technique: str, k: int = 4, category: str = "collateral", mode: str = "pre", accuracy: int = 90) -> str:
    """The SQL each technique runs, with this request's parameters, for the UI's SQL pane."""
    template = SQL_TEMPLATES.get(technique, VECTOR_SQL)
    return template.format(k=k, per_list=10, seed_k=max(5, k), hint=FILTER_HINTS.get(mode, FILTER_HINTS["pre"]),
                           accuracy=accuracy).replace(":cat", f"'{category}'")


@dataclass
class Hit:
    doc_id: str
    title: str
    category: str
    version: int
    score: float
    content: str = ""

    def as_dict(self) -> dict:
        return {"doc_id": self.doc_id, "title": self.title, "category": self.category, "version": int(self.version),
                "score": round(float(self.score), 4), "content": self.content}


def _hits(cur) -> list[Hit]:
    return [Hit(d, t, c, int(v), float(s), body) for d, t, c, v, body, s in cur.fetchall()]


def text_query(query: str) -> tuple[str, list[str]]:
    """A forgiving Oracle Text query: meaningful terms, brace-escaped, joined with ACCUM."""
    tokens = re.findall(r"[A-Za-z0-9]+", query.lower())
    terms = [t for t in tokens if len(t) > 2 and t not in _STOP] or tokens[:1]
    terms = list(dict.fromkeys(terms))
    return (" ACCUM ".join("{%s}" % t for t in terms) if terms else "{__no_match__}"), terms


# ── techniques ──────────────────────────────────────────────────────────────────
def vector_search(query: str, k: int = 4) -> list[Hit]:
    q = db.as_vector(db.embed_query(query))
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(VECTOR_SQL.format(k=int(k)), q=q)
        return _hits(cur)


def keyword_search(query: str, k: int = 4) -> list[Hit]:
    kw, _ = text_query(query)
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(KEYWORD_SQL.format(k=int(k)), kw=kw)
        return _hits(cur)


def filtered_search(query: str, category: str, k: int = 4, mode: str = "pre", accuracy: int = 90) -> list[Hit]:
    """Vector search restricted to one category. Post-filter is computed explicitly (rank, then filter),
    because on a small table the optimizer would answer it with an exact scan and hide the under-return."""
    if mode == "post":
        return [h for h in vector_search(query, k) if h.category == category]
    q = db.as_vector(db.embed_query(query))
    sql = FILTERED_SQL.format(hint=FILTER_HINTS[mode], k=int(k), accuracy=int(accuracy))
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, q=q, cat=category)
        return _hits(cur)


def hybrid_search(query: str, k: int = 4, per_list: int = 10, rrf_k: int = 60) -> list[Hit]:
    q = db.as_vector(db.embed_query(query))
    kw, _ = text_query(query)
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(HYBRID_SQL.format(per_list=int(per_list), k=int(k)), q=q, kw=kw, rk=rrf_k)
        ranked = cur.fetchall()
        docs = _docs_by_id(cur)
    return [Hit(d, docs[d]["title"], docs[d]["category"], docs[d]["version"], float(s), docs[d]["content"])
            for d, _, _, s in ranked]


def graph_search(query: str, k: int = 4, seed_k: int = 5) -> list[Hit]:
    q = db.as_vector(db.embed_query(query))
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(GRAPH_SQL.format(seed_k=int(max(seed_k, k)), k=int(k)), q=q)
        return _hits(cur)


TECHNIQUES = {"vector": vector_search, "keyword": keyword_search, "hybrid": hybrid_search, "graph": graph_search}


def search(query: str, technique: str = "vector", k: int = 4) -> list[Hit]:
    return TECHNIQUES.get(technique, vector_search)(query, k)


def retrieve(query: str, k: int = 3) -> list[dict]:
    """The unified retriever the workflow and the agent reuse: id, version, text, similarity."""
    return [{"doc_id": h.doc_id, "version": h.version, "content": h.content, "similarity": h.score}
            for h in vector_search(query, k)]


def context_block(hits: list[dict]) -> str:
    return "\n".join(f"[{i + 1}] ({h['doc_id']} v{h['version']}) {h['content']}" for i, h in enumerate(hits))


def _docs_by_id(cur) -> dict:
    cur.execute("SELECT doc_id, title, category, version, content FROM policy_docs")
    return {d: {"title": t, "category": c, "version": int(v), "content": body} for d, t, c, v, body in cur.fetchall()}


def _all_docs():
    """Every section with its embedding (for distances, projections and the graph view)."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, title, category, version, content, embedding FROM policy_docs ORDER BY doc_id")
        rows = cur.fetchall()
    meta = [{"doc_id": d, "title": t, "category": c, "version": int(v), "content": body} for d, t, c, v, body, _ in rows]
    vectors = np.array([db.unit(np.array(r[5], dtype=np.float32)) for r in rows])
    return meta, vectors


# ── explanations for the visualizations ────────────────────────────────────────────
def explain_keyword(query: str, k: int = 4) -> dict:
    """Terms → postings (which sections contain each term, with its SCORE) → the ACCUM ranking."""
    kw, terms = text_query(query)
    postings = []
    with db.connection() as conn, conn.cursor() as cur:
        for term in terms:
            cur.execute("SELECT doc_id, SCORE(1) FROM policy_docs WHERE CONTAINS(content, :kw, 1) > 0 "
                        "ORDER BY SCORE(1) DESC", kw="{%s}" % term)
            postings.append({"term": term, "docs": [{"doc_id": d, "score": int(s)} for d, s in cur.fetchall()]})
        cur.execute(KEYWORD_SQL.format(k=int(k)), kw=kw)
        ranked = [h.as_dict() for h in _hits(cur)]
        docs = _docs_by_id(cur)
    return {"technique": "keyword", "text_query": kw, "terms": terms, "postings": postings, "results": ranked,
            "documents": [{"doc_id": d, "title": v["title"], "category": v["category"]} for d, v in sorted(docs.items())],
            "sql": sql_for("keyword", k)}


def explain_vector(query: str, k: int = 4) -> dict:
    """The distance from the query to every section, in rank order, with the top-k cut."""
    meta, vectors = _all_docs()
    sims = vectors @ db.embed_query(query)
    order = np.argsort(-sims)
    ranked = [{**{x: meta[i][x] for x in ("doc_id", "title", "category", "version")},
               "similarity": round(float(sims[i]), 4), "distance": round(float(1 - sims[i]), 4),
               "rank": r + 1, "in_top_k": r < k} for r, i in enumerate(order)]
    return {"technique": "vector", "k": k, "ranked": ranked, "results": [h.as_dict() for h in vector_search(query, k)],
            "sql": sql_for("vector", k)}


def explain_hybrid(query: str, k: int = 4, per_list: int = 10, rrf_k: int = 60) -> dict:
    """Both ranked lists and every section's fused score, with each list's contribution."""
    q = db.as_vector(db.embed_query(query))
    kw, terms = text_query(query)
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT doc_id FROM policy_docs ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE) "
                    f"FETCH FIRST {int(per_list)} ROWS ONLY", q=q)
        vec_list = [d for (d,) in cur.fetchall()]
        cur.execute(f"SELECT doc_id FROM policy_docs WHERE CONTAINS(content, :kw, 1) > 0 ORDER BY SCORE(1) DESC "
                    f"FETCH FIRST {int(per_list)} ROWS ONLY", kw=kw)
        txt_list = [d for (d,) in cur.fetchall()]
        docs = _docs_by_id(cur)
    fused = []
    for doc_id in dict.fromkeys(vec_list + txt_list):
        r_vec = vec_list.index(doc_id) + 1 if doc_id in vec_list else None
        r_txt = txt_list.index(doc_id) + 1 if doc_id in txt_list else None
        from_vec = 1 / (rrf_k + r_vec) if r_vec else 1 / (rrf_k + 999999)
        from_txt = 1 / (rrf_k + r_txt) if r_txt else 1 / (rrf_k + 999999)
        fused.append({"doc_id": doc_id, "title": docs[doc_id]["title"], "r_vec": r_vec, "r_txt": r_txt,
                      "from_vector": round(from_vec, 6), "from_keyword": round(from_txt, 6),
                      "rrf_score": round(from_vec + from_txt, 6)})
    fused.sort(key=lambda f: -f["rrf_score"])
    for i, f in enumerate(fused):
        f["in_top_k"] = i < k
    return {"technique": "hybrid", "terms": terms, "rrf_k": rrf_k, "vector_list": vec_list, "keyword_list": txt_list,
            "fused": fused, "results": [h.as_dict() for h in hybrid_search(query, k, per_list, rrf_k)],
            "sql": sql_for("hybrid", k)}


def explain_graph(query: str, k: int = 4, seed_k: int = 5) -> dict:
    """Seeds, the SIMILAR_TO and IN_CATEGORY edges walked from them, and the blended candidates."""
    seed_k = max(seed_k, k)
    meta, vectors = _all_docs()
    by_id = {m["doc_id"]: m for m in meta}
    sims = vectors @ db.embed_query(query)
    seeds = [{"doc_id": meta[i]["doc_id"], "seed_score": round(float(sims[i]), 4)} for i in np.argsort(-sims)[:seed_k]]
    seed_ids = {s["doc_id"]: s["seed_score"] for s in seeds}
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_doc_id, target_doc_id, sim_score FROM policy_doc_similarities")
        similar = [(s, t, float(score)) for s, t, score in cur.fetchall()]
    edges, best = [], {}

    def bump(doc_id, score, rel, via):
        if score > best.get(doc_id, {"score": -1})["score"]:
            best[doc_id] = {"score": score, "rel": rel, "via": via}

    for s, score in seed_ids.items():
        bump(s, score, "seed", None)
    for src, dst, edge in similar:
        if src in seed_ids:
            edges.append({"source": src, "target": dst, "type": "similar_to", "weight": round(edge, 4)})
            bump(dst, seed_ids[src] * edge, "similar_to", src)
    for src, score in seed_ids.items():
        for m in meta:
            if m["category"] == by_id[src]["category"] and m["doc_id"] != src:
                edges.append({"source": src, "target": m["doc_id"], "type": "same_category", "weight": CATEGORY_EDGE})
                bump(m["doc_id"], score * CATEGORY_EDGE, "same_category", src)
    ranked = sorted(best.items(), key=lambda kv: -kv[1]["score"])
    nodes = [{"doc_id": d, "title": by_id[d]["title"], "category": by_id[d]["category"], "graph_score": round(v["score"], 4),
              "reached_by": v["rel"], "via": v["via"], "in_top_k": i < k} for i, (d, v) in enumerate(ranked)]
    return {"technique": "graph", "seeds": seeds, "edges": edges, "nodes": nodes,
            "categories": sorted({m["category"] for m in meta}),
            "results": [h.as_dict() for h in graph_search(query, k, seed_k)], "sql": sql_for("graph", k)}


EXPLAINERS = {"keyword": explain_keyword, "vector": explain_vector, "hybrid": explain_hybrid, "graph": explain_graph}


# ── the latent-space viewer ────────────────────────────────────────────────────────
def space(query: str, k: int = 4, category: str | None = None, mode: str = "pre", accuracy: int = 90) -> dict:
    """Project the section embeddings to 3-D with PCA, place the query, and run the filter strategy for real.

    PCA keeps the directions of greatest variance, so distances in the picture are an approximation:
    the cosine similarity reported for each point is computed in the full 768-dimensional space.
    """
    meta, vectors = _all_docs()
    qv = db.embed_query(query)
    mean = vectors.mean(axis=0)
    _, singular, components = np.linalg.svd(vectors - mean, full_matrices=False)
    axes = components[:3]
    variance = (singular ** 2) / float((singular ** 2).sum())
    doc_xyz = (vectors - mean) @ axes.T
    q_xyz = (qv - mean) @ axes.T
    scale = float(np.abs(np.vstack([doc_xyz, q_xyz])).max()) or 1.0
    sims = vectors @ qv
    order = list(np.argsort(-sims))
    rank = {int(i): r + 1 for r, i in enumerate(order)}
    global_top = [meta[int(i)]["doc_id"] for i in order[:k]]
    points = [{**{x: m[x] for x in ("doc_id", "title", "category", "version")},
               "x": round(float(doc_xyz[i][0] / scale), 4), "y": round(float(doc_xyz[i][1] / scale), 4),
               "z": round(float(doc_xyz[i][2] / scale), 4), "similarity": round(float(sims[i]), 4),
               "distance": round(float(1 - sims[i]), 4), "rank": rank[i], "eligible": category in (None, "", m["category"])}
              for i, m in enumerate(meta)]
    result = {"query": {"text": query, "x": round(float(q_xyz[0] / scale), 4), "y": round(float(q_xyz[1] / scale), 4),
                        "z": round(float(q_xyz[2] / scale), 4)},
              "points": points, "explained_variance": [round(float(v), 4) for v in variance[:3]],
              "dimensions": int(vectors.shape[1]), "k": k, "global_top_k": global_top,
              "category": category or None, "mode": mode if category else None}
    if category:
        hits = filtered_search(query, category, k=k, mode=mode, accuracy=accuracy)
        result.update(
            retrieved=[h.doc_id for h in hits],
            dropped_by_post_filter=[d for d in global_top if d not in {h.doc_id for h in hits}] if mode == "post" else [],
            comparison={m: [h.doc_id for h in filtered_search(query, category, k=k, mode=m, accuracy=accuracy)]
                        for m in ("pre", "in", "post")},
            sql=sql_for("filtered", k, category, mode, accuracy) if mode != "post" else
                sql_for("vector", k) + f"\n-- post-filter: keep only rows WHERE category = '{category}'",
        )
    else:
        result.update(retrieved=global_top, dropped_by_post_filter=[], comparison=None, sql=sql_for("vector", k))
    return result
