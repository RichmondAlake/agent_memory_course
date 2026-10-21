"""Data for the RAG page's HNSW lab: the policy, one sentence per row, with real embeddings.

The browser builds and searches an HNSW graph over these vectors itself (the same algorithm as the
notebook's TinyHNSW), so changing m, efConstruction or efSearch rebuilds instantly. The 2-D projection
is for drawing only; every distance in the lab is computed on the full 768-dimensional vectors.
"""
from __future__ import annotations

import hashlib
import re
import threading

import numpy as np

from backend.core import db

_lock = threading.Lock()
_cache: dict = {}


def _sentences() -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, category, content FROM policy_docs ORDER BY doc_id")
        rows = cur.fetchall()
    return [{"doc_id": d, "category": c, "text": s}
            for d, c, body in rows for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]


def corpus() -> dict:
    """Every policy sentence with its unit embedding and a 2-D PCA position (recomputed if the policy changed)."""
    items = _sentences()
    key = hashlib.sha256("\n".join(i["text"] for i in items).encode()).hexdigest()
    with _lock:
        if _cache.get("key") != key:
            vectors = db.embed_documents([i["text"] for i in items])
            mu = vectors.mean(axis=0)
            _, _, vt = np.linalg.svd(vectors - mu, full_matrices=False)
            xy = (vectors - mu) @ vt[:2].T
            lo, hi = xy.min(axis=0), xy.max(axis=0)
            _cache.update(key=key, items=items, vectors=vectors, mu=mu, basis=vt[:2], lo=lo, span=np.where(hi - lo > 0, hi - lo, 1))
        c = dict(_cache)
    xy = ((c["vectors"] - c["mu"]) @ c["basis"].T - c["lo"]) / c["span"]
    return {"items": [{**item, "id": i, "x": round(float(x), 4), "y": round(float(y), 4)}
                      for i, (item, (x, y)) in enumerate(zip(c["items"], xy))],
            "dim": int(c["vectors"].shape[1]),
            "vectors": [[round(float(v), 5) for v in row] for row in c["vectors"]]}


def query(text: str) -> dict:
    """A question's unit embedding and its position in the same 2-D projection."""
    if "key" not in _cache:
        corpus()
    q = db.embed_query(text)
    c = dict(_cache)
    x, y = ((q - c["mu"]) @ c["basis"].T - c["lo"]) / c["span"]
    return {"vector": [round(float(v), 5) for v in q], "x": round(float(x), 4), "y": round(float(y), 4)}
