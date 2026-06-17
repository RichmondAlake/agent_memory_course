"""FF2 — the rigorous retrieval bake-off on the BEIR `scifact` benchmark.

Loads the **precomputed** corpus + 768-dim nomic vectors from ``beir_scifact_seed.npz``
(skipping the ~11-minute embed), pulls the tiny queries + relevance judgments (qrels)
from the Hugging Face Hub, and scores three retrievers — keyword / vector / hybrid —
with the classic IR metrics: precision@k, recall@k, NDCG@k.

Retrieval runs in-memory over the seed vectors (cosine = dot product, since the seed
vectors are unit-normalized), reusing the app's already-warm embedder for the query
side. This is the same comparison the notebook runs against Oracle ``beir_docs``.
"""
from __future__ import annotations

import math
import re
import threading
from collections.abc import Iterator

import numpy as np

from backend.config import settings
from backend.core.retrieval import store

_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "do", "does", "we",
         "i", "my", "for", "how", "what", "can", "me", "with", "be", "it", "this", "that", "from",
         "at", "as", "by", "if", "show", "have", "has", "not", "no", "than", "more", "less"}


def _terms(q: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", q.lower()) if len(t) > 2 and t not in _STOP}


# Each BEIR dataset we ship a seed for: a human label, the seed .npz filename (next to the
# scifact seed), and the HF names for its queries + qrels.
DATASETS = {
    "scifact": {"label": "scifact (scientific claims)", "seed": "beir_scifact_seed.npz",
                "hf": "BeIR/scifact", "qrels": "BeIR/scifact-qrels",
                "blurb": "scientific claims vs. paper abstracts — ~1 relevant doc per query, so precision@10 is capped near 0.1."},
    "fiqa": {"label": "fiqa (financial questions)", "seed": "beir_fiqa_seed.npz",
             "hf": "BeIR/fiqa", "qrels": "BeIR/fiqa-qrels",
             "blurb": "financial questions vs. forum/opinion posts — ~2.6 relevant docs per query, so precision@10 runs higher. A different domain to measure on."},
}


class BeirBench:
    """Lazy-loaded BEIR benchmark over a precomputed seed artifact (one per dataset)."""

    def __init__(self, key: str = "scifact") -> None:
        self.key = key
        self.spec = DATASETS[key]
        self._lock = threading.Lock()
        self.ready = False
        self.error: str | None = None
        self.doc_ids: list[str] = []
        self.vectors: np.ndarray | None = None     # (N, 768), unit-normalized
        self._content_terms: list[set[str]] = []
        self.qtext: dict[str, str] = {}
        self.qrels: dict[str, dict[str, int]] = {}
        self.test_qids: list[str] = []

    def status(self) -> dict:
        return {"dataset": self.key, "ready": self.ready, "error": self.error,
                "n_docs": len(self.doc_ids), "n_queries": len(self.test_qids)}

    def initialize(self) -> None:
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            try:
                seed = np.load(settings.seed_path.parent / self.spec["seed"], allow_pickle=True)
                self.doc_ids = [str(x) for x in seed["doc_ids"]]
                contents = [str(x) for x in seed["contents"]]
                titles = [str(x) for x in seed["titles"]]
                self.vectors = seed["vectors"].astype(np.float32)
                self._content_terms = [_terms(f"{t} {c}") for t, c in zip(titles, contents)]
                seed_set = set(self.doc_ids)

                from datasets import load_dataset

                queries = load_dataset(self.spec["hf"], "queries", split="queries")
                qrels = load_dataset(self.spec["qrels"], split="test")
                self.qtext = {str(q["_id"]): (q["text"] or "") for q in queries}
                by_q: dict[str, dict[str, int]] = {}
                for r in qrels:
                    by_q.setdefault(str(r["query-id"]), {})[str(r["corpus-id"])] = int(r["score"])
                self.qrels = by_q
                # queries whose relevant docs are all in the seed → recall achievable
                self.test_qids = [qid for qid in by_q
                                  if qid in self.qtext
                                  and all(c in seed_set for c, s in by_q[qid].items() if s > 0)][:settings.beir_n_queries]
                self.ready = True
            except Exception as exc:  # noqa: BLE001
                self.error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
                raise

    # ── retrievers (return ranked doc_ids) ────────────────────────────────────
    def _vector_rank(self, query: str, k: int) -> list[str]:
        qv = store.query_vector(query).astype(np.float32)
        sims = self.vectors @ qv
        idx = np.argsort(-sims)[:k]
        return [self.doc_ids[i] for i in idx]

    def _keyword_rank(self, query: str, k: int) -> list[str]:
        qt = _terms(query)
        scored = [(len(qt & self._content_terms[i]), i) for i in range(len(self.doc_ids))]
        scored = [s for s in scored if s[0] > 0]
        scored.sort(key=lambda s: -s[0])
        return [self.doc_ids[i] for _, i in scored[:k]]

    def _hybrid_rank(self, query: str, k: int, per_list: int = 50, rrf_k: int = 60) -> list[str]:
        vec = self._vector_rank(query, per_list)
        txt = self._keyword_rank(query, per_list)
        rv = {d: i + 1 for i, d in enumerate(vec)}
        rt = {d: i + 1 for i, d in enumerate(txt)}
        fused = {}
        for d in set(vec) | set(txt):
            fused[d] = 1.0 / (rrf_k + rv.get(d, 10 ** 6)) + 1.0 / (rrf_k + rt.get(d, 10 ** 6))
        return [d for d, _ in sorted(fused.items(), key=lambda x: -x[1])[:k]]

    RETRIEVERS = {"keyword": "_keyword_rank", "vector": "_vector_rank", "hybrid": "_hybrid_rank"}

    # ── metrics ────────────────────────────────────────────────────────────────
    @staticmethod
    def _precision(retrieved, relevant, k):
        return sum(1 for d in retrieved[:k] if relevant.get(d, 0) > 0) / k

    @staticmethod
    def _recall(retrieved, relevant, k):
        rel = {d for d, s in relevant.items() if s > 0}
        return len(rel & set(retrieved[:k])) / len(rel) if rel else 0.0

    @staticmethod
    def _ndcg(retrieved, relevant, k):
        dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(retrieved[:k]) if relevant.get(d, 0) > 0)
        n_rel = sum(1 for s in relevant.values() if s > 0)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(k, n_rel)))
        return dcg / idcg if idcg > 0 else 0.0

    def run(self, k: int = 10) -> Iterator[dict]:
        """Stream the bake-off: a status line per technique, then the final table."""
        self.initialize()
        yield {"type": "status", "dataset": self.key,
               "message": f"{self.spec['label']} — {len(self.test_qids)} queries · {len(self.doc_ids)} docs (from seed)"}
        table = {}
        for name, method in self.RETRIEVERS.items():
            rank = getattr(self, method)
            P = R = N = 0.0
            for qid in self.test_qids:
                got, rel = rank(self.qtext[qid], k), self.qrels[qid]
                P += self._precision(got, rel, k)
                R += self._recall(got, rel, k)
                N += self._ndcg(got, rel, k)
            n = len(self.test_qids)
            row = {f"precision@{k}": round(P / n, 3), f"recall@{k}": round(R / n, 3), f"NDCG@{k}": round(N / n, 3)}
            table[name] = row
            yield {"type": "technique", "name": name, "metrics": row}
        yield {"type": "summary", "k": k, "dataset": self.key, "table": table}


# One lazily-built bench per dataset; `bench` stays the scifact default for /health.
_benches: dict[str, BeirBench] = {}


def get_bench(key: str = "scifact") -> BeirBench:
    if key not in DATASETS:
        key = "scifact"
    if key not in _benches:
        _benches[key] = BeirBench(key)
    return _benches[key]


bench = get_bench("scifact")
