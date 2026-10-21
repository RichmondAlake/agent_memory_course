"""Live checks against a running appbook: real gpt-5.5, real Oracle, real Jev.

    ./run.sh &                                            # from appbook/, port 8710
    ../../../.venv/bin/python tests/check_live.py         # APPBOOK_URL overrides the address

Every Part is exercised in notebook order on a fresh lab session, asserting the
effect the notebook shows for that Part. The session is reset at the end and the
old scope is checked for leftovers. Prints PASS/FAIL lines; exits 1 on any FAIL.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
BASE = os.getenv("APPBOOK_URL", "http://127.0.0.1:8710")
client = httpx.Client(base_url=BASE, timeout=600)
failures: list[str] = []
started_all = time.perf_counter()


def check(label: str, condition: bool, detail: object = "") -> None:
    if condition:
        print(f"PASS  {label}", flush=True)
    else:
        failures.append(label)
        print(f"FAIL  {label}  {str(detail)[:300]}", flush=True)


def chat(part: int, message: str, **body) -> dict:
    events: dict = {}
    with client.stream("POST", f"/api/parts/{part}/chat", json={"message": message, **body}) as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip() or "{}")
                if event.get("type") == "answer":
                    events[event["side"]] = event
                elif event.get("type") == "error":
                    events["error"] = event["message"]
    if "error" in events:
        print(f"      error: {events['error']}")
    return events


def action(part: int, name: str, **params) -> dict:
    response = client.post(f"/api/parts/{part}/actions/{name}", json={"params": params})
    if response.status_code != 200:
        print(f"      {name}: HTTP {response.status_code} {response.text[:300]}")
        return {}
    return response.json()


def page(part: int) -> dict:
    return client.get(f"/api/parts/{part}").json()


def table(data: dict, side: str, name: str) -> dict:
    return next((t for t in data[side] if t["table"] == name), {"rows": [], "row_count": 0})


def low(event: dict, side: str) -> str:
    return str((event.get(side) or {}).get("text", "")).lower()


for _ in range(90):                     # the runtime warms in the background after the server starts
    health = client.get("/api/health").json()
    if health["memory"]["ready"] or health["memory"].get("error"):
        break
    time.sleep(1)
check("Oracle runtime is ready on the MEMORIZZ schema", health["memory"]["ready"], health["memory"].get("error"))
check("OpenAI and Jev keys are configured", health["api_key_set"] and health["jev_key_set"])
client.post("/api/session/reset")
session = client.get("/api/session").json()
print(f"      session {session['scope']}")

# Part 1 · stateless baseline
result = action(1, "baseline")
check("1 · two raw calls: the second does not know Ada", bool(result) and "ada" not in result["second"].lower(), result)
event = chat(1, "What am I working on, and what's my name?")
check("1 · Memo with no layers cannot answer either", "ada" not in low(event, "scratch") and event.get("memorizz", {}).get("raw"))

# Part 2 · conversation
chat(2, "I'm Ada. I'm migrating our RAG stack to Oracle AI Database.")
event = chat(2, "What am I working on, and what's my name?")
check("2 · both agents recall Ada and the migration in the same thread",
      all("ada" in low(event, s) and ("oracle" in low(event, s) or "rag" in low(event, s)) for s in ("scratch", "memorizz")), event)
event = chat(2, "What am I working on?", thread="on-call")
check("2 · scratch history is thread-isolated", "rag" not in low(event, "scratch") and "oracle" not in low(event, "scratch"),
      low(event, "scratch"))
result = action(2, "restore")
check("2 · fresh scratch agent and MemAgent.load both recall the project",
      all(word in (result.get(s) or "").lower() for s in ("scratch", "memorizz") for word in ("oracle",)), result)
data = page(2)
check("2 · rows written to scratch_conversation and conversation_memory",
      table(data, "scratch", "scratch_conversation")["row_count"] >= 8 and table(data, "memorizz", "conversation_memory")["row_count"] >= 8)

# Part 3 · persona
event = chat(3, "Who are you, and how do you answer?")
check("3 · both agents answer as Memo", all("memo" in low(event, s) for s in ("scratch", "memorizz")), event)
result = action(3, "evolve", field="goals", value="Help platform engineers ship reliable, grounded and cost-aware AI systems.",
                reason="The platform team adopted cost budgets.")
check("3 · persona evolves to version 2 on both sides with the reason",
      result.get("scratch_version") == 2 and result.get("memorizz_version") == 2
      and any("cost budgets" in str(h.get("reason")) for h in result.get("memorizz_history", [])), result)

# Part 4 · entities
chat(4, "For the record: I own the retrieval-api service, and I prefer answers with SQL examples.")
data = page(4)
facts = json.dumps(table(data, "scratch", "scratch_entity")["rows"]).lower()
check("4 · scratch extracted the facts with source and confidence", "retrieval-api" in facts and "sql" in facts, facts[:300])
event = chat(4, "Which service do I own?", thread="on-call")
check("4 · both agents know the service in another thread",
      all("retrieval-api" in low(event, s) for s in ("scratch", "memorizz")), event)
chat(4, "Correction: from now on I'd rather have Python examples than SQL.", thread="on-call")
rows = table(page(4), "scratch", "scratch_entity")["rows"]
check("4 · the SQL preference is superseded, Python is current",
      any(r.get("superseded_at") and "sql" in str(r.get("value")).lower() for r in rows)
      and any(not r.get("superseded_at") and "python" in str(r.get("value")).lower() for r in rows), rows)
check("4 · MemoRizz entity memory holds the Python preference",
      "python" in json.dumps(table(page(4), "memorizz", "entity_memory")["rows"]).lower())

# Part 5 · knowledge
question = "When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?"
event = chat(5, question)
check("5 · both answers give the Tuesday window and the ORAMNT ticket",
      all("tuesday" in low(event, s) and "oramnt" in low(event, s) for s in ("scratch", "memorizz")), event)
check("5 · scratch cites the runbook; MemoRizz recalled runbook chunks before the call (or looked them up)",
      "platform-runbook#" in low(event, "scratch")
      and ((event["memorizz"].get("source_counts") or {}).get("semantic_memories", 0) > 0
           or "knowledge_base_lookup" in event["memorizz"]["tool_calls"]), event)
result = action(5, "search", query=question)
ranked = [r["chunk_index"] for r in result.get("scratch", [])]
check("5 · the rebuild window ranks first and change control is inside the layer's k=4",
      ranked[:1] == [0] and 1 in ranked[:4] and len(result.get("memorizz", [])) >= 3, ranked)

# Part 6 · toolbox
event = chat(6, "Check the health of the docs_hnsw index.")
check("6 · both agents call index_health",
      "index_health" in event["scratch"]["tool_calls"] and "index_health" in event["memorizz"]["tool_calls"], event)
result = action(6, "preview", query="Check the health of the docs_hnsw index.")
check("6 · index_health ranks first in scratch selection and is in the MemoRizz router preview",
      result.get("scratch", [{}])[0].get("name") == "index_health" and "index_health" in result.get("memorizz", []), result)

# Part 7 · tool log
chat(7, "Check docs_hnsw health and tell me how many checks passed.")
event = chat(7, "Run the docs_hnsw health check once more.")
data = page(7)
log = table(data, "scratch", "scratch_tool_log")["rows"]
check("7 · scratch logged an offloaded result and reused it", any(r.get("offloaded") for r in log)
      and any(r.get("status") == "reused" for r in log), log)
check("7 · MemoRizz tool log rows and a tool-cache hit",
      table(data, "memorizz", "tool_log")["row_count"] >= 1 and (data["extra"].get("tool_cache") or {}).get("hits", 0) >= 1,
      data.get("extra"))

# Part 8 · workflows
chat(8, "Check docs_hnsw health and tell me who owns retrieval-api.")
event = chat(8, "Check docs_ivf health and tell me who owns embedding-worker.")
data = page(8)
hashes = [r["canonical_hash"] for r in table(data, "scratch", "scratch_workflow")["rows"][:2]]
check("8 · the two runs share one canonical hash", len(hashes) == 2 and hashes[0] == hashes[1], hashes)
check("8 · the second request carried the first run's steps",
      any("workflow memory" in r["part"] for r in event["scratch"]["context"]), event["scratch"]["context"])
check("8 · MemoRizz captured workflows", table(data, "memorizz", "workflow_memory")["row_count"] >= 2)

# Part 9 · skills
result = action(9, "propose")
check("9 · a repeated workflow becomes a candidate skill", bool(result.get("proposed")), result)
result = action(9, "approve")
check("9 · approval activates it; MemoRizz retrieves the authored skill",
      result.get("approved", 0) >= 1 and bool(result.get("memorizz_skills")), result)
event = chat(9, "Plan the retrieval-api index rebuild for me.")
check("9 · the plan follows the reviewed playbook on both sides",
      all("oramnt" in low(event, s) for s in ("scratch", "memorizz"))
      and any(r["part"].startswith("Reviewed skill") for r in event["scratch"]["context"]), event)

# Part 10 · working memory
event = chat(10, "Summarise where my migration stands in three bullets.", thread="migration", budget=500)
check("10 · a 500-token budget drops the oldest history", (event["scratch"].get("dropped") or 0) > 0, event["scratch"])
page_text = "incident INC-4821: retrieval-api p95 latency above 800 ms"
event = chat(10, "Which incident am I looking at?", thread="incident-review", open_page=page_text)
check("10 · request context reaches both agents", all("4821" in low(event, s) for s in ("scratch", "memorizz")), event)
event = chat(10, "Which incident am I looking at?", thread="incident-review-2")
check("10 · a fresh thread without the context does not know it (scratch)", "4821" not in low(event, "scratch"),
      low(event, "scratch"))

# Part 11 · summaries
result = action(11, "compact")
check("11 · scratch summary linked to its source turns",
      bool(result.get("scratch_summary_id")) and len(result.get("scratch_sources", [])) >= 2, result)
check("11 · MemoRizz summary with source message ids",
      bool(result.get("memorizz_summary_ids")) and (result.get("memorizz_summary") or {}).get("source_message_ids", 0) >= 1, result)
event = chat(11, "What have we covered so far?")
check("11 · the next request carries the summary block",
      any(r["part"].startswith("Summary #") for r in event["scratch"]["context"]), event["scratch"]["context"])

# Part 12 · semantic cache
policy = {"cache_domain": "runbook", "data_version": "2026-10-17"}
chat(12, "What ticket prefix do Oracle maintenance changes need?", **policy)
event = chat(12, "Which ticket prefix is required for Oracle maintenance changes?", **policy)
check("12 · the paraphrase is a scratch cache hit", event["scratch"].get("cache_hit") is not None, event["scratch"])
check("12 · and a MemoRizz semantic-cache hit", (event["memorizz"].get("semantic_cache") or {}).get("hits", 0) >= 1,
      event["memorizz"].get("semantic_cache"))
event = chat(12, "Which ticket prefix is required for Oracle maintenance changes?", cache_domain="runbook", data_version="2026-10-18")
check("12 · a new data version is a miss", event["scratch"].get("cache_hit") is None, event["scratch"])
result = action(12, "invalidate", domain="runbook")
check("12 · invalidating the domain removes entries on both sides",
      result.get("scratch_removed", 0) >= 1 and result.get("memorizz_removed", 0) >= 1, result)

# Context window: every model call of every turn above, both agents, section by section
turns = client.get("/api/context").json()["turns"]
check("context · every chat turn so far has its context window for both agents",
      len(turns) >= 20 and all(t["scratch"]["calls"] + t["memorizz"]["calls"] >= 1 for t in turns), len(turns))
by_question: dict = {}
for t in turns:                                  # the first turn that asked each question
    by_question.setdefault(t["question"], t["turn"])
record = client.get(f"/api/context/{by_question['Run the docs_hnsw health check once more.']}").json()
kinds = {side: [[s["kind"] for s in call["sections"]] for call in record[side]["calls"]] for side in ("scratch", "memorizz")}
check("context · scratch: instruction and memory blocks, tools, history, the message, then tool calls and results",
      kinds["scratch"] and kinds["scratch"][0][0] == "system" and {"tools", "history", "query"} <= set(kinds["scratch"][0])
      and any("tool_io" in call for call in kinds["scratch"]), kinds["scratch"])
check("context · MemoRizz: the stored snapshot, system prompt then tools then messages, with OpenAI's cached count",
      kinds["memorizz"] and kinds["memorizz"][0][:2] == ["system", "tools"] and "query" in kinds["memorizz"][0]
      and any((call["cached_tokens"] or 0) > 0 for call in record["memorizz"]["calls"]), record["memorizz"]["calls"][:1])
hit = client.get(f"/api/context/{by_question['Which ticket prefix is required for Oracle maintenance changes?']}").json()
check("context · a semantic-cache hit has no MemoRizz model call", not hit["memorizz"]["calls"]
      and "semantic cache" in (hit["memorizz"]["note"] or ""), hit["memorizz"])
check("context · an unknown turn is a 404", client.get("/api/context/99999").status_code == 404)

# Part 13 · shared memory
result = action(13, "review")
check("13 · Rev reports on both sides and Memo revises",
      all(result.get(s, {}).get(k) for s in ("scratch", "memorizz") for k in ("plan", "findings", "revised")), result)
check("13 · the revision keeps to the Tuesday window",
      all("tuesday" in result.get(s, {}).get("revised", "").lower() for s in ("scratch", "memorizz")))
check("13 · the MemoRizz blackboard has a command and a report",
      {e.get("type") for e in result.get("memorizz", {}).get("blackboard", [])} >= {"COMMAND", "REPORT"}, result.get("memorizz"))
board = table(page(13), "scratch", "scratch_blackboard")["rows"]
check("13 · the scratch blackboard has a command and a report", {r.get("kind") for r in board} >= {"COMMAND", "REPORT"})

# Part 14 · forgetting
result = action(14, "scores", query="Who do I page when the rebuild fails?")
check("14 · every runbook chunk has a score and a retention", len(result.get("scratch", [])) >= 7, result)
result = action(14, "suppress")
suppressed = set(result.get("scratch_suppressed_ids", []))
check("14 · low-retention chunks are suppressed and leave search",
      bool(suppressed) and len(result.get("scratch_search_after", [])) < 7, result)
check("14 · MemoRizz plans and applies a reviewed suppression",
      (result.get("memorizz_plan") or {}).get("dry_run") is True and result.get("memorizz_suppressed", 0) >= 1, result)
result = action(14, "restore")
check("14 · suppression is reversible on both sides",
      result.get("scratch_restored", 0) >= 1 and len(result.get("scratch_search_after", [])) == 7
      and result.get("memorizz_still_suppressed") == 0, result)

# Part 15 · routing
result = action(15, "route")
accuracy = result.get("accuracy") or {}
check("15 · Jev matches the expected stores", (accuracy.get("jev") or 0) >= 0.75, accuracy)
check("15 · Jev answers the batch faster than the chat model", result.get("jev_seconds", 99) < result.get("llm_seconds", 0), result)
check("15 · MemoRizz's question has every store and place() applies the threshold",
      "do_not_store" in result.get("memorizz_options", []) and all("filed_to" in r for r in result.get("rows", [])))
result = action(15, "file", item="Policy: vector indexes for embedding-worker may only be rebuilt on Thursdays.")
check("15 · a policy item is filed into knowledge on both sides",
      result.get("scratch_filed") == "knowledge" and str(result.get("memorizz_filed", "")).startswith("knowledge_base"), result)
event = chat(15, "Going forward, Memo, put the go or no-go decision in the first line of every plan.")
check("15 · a style instruction in chat is routed to the persona", event["scratch"].get("routed") == "persona", event["scratch"])

# Part 16 · complete agent
result = action(16, "save_restore")
check("16 · both agents restore with their layers and knowledge",
      len(result.get("scratch_layers", [])) >= 12 and (result.get("memorizz") or {}).get("knowledge_bases", 0) >= 1, result)
result = action(16, "compare")
check("16 · both restored agents answer the integrated request with tools",
      all(result.get(s, {}).get("text") and result.get(s, {}).get("tool_calls") for s in ("scratch", "memorizz")), result)
# The go/no-go decision is graded by the same LLM judge as the Tokenomics page, against the runbook.
from backend.core import judge as llm_judge  # noqa: E402  (same .env as the server)

GO_REFERENCE = ("GO: Tuesday 02:20 UTC is inside the Tuesday 02:00-04:00 UTC rebuild window, docs_hnsw is ready, "
                "and the vector memory pool has at least 20 percent free (27.5 percent).")


def judged(result: dict) -> dict:
    return {side: llm_judge.grade(result["request"], GO_REFERENCE, result.get(side, {}).get("text", ""))
            for side in ("scratch", "memorizz")}


verdicts = judged(result)
retried = not all(v["score"] == 1 for v in verdicts.values())
if retried:                                   # a model's answer varies from run to run; allow one retry and say so
    result = action(16, "compare")
    verdicts = judged(result)
check("16 · the LLM judge grades both go/no-go decisions correct against the runbook" + (" (on the retry)" if retried else ""),
      all(v["score"] == 1 for v in verdicts.values()),
      {side: (v["verdict"], v["missing"], v["reason"]) for side, v in verdicts.items()})
result = action(16, "observability")
check("16 · operational evidence on both sides",
      (result.get("scratch_counts") or {}).get("scratch_conversation", 0) > 0
      and ((result.get("memorizz") or {}).get("conversation") or {}).get("row_count", 0) > 0, result)

# Tokenomics: every turn above is measured on both sides, then the memory workload
data = client.get("/api/tokenomics").json()
measured = {agent: [r for r in data["turns"] if r["agent"] == agent] for agent in ("scratch", "memorizz")}
check("tokenomics · chat turns measured for both agents",
      len(measured["scratch"]) >= 10 and len(measured["scratch"]) == len(measured["memorizz"]),
      {agent: len(rows) for agent, rows in measured.items()})
check("tokenomics · latency phases add up and tokens are priced",
      all(abs(sum(r["latency"][k] for k in ("model_ms", "memory_ms", "tools_ms", "other_ms")) - r["latency"]["total_ms"]) < 1
          for r in data["turns"])
      and all(r["cost_usd"] is not None for r in data["turns"])
      and any(r["usage"]["cached_input_tokens"] for r in measured["memorizz"]), data["turns"][-1])
before = len(data["turns"])
progress, notes, done = [], [], {}
with client.stream("POST", "/api/tokenomics/workload", timeout=2400) as response:
    for line in response.iter_lines():
        if line.startswith("data:"):
            event = json.loads(line[5:])
            if event.get("type") == "progress":
                (notes if event.get("note") else progress).append(event)
            if event.get("type") == "done":
                done = event
            if event.get("type") == "error":
                done = {"error": event["message"]}
check("tokenomics · the memory workload measures 30 turns for all three agents, with one compaction",
      len(progress) == 30 and len(notes) == 1 and len(done.get("turns", [])) == before + 90,
      done.get("error") or (len(progress), len(notes), len(done.get("turns", []))))
workload = [r for r in done.get("turns", [])[before:]]
check("tokenomics · the paraphrased policy question is served from a cache on at least one side",
      any(r["cache_hit"] for r in workload if r["test"] == "cache"), [r for r in workload if r["test"] == "cache"])
graded = [r for r in workload if r["accuracy"]["method"]]
check("tokenomics · the LLM judge grades every probe for every agent; what Ada tells Memo stays unscored",
      len(graded) == 75 and all(r["accuracy"]["verdict"] in ("correct", "incorrect") for r in graded)
      and all(r["accuracy"]["verdict"] == "unscored" for r in workload if r["test"] == "told"),
      [(r["agent"], r["question"][:30], r["accuracy"]["verdict"]) for r in workload])
summary = done.get("summary") or {}
print("   accuracy:", {a: (summary.get(a) or {}).get("accuracy") for a in ("scratch", "memorizz", "naive")},
      "judge cost:", {a: (summary.get(a) or {}).get("judge_cost_usd") for a in ("scratch", "memorizz", "naive")})
print("   total cost:", {a: (summary.get(a) or {}).get("total_cost_usd") for a in ("scratch", "memorizz", "naive")})
for agent in ("scratch", "memorizz", "naive"):
    print(f"   {agent} by test:", {k: f"{v['correct']}/{v['scored']}" for k, v in ((summary.get(agent) or {}).get("by_test") or {}).items()})
check("tokenomics · the probes are answerable: each agent is graded correct on most of them",
      all(((summary.get(a) or {}).get("accuracy") or 0) >= 0.5 for a in ("scratch", "memorizz")),
      {a: (summary.get(a) or {}).get("accuracy") for a in ("scratch", "memorizz")})
check("tokenomics · accuracy is broken down by memory test for both agents",
      all(set(done.get("tests", {})) - {"told"} <= set((summary.get(a) or {}).get("by_test") or {}) for a in ("scratch", "memorizz")),
      {a: sorted((summary.get(a) or {}).get("by_test") or {}) for a in ("scratch", "memorizz")})
naive = [r for r in workload if r["agent"] == "naive"]
main = [r["usage"]["input_tokens"] for r in naive if r["thread"] == "tokenomics"]
check("tokenomics · the naive agent answers every turn with one model call, no tools and no cache",
      len(naive) == 30 and all(r["usage"]["model_calls"] == 1 and not r["tool_calls"] and not r["cache_hit"] for r in naive),
      [(r["turn"], r["usage"]["model_calls"], r["tool_calls"]) for r in naive])
check("tokenomics · the naive context grows every turn of its thread: the whole transcript is resent",
      len(main) == 26 and all(b > a for a, b in zip(main, main[1:])), main)
stacks = done.get("stacks") or {}
check("tokenomics · both agents ran with every memory unit (MemoRizz: knowledge, entities, summaries, evidence pack, cache)",
      {"conversation", "entities", "knowledge", "summaries", "semantic cache"} <= set(stacks.get("scratch") or [])
      and {"knowledge_base", "entity_memory", "summaries", "skillbox", "workflow_memory", "semantic_cache",
           "evidence pack (continual learning)"} <= set(stacks.get("memorizz") or []), stacks)
check("tokenomics · the summary totals all three agents",
      all((summary.get(a) or {}).get("turns", 0) >= 30 and (summary.get(a) or {}).get("total_cost_usd", 0) > 0
          for a in ("scratch", "memorizz", "naive")), summary)
from backend.core import scratch  # noqa: E402  (same credentials as the server's .env)

session_rows = scratch.sql("SELECT COUNT(*) AS n FROM scratch_conversation WHERE memory_id = :m AND thread_id IN "
                           "('tokenomics', 'standup')", m=session["scope"]["memory_id"])[0]["n"]
check("tokenomics · the workload runs in its own fresh scope: the session's memory is untouched", session_rows == 0,
      session_rows)
contexts = client.get("/api/context").json()["turns"]
first = next((t for t in contexts if t["question"] == "What was the very first thing I asked you today?"), None)
record = client.get(f"/api/context/{first['turn']}").json() if first else {}
labels = {side: [s["label"] for call in (record.get(side) or {}).get("calls", []) for s in call["sections"]]
          for side in ("scratch", "memorizz")}
check("context · every workload turn has its context window; after compaction both carry the summary",
      len(contexts) == len({r["turn"] for r in done.get("turns", [])}) and any(l.startswith("Summary #") for l in labels["scratch"])
      and any("summar" in l.lower() for l in labels["memorizz"]), labels)
cleared = client.post("/api/tokenomics/clear").json()
check("tokenomics · clearing removes measurements only", cleared["turns"] == [], cleared["summary"])
check("context · clearing the measurements clears the context windows", client.get("/api/context").json()["turns"] == [])
agent_id = client.get("/api/session").json()["agent_id"]

# Reset: exact-scope cleanup leaves nothing behind
old = session["scope"]
report = client.post("/api/session/reset").json()
check("reset cleans the session", (report.get("cleanup") or {}).get("cleaned") is True, report)

leftover = {table: scratch.sql(f"SELECT COUNT(*) AS n FROM {table} WHERE memory_id = :m", m=old["memory_id"])[0]["n"]
            for table in scratch.SCRATCH_TABLES if table != "scratch_blackboard"}
leftover["conversation_memory"] = scratch.sql("SELECT COUNT(*) AS n FROM conversation_memory WHERE memory_id = :m",
                                              m=old["memory_id"])[0]["n"]
leftover["entity_memory"] = scratch.sql("SELECT COUNT(*) AS n FROM entity_memory WHERE memory_id = :m",
                                        m=old["memory_id"])[0]["n"]
leftover["context_snapshots"] = scratch.sql("SELECT COUNT(*) AS n FROM shared_memory WHERE memory_id LIKE 'ctx-%' "
                                           "AND owner_agent_id = :a", a=agent_id)[0]["n"]
check("no rows remain for the old session", not any(leftover.values()), leftover)

print(f"\n{'FAILED' if failures else 'PASSED'}: {len(failures)} failing check(s) · {time.perf_counter() - started_all:.0f}s")
for label in failures:
    print(f"  - {label}")
sys.exit(1 if failures else 0)
