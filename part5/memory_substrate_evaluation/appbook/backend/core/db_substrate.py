"""The database substrate: agent memory in Oracle AI Database with vector search.

Each note is embedded with nomic and stored in a native ``VECTOR`` column; retrieval
is semantic — ``VECTOR_DISTANCE(..., COSINE)`` finds notes by *meaning*, so a question
phrased with different words still lands on the right passage.

Prefers Oracle exactly as the notebook does. If Oracle is unreachable it transparently
falls back to an in-memory NumPy cosine index so the whole app still runs; the active
backend is reported to the UI via /api/health.
"""
from __future__ import annotations

import array
import threading
import time

import numpy as np

from backend.config import settings
from backend.core.embeddings import embedder, unit


class DatabaseSubstrate:
    """Oracle vector store (preferred) with a NumPy fallback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.backend = "uninitialized"      # → "oracle" | "memory"
        self.error: str | None = None
        self.dim = 0
        self._conn = None
        self._docs: list[dict] = []
        self._vectors: np.ndarray | None = None
        self.ready = False
        self.last_embed_ms = 0.0
        self.last_store_ms = 0.0

    # ── lifecycle ───────────────────────────────────────────────────────────
    def initialize(self) -> None:
        """Pick a backend (warms the embedder + tries Oracle). Idempotent."""
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            self.dim = embedder.dim  # warms the nomic model (first call downloads it)
            if settings.oracle_enabled:
                try:
                    self._connect_oracle()
                    self.backend = "oracle"
                except Exception as exc:  # noqa: BLE001 — any failure → memory fallback
                    self.error = str(exc).splitlines()[0][:200]
                    self.backend = "memory"
            else:
                self.backend = "memory"
            self.ready = True

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "dim": self.dim,
            "doc_count": self._doc_count(),
            "error": self.error,
        }

    def _doc_count(self) -> int:
        if self.backend == "oracle" and self._conn is not None:
            try:
                with self._conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) FROM {settings.db_table}")
                    return int(cur.fetchone()[0])
            except Exception:  # noqa: BLE001
                return 0
        return len(self._docs)

    def reset(self) -> None:
        """Empty the substrate so the demo can re-run from scratch."""
        self.initialize()
        with self._lock:
            if self.backend == "oracle":
                try:
                    self._create_table()  # drop + recreate empty
                except Exception as exc:  # noqa: BLE001
                    self.error = str(exc).splitlines()[0][:200]
            else:
                self._docs = []
                self._vectors = None

    # ── Oracle wiring ─────────────────────────────────────────────────────────
    def _connect_oracle(self) -> None:
        import oracledb

        self._conn = oracledb.connect(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
            tcp_connect_timeout=8,
        )
        self._create_table()

    def _create_table(self) -> None:
        ddl = f"""
BEGIN EXECUTE IMMEDIATE 'DROP TABLE {settings.db_table} CASCADE CONSTRAINTS PURGE';
EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;
/
CREATE TABLE {settings.db_table} (
    doc_id    VARCHAR2(64) PRIMARY KEY,
    title     VARCHAR2(400),
    category  VARCHAR2(64),
    content   VARCHAR2(4000),
    embedding VECTOR({self.dim}, FLOAT32)
)
"""
        with self._conn.cursor() as cur:
            for stmt in ddl.split("/"):
                if stmt.strip():
                    cur.execute(stmt)
        self._conn.commit()

    # ── writes ──────────────────────────────────────────────────────────────
    def write_all(self, docs: list[dict]) -> dict:
        """Embed + store the whole corpus. Returns embed/store timing for the UI."""
        self.initialize()
        with self._lock:
            texts = [f"{d['title']}. {d['content']}" for d in docs]

            t0 = time.perf_counter()
            vectors = embedder.embed_documents(texts)
            embed_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            if self.backend == "oracle":
                self._create_table()  # fresh
                rows = [
                    (d["doc_id"], d["title"], d["category"], d["content"][:3999],
                     array.array("f", vec.astype(np.float32).tolist()))
                    for d, vec in zip(docs, vectors)
                ]
                with self._conn.cursor() as cur:
                    cur.executemany(
                        f"INSERT INTO {settings.db_table} (doc_id, title, category, content, embedding) "
                        f"VALUES (:1, :2, :3, :4, :5)", rows,
                    )
                self._conn.commit()
            else:
                self._docs = list(docs)
                self._vectors = vectors
            store_ms = (time.perf_counter() - t1) * 1000

            self.last_embed_ms, self.last_store_ms = embed_ms, store_ms
            return {
                "backend": self.backend,
                "doc_count": len(docs),
                "embed_ms": round(embed_ms, 2),
                "store_ms": round(store_ms, 2),
                "total_ms": round(embed_ms + store_ms, 2),
                "per_doc_ms": round((embed_ms + store_ms) / len(docs), 3) if docs else 0,
                "dim": self.dim,
                "note": "Each note is embedded with nomic, then indexed for semantic search.",
            }

    # ── search (semantic vector) ──────────────────────────────────────────────
    def search(self, query: str, k: int = 4) -> dict:
        self.initialize()
        with self._lock:
            t0 = time.perf_counter()
            qv = embedder.embed_query(query)
            if self.backend == "oracle":
                hits = self._oracle_search(qv, k)
                cmd = (
                    f"SELECT doc_id, title, content,\n"
                    f"       ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS similarity\n"
                    f"FROM {settings.db_table} ORDER BY similarity DESC FETCH FIRST {k} ROWS ONLY"
                )
            else:
                hits = self._memory_search(qv, k)
                cmd = "numpy: cosine(query_vec, doc_vecs).argsort()[::-1][:k]  # in-memory fallback"
            latency = (time.perf_counter() - t0) * 1000
            return {
                "backend": self.backend,
                "method": "semantic (nomic embeddings + cosine vector search)",
                "hits": hits,
                "latency_ms": round(latency, 2),
                "command": cmd,
            }

    def _oracle_search(self, qv: np.ndarray, k: int) -> list[dict]:
        q = array.array("f", qv.astype(np.float32).tolist())
        sql = (
            f"SELECT doc_id, title, category, content, "
            f"ROUND(1 - VECTOR_DISTANCE(embedding, :q, COSINE), 4) AS sim "
            f"FROM {settings.db_table} ORDER BY sim DESC FETCH FIRST {int(k)} ROWS ONLY"
        )
        with self._conn.cursor() as cur:
            cur.execute(sql, q=q)
            out = []
            for doc_id, title, category, content, sim in cur.fetchall():
                body = content.read() if hasattr(content, "read") else str(content)
                out.append({"doc_id": doc_id, "title": title, "category": category,
                            "score": float(sim), "snippet": body[:150].strip() + "…"})
            return out

    def _memory_search(self, qv: np.ndarray, k: int) -> list[dict]:
        if self._vectors is None or not len(self._docs):
            return []
        sims = self._vectors @ qv  # unit vectors → cosine == dot product
        order = np.argsort(-sims)[:k]
        out = []
        for i in order:
            d = self._docs[int(i)]
            out.append({"doc_id": d["doc_id"], "title": d["title"], "category": d["category"],
                        "score": round(float(sims[int(i)]), 4),
                        "snippet": d["content"][:150].strip() + "…"})
        return out


db_substrate = DatabaseSubstrate()
