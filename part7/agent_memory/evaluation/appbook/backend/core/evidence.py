"""Evidence in Oracle: write an appbook run's rows, and read any run (notebook or appbook) back as a scorecard and gates.

The tables and the `part` names are the evaluation notebook's ('3-validation', '5-longmemeval', '6-factconsolidation',
'7-operations'); the appbook adds '7-writes' rows (write quality) that the notebook does not measure.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import numpy as np

from backend.config import settings
from backend.core import db, decision, graders, stats

PARTS = {"3-validation": "graders", "5-longmemeval": "longmemeval", "6-factconsolidation": "factconsolidation",
         "7-operations": "operations", "7-writes": "operations"}
SYSTEMS = ["naive", "scratch", "memorizz"]


class Run:
    """One appbook run: a row in MEMEVAL_RUNS, then results and grades under its id."""

    def __init__(self, suite: str, size: str, options: dict | None = None):
        self.run_id = f"appbook-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
        self.suite = suite
        record = {"source": "appbook", "suite": suite, "size": size, "options": options or {}, "provider": settings.provider,
                  "model": settings.model, "cheap_model": settings.cheap_model,
                  "embeddings": f"{settings.embed_model}@{settings.dimensions}", "judge": settings.judge_model,
                  "decision_models": decision.available(), "clef": decision.clef_id()}
        db.sql("INSERT INTO memeval_runs (run_id, settings) VALUES (:r, :s)", r=self.run_id, s=json.dumps(stats.clean(record)))

    def results(self, part: str, rows: list[dict]) -> int:
        return db.executemany("""INSERT INTO memeval_results (run_id, part, system, item_id, category, correct, input_tokens,
                                 cached_tokens, output_tokens, latency_ms, cost_usd, detail)
                                 VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12)""",
                              [(self.run_id, part, r["system"], str(r["item_id"])[:200], r.get("category"),
                                None if r.get("correct") is None else int(bool(r["correct"])), r.get("input_tokens"),
                                r.get("cached_tokens"), r.get("output_tokens"), round((r.get("seconds") or 0) * 1000),
                                r.get("cost_usd"), stats.clean(r.get("detail", {}))) for r in rows], json_positions=(11,))

    def grades(self, part: str, rows: list[dict]) -> int:
        return db.executemany("""INSERT INTO memeval_grades (run_id, part, item_id, check_type, grader, label, verdict,
                                 probability, latency_ms, cost_usd) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10)""",
                              [(self.run_id, part, str(r["item_id"])[:200], r["check_type"], r["grader"],
                                None if r.get("label") is None else int(bool(r["label"])), int(bool(r["verdict"])),
                                r.get("probability"), round((r.get("seconds") or 0) * 1000), r.get("cost_usd") or 0.0)
                               for r in rows])

    def save_gates(self) -> int:
        gates = [g for g in evaluate_gates(summarize(self.run_id)) if g["value"] is not None]
        db.sql("DELETE FROM memeval_gates WHERE run_id = :r", r=self.run_id)
        return db.executemany("""INSERT INTO memeval_gates (run_id, gate, system, threshold, value, passed)
                                 VALUES (:1, :2, :3, :4, :5, :6)""",
                              [(self.run_id, g["gate"], g["system"], f"{g['op']} {g['threshold']}", g["value"], int(g["passed"]))
                               for g in gates])


# ── reading runs back ─────────────────────────────────────────────────────────────────────────────────────────
def runs(limit: int = 60) -> list[dict]:
    rows = db.sql("""SELECT r.run_id, TO_CHAR(r.started_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS started_at, r.settings,
                            (SELECT LISTAGG(DISTINCT part, ',') WITHIN GROUP (ORDER BY part) FROM memeval_results x
                              WHERE x.run_id = r.run_id) AS parts,
                            (SELECT COUNT(*) FROM memeval_results x WHERE x.run_id = r.run_id) AS results,
                            (SELECT COUNT(*) FROM memeval_grades g WHERE g.run_id = r.run_id) AS grades,
                            (SELECT COUNT(*) FROM memeval_grades g WHERE g.run_id = r.run_id AND g.part = '3-validation') AS validation
                     FROM memeval_runs r ORDER BY r.started_at DESC FETCH FIRST :n ROWS ONLY""", n=limit)
    out = []
    for r in rows:
        s = r.get("settings") or {}
        parts = sorted({PARTS[p] for p in (r["parts"] or "").split(",") if p in PARTS} | ({"graders"} if r["validation"] else set()))
        out.append({"run_id": r["run_id"], "started_at": r["started_at"],
                    "source": s.get("source") or ("appbook" if r["run_id"].startswith("appbook-") else "notebook"),
                    "suite": s.get("suite") or "full notebook", "model": s.get("model"), "judge": s.get("judge"),
                    "provider": s.get("provider"), "parts": parts, "results": int(r["results"]), "grades": int(r["grades"])})
    return out


def results(run_id: str, part: str | None = None) -> list[dict]:
    rows = db.sql("""SELECT part, system, item_id, category, correct, input_tokens, cached_tokens, output_tokens, latency_ms,
                            cost_usd, detail FROM memeval_results WHERE run_id = :r ORDER BY id""", r=run_id)
    return [r for r in rows if part is None or r["part"] == part or (isinstance(part, (list, tuple)) and r["part"] in part)]


def latest_run_with(part: str) -> str | None:
    if part == "3-validation":
        return graders.latest_validation_run()
    rows = db.sql("""SELECT r.run_id FROM memeval_runs r WHERE EXISTS (SELECT 1 FROM memeval_results x
                     WHERE x.run_id = r.run_id AND x.part = :p) ORDER BY r.started_at DESC FETCH FIRST 1 ROWS ONLY""", p=part)
    return rows[0]["run_id"] if rows else None


def _mean(values):
    values = [float(v) for v in values if v is not None]
    return float(np.mean(values)) if values else None


def _answers(rows: list[dict]) -> dict:
    """Per system: accuracy with its interval, tokens, latency and dollars per answer."""
    out = {}
    for system in sorted({r["system"] for r in rows}, key=lambda s: SYSTEMS.index(s) if s in SYSTEMS else 9):
        g = [r for r in rows if r["system"] == system]
        seconds = [(r["latency_ms"] or 0) / 1000 for r in g]
        tokens_in = sum(r["input_tokens"] or 0 for r in g)
        out[system] = {"accuracy": stats.proportion([r["correct"] for r in g if r["correct"] is not None]),
                       "input_tokens": _mean(r["input_tokens"] for r in g),
                       "cached_share": (sum(r["cached_tokens"] or 0 for r in g) / tokens_in) if tokens_in else None,
                       "p50_s": stats.pctl(seconds, 50), "p95_s": stats.pctl(seconds, 95),
                       "cost_per_answer": _mean(r["cost_usd"] for r in g),
                       "by_category": {c: stats.proportion([r["correct"] for r in g if r["category"] == c])
                                       for c in sorted({r["category"] for r in g if r["category"]})}}
    return out


def summarize(run_id: str) -> dict:
    """Per suite: the headline metrics the scorecard and gates need, from whatever this run recorded."""
    rows = results(run_id)
    pick = lambda part: [r for r in rows if r["part"] == part]
    out: dict = {}
    lme = pick("5-longmemeval")
    if lme:
        out["longmemeval"] = {"n": len({r["item_id"] for r in lme}), "systems": _answers(lme)}
        for system, s in out["longmemeval"]["systems"].items():
            ret = [r["detail"] for r in lme if r["system"] == system and (r.get("detail") or {}).get("recall_any") is not None]
            if ret:
                s["recall_any"] = _mean(d["recall_any"] for d in ret)
                s["recall_all"] = _mean(d["recall_all"] for d in ret)
                s["ndcg"] = _mean(d["ndcg"] for d in ret)
        pairs = {}
        for a, b in (("scratch", "naive"), ("memorizz", "naive"), ("memorizz", "scratch")):
            ga = {r["item_id"]: r["correct"] for r in lme if r["system"] == a}
            gb = {r["item_id"]: r["correct"] for r in lme if r["system"] == b}
            shared = [i for i in ga if i in gb]
            if shared:
                pairs[f"{a} vs {b}"] = stats.mcnemar([ga[i] for i in shared], [gb[i] for i in shared])
        out["longmemeval"]["mcnemar"] = pairs
    fc = pick("6-factconsolidation")
    if fc:
        systems = _answers(fc)
        for system, s in systems.items():
            s["stale"] = sum(bool((r.get("detail") or {}).get("stale")) for r in fc if r["system"] == system)
        out["factconsolidation"] = {"n": len({r["item_id"] for r in fc}), "systems": systems}
    ops = pick("7-operations") + pick("7-writes")
    if ops:
        per, notebook_writes = {}, {}
        if not pick("7-writes"):   # the notebook keeps its write checks as grades ("ada:fact:…", "ada:distractor:…")
            for g in db.sql("""SELECT item_id, verdict FROM memeval_grades WHERE run_id = :r AND part = '7-writes'
                               AND check_type = 'states_fact'""", r=run_id):
                system, kind, _ = (g["item_id"].split(":", 2) + ["", ""])[:3]
                if kind in ("fact", "distractor"):
                    notebook_writes.setdefault(system, []).append(
                        {"category": "write recall" if kind == "fact" else "false memory",
                         "correct": bool(g["verdict"]) if kind == "fact" else not g["verdict"]})
        for system in sorted({r["system"] for r in ops}, key=lambda s: SYSTEMS.index(s) if s in SYSTEMS else 9):
            g = [r for r in ops if r["system"] == system]
            probes = [r for r in g if r["category"] == "isolation"]
            leaks = [r for r in probes if not (r.get("detail") or {}).get("expected") and not r["correct"]]
            forget = [r for r in g if r["category"] == "forgetting"]
            every = [r for r in forget if "every copy" in r["item_id"]]
            writes = [r for r in g if r["category"] in ("write recall", "false memory")] or notebook_writes.get(system, [])
            per[system] = {"probes": len(probes), "leaks": len(leaks),
                           "forgetting_every_copy": float(all(bool((r.get("detail") or {}).get("forgotten", r["correct"])) for r in every)) if every else None,
                           "updates_correct": _mean(float(r["correct"]) for r in g if r["category"] == "update"),
                           "write_recall": _mean(float(r["correct"]) for r in writes if r["category"] == "write recall"),
                           "false_memory_resistance": _mean(float(r["correct"]) for r in writes if r["category"] == "false memory")}
        out["operations"] = {"systems": per}
    if db.sql("SELECT COUNT(*) AS n FROM memeval_grades WHERE run_id = :r AND part = '3-validation'", r=run_id)[0]["n"]:
        analysis = graders.analyse(graders.validation_rows(run_id))
        lows = [c["kappa_cascade"] if c.get("kappa_cascade") is not None and c["kappa_cascade"] >= 0.8 else c.get("kappa_judge")
                for c in analysis.get("choices", [])]
        lows = [v for v in lows if v is not None]
        out["graders"] = {"min_kappa": min(lows) if lows else None, "choices": analysis.get("choices", [])}
    return stats.clean(out)


GATES = [  # the notebook's release gates (6.2): gate, where the value comes from, comparison, threshold
    ("LongMemEval accuracy", lambda s, n: _get(s, "longmemeval", n, "accuracy", "p"), ">=", 0.70),
    ("FactConsolidation accuracy", lambda s, n: _get(s, "factconsolidation", n, "accuracy", "p"), ">=", 0.70),
    ("stale FactConsolidation answers", lambda s, n: _get(s, "factconsolidation", n, "stale"), "<=", 2),
    ("canary leaks", lambda s, n: _get(s, "operations", n, "leaks"), "<=", 0),
    ("forgetting reaches every copy", lambda s, n: _get(s, "operations", n, "forgetting_every_copy"), ">=", 1),
    ("p95 answer latency (s)", lambda s, n: _get(s, "longmemeval", n, "p95_s"), "<=", 15),
    ("graders trusted (lowest held-out κ)", lambda s, n: (s.get("graders") or {}).get("min_kappa"), ">=", 0.8),
]


def _get(summary, suite, system, *keys):
    value = ((summary.get(suite) or {}).get("systems") or {}).get(system)
    for key in keys:
        value = (value or {}).get(key) if isinstance(value, dict) else None
    return value


def evaluate_gates(summary: dict) -> list[dict]:
    """Every gate for both Memos, with its value (None when the run did not measure it) and pass or fail."""
    gates = []
    for system in ("scratch", "memorizz"):
        for gate, measure, op, threshold in GATES:
            value = measure(summary, system)
            passed = None if value is None else (value >= threshold if op == ">=" else value <= threshold)
            gates.append({"system": system, "gate": gate, "op": op, "threshold": threshold,
                          "value": None if value is None else float(value), "passed": passed})
    return gates


def readiness(gates: list[dict]) -> dict:
    out = {}
    for system in ("scratch", "memorizz"):
        mine = [g for g in gates if g["system"] == system and g["passed"] is not None]
        out[system] = "not measured" if not mine else "ready" if all(g["passed"] for g in mine) else "blocked"
    return out
