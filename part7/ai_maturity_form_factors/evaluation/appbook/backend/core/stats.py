"""The statistics every page reports: Wilson intervals, Cohen's κ, calibration, retrieval metrics, grader choice.

Pure functions, the same formulas as the evaluation notebook, so the offline tests can pin them with known values.
"""
from __future__ import annotations

from math import sqrt

import numpy as np

COST_ORDER = ["clef", "jev", "judge"]   # cheapest first: local, hosted decision model, LLM judge
ESCALATE = (0.2, 0.8)                    # decision-model answers in this band go to the judge…


def escalation_band(threshold: float) -> tuple[float, float]:
    """…stretched to just around a high or low chosen threshold: a model that needs 0.9 to say yes is not sure at 0.85."""
    return (round(min(ESCALATE[0], threshold - 0.05), 4), round(max(ESCALATE[1], threshold + 0.05), 4))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate(flags) -> dict:
    flags = [bool(f) for f in flags]
    k, n = sum(flags), len(flags)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None, "lo": lo, "hi": hi}


def percentile(values, q: float) -> float | None:
    values = [float(v) for v in values if v is not None]
    return float(np.percentile(values, q)) if values else None


def kappa(gold, predicted) -> float:
    """Cohen's kappa for two binary label lists."""
    gold, predicted = np.asarray(gold, int), np.asarray(predicted, int)
    if not len(gold):
        return 0.0
    observed = (gold == predicted).mean()
    expected = gold.mean() * predicted.mean() + (1 - gold.mean()) * (1 - predicted.mean())
    return float((observed - expected) / (1 - expected)) if expected < 1 else 1.0


def ece(gold, probability, bins: int = 10) -> float:
    """Expected calibration error with equal-width confidence bins."""
    gold, probability = np.asarray(gold, float), np.asarray(probability, float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        inside = (probability >= lo) & (probability < hi if hi < 1 else probability <= hi)
        if inside.any():
            total += inside.mean() * abs(probability[inside].mean() - gold[inside].mean())
    return float(total)


def brier(gold, probability) -> float:
    gold, probability = np.asarray(gold, float), np.asarray(probability, float)
    return float(((probability - gold) ** 2).mean()) if len(gold) else 0.0


def reliability(gold, probability, bins: int = 10, min_count: int = 3) -> list[dict]:
    """Points for a reliability diagram: mean probability against the share of yes labels, per bin."""
    gold, probability = np.asarray(gold, float), np.asarray(probability, float)
    points = []
    for lo in np.linspace(0, 0.9, bins):
        inside = (probability >= lo) & (probability < lo + 0.1 + (lo >= 0.9))
        if inside.sum() >= min_count:
            points.append({"p": float(probability[inside].mean()), "observed": float(gold[inside].mean()),
                           "n": int(inside.sum())})
    return points


def best_threshold(gold, probability) -> float:
    """The cut-off with the highest accuracy (ties go to the one nearest 0.5)."""
    gold, probability = np.asarray(gold, int), np.asarray(probability, float)
    grid = np.round(np.arange(0.05, 0.96, 0.05), 2)
    return float(max(grid, key=lambda t: (((probability >= t).astype(int) == gold).mean(), -abs(t - 0.5))))


def retrieval_metrics(ranked: list[str], relevant: dict) -> dict:
    """recall@3, MRR, MAP@5, nDCG@5 (graded relevance) and the candidate ceiling for one question."""
    answers = {d for d, g in relevant.items() if g == 2}
    first = next((i for i, d in enumerate(ranked, 1) if d in answers), None)
    hits, average_precision = 0, 0.0
    for i, d in enumerate(ranked[:5], 1):
        if d in answers:
            hits += 1
            average_precision += hits / i          # precision at each rank that holds an answer
    dcg = sum(relevant.get(d, 0) / np.log2(i + 1) for i, d in enumerate(ranked[:5], 1))
    ideal = sum(g / np.log2(i + 1) for i, g in enumerate(sorted(relevant.values(), reverse=True)[:5], 1))
    return {"recall@3": len(answers & set(ranked[:3])) / len(answers), "mrr": 1 / first if first else 0.0,
            "map@5": average_precision / len(answers), "ndcg@5": float(dcg / ideal),
            "ceiling": len(answers & set(ranked)) / len(answers)}


def context_precision(passage_ids: list[str], relevant: dict) -> float:
    """Rank-aware precision of the passages given to the generator: precision at each labelled one, averaged."""
    hits, total = 0, 0.0
    for k, d in enumerate(passage_ids, 1):
        if d in relevant:
            hits += 1
            total += hits / k
    return total / hits if hits else 0.0


def context_recall(passage_ids: list[str], relevant: dict) -> float:
    """Share of the sections that answer the question (grade 2) that reached the generator."""
    answers = {d for d, g in relevant.items() if g == 2}
    return len(answers & set(passage_ids)) / len(answers) if answers else 0.0


def chunk_utilisation(passages: int, claims: list[dict]) -> float:
    """Share of the passages given to the generator that the answer cites."""
    used = {i for claim in claims for i in claim["citations"] if 1 <= i <= passages}
    return len(used) / passages if passages else 0.0


def grader_scoreboard(rows: list[dict]) -> dict:
    """From labelled checks (kind, split, gold, grader, probability, latency_ms): scores per kind × grader on the test
    half, the grader chosen per kind (on the dev half: cheapest within 0.05 κ of the best), and the cascade."""
    kinds = sorted({r["kind"] for r in rows})
    graders = [g for g in COST_ORDER if any(r["grader"] == g for r in rows)]
    by = {}
    for r in rows:
        by.setdefault((r["kind"], r["grader"], r["split"]), []).append(r)
    scores, choices = [], []
    for kind in kinds:
        thresholds, dev_kappas, test_kappas = {}, {}, {}
        for g in graders:
            dev = by.get((kind, g, "dev"), [])
            test = by.get((kind, g, "test"), [])
            if not test:
                continue
            thresholds[g] = 0.5 if g == "judge" or not dev else best_threshold([d["gold"] for d in dev],
                                                                                [d["probability"] for d in dev])
            gold_t = [t["gold"] for t in test]
            prob_t = [t["probability"] for t in test]
            predicted = [p >= 0.5 for p in prob_t]
            scores.append({"kind": kind, "grader": g, "n": len(test),
                           "accuracy": float(np.mean([int(p) == y for p, y in zip(predicted, gold_t)])),
                           "kappa": kappa(gold_t, predicted),
                           "ece": None if g == "judge" else ece(gold_t, prob_t),
                           "ms": percentile([t.get("latency_ms") for t in test], 50)})
            dev_kappas[g] = kappa([d["gold"] for d in dev], [d["probability"] >= thresholds[g] for d in dev]) if dev else -1
            test_kappas[g] = kappa(gold_t, [p >= thresholds[g] for p in prob_t])
        if not dev_kappas:
            continue
        best = max(dev_kappas.values())
        chosen = next(g for g in COST_ORDER if g in dev_kappas and dev_kappas[g] >= best - 0.05)
        band = escalation_band(thresholds[chosen])
        choice = {"kind": kind, "grader": chosen, "threshold": thresholds[chosen], "band": band,
                  "kappa_dev": dev_kappas[chosen], "kappa_test": test_kappas[chosen], "kappa_test_judge": test_kappas.get("judge")}
        if chosen != "judge" and "judge" in graders:
            mine = {r["item_key"]: r for r in by.get((kind, chosen, "test"), [])}
            theirs = {r["item_key"]: r for r in by.get((kind, "judge", "test"), [])}
            keys = [k for k in mine if k in theirs]
            middle = [band[0] < mine[k]["probability"] < band[1] for k in keys]
            cascade = [(theirs[k]["probability"] >= 0.5) if m else (mine[k]["probability"] >= thresholds[chosen])
                       for k, m in zip(keys, middle)]
            choice.update(escalated=float(np.mean(middle)) if keys else 0.0,
                          kappa_cascade=kappa([mine[k]["gold"] for k in keys], cascade) if keys else None)
        choices.append(choice)
    return {"scores": scores, "choices": choices}
