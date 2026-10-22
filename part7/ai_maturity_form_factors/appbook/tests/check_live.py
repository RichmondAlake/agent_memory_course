"""Live end-to-end checks against a running AI Maturity Ladder appbook.

Every form factor runs for real on Acme Home Loans' mortgage use case: Claude
Haiku 5.5 through the Anthropic API, policy memory and retrieval in Oracle AI
Database, the Clef-Flash decision model, and the Claude Agent SDK (sessions in
Oracle) for Form Factors 4 and 5. Nothing is mocked. Start the app first (./run.sh), then:

    python tests/check_live.py                      # http://127.0.0.1:8700
    APPBOOK_URL=http://127.0.0.1:9000 python tests/check_live.py
    python tests/check_live.py --skip-agents        # skip Form Factors 4-5 (Agent SDK runs)

Prints one PASS/FAIL line per check and exits non-zero if any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8700")
APPBOOK = Path(__file__).resolve().parents[1]
client = httpx.Client(base_url=BASE, timeout=httpx.Timeout(600, connect=10))
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS: {label}", flush=True)
    else:
        failures.append(label)
        print(f"FAIL: {label}  {detail[:400]}", flush=True)


def get(path: str) -> dict:
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def post(path: str, body: dict | None = None) -> httpx.Response:
    return client.post(path, json=body or {})


def stream(path: str, body: dict) -> list[dict]:
    """POST and collect the SSE events until the server's `end` event."""
    events, name = [], "message"
    with client.stream("POST", path, json=body) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                if name == "end":
                    break
                events.append(json.loads(line[5:].strip()))
                name = "message"
    return events


def text_of(events: list[dict], kind: str = "delta") -> str:
    return "".join(e.get("text", "") for e in events if e.get("type") == kind)


def appbook_files() -> set[str]:
    """Every file under the appbook except the sandbox, saved automations and caches."""
    skip = ("backend/sandbox", "backend/automations", "tests/artifacts", "__pycache__", ".pytest_cache")
    return {str(p.relative_to(APPBOOK)) for p in APPBOOK.rglob("*")
            if p.is_file() and not any(part in str(p.relative_to(APPBOOK)) for part in skip)}


def wait_until_ready(seconds: int = 180) -> dict:
    deadline = time.time() + seconds
    while True:
        health = get("/api/health")
        if health["retrieval"]["ready"] or time.time() > deadline:
            return health
        time.sleep(2)


def tools(events: list[dict]) -> list[str]:
    return [e["name"].split("__")[-1] for e in events if e["type"] == "tool_use"]


def result_of(events: list[dict]) -> dict:
    return next((e for e in events if e["type"] == "result"), {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-agents", action="store_true", help="skip Form Factors 4-5 (Agent SDK runs)")
    args = parser.parse_args()

    health = wait_until_ready()
    check("Oracle policy memory is ready", health["retrieval"]["ready"] and health["retrieval"]["backend"] == "oracle",
          str(health["retrieval"]))
    if health.get("provider") == "ollama":
        check("Model is Gemma 4 through Ollama, with a 32k context window",
              health["model"].endswith("-32k") and health["open_models"]["status"] == "ready",
              f"{health['model']} / {health['open_models']}")
    else:
        check("Model is Claude Haiku 5.5 at low effort", health["model"] == "claude-haiku-5-5" and health["effort"] == "low",
              f"{health['model']} / {health['effort']}")
    ledger = {row["table"]: row["items"] for row in get("/api/memory")["ledger"]}
    check("Memory ledger lists every store", {"policy_docs", "loan_decisions", "agent_session_entries"} <= set(ledger), str(ledger))
    check("Policy holds 17 sections", ledger.get("policy_docs") == 17, str(ledger))

    # ── Form Factor 1: chatbot, short-term memory only ───────────────────────────
    sid = f"live-{int(time.time())}"
    first = stream("/api/chat/message", {"session_id": sid, "message": "I earn $9,000 a month and want a $350,000 home. My name is Dana."})
    second = stream("/api/chat/message", {"session_id": sid, "message": "What did I say my monthly income was?"})
    check("Chatbot streams a reply", bool(text_of(first)))
    check("Chatbot remembers within the conversation", "9,000" in text_of(second) or "9000" in text_of(second), text_of(second))
    done = next((e for e in second if e["type"] == "done"), {})
    check("Chatbot reports the growing context", done.get("turns", 0) >= 2 and done.get("input_tokens", 0) > 0, str(done))

    # ── Form Factor 2: RAG over policy memory ────────────────────────────────────
    question = "Do I need mortgage insurance with a small down payment?"
    for technique in ("vector", "keyword", "hybrid", "graph"):
        explained = post("/api/rag/explain", {"query": question, "technique": technique, "k": 4}).json()
        check(f"Explain {technique}: four results", len(explained["results"]) == 4, str(explained.get("results"))[:200])
    vector = post("/api/rag/explain", {"query": question, "technique": "vector", "k": 4}).json()
    check("Vector retrieval ranks the PMI section first", vector["results"][0]["doc_id"] == "pmi", str(vector["results"][:2]))
    keyword = post("/api/rag/explain", {"query": question, "technique": "keyword", "k": 4}).json()
    check("Keyword explainer shows terms and postings", keyword["terms"] and keyword["postings"], str(keyword)[:200])
    space = post("/api/rag/space", {"query": "how much house can I afford with my salary", "k": 2,
                                    "category": "compliance", "mode": "post"}).json()
    check("Latent space: post-filter under-returns, pre-filter does not",
          space["comparison"]["post"] == [] and len(space["comparison"]["pre"]) == 2, str(space["comparison"]))
    check("Latent space projects all 17 sections to 3-D", len(space["points"]) == 17 and len(space["explained_variance"]) == 3)
    events = stream("/api/rag/answer", {"query": "Will an algorithm decide my loan on its own?", "technique": "hybrid", "k": 3, "rerank": True})
    rr = next((e for e in events if e["type"] == "rerank"), {})
    check("Rerank re-orders 8 hybrid candidates", len(rr.get("rows", [])) == 8, str(rr)[:200])
    first = next((r for r in rr.get("rows", []) if r["after"] == 1), {})
    check("The reranker puts human_review first", first.get("doc_id") == "human_review", str(first))
    corpus = get("/api/rag/hnsw/corpus")
    check("HNSW lab corpus: policy sentences with 768-d vectors",
          len(corpus["items"]) >= 30 and len(corpus["vectors"][0]) == corpus["dim"] == 768, f"{len(corpus['items'])} items")
    hq = post("/api/rag/hnsw/query", {"query": "PMI"}).json()
    check("HNSW lab embeds a query", len(hq["vector"]) == 768 and 0 <= hq["x"] <= 1.5, str(hq)[:80])
    answer = text_of(stream("/api/rag/answer", {"query": "What is the maximum debt-to-income ratio?", "technique": "vector", "k": 4}))
    pol = get("/api/rag/policy")
    max_dti = "43%" if next(b for b in pol["bulletins"] if b["id"] == "dti_43")["applied"] else "41%"
    check(f"Grounded answer quotes the DTI limit in force ({max_dti})", max_dti in answer, answer[:300])

    # ── Form Factor 3: workflow with the Clef decision model ─────────────────────
    samples = {s["id"]: s for s in get("/api/workflow/samples")["samples"]}
    events = stream("/api/workflow/run", {"email": samples["jordan"]["email"]})
    lane = next((e for e in events if e["type"] == "lane_done"), {})
    check("Workflow declines Jordan (DTI over the limit)", lane.get("outcome") == "decline", str(lane))
    gate = next((e for e in events if e["type"] == "step" and e["step"] == "gate"), {})
    tree = gate.get("data", {}).get("tree", {})
    check("Gate returns the decision tree", len(tree.get("criteria", [])) == 6 and len(tree.get("gates", [])) == 3)
    decide = next((e for e in events if e["type"] == "step" and e["step"] == "decide" and e["status"] == "done"), {})
    check("Clef answers in one forward pass (0 output tokens)", decide.get("data", {}).get("usage", {}).get("output_tokens") == 0,
          str(decide.get("data", {}).get("usage")))
    started = time.time()
    events = stream("/api/workflow/batch", {"samples": ["maya", "sam", "priya"]})
    outcomes = {e["lane"]: e["outcome"] for e in events if e["type"] == "lane_done"}
    check("Parallel batch: Maya approve, Sam refer, Priya decline",
          outcomes == {"maya": "approve", "sam": "refer", "priya": "decline"}, f"{outcomes} in {time.time() - started:.0f}s")
    queued = {e["lane"] for e in events if e["type"] == "step" and e["step"] == "decide" and e["status"] == "queued"}
    check("Lanes queue for the one decision model", len(queued) >= 1, str(queued))
    check("Decisions are recorded in Oracle", len(get("/api/workflow/decisions")["decisions"]) >= 4)

    if args.skip_agents:
        print("SKIP: Form Factors 4-5 (--skip-agents)")
    else:
        # ── Form Factor 4: agent with session memory in Oracle ───────────────────
        events = stream("/api/agent/run", {"prompt": "Hi, it's Maya Patel. Was my application approved, and will my loan need PMI?"})
        session = result_of(events).get("session_id")
        check("Agent looks up the case history", "get_case_history" in tools(events), str(tools(events)))
        resumed = stream("/api/agent/run", {"prompt": "In one sentence, remind me what you just told me about PMI.", "session_id": session})
        check("Resume continues the same session with no tool calls",
              result_of(resumed).get("session_id") == session and not tools(resumed), str(tools(resumed)))
        forked = stream("/api/agent/run", {"prompt": "Hypothetically, with 10% down would I still be inside the LTV limit? One sentence.",
                                           "session_id": session, "fork": True})
        check("Fork starts a new session", result_of(forked).get("session_id") not in (None, session))
        listed = {s["session_id"] for s in get("/api/agent/sessions")["sessions"]}
        check("Sessions are listed from the Oracle store", session in listed)
        messages = get(f"/api/agent/sessions/{session}")["messages"]
        first_reply = next(m for m in messages if m["role"] == "assistant" and m["kind"] == "text")
        branched = post("/api/agent/branch", {"session_id": session, "message_uuid": first_reply["uuid"]}).json()
        shorter = get(f"/api/agent/sessions/{branched['session_id']}")["messages"]
        check("Branch keeps the transcript up to the chosen reply", 0 < len(shorter) < len(messages), f"{len(shorter)} < {len(messages)}")

        # ── Form Factor 5: autonomous agent in a sandbox ─────────────────────────
        before = appbook_files()
        events = stream("/api/builder/chat", {"message": "Make a bar chart of each applicant's DTI in applications_batch1.csv "
                                                         "against the DTI limit in policy.json, save it as dti_live.png, "
                                                         "and tell me who is over the limit."})
        images = [f["path"] for e in events if e["type"] == "files" for f in e["changed"] if f["kind"] == "image"]
        check("Autonomous agent makes a chart in the sandbox", "dti_live.png" in images, str(images))
        png = client.get("/api/builder/raw", params={"path": "dti_live.png"})
        check("The chart is served to the chat", png.status_code == 200 and png.headers["content-type"] == "image/png")
        session = result_of(events).get("session_id")
        prompt = next(s["prompt"] for s in get("/api/builder/samples")["samples"] if "escape" in s["label"].lower())
        events = stream("/api/builder/chat", {"message": prompt, "session_id": session})
        denied = [e for e in events if e["type"] == "hook" and e["decision"] == "deny"]
        check("The PreToolUse hook denies a read outside the sandbox", bool(denied), str(tools(events)))
        check("The agent wrote nothing outside its sandbox", appbook_files() == before, str(sorted(appbook_files() ^ before)))
        check("Autonomous sessions are in Oracle", any(s["session_id"] == session for s in get("/api/builder/sessions")["sessions"]))

        saved = post("/api/builder/automations/save", {"name": "live-check", "command": "python -c 1"})
        check("Non-script automation command is refused", saved.status_code == 400)
        refused = post("/api/builder/automations/save", {"name": "bad", "command": "rm -rf /"})
        check("Unsafe automation command is refused", refused.status_code == 400)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
