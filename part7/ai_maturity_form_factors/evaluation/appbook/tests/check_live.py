"""Live checks against a running evaluation studio: real models, the decision models, Oracle, the Agent SDK.

Start the app first (./run.sh), then:

    python tests/check_live.py                          # http://127.0.0.1:8705
    APPBOOK_URL=http://127.0.0.1:9000 python tests/check_live.py
    python tests/check_live.py --skip-agent              # skip the Agent SDK task

It asks every grader one check, runs a quick RAG suite, a quick workflow suite and one agent task through the API,
then reads the evidence they wrote back from Oracle. Prints one PASS/FAIL line per check and exits non-zero if any
check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8705")
client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(600, connect=10))
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS: {label}", flush=True)
    else:
        failures.append(label)
        print(f"FAIL: {label}  {str(detail)[:400]}", flush=True)


def get(path: str, **params) -> dict:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def run_suite(kind: str, body: dict, timeout: float = 1800) -> tuple[dict, list[dict]]:
    """Start a suite, follow its event stream to the end, and return its final status and events."""
    response = client.post(f"/api/suites/{kind}/start", json=body)
    response.raise_for_status()
    events = []
    started = time.time()
    with client.stream("GET", f"/api/suites/{kind}/stream", params={"since": 0}, timeout=timeout) as stream:
        name = "message"
        for line in stream.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                if name == "end":
                    break
                event = json.loads(line[5:].strip())
                events.append(event)
                if event.get("type") == "end":
                    break
            if time.time() - started > timeout:
                break
    return get(f"/api/suites/{kind}/status"), events


def summary_of(events: list[dict]) -> dict:
    return next((e for e in events if e.get("type") == "summary"), {})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-agent", action="store_true")
    args = parser.parse_args()
    t0 = time.time()

    health = get("/api/health")
    check("health · Oracle is ready", health["oracle"]["ready"], health["oracle"])
    check("health · the graders include Clef and the judge", {"clef", "judge"} <= set(health["graders"]), health["graders"])
    check("health · the judge comes from another family than the application under test",
          health["provider"] == "ollama" or not health["judge"]["model"].startswith("claude-haiku"), health["judge"])

    tables = {t["name"] for t in get("/api/data_explorer/tables")["tables"]}
    check("data explorer · lists the evidence tables", {"ffeval_runs", "ffeval_results", "ffeval_grader_checks"} <= tables, tables)
    refused = client.get("/api/data_explorer/tables/policy_docs/rows")
    check("data explorer · refuses a table outside FFEVAL_ / FFAPP_", refused.status_code == 400, refused.status_code)

    right = client.post("/api/graders/try", json={"kind": "states_fact", "question": "What is your maximum DTI?",
                                                 "answer": "Acme caps DTI at 43% of gross monthly income.",
                                                 "fact": "The maximum DTI is 43%."}).json()
    wrong = client.post("/api/graders/try", json={"kind": "states_fact", "question": "What is your maximum DTI?",
                                                 "answer": "Acme caps DTI at 41% of gross monthly income.",
                                                 "fact": "The maximum DTI is 43%."}).json()
    ok = [a for a in right["answers"] if "p" in a]
    check("playground · every grader answered", len(ok) == len(health["graders"]), right["answers"])
    check("playground · the chosen grader says yes to a right answer and no to a wrong value",
          next(a["p"] for a in right["answers"] if a.get("chosen")) >= 0.5
          and next(a["p"] for a in wrong["answers"] if a.get("chosen")) < 0.5, (right["answers"], wrong["answers"]))
    judge = next((a for a in right["answers"] if a["grader"] == "judge"), {})
    check("playground · the judge gives a reason", bool(judge.get("reason")), judge)

    status, events = run_suite("rag", {"size": "quick"})
    rag = summary_of(events).get("summary", {})
    rag_run = status.get("run_id")
    check("RAG quick suite · finished", status["status"] == "done", status)
    check("RAG quick suite · streamed retrieval and generation rows",
          {"retrieval", "generation"} <= {e.get("section") for e in events if e.get("type") == "case"})
    check("RAG quick suite · recall@3 (vector → rerank) ≥ 0.9", (rag.get("recall@3") or 0) >= 0.9, rag)
    check("RAG quick suite · the stale 41% never appears", rag.get("stale") == 0, rag)
    check("RAG quick suite · faithfulness measured claim by claim", rag.get("faithfulness") is not None, rag)

    status, events = run_suite("workflow", {"size": "quick"})
    wf = summary_of(events).get("summary", {})
    wf_run = status.get("run_id")
    check("workflow quick suite · finished", status["status"] == "done", status)
    check("workflow quick suite · no unsafe errors", wf.get("unsafe_errors") == 0, wf)
    check("workflow quick suite · end to end ≥ 0.8", (wf.get("end_to_end") or 0) >= 0.8, wf)
    check("workflow quick suite · Clef measured on gold inputs", wf.get("decision_on_gold") is not None, wf)

    runs = [r for r in (rag_run, wf_run) if r]
    if not args.skip_agent:
        status, events = run_suite("agent", {"size": "quick", "tasks": ["unknown_applicant"], "k": 1, "sessions": False})
        rows = [e["row"] for e in events if e.get("type") == "case" and e.get("section") == "tasks"]
        check("agent · one task ran and was graded", status["status"] == "done" and len(rows) == 1, status)
        check("agent · the unknown applicant gets no invented decision and no write",
              bool(rows) and rows[0]["passed"], rows[0]["problems"] if rows else events[-3:])
        if status.get("run_id"):
            runs.append(status["run_id"])
            events_rows = get("/api/data_explorer/tables/ffeval_tool_events/rows", run_id=status["run_id"])
            check("agent · its tool calls are in FFEVAL_TOOL_EVENTS", events_rows["total"] >= 1, events_rows["total"])

    for run_id in runs:
        detail = get(f"/api/runs/{run_id}")
        results = get(f"/api/runs/{run_id}/results")
        gates = get("/api/data_explorer/tables/ffeval_gates/rows", run_id=run_id)
        check(f"evidence · {run_id} wrote results, a summary and its gates",
              results["total"] > 0 and detail["summary"] and gates["total"] > 0,
              (results["total"], list(detail["summary"]), gates["total"]))
    listed = {r["run_id"] for r in get("/api/runs", limit=200)["runs"]}
    check("evidence · appbook runs sit beside notebook runs in FFEVAL_RUNS",
          set(runs) <= listed and any(r.startswith("ffeval-") for r in listed), sorted(listed)[:5])

    print(f"\n{'PASSED' if not failures else f'FAILED: {len(failures)} failing check(s)'} · {time.time() - t0:.0f}s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
