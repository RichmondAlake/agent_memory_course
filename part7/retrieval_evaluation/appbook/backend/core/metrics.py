"""The notebook's metrics and statistics, line for line (its §1.3 and §1.5), so the app reproduces its numbers."""
from __future__ import annotations

from math import log2

import numpy as np

from backend.config import METRICS, settings


def score_ranking(ranked: list[str], qrels: dict[str, int]) -> dict:
    """Every metric for one ranked list (best first) against one query's graded judgements."""
    relevant = {doc for doc, grade in qrels.items() if grade > 0}
    if not relevant:
        return {m: None for m in METRICS}
    hits = np.array([doc in relevant for doc in ranked[:100]], dtype=float)
    hits = np.pad(hits, (0, 100 - len(hits)))
    dcg = sum(qrels.get(doc, 0) / log2(i + 2) for i, doc in enumerate(ranked[:10]))
    idcg = sum(grade / log2(i + 2) for i, grade in enumerate(sorted(qrels.values(), reverse=True)[:10]))
    first = next((i for i in range(10) if hits[i]), None)
    precision_at_hits = np.cumsum(hits) / np.arange(1, 101)
    return {
        "ndcg10": dcg / idcg if idcg else 0.0,
        "p1": float(hits[:1].mean()), "p5": float(hits[:5].mean()), "p10": float(hits[:10].mean()),
        "r10": float(hits[:10].sum() / len(relevant)), "r100": float(hits.sum() / len(relevant)),
        "mrr10": 0.0 if first is None else 1 / (first + 1),
        "map100": float((precision_at_hits * hits).sum() / len(relevant)),
        "hit10": float(hits[:10].any()),
    }


def bootstrap_ci(values, n_boot: int = 2000, seed: int = settings.seed) -> tuple[float, float]:
    """95% bootstrap interval of the mean of per-query values."""
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (float("nan"), float("nan"))
    idx = np.random.default_rng(seed).integers(0, len(values), (n_boot, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_test(a, b, n_perm: int = 10000, seed: int = settings.seed) -> dict:
    """Mean of a - b over the same queries, its 95% bootstrap interval, and a two-sided randomisation p-value."""
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    signs = np.random.default_rng(seed).choice([-1.0, 1.0], size=(n_perm, len(diff)))
    shuffled = np.abs((signs * diff).mean(axis=1))
    p_value = (1 + (shuffled >= abs(diff.mean()) - 1e-12).sum()) / (n_perm + 1)
    return {"mean_diff": float(diff.mean()), "ci": bootstrap_ci(diff, seed=seed), "p_value": float(p_value)}


def holm(p_values: list[float]) -> list[float]:
    """Holm-adjusted p-values, in the input order (the notebook's §9.5)."""
    order = np.argsort(p_values)
    out = np.empty(len(p_values))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[i]))
        out[i] = running
    return [float(round(v, 4)) for v in out]


def mean_metrics(per_query: list[dict], names=("ndcg10", "mrr10", "r100")) -> dict:
    graded = [m for m in per_query if m.get("ndcg10") is not None]
    return {name: float(np.mean([m[name] for m in graded])) if graded else None for name in names}
