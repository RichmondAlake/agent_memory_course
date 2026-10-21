"""Stage 2 of retrieval: an open cross-encoder re-orders the candidates a first stage returns.

BAAI/bge-reranker-v2-m3 (Apache-2.0), the int8 ONNX build FastEmbed serves from Hugging Face, the same model
as the notebook's §2.7. It reads the question and each section together and scores the pair. Loaded on first
use (about 0.6 GB, downloaded once).
"""
from __future__ import annotations

import threading
import time

MODEL = "BAAI/bge-reranker-v2-m3-int8"
CANDIDATES = 8
_lock = threading.Lock()
_state: dict = {"model": None, "load_seconds": None}


def _model():
    with _lock:
        if _state["model"] is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            started = time.perf_counter()
            _state["model"] = TextCrossEncoder(model_name=MODEL)
            _state["load_seconds"] = round(time.perf_counter() - started, 1)
        return _state["model"]


def status() -> dict:
    return {"model": MODEL, "loaded": _state["model"] is not None, "load_seconds": _state["load_seconds"]}


def rerank(query: str, hits: list, k: int) -> dict:
    """Score every (query, section) pair; return the hits best first, cut to k, with each one's move."""
    model = _model()
    started = time.perf_counter()
    with _lock:
        scores = [float(s) for s in model.rerank(query, [f"{h.title}. {h.content}" for h in hits])]
    ms = round((time.perf_counter() - started) * 1000)
    order = sorted(range(len(hits)), key=lambda i: -scores[i])
    rows = [{"doc_id": hits[i].doc_id, "title": hits[i].title, "before": i + 1, "after": new + 1,
             "score": round(scores[i], 3)} for new, i in enumerate(order)]
    return {"hits": [hits[i] for i in order[:k]], "rows": rows, "ms": ms, "model": MODEL}
