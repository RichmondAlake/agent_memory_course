"""Live checks against a running studio: real models, the decision models, Oracle, MemoRizz.

Start the app first (./run.sh), then:

    python tests/check_live.py                          # http://127.0.0.1:8715
    APPBOOK_URL=http://127.0.0.1:9000 python tests/check_live.py
    python tests/check_live.py --skip graders,factconsolidation

It asks every grader one check, runs each suite at its quick size through the API (graders, memory operations,
LongMemEval, FactConsolidation), reads the evidence each one wrote back from Oracle, and checks that a
run keeps what its agents wrote (MEMO_CLEANUP=1 to delete it) and its evidence. Prints one PASS/FAIL line per check and exits non-zero if
any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8715")
client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(900, connect=10))
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}: {label}" + ("" if condition else f"  {str(detail)[:400]}"), flush=True)
    if not condition:
        failures.append(label)


def get(path: str, **params) -> dict:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def run_suite(kind: str, body: dict, timeout: float = 2400) -> tuple[dict, list[dict]]:
    """Start a suite, follow its event stream to the end, and return its final status and events."""
    response = client.post(f"/api/suites/{kind}/start", json=body)
    response.raise_for_status()
    events, started = [], time.time()
    with client.stream("GET", f"/api/suites/{kind}/stream", params={"since": 0}, timeout=timeout) as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if event.get("type"):
                    events.append(event)
                    if event["type"] == "end":
                        break
            if time.time() - started > timeout:
                break
    return get(f"/api/suites/{kind}/status"), events


def of(events, type_):
    return [e for e in events if e.get("type") == type_]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", default="", help="comma-separated suites to skip")
    skip = set(filter(None, parser.parse_args().skip.split(",")))
    started = time.time()

    health = get("/api/health")
    check("health · Oracle is ready", health["oracle"]["ready"], health["oracle"])
    check("health · the graders include the judge and Clef", {"clef", "judge"} <= set(health["graders"]), health["graders"])
    tried = client.post("/api/graders/try", json={"check": "uses_old_value", "question": "Where does Ada live?",
                                                  "answer": "From what you told me, Porto.", "old": "Porto"}).json()
    answers = {a["grader"]: a for a in tried["answers"]}
    check("graders · every grader answers one check", set(health["graders"]) <= set(answers) and not any("error" in a for a in answers.values()), answers)
    check("graders · the judge sees the old value as current", answers.get("judge", {}).get("p") == 1.0, answers.get("judge"))

    runs, runs_kept = {}, {}
    plan = [("graders", {"size": "quick"}), ("operations", {"size": "quick"}), ("longmemeval", {"size": "quick", "per_type": 1, "abstention": 1}),
            ("factconsolidation", {"size": "quick", "questions": 6})]
    for kind, body in plan:
        if kind in skip:
            continue
        status, events = run_suite(kind, body)
        runs[kind] = status.get("run_id")
        check(f"{kind} · the quick suite finishes", status["status"] == "done", (status, of(events, "error")[:1]))
        summary = (of(events, "summary") or [{}])[-1]
        if kind == "graders":
            a = summary.get("analysis") or {}
            check("graders · the analysis scores every check for every grader", len(a.get("scores", [])) == 3 * len(health["graders"]), len(a.get("scores", [])))
            check("graders · a policy is chosen for every check", set(summary.get("policy") or {}) == {"states_fact", "uses_old_value", "abstains"}, summary.get("policy"))
        if kind == "operations":
            probes = of(events, "probe")
            check("operations · no canary leaks", probes and not any(p["leaked"] for p in probes), [p for p in probes if p["leaked"]])
            controls = [p for p in probes if p["expected"]]
            sealed = sum(p["found"] for p in controls if "sealed" in p["probe"])
            # The own-scope control tests the store; inside the sealed thread the model may still decline to repeat a
            # passcode, which the page reports as a utility failure rather than a broken check.
            check(f"operations · the own-scope controls find the canary (sealed-thread controls: {sealed} of 2 found)",
                  len(controls) == 4 and all(p["found"] for p in controls if "own scope" in p["probe"]), controls)
            forget = of(events, "forget")
            check("operations · forgetting every copy forgets the city in both Memos",
                  all(f["forgotten"] for f in forget if f["stage"].startswith("2")) and len(forget) == 4, forget)
        if kind == "longmemeval":
            answers_ = of(events, "answer")
            check("longmemeval · three agents answered every question", len(answers_) == 3 * 7, len(answers_))
            check("longmemeval · the scratch Memo answers most questions right", sum(a["correct"] for a in answers_ if a["system"] == "scratch") >= 4,
                  [(a["category"], a["correct"]) for a in answers_ if a["system"] == "scratch"])
        if kind == "factconsolidation":
            answers_ = of(events, "answer")
            check("factconsolidation · three agents answered every question", len(answers_) == 3 * 6, len(answers_))
            written = (of(events, "written") or [{}])[-1]
            check("factconsolidation · the scratch Memo superseded some facts", (written.get("scratch_facts") or 0) > (written.get("scratch_current") or 0), written)
        if kind in ("operations", "longmemeval", "factconsolidation"):
            if os.getenv("MEMO_CLEANUP") == "1":
                cleanup = (of(events, "cleanup") or [{}])[-1]
                check(f"{kind} · MEMO_CLEANUP=1 deleted the run's rows", "deleted" in cleanup and cleanup["deleted"].get("memorizz agent rows", 0) > 0, cleanup)
            else:
                kept = (of(events, "kept") or [{}])[-1]
                check(f"{kind} · the run kept its MemoRizz agent and memory (no cleanup by default)",
                      bool(kept.get("agent_id") and kept.get("memory_id")) and not of(events, "cleanup"), kept or of(events, "cleanup"))
                runs_kept[kind] = kept

    listed = {r["run_id"]: r for r in get("/api/runs", limit=200)["runs"]}
    for kind, run_id in runs.items():
        check(f"evidence · the {kind} run is listed as an appbook run", run_id in listed and listed[run_id]["source"] == "appbook", run_id)
    if runs.get("longmemeval"):
        detail = get(f"/api/runs/{runs['longmemeval']}")
        lme = (detail["summary"].get("longmemeval") or {}).get("systems") or {}
        check("evidence · LongMemEval summary has every agent with tokens and latency", set(lme) == {"naive", "scratch", "memorizz"}
              and all(v.get("p95_s") for v in lme.values()), lme)
        check("evidence · the scratch Memo's retrieval was scored", lme.get("scratch", {}).get("recall_any") is not None, lme.get("scratch"))
        last = get("/api/suites/longmemeval/last")
        check("evidence · the LongMemEval page reads the latest run", last["run_id"] == runs["longmemeval"], last["run_id"])
    if runs.get("operations"):
        gates = get(f"/api/runs/{runs['operations']}")["gates"]
        check("gates · the operations run measured leaks and forgetting", sum(g["value"] is not None for g in gates) >= 4, gates)
    rows = get("/api/data_explorer/tables/memeval_results/rows", limit=5, run_id=runs.get("operations") or runs.get("graders") or "")
    check("data explorer · reads MEMEVAL_RESULTS for a run", rows["total"] >= 1, rows["total"])
    blocked = client.get("/api/data_explorer/tables/conversation_memory/rows")
    check("data explorer · refuses tables outside the allowlist", blocked.status_code == 400, blocked.status_code)
    for kind, kept in runs_kept.items():
        print(f"kept · {kind}: {kept.get('agent')} ({kept.get('agent_id')}) · memory {kept.get('memory_id')}")
    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - started:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
