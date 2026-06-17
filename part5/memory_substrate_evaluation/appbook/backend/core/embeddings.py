"""Local, open-source embeddings: nomic-embed-text-v1.5 (768-dim) via fastembed.

Torch-free ONNX — no API key, no network after the first model download. fastembed
applies nomic's `search_document:` / `search_query:` prefixes internally, so passages
(``embed``) and questions (``embed_query``) land in the same vector space. The model
is loaded lazily on first use so the web server starts instantly.
"""
from __future__ import annotations

import threading
from typing import List

import numpy as np

from backend.config import settings


def unit(v) -> np.ndarray:
    """Normalize to a unit vector so cosine similarity is a plain dot product."""
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


class NomicEmbedder:
    """Thread-safe, lazily-initialised wrapper around fastembed's nomic model."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embed_model
        self._model = None
        self._lock = threading.Lock()
        self._dim = 0

    def _ensure(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(model_name=self.model_name)
                    self._dim = int(len(next(iter(self._model.query_embed(["probe"])))))

    @property
    def dim(self) -> int:
        self._ensure()
        return self._dim

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        self._ensure()
        return np.array([unit(v) for v in self._model.embed(list(texts))], dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        self._ensure()
        return unit(next(iter(self._model.query_embed([text]))))


# Module-level singleton shared by the DB substrate.
embedder = NomicEmbedder()
