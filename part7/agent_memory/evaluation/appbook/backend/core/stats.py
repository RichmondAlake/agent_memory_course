"""The evaluation notebook's metrics and reporting helpers (Parts 1 and 2), plus the reliability bins the charts draw."""
from __future__ import annotations

import math
import re

import numpy as np


ESCALATE = (0.2, 0.8)   # decision-model probabilities strictly inside this band go to the LLM judge…


def escalation_band(threshold: float) -> tuple[float, float]:
    """…stretched to reach 0.05 past a high or low threshold: a model that needs 0.9 to say yes is not sure at 0.85."""
    return (round(min(ESCALATE[0], threshold - 0.05), 2), round(max(ESCALATE[1], threshold + 0.05), 2))


def normalize(text) -> str:
    text = re.sub(r"\b(a|an|the)\b", " ", str(text).lower())
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def contains_answer(response, answers) -> bool:
    """MemoryAgentBench's substring exact match: any normalised gold answer inside the normalised response."""
    response = normalize(response)
    return any(normalize(a) and normalize(a) in response for a in answers)


def retrieval_metrics(retrieved, relevant, k: int = 10) -> dict:
    """recall@k (any, all) and binary nDCG@k of a ranked list of ids against the relevant ids."""
    ranked = list(dict.fromkeys(retrieved))[:k]
    relevant = set(relevant)
    hits = [1.0 if item in relevant else 0.0 for item in ranked]
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return {"recall_any": float(any(hits)), "recall_all": float(relevant <= set(ranked)),
            "ndcg": sum(h / math.log2(i + 2) for i, h in enumerate(hits)) / ideal if ideal else 0.0}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Proportion and its Wilson score interval (never rounded past the proportion itself)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, max(0.0, min(p, centre - half)), min(1.0, max(p, centre + half))


def proportion(values) -> dict:
    values = [bool(v) for v in values]
    p, low, high = wilson(sum(values), len(values))
    return {"k": sum(values), "n": len(values), "p": None if not values else p,
            "low": None if not values else low, "high": None if not values else high}


def mcnemar(a, b) -> dict:
    """Exact McNemar test on paired booleans."""
    only_a = sum(bool(x) and not bool(y) for x, y in zip(a, b))
    only_b = sum(bool(y) and not bool(x) for x, y in zip(a, b))
    n = only_a + only_b
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / 2 ** n if n else 1.0
    return {"only_a": only_a, "only_b": only_b, "p": min(1.0, 2 * tail)}


def kappa(a, b) -> float:
    """Cohen's kappa between two lists of booleans."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    if not len(a):
        return float("nan")
    observed = (a == b).mean()
    expected = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return float((observed - expected) / (1 - expected)) if expected < 1 else 1.0


def ece(probabilities, labels, bins: int = 10) -> float:
    p, y = np.asarray(probabilities, float), np.asarray(labels, float)
    if not len(p):
        return float("nan")
    edges = np.linspace(0, 1, bins + 1)
    index = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    return float(sum(abs(y[index == b].mean() - p[index == b].mean()) * (index == b).mean()
                     for b in range(bins) if (index == b).any()))


def brier(probabilities, labels) -> float:
    p, y = np.asarray(probabilities, float), np.asarray(labels, float)
    return float(np.mean((p - y) ** 2)) if len(p) else float("nan")


def reliability(probabilities, labels, bins: int = 5) -> list[dict]:
    """Points for a reliability diagram: mean probability against the share really true, per bin."""
    p, y = np.asarray(probabilities, float), np.asarray(labels, float)
    if not len(p):
        return []
    index = np.clip(np.digitize(p, np.linspace(0, 1, bins + 1)[1:-1]), 0, bins - 1)
    return [{"p": float(p[index == b].mean()), "observed": float(y[index == b].mean()), "n": int((index == b).sum())}
            for b in range(bins) if (index == b).any()]


def pctl(values, q: float) -> float | None:
    values = [float(v) for v in values if v is not None]
    return float(np.percentile(values, q)) if values else None


def clean(value):
    """JSON-safe: numpy types to Python, NaN to None."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if math.isnan(float(value)) else float(value)
    return value if value is None or isinstance(value, (int, str)) else str(value)
