"""The notebook's Part 3 diagnostics, recomputed from the stored corpora: query and document length, relevant
documents per query, lexical overlap, vocabulary mismatch and the cohesion of relevant documents.

Computed once per dataset and kept in memory; the document vectors read for cohesion are released afterwards.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from backend.config import DATASETS, settings
from backend.core import db, text

_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _vectors(table: str) -> tuple[list[str], np.ndarray]:
    rows = db.rows(f"SELECT doc_id, embedding FROM {table} ORDER BY doc_id")
    return [r[0] for r in rows], np.array([np.asarray(r[1], dtype=np.float32) for r in rows])


def compute(ds: str) -> dict:
    if ds not in DATASETS:
        raise ValueError(ds)
    with _lock:
        if ds in _cache:
            return _cache[ds]
    started = time.perf_counter()
    queries = {q: t for q, t in db.rows(f"SELECT query_id, text FROM beir7_{ds}_queries")}
    judged: dict[str, dict[str, int]] = {}
    for q, d, g in db.rows(f"SELECT query_id, doc_id, grade FROM beir7_{ds}_qrels"):
        if q in queries:
            judged.setdefault(q, {})[d] = int(g)
    docs = sorted({d for rel in judged.values() for d in rel})
    words: dict[str, set] = {}
    for start in range(0, len(docs), 500):
        chunk = docs[start:start + 500]
        binds = {f"d{i}": d for i, d in enumerate(chunk)}
        for d, body in db.rows(f"SELECT doc_id, body FROM beir7_{ds}_docs WHERE doc_id IN "
                               f"({', '.join(':' + b for b in binds)})", **binds):
            words[d] = set(text.content_words(body or ""))
    overlaps, mismatched = [], []
    for q, rel in judged.items():
        qwords = set(text.content_words(queries[q]))
        for d in rel:
            if d in words and qwords:
                shared = len(qwords & words[d])
                overlaps.append(shared / len(qwords))
                mismatched.append(shared <= 1)
    doc_lengths = [int(n) for (n,) in db.rows(
        f"SELECT NVL(REGEXP_COUNT(body, '\\S+'), 0) FROM beir7_{ds}_docs")]
    ids, matrix = _vectors(f"beir7_{ds}_bge")
    position = {d: i for i, d in enumerate(ids)}
    pair_sims, multi = [], 0
    for q, rel in judged.items():
        idx = [position[d] for d in rel if d in position]
        if len(idx) >= 2:
            multi += 1
            sims = matrix[idx] @ matrix[idx].T
            pair_sims.extend(sims[np.triu_indices(len(idx), 1)])
    rng = np.random.default_rng(settings.seed)
    a, b = rng.integers(0, len(ids), 20000), rng.integers(0, len(ids), 20000)
    random_sims = (matrix[a] * matrix[b]).sum(axis=1)[a != b]
    del matrix
    out = {
        "dataset": ds, "name": DATASETS[ds]["name"],
        "query_words_median": int(np.median([len(t.split()) for t in queries.values()])),
        "document_words_median": int(np.median(doc_lengths)),
        "relevant_per_query": round(float(np.mean([len(judged.get(q, {})) for q in queries])), 2),
        "lexical_overlap": round(float(np.mean(overlaps)), 3),
        "vocabulary_mismatch": round(float(np.mean(mismatched)), 3),
        "no_shared_word": round(float(np.mean(np.array(overlaps) == 0)), 3),
        "queries_with_2plus_relevant": round(multi / len(queries), 3),
        "cohesion_relevant": round(float(np.mean(pair_sims)), 3) if pair_sims else None,
        "cohesion_random": round(float(np.mean(random_sims)), 3),
        "seconds": round(time.perf_counter() - started, 1),
    }
    with _lock:
        _cache[ds] = out
    return out
