"""Oracle AI Database access for every form factor: one connection pool, the embedder, and start-up.

``bootstrap()`` runs once in the background at start-up: it loads the embedding model, opens the
pool, removes the old Acme Cloud dataset, and creates and seeds whatever the mortgage schema lacks.
"""
from __future__ import annotations

import array
import json
import threading
import time
from contextlib import contextmanager

import numpy as np

from backend.config import settings
from backend.core import policy

_state = {"ready": False, "backend": "initializing", "error": None, "dim": 0, "removed_legacy": []}
_lock = threading.Lock()
_embed_lock = threading.Lock()
_pool = None
_embedder = None


def unit(v) -> np.ndarray:
    """Normalize to a unit vector so cosine similarity is a plain dot product."""
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def embed_documents(texts: list[str]) -> np.ndarray:
    with _embed_lock:
        return np.array([unit(v) for v in _embedder.embed(texts)], dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """fastembed applies nomic's query prefix inside query_embed."""
    with _embed_lock:
        return unit(next(_embedder.query_embed(text)))


def as_vector(v: np.ndarray) -> array.array:
    """The form python-oracledb binds to a VECTOR parameter."""
    return array.array("f", np.asarray(v, dtype=np.float32).tolist())


@contextmanager
def connection():
    """A pooled connection; commits are explicit in the callers."""
    if _pool is None:
        raise RuntimeError(f"Oracle AI Database is not available: {_state['error'] or 'still starting'}")
    conn = _pool.acquire()
    try:
        yield conn
    finally:
        _pool.release(conn)


def status() -> dict:
    return {**_state, "doc_count": len(policy.POLICY_DOCS)}


def ready() -> bool:
    return _state["ready"]


def wait_ready(timeout: float = 120) -> None:
    deadline = time.time() + timeout
    while not _state["ready"] and time.time() < deadline:
        if _state["backend"] == "unavailable":
            break
        time.sleep(0.25)
    if not _state["ready"]:
        raise RuntimeError(f"Oracle AI Database is not available: {_state['error'] or 'still starting'}")


def bootstrap() -> None:
    """Idempotent warm-up: embedder, pool, legacy clean-up, schema and seed."""
    global _pool, _embedder
    with _lock:
        if _state["ready"]:
            return
        try:
            from fastembed import TextEmbedding
            import oracledb

            _embedder = TextEmbedding(model_name=settings.embed_model)
            _state["dim"] = int(embed_documents(["probe"]).shape[1])
            last = None
            for attempt in range(max(1, settings.oracle_connect_retries)):
                try:
                    _pool = oracledb.create_pool(user=settings.oracle_user, password=settings.oracle_password,
                                                 dsn=settings.oracle_dsn, min=1, max=8, increment=1)
                    with connection() as conn, conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM dual")
                    break
                except Exception as exc:  # noqa: BLE001 — retry while the database starts
                    last, _pool = exc, None
                    time.sleep(settings.oracle_connect_delay)
            if _pool is None:
                raise last or RuntimeError("could not connect")
            with connection() as conn:
                _state["removed_legacy"] = policy.drop_legacy(conn)
                ensure_schema(conn)
            _state.update(ready=True, backend="oracle", error=None)
        except Exception as exc:  # noqa: BLE001 — surfaced through /api/health
            _state.update(ready=False, backend="unavailable", error=str(exc).splitlines()[0][:240])


def ensure_schema(conn) -> list[str]:
    """Create any missing table, seed the policy if it is empty, and build the graph if it is missing."""
    created = []
    with conn.cursor() as cur:
        present = policy.existing_tables(cur)
        for table in policy.APP_TABLES:
            if table not in present:
                cur.execute(policy.TABLE_DDL[table].format(dim=_state["dim"]))
                created.append(table)
        cur.execute("CREATE INDEX IF NOT EXISTS agent_session_entries_key ON agent_session_entries "
                    "(store_name, project_key, session_id, subpath, seq)")
        cur.execute("SELECT COUNT(*) FROM policy_docs")
        empty = cur.fetchone()[0] == 0
    conn.commit()
    if empty:
        seed_policy(conn)
    ensure_indexes(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'POLICY_GRAPH'")
        has_graph = cur.fetchone()[0] > 0
        cur.execute("SELECT COUNT(*) FROM policy_doc_similarities")
        has_edges = cur.fetchone()[0] > 0
    if empty or not has_graph or not has_edges:
        rebuild_graph(conn)
    return created


def seed_policy(conn) -> None:
    """Insert the seventeen policy sections at version 1, with embeddings and JSON rules."""
    vectors = embed_documents([policy.doc_text(d) for d in policy.POLICY_DOCS])
    rows = [(d["doc_id"], d["title"], d["category"], d["content"],
             json.dumps(d["rules"]) if d["rules"] else None, as_vector(v))
            for d, v in zip(policy.POLICY_DOCS, vectors)]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO policy_docs (doc_id, title, category, content, rules, embedding) "
                        "VALUES (:1, :2, :3, :4, :5, :6)", rows)
    conn.commit()


def ensure_indexes(conn) -> None:
    import oracledb

    with conn.cursor() as cur:
        cur.execute("SELECT LOWER(index_name) FROM user_indexes WHERE table_name = 'POLICY_DOCS'")
        indexes = {name for (name,) in cur.fetchall()}
        if "policy_text_idx" not in indexes:
            cur.execute("CREATE INDEX policy_text_idx ON policy_docs(content) "
                        "INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (ON COMMIT)')")
        if "policy_vec_idx" not in indexes:
            try:
                cur.execute("CREATE VECTOR INDEX policy_vec_idx ON policy_docs(embedding) "
                            "ORGANIZATION INMEMORY NEIGHBOR GRAPH DISTANCE COSINE WITH TARGET ACCURACY 90 "
                            "PARAMETERS (TYPE HNSW, NEIGHBORS 16, EFCONSTRUCTION 200)")
            except oracledb.DatabaseError:
                pass  # exact search still works without the HNSW index
    conn.commit()


def rebuild_graph(conn) -> int:
    """Recompute the IN_CATEGORY and SIMILAR_TO edges from the current embeddings and (re)register the graph."""
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, category, embedding FROM policy_docs ORDER BY doc_id")
        rows = cur.fetchall()
        doc_ids = [r[0] for r in rows]
        vectors = np.array([unit(np.array(r[2], dtype=np.float32)) for r in rows])
        cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'POLICY_GRAPH'")
        if cur.fetchone()[0]:
            cur.execute("DROP PROPERTY GRAPH policy_graph")
        cur.execute("DELETE FROM policy_doc_similarities")
        cur.execute("DELETE FROM policy_doc_categories")
        cur.execute("DELETE FROM policy_categories")
        categories = sorted({r[1] for r in rows})
        cur.executemany("INSERT INTO policy_categories (category) VALUES (:1)", [(c,) for c in categories])
        cur.executemany("INSERT INTO policy_doc_categories (doc_id, category) VALUES (:1, :2)",
                        [(r[0], r[1]) for r in rows])
        sim = vectors @ vectors.T
        np.fill_diagonal(sim, -np.inf)
        edges = [(src, doc_ids[int(j)], round(float(sim[i][int(j)]), 6), rank)
                 for i, src in enumerate(doc_ids)
                 for rank, j in enumerate(np.argsort(sim[i])[::-1][:3], start=1)]
        cur.executemany("INSERT INTO policy_doc_similarities (source_doc_id, target_doc_id, sim_score, rank_no) "
                        "VALUES (:1, :2, :3, :4)", edges)
        cur.execute("""
            CREATE PROPERTY GRAPH policy_graph
            VERTEX TABLES (
                policy_docs       KEY (doc_id)   LABEL doc      PROPERTIES (doc_id, title, category),
                policy_categories KEY (category) LABEL category PROPERTIES (category))
            EDGE TABLES (
                policy_doc_categories KEY (doc_id, category)
                    SOURCE KEY (doc_id) REFERENCES policy_docs (doc_id)
                    DESTINATION KEY (category) REFERENCES policy_categories (category)
                    LABEL in_category,
                policy_doc_similarities KEY (source_doc_id, target_doc_id)
                    SOURCE KEY (source_doc_id) REFERENCES policy_docs (doc_id)
                    DESTINATION KEY (target_doc_id) REFERENCES policy_docs (doc_id)
                    LABEL similar_to PROPERTIES (sim_score, rank_no))""")
    conn.commit()
    return len(edges)


def reset_demo() -> dict:
    """Drop and rebuild every appbook table from the seed: policy back to version 1, no applications."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'POLICY_GRAPH'")
            if cur.fetchone()[0]:
                cur.execute("DROP PROPERTY GRAPH policy_graph")
            for table in reversed(policy.APP_TABLES):
                cur.execute(policy._DROP.format(t=table))
            cur.execute("PURGE RECYCLEBIN")
        conn.commit()
        created = ensure_schema(conn)
    return {"recreated": created}
