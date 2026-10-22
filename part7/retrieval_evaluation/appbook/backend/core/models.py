"""The two local models, loaded on first use at the notebook's pinned revisions.

bge-small-en-v1.5 embeds a typed query (a stored test or dev query uses its stored vector instead), and the
ms-marco cross-encoder reranks one query's top documents. Corpora are never re-embedded.
"""
from __future__ import annotations

import array
import threading
import time

import numpy as np

from backend.config import BGE_QUERY_PREFIX, PIN
from backend.core import tracing

_lock = threading.Lock()
_run_lock = threading.Lock()
_embedder = None
_reranker = None
LOAD_SECONDS: dict[str, float] = {}


def _snapshot(key: str) -> str:
    from huggingface_hub import snapshot_download

    repo, revision, model_file = PIN[key]
    return snapshot_download(repo, revision=revision, allow_patterns=[model_file, "*.json", "vocab.txt"])


def embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding
            from fastembed.common.model_description import ModelSource, PoolingType

            started = time.perf_counter()
            repo, _, model_file = PIN["bge"]
            name = "beir7/bge"
            if name not in {m["model"] for m in TextEmbedding.list_supported_models()}:
                TextEmbedding.add_custom_model(model=name, pooling=PoolingType.CLS, normalization=True,
                                               sources=ModelSource(hf=repo), dim=384, model_file=model_file)
            _embedder = TextEmbedding(model_name=name, specific_model_path=_snapshot("bge"))
            LOAD_SECONDS["bge"] = round(time.perf_counter() - started, 1)
    return _embedder


def reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            started = time.perf_counter()
            _reranker = TextCrossEncoder(model_name="Xenova/ms-marco-MiniLM-L-6-v2",
                                         specific_model_path=_snapshot("reranker"))
            LOAD_SECONDS["reranker"] = round(time.perf_counter() - started, 1)
    return _reranker


def embed_query(text: str) -> tuple[array.array, float]:
    """A typed query's bge vector (with the model's retrieval instruction) and the milliseconds it took."""
    model = embedder()
    with _run_lock, tracing.traced("embed query", "EMBEDDING", **{"embedding.model_name": PIN["bge"][0],
                                                                  "input.value": text[:2000]}):
        started = time.perf_counter()
        vector = next(iter(model.embed([BGE_QUERY_PREFIX + text])))
        ms = (time.perf_counter() - started) * 1000
    return array.array("f", np.asarray(vector, dtype=np.float32).tolist()), ms


def rerank_scores(query: str, texts: list[str]) -> tuple[list[float], float]:
    """Cross-encoder scores, shortest text first in batches of four (the notebook's §8.1), and the milliseconds."""
    model = reranker()
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    scores = [0.0] * len(texts)
    with _run_lock:
        started = time.perf_counter()
        for i, score in zip(order, model.rerank(query, [texts[i] for i in order], batch_size=4)):
            scores[i] = float(score)
        ms = (time.perf_counter() - started) * 1000
    return scores, ms


def status() -> dict:
    return {"bge": "loaded" if _embedder is not None else "on first typed query",
            "reranker": "loaded" if _reranker is not None else "on first rerank", "load_seconds": dict(LOAD_SECONDS)}
