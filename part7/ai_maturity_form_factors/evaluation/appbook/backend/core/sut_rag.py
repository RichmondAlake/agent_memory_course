"""② RAG under test: Acme's policy in Oracle (FFAPP_ tables), four first stages, the reranker and cited answers.

The same SQL as the evaluation notebook's Part 4, under `FFAPP_` names (vector search is an exact scan here). `ensure_policy()` rebuilds the policy memory
whenever it is missing or not at the expected versions (the autonomous suite raises a limit, then puts it back).
"""
from __future__ import annotations

import json
import re
import threading

import numpy as np

from backend.config import settings
from backend.core import data, db, llm
from backend.core.tracing import documents, traced

EXPECTED_VERSIONS = {d["doc_id"]: 1 for d in data.POLICY_DOCS} | {d: 2 for d, *_ in data.POLICY_UPDATES}
_build_lock = threading.Lock()
STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "do", "does", "i", "my", "for", "how",
             "what", "can", "me", "with", "be", "it", "you", "your", "this", "that", "from", "at", "as", "by", "if", "we",
             "our", "much", "many", "need", "will", "would", "there", "any", "have", "has", "am"}
RAG_SYSTEM = ("You are Acme Home Loans' mortgage assistant. Answer using ONLY the numbered policy context. Cite every "
              "fact with its bracketed number, like [1]. If the context does not contain the answer, say so.")
POLICY_TABLES = ["ffapp_policy_similarities", "ffapp_policy_doc_categories", "ffapp_policy_categories",
                 "ffapp_policy_versions", "ffapp_policy"]


def versions() -> dict:
    try:
        return {r["doc_id"]: int(r["version"]) for r in db.sql("SELECT doc_id, version FROM ffapp_policy")}
    except Exception:  # noqa: BLE001 — the table does not exist yet
        return {}


def doc_text(doc: dict) -> str:
    return f"{doc['title']}. {doc['content']}"


def update_policy(doc_id: str, content: str, rules: dict | None, reason: str) -> int:
    """A new version of one section: archive the old row, re-embed, update in place, in one transaction."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT title FROM ffapp_policy WHERE doc_id = :d", d=doc_id)
        vector = db.embed_documents([f"{cur.fetchone()[0]}. {content}"])[0]
        cur.execute("""INSERT INTO ffapp_policy_versions (doc_id, version, content, rules, change_reason)
                       SELECT doc_id, version, content, rules, :reason FROM ffapp_policy WHERE doc_id = :d""",
                    reason=reason, d=doc_id)
        import array

        cur.execute("""UPDATE ffapp_policy SET content = :c, rules = :r, embedding = :e, version = version + 1,
                              updated_at = SYSTIMESTAMP WHERE doc_id = :d""",
                    c=content, r=json.dumps(rules) if rules else None, e=array.array("f", vector.tolist()), d=doc_id)
        cur.execute("SELECT version FROM ffapp_policy WHERE doc_id = :d", d=doc_id)
        version = int(cur.fetchone()[0])
        conn.commit()
    return version


def rebuild() -> dict:
    """Drop and recreate the policy memory: tables, indexes, the DTI update (v2) and the property graph."""
    import array

    vectors = db.embed_documents([doc_text(d) for d in data.POLICY_DOCS])
    dim = int(vectors.shape[1])
    if db.sql("SELECT COUNT(*) AS n FROM user_property_graphs WHERE graph_name = 'FFAPP_POLICY_GRAPH'")[0]["n"]:
        db.sql("DROP PROPERTY GRAPH ffapp_policy_graph")
    db.run_ddl("\n/\n".join(f"DROP TABLE IF EXISTS {t} CASCADE CONSTRAINTS PURGE" for t in POLICY_TABLES) + f"""
/
CREATE TABLE ffapp_policy (
    doc_id VARCHAR2(64) PRIMARY KEY, title VARCHAR2(400), category VARCHAR2(64), content VARCHAR2(4000), rules JSON,
    version NUMBER DEFAULT 1 NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    embedding VECTOR({dim}, FLOAT32))
/
CREATE TABLE ffapp_policy_versions (
    doc_id VARCHAR2(64), version NUMBER, content VARCHAR2(4000), rules JSON,
    valid_to TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP, change_reason VARCHAR2(400),
    CONSTRAINT ffapp_policy_versions_pk PRIMARY KEY (doc_id, version))
/
CREATE TABLE ffapp_policy_categories (category VARCHAR2(64) PRIMARY KEY)
/
CREATE TABLE ffapp_policy_doc_categories (
    doc_id VARCHAR2(64) NOT NULL REFERENCES ffapp_policy(doc_id),
    category VARCHAR2(64) NOT NULL REFERENCES ffapp_policy_categories(category),
    CONSTRAINT ffapp_pdc_pk PRIMARY KEY (doc_id, category))
/
CREATE TABLE ffapp_policy_similarities (
    source_doc_id VARCHAR2(64) NOT NULL REFERENCES ffapp_policy(doc_id),
    target_doc_id VARCHAR2(64) NOT NULL REFERENCES ffapp_policy(doc_id),
    sim_score NUMBER(8,6) NOT NULL, rank_no NUMBER(5) NOT NULL,
    CONSTRAINT ffapp_pds_pk PRIMARY KEY (source_doc_id, target_doc_id))""")
    doc_ids = [d["doc_id"] for d in data.POLICY_DOCS]
    sim = vectors @ vectors.T
    np.fill_diagonal(sim, -np.inf)
    with db.connection() as conn, conn.cursor() as cur:
        cur.executemany("""INSERT INTO ffapp_policy (doc_id, title, category, content, rules, embedding)
                           VALUES (:1, :2, :3, :4, :5, :6)""",
                        [(d["doc_id"], d["title"], d["category"], d["content"], json.dumps(d["rules"]) if d["rules"] else None,
                          array.array("f", v.tolist())) for d, v in zip(data.POLICY_DOCS, vectors)])
        cur.execute("CREATE INDEX ffapp_policy_text_idx ON ffapp_policy(content) INDEXTYPE IS CTXSYS.CONTEXT "
                    "PARAMETERS ('SYNC (ON COMMIT)')")
        # No HNSW index here: seventeen rows are scanned exactly in a millisecond, and an in-memory vector index
        # adds commit-time maintenance every policy update must wait for. The notebook's §4.1 shows the index.
        cur.executemany("INSERT INTO ffapp_policy_categories VALUES (:1)",
                        [(c,) for c in sorted({d["category"] for d in data.POLICY_DOCS})])
        cur.executemany("INSERT INTO ffapp_policy_doc_categories VALUES (:1, :2)",
                        [(d["doc_id"], d["category"]) for d in data.POLICY_DOCS])
        cur.executemany("INSERT INTO ffapp_policy_similarities VALUES (:1, :2, :3, :4)",
                        [(src, doc_ids[int(j)], round(float(sim[i][int(j)]), 6), rank) for i, src in enumerate(doc_ids)
                         for rank, j in enumerate(np.argsort(sim[i])[::-1][:3], start=1)])
        cur.execute("""CREATE PROPERTY GRAPH ffapp_policy_graph
            VERTEX TABLES (ffapp_policy KEY (doc_id) LABEL doc PROPERTIES (doc_id, title, category),
                           ffapp_policy_categories KEY (category) LABEL category PROPERTIES (category))
            EDGE TABLES (ffapp_policy_doc_categories KEY (doc_id, category)
                             SOURCE KEY (doc_id) REFERENCES ffapp_policy (doc_id)
                             DESTINATION KEY (category) REFERENCES ffapp_policy_categories (category) LABEL in_category,
                         ffapp_policy_similarities KEY (source_doc_id, target_doc_id)
                             SOURCE KEY (source_doc_id) REFERENCES ffapp_policy (doc_id)
                             DESTINATION KEY (target_doc_id) REFERENCES ffapp_policy (doc_id)
                             LABEL similar_to PROPERTIES (sim_score))""")
        conn.commit()
    for doc_id, content, new_rules, reason in data.POLICY_UPDATES:
        update_policy(doc_id, content, new_rules, reason)
    return versions()


def _has_vector_index() -> bool:
    return bool(db.sql("""SELECT COUNT(*) AS n FROM user_indexes WHERE table_name = 'FFAPP_POLICY'
                          AND index_type = 'VECTOR'""")[0]["n"])


def ensure_policy() -> dict:
    """Rebuild the policy memory unless it is present at exactly the expected versions (and without an HNSW index)."""
    with _build_lock:
        current = versions()
        if current != EXPECTED_VERSIONS or _has_vector_index():
            return {"rebuilt": True, "versions": rebuild()}
        return {"rebuilt": False, "versions": current}


def current_rules() -> tuple[dict, dict]:
    rows = db.sql("SELECT doc_id, version, rules FROM ffapp_policy")
    rules = {}
    for row in rows:
        rules.update(db.plain(row["rules"]) or {})          # JSON numbers arrive as Decimal
    return rules, {row["doc_id"]: int(row["version"]) for row in rows}


# ── the four first stages and the reranker ─────────────────────────────────────────────────────────────────────
def text_terms(question: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in STOPWORDS]
    return " ACCUM ".join("{%s}" % w for w in dict.fromkeys(words)) or "{none}"


def _ids(statement: str, **binds) -> list[str]:
    return [row["doc_id"] for row in db.sql(statement, **binds)]


def keyword_search(q: str, n: int = 8) -> list[str]:
    with traced("keyword_search", "RETRIEVER", **{"input.value": q}) as span:
        found = _ids(f"""SELECT doc_id FROM ffapp_policy WHERE CONTAINS(content, :kw, 1) > 0
                        ORDER BY SCORE(1) DESC FETCH FIRST {int(n)} ROWS ONLY""", kw=text_terms(q))
        if span:
            span.set_attributes(documents("retrieval.documents", found))
    return found


def vector_search(q: str, n: int = 8) -> list[str]:
    with traced("vector_search", "RETRIEVER", **{"input.value": q}) as span:
        found = _ids(f"""SELECT doc_id FROM ffapp_policy ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)
                        FETCH FIRST {int(n)} ROWS ONLY""", q=db.query_vector(q))
        if span:
            span.set_attributes(documents("retrieval.documents", found))
    return found


def hybrid_search(q: str, n: int = 8, rrf_k: int = 60) -> list[str]:
    with traced("hybrid_search", "RETRIEVER", **{"input.value": q}) as span:
        found = _ids(f"""
            WITH vec AS (SELECT doc_id, ROW_NUMBER() OVER (ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)) AS r
                         FROM ffapp_policy ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE) FETCH FIRST 10 ROWS ONLY),
                 txt AS (SELECT doc_id, ROW_NUMBER() OVER (ORDER BY SCORE(1) DESC) AS r FROM ffapp_policy
                         WHERE CONTAINS(content, :kw, 1) > 0 ORDER BY SCORE(1) DESC FETCH FIRST 10 ROWS ONLY)
            SELECT COALESCE(v.doc_id, t.doc_id) AS doc_id
            FROM vec v FULL OUTER JOIN txt t ON t.doc_id = v.doc_id
            ORDER BY 1.0 / (:rk + NVL(v.r, 999999)) + 1.0 / (:rk + NVL(t.r, 999999)) DESC, 1
            FETCH FIRST {int(n)} ROWS ONLY""", q=db.query_vector(q), kw=text_terms(q), rk=rrf_k)
        if span:
            span.set_attributes(documents("retrieval.documents", found))
    return found


def graph_search(q: str, n: int = 8) -> list[str]:
    with traced("graph_search", "RETRIEVER", **{"input.value": q}) as span:
        found = _ids(f"""
            WITH seed AS (SELECT doc_id, CAST(1 - VECTOR_DISTANCE(embedding, :q, COSINE) AS NUMBER) AS s FROM ffapp_policy
                          ORDER BY s DESC FETCH FIRST 5 ROWS ONLY),
                 hops AS (SELECT doc_id AS c, s, 1.0 AS e FROM seed
                          UNION ALL
                          SELECT gt.dst, sd.s, gt.e FROM seed sd JOIN GRAPH_TABLE(ffapp_policy_graph
                              MATCH (a IS doc)-[x IS similar_to]->(b IS doc)
                              COLUMNS (a.doc_id AS src, b.doc_id AS dst, x.sim_score AS e)) gt ON gt.src = sd.doc_id
                          UNION ALL
                          SELECT gt.dst, sd.s, 0.9 FROM seed sd JOIN GRAPH_TABLE(ffapp_policy_graph
                              MATCH (a IS doc)-[IS in_category]->(c IS category)<-[IS in_category]-(b IS doc)
                              COLUMNS (a.doc_id AS src, b.doc_id AS dst)) gt ON gt.src = sd.doc_id AND gt.dst <> sd.doc_id)
            SELECT c AS doc_id FROM hops GROUP BY c ORDER BY MAX(s * e) DESC, 1 FETCH FIRST {int(n)} ROWS ONLY""",
                    q=db.query_vector(q))
        if span:
            span.set_attributes(documents("retrieval.documents", found))
    return found


FIRST_STAGES = {"keyword": keyword_search, "vector": vector_search, "hybrid": hybrid_search, "graph": graph_search}


def section_texts() -> dict:
    return {r["doc_id"]: f"{r['title']}. {r['content']}" for r in db.sql("SELECT doc_id, title, content FROM ffapp_policy")}


def rerank(q: str, candidates: list[str], texts: dict | None = None) -> list[str]:
    if not candidates:
        return []
    texts = texts or section_texts()
    with traced("rerank", "RERANKER", **{"reranker.query": q, "reranker.model_name": settings.reranker_model,
                                         "reranker.top_k": len(candidates)}) as span:
        scores = db.rerank_scores(q, [texts[d] for d in candidates])
        ranked = sorted(zip(candidates, scores), key=lambda pair: -pair[1])
        if span:
            span.set_attributes({**documents("reranker.input_documents", candidates, texts),
                                 **documents("reranker.output_documents", [d for d, _ in ranked], texts,
                                             [s for _, s in ranked])})
    return [d for d, _ in ranked]


def retrieve(q: str, k: int = 4) -> list[dict]:
    """The application's retriever: 8 vector candidates, reranked, best k, with their versions."""
    with traced("retrieve", "RETRIEVER", **{"input.value": q}) as span:
        best = rerank(q, vector_search(q, 8))[:k]
        rows = {r["doc_id"]: r for r in db.sql("SELECT doc_id, version, content FROM ffapp_policy")}
        passages = [{"doc_id": d, "version": int(rows[d]["version"]), "content": rows[d]["content"]} for d in best]
        if span:
            span.set_attributes(documents("retrieval.documents", [p["doc_id"] for p in passages],
                                          [p["content"] for p in passages]))
    return passages


def rag_answer(q: str) -> dict:
    passages = retrieve(q)
    context = "\n".join(f"[{i}] ({p['doc_id']} v{p['version']}) {p['content']}" for i, p in enumerate(passages, 1))
    answer = llm.text_of(llm.claude("rag answer", f"{RAG_SYSTEM}\n\nPolicy context:\n{context}", [{"role": "user", "content": q}]))
    return {"answer": answer, "passages": passages}
