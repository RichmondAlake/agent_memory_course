"""Retrieval for Form Factor 2 (RAG) — and reused by FF3 (workflow) and FF4 (agent).

A single ``VectorStore`` embeds the Acme docs once (fastembed / ONNX, torch-free)
and serves three retrieval techniques: **vector**, **keyword**, and **hybrid (RRF)**.

It prefers **Oracle AI Database** (native ``VECTOR`` columns + Oracle Text), exactly
as in the notebook. If Oracle is unreachable it transparently falls back to an
in-memory NumPy cosine index so the whole app still runs on a laptop. The active
backend is reported to the UI via ``/api/health``.
"""
from __future__ import annotations

import array
import re
import threading
import time
from dataclasses import dataclass

import numpy as np

# Small stopword set so free-form queries reduce to meaningful keyword terms.
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "do", "does",
         "i", "my", "for", "how", "what", "can", "me", "with", "be", "it", "you", "your",
         "this", "that", "from", "at", "as", "by", "if", "we", "our"}

from backend.config import settings
from backend.core.knowledge_base import DOCS


# ── SQL shown in the UI's "SQL" pane. The graph template is executed verbatim;
#    the others mirror the technique methods below (kept readable for teaching). ──
_VECTOR_SQL = """SELECT doc_id, title, category, content,
       ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS similarity
FROM acme_docs
ORDER BY similarity DESC
FETCH FIRST {k} ROWS ONLY"""

_KEYWORD_SQL = """SELECT doc_id, title, category, content, SCORE(1) AS score
FROM acme_docs
WHERE CONTAINS(content, :kw, 1) > 0          -- Oracle Text (CTXSYS.CONTEXT) index
ORDER BY SCORE(1) DESC
FETCH FIRST {k} ROWS ONLY"""

_HYBRID_SQL = """WITH
vec AS (                                       -- A) vector ranking
  SELECT doc_id, ROW_NUMBER() OVER (ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)) AS r_vec
  FROM acme_docs ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)
  FETCH FIRST {per_list} ROWS ONLY
),
txt AS (                                       -- B) keyword ranking (Oracle Text)
  SELECT doc_id, ROW_NUMBER() OVER (ORDER BY SCORE(1) DESC) AS r_txt
  FROM acme_docs WHERE CONTAINS(content, :kw, 1) > 0
  ORDER BY SCORE(1) DESC FETCH FIRST {per_list} ROWS ONLY
),
fused AS (
  SELECT COALESCE(v.doc_id, t.doc_id) AS doc_id,
         NVL(v.r_vec, 999999) AS r_vec, NVL(t.r_txt, 999999) AS r_txt
  FROM vec v FULL OUTER JOIN txt t ON t.doc_id = v.doc_id
)
SELECT doc_id,                                 -- C) Reciprocal Rank Fusion
       ROUND(1.0/(:rk + r_vec) + 1.0/(:rk + r_txt), 6) AS rrf_score
FROM fused ORDER BY rrf_score DESC
FETCH FIRST {k} ROWS ONLY"""

_GRAPH_SQL = """WITH seed AS (                  -- 1) vector-seed the graph
  SELECT doc_id, 1 - VECTOR_DISTANCE(embedding, :q, COSINE) AS seed_score
  FROM acme_docs ORDER BY seed_score DESC
  FETCH FIRST {seed_k} ROWS ONLY
),
seed_hits AS (
  SELECT doc_id AS candidate, seed_score, 'seed' AS rel, seed_score AS edge_score FROM seed
),
sim_hops AS (                                   -- 2) hop along SIMILAR_TO edges
  SELECT gt.target_doc_id AS candidate, s.seed_score, 'similar_to' AS rel, gt.edge_score
  FROM seed s
  JOIN GRAPH_TABLE(acme_graph
    MATCH (src IS doc)-[e IS similar_to]->(dst IS doc)
    COLUMNS (src.doc_id AS source_doc_id, dst.doc_id AS target_doc_id, e.sim_score AS edge_score)
  ) gt ON gt.source_doc_id = s.doc_id
),
cat_hops AS (                                   -- 3) hop to same-category docs
  SELECT gt.target_doc_id AS candidate, s.seed_score, 'same_category' AS rel, 1.0 AS edge_score
  FROM seed s
  JOIN GRAPH_TABLE(acme_graph
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
scored AS (                                     -- 4) blend seed + edge scores
  SELECT candidate AS doc_id,
         MAX(CASE rel
             WHEN 'seed'          THEN seed_score
             WHEN 'similar_to'    THEN 0.70 * seed_score + 0.30 * edge_score
             WHEN 'same_category' THEN 0.85 * seed_score + 0.15 * edge_score
             ELSE seed_score END) AS graph_score
  FROM candidates GROUP BY candidate
)
SELECT d.doc_id, d.title, d.category, d.content, ROUND(sc.graph_score, 4) AS graph_score
FROM scored sc JOIN acme_docs d ON d.doc_id = sc.doc_id
ORDER BY graph_score DESC
FETCH FIRST {k} ROWS ONLY"""

# Parameterized copies (demo default k) for the UI's SQL pane.
RAG_SQL = {
    "vector": _VECTOR_SQL.format(k=4),
    "keyword": _KEYWORD_SQL.format(k=4),
    "hybrid": _HYBRID_SQL.format(per_list=10, k=4),
    "graph": _GRAPH_SQL.format(seed_k=5, k=4),
}


@dataclass
class Hit:
    doc_id: str
    title: str
    category: str
    score: float
    content: str = ""

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "score": round(float(self.score), 4),
            "content": self.content,
        }


def _unit(v) -> np.ndarray:
    """Normalize to a unit vector so cosine similarity is a plain dot product."""
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


class VectorStore:
    """Embeds the corpus once, then serves vector / keyword / hybrid retrieval."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ready = False
        self.backend = "initializing"   # → "oracle" | "memory"
        self.error: str | None = None
        self.dim = 0
        self._embedder = None
        self._doc_vectors: np.ndarray | None = None
        self._conn = None
        self._by_id = {d["doc_id"]: d for d in DOCS}

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def initialize(self) -> None:
        """Idempotent, thread-safe warm-up: load embeddings, then try Oracle."""
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=settings.embed_model)
            doc_texts = [f"{d['title']}. {d['content']}" for d in DOCS]
            self._doc_vectors = np.array(
                [_unit(v) for v in self._embedder.embed(doc_texts)], dtype=np.float32
            )
            self.dim = int(self._doc_vectors.shape[1])

            if settings.oracle_enabled:
                try:
                    self._setup_oracle()
                    self.backend = "oracle"
                except Exception as exc:  # noqa: BLE001 — any failure → memory fallback
                    self.error = str(exc).splitlines()[0][:200]
                    self.backend = "memory"
            else:
                self.backend = "memory"

            self.ready = True

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "backend": self.backend,
            "dim": self.dim,
            "doc_count": len(DOCS),
            "error": self.error,
        }

    # ── query embedding ─────────────────────────────────────────────────────────
    def _query_vec(self, text: str) -> np.ndarray:
        # fastembed applies nomic's query prefix internally via query_embed.
        return _unit(next(self._embedder.query_embed(text)))

    # Public accessor so the BEIR benchmark can reuse this store's already-warm
    # embedder (avoids loading a second copy of the nomic model).
    def query_vector(self, text: str) -> np.ndarray:
        if not self.ready:
            self.initialize()
        return self._query_vec(text)

    # ── Oracle setup (mirrors the notebook DDL/ingest) ───────────────────────────
    def _setup_oracle(self) -> None:
        import oracledb

        # Retry the connect so the app reliably attaches while Oracle is still
        # warming up (e.g. in Codespaces). Retries default to 1 locally.
        last_exc: Exception | None = None
        for attempt in range(1, max(1, settings.oracle_connect_retries) + 1):
            try:
                self._conn = oracledb.connect(
                    user=settings.oracle_user,
                    password=settings.oracle_password,
                    dsn=settings.oracle_dsn,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < settings.oracle_connect_retries:
                    time.sleep(settings.oracle_connect_delay)
        else:
            raise last_exc if last_exc else RuntimeError("Oracle connect failed")
        dim = self.dim

        # A property graph from a previous run references acme_docs and would block
        # dropping/recreating it — remove it first.
        with self._conn.cursor() as cur:
            try:
                cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'ACME_GRAPH'")
                if cur.fetchone()[0] > 0:
                    cur.execute("DROP PROPERTY GRAPH acme_graph")
            except Exception:  # noqa: BLE001 — view may be absent on older DBs
                pass
        self._conn.commit()

        table_ddl = f"""
BEGIN EXECUTE IMMEDIATE 'DROP TABLE acme_docs CASCADE CONSTRAINTS PURGE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
CREATE TABLE acme_docs (
    doc_id    VARCHAR2(64) PRIMARY KEY,
    title     VARCHAR2(400),
    category  VARCHAR2(64),
    content   VARCHAR2(4000),
    embedding VECTOR({dim}, FLOAT32)
)
"""
        with self._conn.cursor() as cur:
            for stmt in table_ddl.split("/"):
                if stmt.strip():
                    cur.execute(stmt)
        self._conn.commit()

        with self._conn.cursor() as cur:
            try:
                cur.execute("DROP INDEX acme_text_idx")
            except oracledb.DatabaseError:
                pass
            cur.execute(
                "CREATE INDEX acme_text_idx ON acme_docs(content) "
                "INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (ON COMMIT)')"
            )
            try:
                cur.execute("DROP INDEX acme_vec_idx")
            except oracledb.DatabaseError:
                pass
            try:
                cur.execute(
                    "CREATE VECTOR INDEX acme_vec_idx ON acme_docs(embedding) "
                    "ORGANIZATION INMEMORY NEIGHBOR GRAPH DISTANCE COSINE "
                    "WITH TARGET ACCURACY 90 PARAMETERS (TYPE HNSW, NEIGHBORS 16, EFCONSTRUCTION 200)"
                )
            except oracledb.DatabaseError:
                pass  # exact search still works without the HNSW index
        self._conn.commit()

        rows = [
            (d["doc_id"], d["title"], d["category"], d["content"], array.array("f", vec))
            for d, vec in zip(DOCS, self._doc_vectors.astype(np.float32).tolist())
        ]
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO acme_docs (doc_id, title, category, content, embedding) "
                "VALUES (:1, :2, :3, :4, :5)",
                rows,
            )
        self._conn.commit()

        # Build the SQL property graph for graph retrieval. Optional: if it fails
        # (e.g. an older DB without property graphs) the other techniques still work.
        try:
            self._setup_graph()
        except Exception as exc:  # noqa: BLE001
            self.error = ((self.error or "") + f" | graph: {str(exc).splitlines()[0][:140]}").strip(" |")

    def _setup_graph(self) -> None:
        """Create IN_CATEGORY + SIMILAR_TO edge tables and the ACME_GRAPH property
        graph (computed from the doc vectors), mirroring the notebook."""
        graph_ddl = """
BEGIN EXECUTE IMMEDIATE 'DROP TABLE doc_similarities'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE doc_categories'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP TABLE categories'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
CREATE TABLE categories (category VARCHAR2(64) PRIMARY KEY)
/
CREATE TABLE doc_categories (
    doc_id   VARCHAR2(64) NOT NULL,
    category VARCHAR2(64) NOT NULL,
    CONSTRAINT pk_doc_categories PRIMARY KEY (doc_id, category),
    CONSTRAINT fk_dc_doc FOREIGN KEY (doc_id) REFERENCES acme_docs(doc_id),
    CONSTRAINT fk_dc_cat FOREIGN KEY (category) REFERENCES categories(category)
)
/
CREATE TABLE doc_similarities (
    source_doc_id VARCHAR2(64) NOT NULL,
    target_doc_id VARCHAR2(64) NOT NULL,
    sim_score NUMBER(8,6) NOT NULL,
    rank_no   NUMBER(5) NOT NULL,
    CONSTRAINT pk_doc_similarities PRIMARY KEY (source_doc_id, target_doc_id),
    CONSTRAINT fk_ds_src FOREIGN KEY (source_doc_id) REFERENCES acme_docs(doc_id),
    CONSTRAINT fk_ds_tgt FOREIGN KEY (target_doc_id) REFERENCES acme_docs(doc_id),
    CONSTRAINT ck_ds_not_self CHECK (source_doc_id <> target_doc_id)
)
"""
        with self._conn.cursor() as cur:
            for stmt in graph_ddl.split("/"):
                if stmt.strip():
                    cur.execute(stmt)
        self._conn.commit()

        doc_ids = [d["doc_id"] for d in DOCS]
        categories = sorted({d["category"] for d in DOCS})
        doc_cat_rows = [(d["doc_id"], d["category"]) for d in DOCS]
        sim = self._doc_vectors @ self._doc_vectors.T   # cosine (unit vectors)
        np.fill_diagonal(sim, -np.inf)                  # never link a doc to itself
        top_n = 3
        sim_rows = []
        for i, src in enumerate(doc_ids):
            for rank, j in enumerate(np.argsort(sim[i])[::-1][:top_n], start=1):
                sim_rows.append((src, doc_ids[int(j)], round(float(sim[i][int(j)]), 6), rank))

        with self._conn.cursor() as cur:
            cur.executemany("INSERT INTO categories (category) VALUES (:1)", [(c,) for c in categories])
            cur.executemany("INSERT INTO doc_categories (doc_id, category) VALUES (:1, :2)", doc_cat_rows)
            cur.executemany(
                "INSERT INTO doc_similarities (source_doc_id, target_doc_id, sim_score, rank_no) "
                "VALUES (:1, :2, :3, :4)",
                sim_rows,
            )
        self._conn.commit()

        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'ACME_GRAPH'")
            if cur.fetchone()[0] > 0:
                cur.execute("DROP PROPERTY GRAPH acme_graph")
            cur.execute("""
                CREATE PROPERTY GRAPH acme_graph
                VERTEX TABLES (
                    acme_docs  KEY (doc_id)   LABEL doc      PROPERTIES (doc_id, title, category),
                    categories KEY (category) LABEL category PROPERTIES (category)
                )
                EDGE TABLES (
                    doc_categories KEY (doc_id, category)
                        SOURCE KEY (doc_id) REFERENCES acme_docs (doc_id)
                        DESTINATION KEY (category) REFERENCES categories (category)
                        LABEL in_category,
                    doc_similarities KEY (source_doc_id, target_doc_id)
                        SOURCE KEY (source_doc_id) REFERENCES acme_docs (doc_id)
                        DESTINATION KEY (target_doc_id) REFERENCES acme_docs (doc_id)
                        LABEL similar_to PROPERTIES (sim_score, rank_no)
                )
            """)
        self._conn.commit()

    def _embed_query_oracle(self, text: str):
        return array.array("f", self._query_vec(text).astype(np.float32).tolist())

    @staticmethod
    def _text_query(query: str) -> str:
        """Build a forgiving Oracle Text query: any meaningful term, relevance-ranked.

        Tokens are brace-escaped (so reserved words / punctuation can't break the
        parse) and joined with ACCUM, so a doc matching *any* term scores — far more
        useful for free-form input than the notebook's exact-phrase match.
        """
        tokens = re.findall(r"[A-Za-z0-9]+", query.lower())
        meaningful = [t for t in tokens if len(t) > 2 and t not in _STOP]
        chosen = meaningful or tokens[:1]
        if not chosen:
            return "{__no_match__}"
        return " ACCUM ".join("{%s}" % t for t in chosen)

    # ── public retrieval techniques ─────────────────────────────────────────────
    def search(self, query: str, technique: str = "vector", k: int = 4) -> list[Hit]:
        """Dispatch to a retrieval technique. technique ∈ vector|keyword|hybrid."""
        self.initialize()
        technique = (technique or "vector").lower()
        with self._lock:
            if self.backend == "oracle":
                fn = {
                    "vector": self._oracle_vector,
                    "keyword": self._oracle_keyword,
                    "hybrid": self._oracle_hybrid,
                    "graph": self._oracle_graph,
                }.get(technique, self._oracle_vector)
            else:
                fn = {
                    "vector": self._mem_vector,
                    "keyword": self._mem_keyword,
                    "hybrid": self._mem_hybrid,
                    "graph": self._mem_graph,
                }.get(technique, self._mem_vector)
            return fn(query, k)

    def retrieve(self, query: str, k: int = 3) -> list[tuple[str, float]]:
        """Unified retriever used by RAG answer / workflow / agent: [(content, score)]."""
        hits = self.search(query, technique="vector", k=k)
        return [(h.content, h.score) for h in hits]

    # ── Oracle techniques ────────────────────────────────────────────────────────
    def _oracle_vector(self, query: str, k: int) -> list[Hit]:
        q = self._embed_query_oracle(query)
        sql = f"""
            SELECT doc_id, title, category, content,
                   ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS similarity
            FROM acme_docs
            ORDER BY similarity DESC
            FETCH FIRST {int(k)} ROWS ONLY
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, q=q)
            return [Hit(d, t, c, float(s), body) for d, t, c, body, s in cur.fetchall()]

    def _oracle_keyword(self, query: str, k: int) -> list[Hit]:
        sql = f"""
            SELECT doc_id, title, category, content, SCORE(1) AS score
            FROM acme_docs
            WHERE CONTAINS(content, :kw, 1) > 0
            ORDER BY SCORE(1) DESC
            FETCH FIRST {int(k)} ROWS ONLY
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, kw=self._text_query(query))
            return [Hit(d, t, c, float(s), body) for d, t, c, body, s in cur.fetchall()]

    def _oracle_hybrid(self, query: str, k: int, per_list: int = 10, rrf_k: int = 60) -> list[Hit]:
        q = self._embed_query_oracle(query)
        sql = f"""
            WITH
            vec AS (
                SELECT doc_id, ROW_NUMBER() OVER (ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)) AS r_vec
                FROM acme_docs ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)
                FETCH FIRST {int(per_list)} ROWS ONLY
            ),
            txt AS (
                SELECT doc_id, ROW_NUMBER() OVER (ORDER BY SCORE(1) DESC) AS r_txt
                FROM acme_docs WHERE CONTAINS(content, :kw, 1) > 0
                ORDER BY SCORE(1) DESC FETCH FIRST {int(per_list)} ROWS ONLY
            ),
            fused AS (
                SELECT COALESCE(v.doc_id, t.doc_id) AS doc_id,
                       NVL(v.r_vec, 999999) AS r_vec, NVL(t.r_txt, 999999) AS r_txt
                FROM vec v FULL OUTER JOIN txt t ON t.doc_id = v.doc_id
            )
            SELECT doc_id, ROUND(1.0/(:rk + r_vec) + 1.0/(:rk + r_txt), 6) AS rrf_score
            FROM fused ORDER BY rrf_score DESC
            FETCH FIRST {int(k)} ROWS ONLY
        """
        with self._conn.cursor() as cur:
            cur.execute(sql, q=q, kw=self._text_query(query), rk=rrf_k)
            out = []
            for doc_id, rrf in cur.fetchall():
                d = self._by_id[doc_id]
                out.append(Hit(doc_id, d["title"], d["category"], float(rrf), d["content"]))
            return out

    def _oracle_graph(self, query: str, k: int, seed_k: int = 5) -> list[Hit]:
        """Vector-seed the graph, then expand over SIMILAR_TO + same-category edges
        (SQL property graph), and blend the scores."""
        q = self._embed_query_oracle(query)
        sql = _GRAPH_SQL.format(seed_k=int(max(seed_k, k)), k=int(k))
        with self._conn.cursor() as cur:
            cur.execute(sql, q=q)
            return [Hit(d, t, c, float(s), body) for d, t, c, body, s in cur.fetchall()]

    # ── In-memory techniques (NumPy fallback) ─────────────────────────────────────
    def _mem_vector(self, query: str, k: int) -> list[Hit]:
        qv = self._query_vec(query)
        sims = self._doc_vectors @ qv  # unit vectors → cosine == dot product
        order = np.argsort(-sims)[:k]
        out = []
        for i in order:
            d = DOCS[int(i)]
            out.append(Hit(d["doc_id"], d["title"], d["category"], float(sims[int(i)]), d["content"]))
        return out

    @staticmethod
    def _term_score(query: str, doc: dict) -> float:
        terms = {t for t in query.lower().split() if len(t) > 2}
        if not terms:
            return 0.0
        haystack = f"{doc['title']} {doc['content']}".lower()
        return sum(haystack.count(t) for t in terms)

    def _mem_keyword(self, query: str, k: int) -> list[Hit]:
        scored = [(self._term_score(query, d), d) for d in DOCS]
        scored = [(s, d) for s, d in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        return [
            Hit(d["doc_id"], d["title"], d["category"], float(s), d["content"])
            for s, d in scored[:k]
        ]

    def _mem_hybrid(self, query: str, k: int, per_list: int = 10, rrf_k: int = 60) -> list[Hit]:
        vec = {h.doc_id: r for r, h in enumerate(self._mem_vector(query, per_list))}
        kw = {h.doc_id: r for r, h in enumerate(self._mem_keyword(query, per_list))}
        fused = []
        for doc_id in set(vec) | set(kw):
            rv = vec.get(doc_id, 999999)
            rt = kw.get(doc_id, 999999)
            fused.append((1.0 / (rrf_k + rv) + 1.0 / (rrf_k + rt), doc_id))
        fused.sort(key=lambda x: -x[0])
        out = []
        for score, doc_id in fused[:k]:
            d = self._by_id[doc_id]
            out.append(Hit(doc_id, d["title"], d["category"], float(score), d["content"]))
        return out

    def _mem_graph(self, query: str, k: int, seed_k: int = 5) -> list[Hit]:
        """Graph-style retrieval without a DB: vector seed, then expand over
        nearest-neighbour (SIMILAR_TO) and same-category links; blend scores with
        the same weights as the Oracle property-graph technique."""
        seed_k = max(seed_k, k)
        qv = self._query_vec(query)
        sims = self._doc_vectors @ qv
        seed_idx = list(np.argsort(-sims))[:seed_k]
        dd = self._doc_vectors @ self._doc_vectors.T   # doc-doc cosine for SIMILAR_TO
        np.fill_diagonal(dd, -np.inf)
        best: dict[str, float] = {}

        def bump(doc_id: str, score: float) -> None:
            if score > best.get(doc_id, -1.0):
                best[doc_id] = score

        for i in seed_idx:
            i = int(i)
            sid = DOCS[i]["doc_id"]
            ss = float(sims[i])
            bump(sid, ss)                                          # seed
            for j in np.argsort(dd[i])[::-1][:3]:                  # SIMILAR_TO hops
                bump(DOCS[int(j)]["doc_id"], 0.70 * ss + 0.30 * float(dd[i][int(j)]))
            for d in DOCS:                                         # same-category hops
                if d["category"] == DOCS[i]["category"] and d["doc_id"] != sid:
                    bump(d["doc_id"], 0.85 * ss + 0.15 * 1.0)

        ranked = sorted(best.items(), key=lambda kv: -kv[1])[:k]
        out = []
        for doc_id, score in ranked:
            d = self._by_id[doc_id]
            out.append(Hit(doc_id, d["title"], d["category"], float(score), d["content"]))
        return out


# Module-level singleton.
store = VectorStore()
