"""FF4 (agent) + FF5 (autonomous agent) evaluation.

FF4 scores the agent through LangSmith's three lenses — **final response**,
**trajectory** (the path of tool calls), and **single step** (isolated decisions).
We capture the trajectory from the live agent stream (the runtime already hides the
built-in ToolSearch discovery call), score each scenario, and stream it all to the UI.

FF5 is **outcome-based**: the builder agent writes a `triage.py` CLI, then we *run it
ourselves* on two batches (one it never saw) and compare the report to a breakdown we
compute independently — plus an LLM-judge on code quality.
"""
from __future__ import annotations

import asyncio
import csv
import json
import subprocess
import sys
from collections import Counter
from collections.abc import AsyncIterator

from backend.config import settings
from backend.core.agent_runtime import AGENT_AVAILABLE, agent_env, run_agent_events
from backend.core.anthropic_client import MODEL
from backend.core.evaluation import judge
from backend.core.retrieval import store

# ──────────────────────────────────────────────────────────────────────────────
# FF4 — the support agent
# ──────────────────────────────────────────────────────────────────────────────
AGENT_SYSTEM = (
    "You are the Acme Cloud support agent. You have exactly two tools: search_docs and "
    "create_support_ticket. Use search_docs to ground every factual claim. Only open a "
    "ticket if the user clearly needs escalation. Cite docs with [n]."
)

AGENT_SCENARIOS = [
    {"id": "info_only", "prompt": "What's the API rate limit on the Pro plan?",
     "expected_tools": ["search_docs"], "forbidden_tools": ["create_support_ticket"],
     "goal": "State the Pro plan rate limit (1,000 requests/minute), grounded in the docs, WITHOUT opening a ticket."},
    {"id": "escalate",
     "prompt": ("I'm on the Pro plan and keep hitting rate limits right before our launch tomorrow. "
                "What are my options, and can you escalate this for me?"),
     "expected_tools": ["search_docs", "create_support_ticket"], "forbidden_tools": [],
     "goal": "Explain the Pro rate-limit options from the docs AND open a support ticket to escalate."},
    {"id": "unknown", "prompt": "Does Acme Cloud support GraphQL subscriptions? If it isn't documented, just say so.",
     "expected_tools": ["search_docs"], "forbidden_tools": ["create_support_ticket"],
     "goal": "Search the docs, then honestly say GraphQL subscriptions are not documented — do not invent a feature or open a ticket."},
]

AGENT_METRICS = ["final_response", "trajectory_subseq", "exact_tool_set",
                 "correct_first_tool", "no_unwarranted_action",
                 "tool_selection", "trajectory_accuracy"]


def _short_tool(name: str) -> str:
    return name.split("__")[-1]


def _build_tools():
    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool("search_docs",
          "Search the Acme Cloud documentation. Use this whenever the user asks about Acme "
          "Cloud's plans, pricing, limits, or features.", {"query": str})
    async def search_docs(args):
        hits = store.retrieve(args["query"], k=3)
        text = "\n".join(f"[{i + 1}] {doc}" for i, (doc, _) in enumerate(hits))
        return {"content": [{"type": "text", "text": text}]}

    @tool("create_support_ticket",
          "Open a support ticket. Use this only when the user asks to escalate, or reports an "
          "urgent, unresolved problem.", {"summary": str, "priority": str})
    async def create_support_ticket(args):
        ticket_id = f"ACME-{abs(hash(args['summary'])) % 10000:04d}"
        return {"content": [{"type": "text",
                             "text": f"Created ticket {ticket_id} (priority={args['priority']}): {args['summary']}"}]}

    return create_sdk_mcp_server(name="acme", version="1.0.0", tools=[search_docs, create_support_ticket])


def _agent_options():
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        model=MODEL, system_prompt=AGENT_SYSTEM,
        mcp_servers={"acme": _build_tools()},
        allowed_tools=["mcp__acme__search_docs", "mcp__acme__create_support_ticket"],
        setting_sources=[], cli_path=settings.claude_cli_path, env=agent_env())


def _subsequence_score(expected, actual):
    if not expected:
        return 1.0
    i = 0
    for t in actual:
        if i < len(expected) and t == expected[i]:
            i += 1
    return round(i / len(expected), 3)


def _score_agent(scenario, tool_names, response) -> dict:
    expected, forbidden = scenario["expected_tools"], set(scenario["forbidden_tools"])
    scores = {
        "trajectory_subseq": _subsequence_score(expected, tool_names),
        "exact_tool_set": float(set(tool_names) == set(expected)),
        "correct_first_tool": float(bool(tool_names) and tool_names[0] == expected[0]),
        "no_unwarranted_action": float(not (forbidden & set(tool_names))),
    }
    rubric = ("You grade whether a support agent's final reply satisfies the stated goal. Return "
              "score 1 if it does (correct, grounded, and only escalates when the goal calls for "
              'it), else 0. Respond as JSON {"score": 0 or 1, "reason": "..."}.')
    v = judge(rubric, f"Goal: {scenario['goal']}\n\nAgent's final reply:\n{response}")
    scores["final_response"] = float(v["score"])

    # LangSmith TRAJECTORY templates (LLM-as-judge over the captured path):
    ts = judge("Given the goal and the tools the agent called, return score 1 if the tool choices were "
               "appropriate (right tools, no needless or wrong ones), else 0. "
               'Respond as JSON {"score": 0 or 1, "reason": "..."}.',
               f"Goal: {scenario['goal']}\nExpected tools: {expected}\nTools called: {tool_names}")
    scores["tool_selection"] = float(ts["score"])
    ta = judge("Given the goal and the ordered trajectory of tool calls, return score 1 if the path was "
               "logical and efficient (no wasteful, circular, or out-of-order steps), else 0. "
               'Respond as JSON {"score": 0 or 1, "reason": "..."}.',
               f"Goal: {scenario['goal']}\nOrdered trajectory: {tool_names}\nFinal reply: {response[:400]}")
    scores["trajectory_accuracy"] = float(ta["score"])
    return {"scores": scores, "comment": v.get("reason", "")}


async def stream_agent_eval() -> AsyncIterator[dict]:
    """Run each scenario live, relay its trajectory, and score all three lenses."""
    if not AGENT_AVAILABLE:
        yield {"type": "error", "message": "Claude Agent SDK CLI not found. Install with "
               "`npm i -g @anthropic-ai/claude-code` to enable FF4/FF5."}
        return
    store.initialize()
    options = _agent_options()
    yield {"type": "start", "total": len(AGENT_SCENARIOS), "metrics": AGENT_METRICS}
    totals: dict[str, float] = {m: 0.0 for m in AGENT_METRICS}

    for sc in AGENT_SCENARIOS:
        yield {"type": "scenario_start", "id": sc["id"], "prompt": sc["prompt"],
               "expected": sc["expected_tools"], "forbidden": sc["forbidden_tools"]}
        tool_names: list[str] = []
        text_parts: list[str] = []
        async for ev in run_agent_events(sc["prompt"], options):
            if ev["type"] == "tool_use":
                name = _short_tool(ev["name"])
                tool_names.append(name)
                yield {"type": "tool_use", "id": sc["id"], "tool": name, "input": ev.get("input", {})}
            elif ev["type"] == "text":
                text_parts.append(ev["text"])
            elif ev["type"] == "error":
                yield {"type": "scenario_error", "id": sc["id"], "message": ev["message"]}
        response = " ".join(text_parts).strip()
        result = await asyncio.to_thread(_score_agent, sc, tool_names, response)
        for k, v in result["scores"].items():
            totals[k] += v
        yield {"type": "scenario_scores", "id": sc["id"], "tools": tool_names,
               "scores": result["scores"], "comment": result["comment"],
               "response": response[:600]}

    n = len(AGENT_SCENARIOS)
    yield {"type": "summary", "aggregate": {m: round(totals[m] / n, 3) for m in AGENT_METRICS}}


# ──────────────────────────────────────────────────────────────────────────────
# FF5 — the autonomous (builder) agent
# ──────────────────────────────────────────────────────────────────────────────
BUILDER_SYSTEM = ("You are an automation engineer. Build the smallest correct, reusable solution, "
                  "then verify it runs on every input you are given. Work ONLY inside your current "
                  "working directory: never `cd` to another directory and never search the wider "
                  "filesystem — every file you need is already in the current directory.")

# Fixed synthetic tickets with KNOWN labels → exact, reproducible ground truth.
TICKETS = [
    ("billing", "high", "Double charged for Pro seats this month"),
    ("billing", "low", "Question about an invoice line item"),
    ("technical", "high", "API returns 500 on the /v1/sync endpoint"),
    ("technical", "high", "Webhooks stopped firing before our launch"),
    ("technical", "medium", "VPN access issue from the office"),
    ("account", "low", "How do I add a teammate to my workspace"),
    ("feature_request", "low", "Please support exporting to Parquet"),
    ("other", "low", "Just saying thanks, the product is great"),
]

BUILD_PROMPT = (
    "You are building a reusable automation in your CURRENT working directory. Start by running "
    "`ls` — it already contains exactly two CSV files, `tickets_batch1.csv` and `tickets_batch2.csv`, "
    "each with columns id,category,priority,message. Do ALL of your work right here. Refer to every "
    "file by its PLAIN RELATIVE NAME only (e.g. `triage.py`, `tickets_batch1.csv`, `report_batch1.json`) "
    "— never use an absolute path, never include any directory, and never `cd` anywhere.\n"
    "1. Write a minimal, well-documented Python CLI `triage.py` (standard library only) that:\n"
    "   - accepts `--input <path>` and `--output <path>` (default `report.json`);\n"
    "   - computes two breakdowns -- messages per category and per priority -- each sorted by count descending;\n"
    "   - writes both breakdowns to the output path as JSON;\n"
    "   - validates input and exits non-zero with a clear message if the file is missing or its columns are wrong;\n"
    "   - uses NO hardcoded paths, so it can be scheduled or reused on any batch.\n"
    "2. Run it on the first batch:  python triage.py --input tickets_batch1.csv --output report_batch1.json\n"
    "3. Then prove it re-runs on NEW data:  python triage.py --input tickets_batch2.csv --output report_batch2.json\n"
    "4. If anything errors, fix it and re-run until both batches succeed.\n"
    "5. Confirm what you built and show both report files."
)

FF5_METRICS = ["runs_clean", "functional_correctness", "code_quality"]


def _write_batch(path, rows, start_id):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "category", "priority", "message"])
        w.writeheader()
        for i, (cat, pri, msg) in enumerate(rows):
            w.writerow({"id": start_id + i, "category": cat, "priority": pri, "message": msg})


def prepare_sandbox():
    """Reset the sandbox and stock it with the two ticket batches."""
    import shutil
    sb = settings.sandbox_dir
    if sb.exists():
        shutil.rmtree(sb)
    sb.mkdir(parents=True, exist_ok=True)
    _write_batch(sb / "tickets_batch1.csv", TICKETS[:4], 1)
    _write_batch(sb / "tickets_batch2.csv", TICKETS[4:], 5)
    return sb


def _builder_options():
    from claude_agent_sdk import ClaudeAgentOptions
    return ClaudeAgentOptions(
        model=MODEL, cwd=str(settings.sandbox_dir),
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        permission_mode="bypassPermissions", max_turns=30, setting_sources=[],
        system_prompt=BUILDER_SYSTEM, cli_path=settings.claude_cli_path, env=agent_env())


def _ground_truth(batch_csv):
    rows = list(csv.DictReader(open(settings.sandbox_dir / batch_csv)))
    return {"category": Counter(r["category"] for r in rows),
            "priority": Counter(r["priority"] for r in rows)}


def _count_pairs(obj):
    pairs = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, int) and not isinstance(v, bool):
                    pairs.add((str(k).lower(), v))
                else:
                    walk(v)
            label = next((str(o[lk]) for lk in ("category", "priority", "name", "label", "key") if isinstance(o.get(lk), str)), None)
            cnt = next((o[ck] for ck in ("count", "n", "total", "value") if isinstance(o.get(ck), int) and not isinstance(o.get(ck), bool)), None)
            if label is not None and cnt is not None:
                pairs.add((label.lower(), cnt))
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(obj)
    return pairs


def _run_triage(batch):
    tool = settings.sandbox_dir / "triage.py"
    if not tool.exists():
        return 127, None
    out = settings.sandbox_dir / f"eval_{batch}.json"
    proc = subprocess.run([sys.executable, "triage.py", "--input", batch, "--output", out.name],
                          cwd=str(settings.sandbox_dir), capture_output=True, text=True)
    report = None
    if out.exists():
        try:
            report = json.load(open(out))
        except Exception:  # noqa: BLE001
            report = None
    return proc.returncode, report


def _functional_checks() -> dict:
    """Run the agent's CLI on both batches and compare to independent ground truth."""
    rows, totals = [], {m: 0.0 for m in FF5_METRICS}
    tool = settings.sandbox_dir / "triage.py"
    quality_score, quality_reason = 0.0, "triage.py missing"
    if tool.exists():
        rubric = ("You review a Python CLI for FOUR qualities: (1) standard library only, "
                  "(2) validates input and exits non-zero on bad/missing input, (3) no hardcoded "
                  "file paths (uses argparse for --input/--output), (4) documented. Return score 1 "
                  'if it clearly satisfies at least 3 of the 4, else 0. Respond as JSON {"score": 0 or 1, "reason": "..."}.')
        v = judge(rubric, f"```python\n{tool.read_text()[:4000]}\n```")
        quality_score, quality_reason = float(v["score"]), v.get("reason", "")

    for batch in ("tickets_batch1.csv", "tickets_batch2.csv"):
        rc, report = _run_triage(batch)
        gt = _ground_truth(batch)
        expected = {(k.lower(), val) for k, val in {**gt["category"], **gt["priority"]}.items()}
        got = _count_pairs(report) if report else set()
        missing = expected - got
        scores = {
            "runs_clean": float(rc == 0),
            "functional_correctness": float(report is not None and not missing),
            "code_quality": quality_score,
        }
        for k, val in scores.items():
            totals[k] += val
        rows.append({"label": batch, "scores": scores,
                     "comment": ("all counts correct" if (report and not missing) else f"missing/incorrect: {sorted(missing)}")})
    n = len(rows)
    return {"rows": rows, "aggregate": {m: round(totals[m] / n, 3) for m in FF5_METRICS},
            "code_quality_reason": quality_reason}


async def stream_builder_eval() -> AsyncIterator[dict]:
    if not AGENT_AVAILABLE:
        yield {"type": "error", "message": "Claude Agent SDK CLI not found. Install with "
               "`npm i -g @anthropic-ai/claude-code` to enable FF4/FF5."}
        return
    store.initialize()
    sb = await asyncio.to_thread(prepare_sandbox)
    yield {"type": "start", "sandbox": str(sb), "metrics": FF5_METRICS,
           "ground_truth": {b: {"category": dict(_ground_truth(b)["category"]),
                                "priority": dict(_ground_truth(b)["priority"])}
                            for b in ("tickets_batch1.csv", "tickets_batch2.csv")}}

    options = _builder_options()
    async for ev in run_agent_events(BUILD_PROMPT, options):
        if ev["type"] == "tool_use":
            yield {"type": "tool_use", "tool": _short_tool(ev["name"]), "input": ev.get("input", {})}
        elif ev["type"] == "text" and ev["text"].strip():
            yield {"type": "text", "text": ev["text"]}
        elif ev["type"] == "error":
            yield {"type": "build_error", "message": ev["message"]}

    yield {"type": "evaluating"}
    result = await asyncio.to_thread(_functional_checks)
    tool = settings.sandbox_dir / "triage.py"
    yield {"type": "artifact", "name": "triage.py",
           "content": tool.read_text()[:4000] if tool.exists() else "(not produced)"}
    for row in result["rows"]:
        yield {"type": "row", **row}
    yield {"type": "summary", "aggregate": result["aggregate"],
           "code_quality_reason": result["code_quality_reason"]}
