"""Offline contracts: no database, no model, no keys.

    ../../../.venv/bin/python -m pytest tests/test_contracts.py -q     # from appbook/
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

APPBOOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APPBOOK))

from fastapi.testclient import TestClient  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.core import activity, context_view, judge, rows, scratch, session, tokenomics  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers.parts import ACTIONS  # noqa: E402
from backend.schemas import ActionRequest, ChatRequest  # noqa: E402

SCRATCH_SOURCE = (APPBOOK / "backend/core/scratch.py").read_text()
APP_JS = (APPBOOK / "frontend/app.js").read_text()


@pytest.fixture()
def offline_client(monkeypatch):
    """A client whose OpenAI key is missing, so nothing reaches Oracle or a model."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    return TestClient(app)        # not entered as a context manager: no lifespan, no warm-up


def test_routes_exist():
    paths = set(app.openapi()["paths"])
    for path in ["/api/health", "/api/session", "/api/session/reset", "/api/parts/{part}",
                 "/api/parts/{part}/chat", "/api/parts/{part}/actions/{name}", "/api/data_explorer/status",
                 "/api/data_explorer/tables", "/api/data_explorer/tables/{table}/rows", "/api/data_explorer/activity",
                 "/api/tokenomics", "/api/tokenomics/workload", "/api/tokenomics/status", "/api/tokenomics/stop", "/api/tokenomics/clear",
                 "/api/context",
                 "/api/context/{turn}"]:
        assert path in paths, path


def test_sixteen_parts_with_tables_and_actions():
    assert sorted(session.PAGE_TABLES) == list(range(1, 17))
    for part, names in ACTIONS.items():
        for name in names:
            assert hasattr(session.LabSession, f"_p{part}_{name}"), (part, name)
    for scratch_tables, memorizz_tables in session.PAGE_TABLES.values():
        assert all(table in scratch.DDL for table in scratch_tables)
        assert all(table in rows.MEMORIZZ_TABLES for table in memorizz_tables)


def test_frontend_mirrors_parts_and_actions():
    assert len(re.findall(r"\{ n: (\d+), group:", APP_JS)) == 16
    for part, names in ACTIONS.items():
        block = re.search(rf"\n  {part}: \[(.*?)\],\n(?:  \d+:|\}};)", APP_JS, re.S)
        assert block, part
        assert sorted(re.findall(r'name: "([a-z_]+)"', block.group(1))) == sorted(names), part
    assert "Nova" not in APP_JS and "/api/lab" not in APP_JS
    html = (APPBOOK / "frontend/index.html").read_text()
    assert '/app.js' in html and '/styles.css' in html and 'data-explorer' in html


def test_request_schemas_are_bounded():
    assert ChatRequest(message="hi").thread == "migration"
    with pytest.raises(ValueError):
        ChatRequest(message="hi", thread="someone-elses-thread")
    with pytest.raises(ValueError):
        ChatRequest(message="x" * 2001)
    with pytest.raises(ValueError):
        ChatRequest(message="hi", cache_domain="runbook; DROP TABLE x", data_version="1")
    assert ChatRequest(message="hi", cache_domain="runbook", data_version="2026-10-17").context() == {
        "cache_domain": "runbook", "data_version": "2026-10-17"}
    assert ChatRequest(message="hi", cache_domain="runbook").context() == {}
    with pytest.raises(ValueError):
        ActionRequest(params={"item": "x" * 7000})


def test_data_explorer_is_allowlisted(offline_client):
    for table in ["user_users", "dual", "SYS_TABLES"]:
        assert not rows.allowed(table)
        assert offline_client.get(f"/api/data_explorer/tables/{table}/rows").status_code == 404
    assert rows.allowed("scratch_conversation") and rows.allowed("CONVERSATION_MEMORY")
    with pytest.raises(ValueError):
        rows.table_columns("user_users")


def test_run_filter_never_reads_everything():
    scope = {"memory_id": "m", "user_id": "u", "knowledge_ids": ["k1"], "shared_ids": [], "agent_ids": ["a1"]}
    where, binds = rows.run_filter(["id", "content"], scope)
    assert where == " WHERE 1 = 0" and binds == {}
    where, binds = rows.run_filter(["memory_id", "user_id", "agent_id"], scope)
    assert ":user_id" in where and set(binds.values()) >= {"m", "k1", "u", "a1"}


def _scratch_statements() -> list[str]:
    statements = []
    for node in ast.walk(ast.parse(SCRATCH_SOURCE)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(part.value if isinstance(part, ast.Constant) else "{x}" for part in node.values)
        else:
            continue
        if re.match(r"\s*(SELECT|UPDATE|DELETE|INSERT|MERGE)\b", text) and "scratch_" in text:
            statements.append(" ".join(text.split()))
    return statements


def test_every_scratch_statement_is_scoped():
    statements = _scratch_statements()
    assert len(statements) > 30
    for statement in statements:
        if statement.startswith(("INSERT", "MERGE")):
            assert "memory_id" in statement or "user_id" in statement, statement
        else:
            assert re.search(r"(memory_id|user_id) = :", statement), statement


def test_scratch_module_keeps_no_run_globals():
    for name in ("MEMORY_ID", "USER_ID", "THREAD_ID", "RUN_ID", "MAIN", "ONCALL", "SESSION"):
        assert not hasattr(scratch, name), name
    for fn in (scratch.ingest, scratch.search_knowledge, scratch.register_tools, scratch.select_tools,
               scratch.add_skill, scratch.propose_skills, scratch.memory_scores, scratch.save_agent):
        assert next(iter(__import__("inspect").signature(fn).parameters)) == "memory_id", fn.__name__


def test_agent_grows_like_the_notebook(monkeypatch):
    monkeypatch.setattr(settings, "typesafe_api_key", "test")
    assert scratch.build_agent(1).layers == []
    names = [layer.name for layer in scratch.build_agent(16).layers]
    assert names[0] == "semantic cache" and names[-1] == "working memory"
    assert {"conversation", "persona", "entities", "knowledge", "toolbox", "workflows", "skills", "summaries",
            "shared memory", "routing"} <= set(names)
    assert scratch.build_agent(5).respond is scratch.single_call
    assert scratch.build_agent(6).respond is scratch.tool_loop and scratch.build_agent(6).execute is scratch.run_tool
    assert scratch.build_agent(7).execute is scratch.logged_tool_call
    toolbox = next(layer for layer in scratch.build_agent(7).layers if layer.name == "toolbox")
    assert toolbox.k == 3 and toolbox.always == ["expand_tool_result"]
    monkeypatch.setattr(settings, "typesafe_api_key", None)
    assert "routing" not in [layer.name for layer in scratch.build_agent(16).layers]


def test_saved_definitions_restore_every_layer(monkeypatch):
    monkeypatch.setattr(settings, "typesafe_api_key", "test")
    for layer in scratch.build_agent(16).layers:
        assert type(layer).__name__ in scratch.LAYER_TYPES
    assert set(scratch.RESPONDERS) == {"single_call", "tool_loop"}
    assert set(scratch.EXECUTORS) == {"run_tool", "logged_tool_call"}


def test_time_columns_carry_a_time_zone():
    for table, ddl in scratch.DDL.items():
        for column in re.findall(r"(\w+_at)\s+TIMESTAMP(?! WITH TIME ZONE)", ddl):
            pytest.fail(f"{table}.{column} must be TIMESTAMP WITH TIME ZONE")


def test_tool_bindings_stay_in_process():
    assert set(scratch.TOOL_BINDINGS) == {fn.__name__ for fn in scratch.PLATFORM_TOOLS} | {"expand_tool_result"}
    turn = scratch.Turn("q", {"memory_id": "m", "user_id": "u", "thread_id": "t"})
    assert "error" in scratch.run_tool(turn, "index_health", {"index_name": "x"})       # not disclosed this turn
    turn.tools = {"index_health": {}}
    assert scratch.run_tool(turn, "index_health", {"index_name": "x"})["checks_passed"] == 30


def test_health_and_failures_are_clear_without_a_key(offline_client):
    health = offline_client.get("/api/health").json()
    assert health["api_key_set"] is False and health["model"]
    response = offline_client.post("/api/parts/2/chat", json={"message": "hello"})
    assert response.status_code == 200 and "OPENAI_API_KEY is not set" in response.text
    response = offline_client.post("/api/parts/5/actions/search", json={"params": {}})
    assert response.status_code == 503 and "OPENAI_API_KEY" in response.json()["detail"]
    assert offline_client.post("/api/parts/5/actions/unknown", json={}).status_code == 404
    assert offline_client.get("/api/parts/99").status_code == 404


def test_tokenomics_prices_and_phases_like_both_agents():
    cost, note = tokenomics.price("gpt-5.5", 10_000, 4_000, 500)
    assert cost == pytest.approx((6_000 * 5 + 4_000 * 0.5 + 500 * 30) / 1_000_000)
    assert "list price" in note
    meter = tokenomics.Meter()
    meter.model_ms, meter.model_ms_in_layers, meter.layer_ms, meter.tools_ms = 900.0, 300.0, 500.0, 40.0
    meter.calls, meter.input_tokens, meter.cached_tokens, meter.output_tokens = 2, 1200, 0, 80
    record = tokenomics.scratch_record(meter, turn=1, part=4, thread="migration", question="q", model="gpt-5.5",
                                       total_ms=1500.0, tool_calls=["index_health"], cache_hit=False)
    assert record["latency"] == {"total_ms": 1500.0, "model_ms": 900.0, "memory_ms": 200.0, "tools_ms": 40.0,
                                 "other_ms": 360.0}
    assert record["usage"]["total_tokens"] == 1280 and record["cost_usd"] > 0
    collector = tokenomics.TraceCollector()
    collector.window = (100.0, 101.0)                       # a one-second turn
    collector.intervals = {"model": [(100.0, 100.7)],
                           "tools": [(100.70, 100.75)],     # a tool that reads memory inside it
                           "memory": [(100.71, 100.74), (100.75, 100.87), (100.80, 100.87)]}  # overlapping reads
    record = tokenomics.memorizz_record(collector, {"calls": 1, "input_tokens": 900, "cached_tokens": 600,
                                                    "output_tokens": 40, "cost_usd": 0.0027}, turn=1, part=4,
                                        thread="migration", question="q", model="gpt-5.5", total_ms=1000.0,
                                        tool_calls=[], cache_hit=False)
    latency = record["latency"]
    assert (latency["model_ms"], latency["tools_ms"], latency["memory_ms"]) == (700.0, 50.0, 120.0)
    assert latency["other_ms"] == 130.0
    assert abs(sum(latency[k] for k in ("model_ms", "tools_ms", "memory_ms", "other_ms")) - 1000) < 0.5
    hit = tokenomics.memorizz_record(tokenomics.TraceCollector(), {}, turn=2, part=12, thread="t", question="q",
                                     model="gpt-5.5", total_ms=300.0, tool_calls=[], cache_hit=True)
    assert hit["cost_usd"] == 0 and hit["usage"]["total_tokens"] == 0 and hit["cache_hit"]
    naive = tokenomics.scratch_record(meter, agent="naive", turn=1, part=16, thread="t", question="q",
                                      model="gpt-5.5", total_ms=1500.0, tool_calls=[], cache_hit=False)
    summary = tokenomics.summary([record, hit, naive])
    assert summary["memorizz"]["turns"] == 2 and summary["memorizz"]["cache_hits"] == 1
    assert summary["scratch"]["turns"] == 0 and summary["naive"]["turns"] == 1
    assert naive["agent"] == "naive" and naive["cost_usd"] > 0 and naive["latency"]["memory_ms"] == 200.0


def test_stop_run_ends_the_workload_after_the_turn_in_progress(monkeypatch):
    record = lambda lab, agent, part, thread, message: tokenomics._record(  # noqa: E731
        turn=lab.turn_no, part=part, thread=thread, question=message, agent=agent, model="m", total_ms=1, model_ms=0,
        memory_ms=0, tools_ms=0, calls=1, input_tokens=1, cached_tokens=0, output_tokens=1, cost=0.0, cost_note="",
        tool_calls=[], cache_hit=False)

    def fake_chat(self, part, message, thread, context, budget, emit, *, reference=None, test=None):
        self.turn_no += 1
        self.metrics += [record(self, agent, part, thread, message) for agent in ("scratch", "memorizz")]
        self.contexts[self.turn_no] = {"turn": self.turn_no}

    cleaned = []
    monkeypatch.setattr(session.LabSession, "chat", fake_chat)
    monkeypatch.setattr(session.LabSession, "naive_chat", lambda self, part, message, thread, **_: self.metrics.append(
        record(self, "naive", part, thread, message)))
    monkeypatch.setattr(session.LabSession, "cleanup", lambda self: cleaned.append(self.run_id) or {})
    monkeypatch.setattr(session.MemorizzMemo, "memory_stack", lambda self: [])
    monkeypatch.setattr(session.scratch, "build_agent", lambda level: scratch.ScratchMemo("x"))
    lab, events = session.LabSession(), []

    def emit(event):
        events.append(event)
        if event["type"] == "turn" and sum(e["type"] == "turn" for e in events) == 2:
            assert lab.tokenomics()["running"]
            assert {k: lab.workload_status()[k] for k in ("state", "completed", "index", "total")} == {
                "state": "running", "completed": 2, "index": 2, "total": 30}
            assert lab.stop_workload() == {"stopping": True} and lab.workload_status()["state"] == "stopping"

    result = lab.workload(emit)
    assert sum(e["type"] == "turn" for e in events) == 2 and events[-1] == {"type": "stopped", "after": 2, "total": 30}
    assert len(result["turns"]) == 6 and result["running"] is False and len(cleaned) == 1   # the bench is cleaned
    assert {k: lab.workload_status()[k] for k in ("state", "completed", "running")} == {
        "state": "stopped", "completed": 2, "running": False}
    events.clear()
    lab.workload(events.append)                                  # the next run starts afresh and runs every turn
    assert sum(e["type"] == "turn" for e in events) == 30 and not any(e["type"] == "stopped" for e in events)
    assert lab.workload_status()["state"] == "complete" and lab.workload_status()["completed"] == 30


def test_naive_agent_appends_the_whole_thread_and_nothing_else(monkeypatch):
    sent = []

    def fake_chat(instructions, messages, tools=None, **options):
        sent.append((instructions, [dict(m) for m in messages], tools))
        return type("R", (), {"output_text": f"answer {len(sent)}"})()

    monkeypatch.setattr(scratch, "chat", fake_chat)
    naive = scratch.NaiveMemo()
    for query, thread in (("one", "a"), ("two", "a"), ("three", "b"), ("four", "a")):
        naive.run(query, memory_id="m", user_id="u", thread_id=thread)
    assert [len(messages) for _, messages, _ in sent] == [1, 3, 1, 5]      # grows by two messages a turn, per thread
    assert sent[1][1] == [{"role": "user", "content": "one"}, {"role": "assistant", "content": "answer 1"},
                          {"role": "user", "content": "two"}]
    assert all(instructions == scratch.INSTRUCTION and tools is None for instructions, _, tools in sent)


def test_scratch_model_and_tool_calls_are_metered():
    assert "tokenomics.record_model(" in SCRATCH_SOURCE and "tokenomics.record_tool(" in SCRATCH_SOURCE
    assert SCRATCH_SOURCE.count('with tokenomics.layer_work(f"{layer.name} layer · ') == 2
    assert '{"instructions": instructions, "input": messages, "tools": tools or []}' in SCRATCH_SOURCE


def test_tokenomics_endpoint_and_workload_offline(offline_client):
    data = offline_client.get("/api/tokenomics").json()
    assert set(data) >= {"turns", "summary", "model", "judge_model", "workload", "tests", "compact_after"}
    assert len(data["workload"]) == 30 and sum(1 for item in data["workload"] if item["reference"]) == 25
    events = offline_client.post("/api/tokenomics/workload").text
    assert "OPENAI_API_KEY" in events
    assert activity.operations_for("POST", "/api/tokenomics/workload")


def test_frontend_has_tokenomics_page_and_unit_cards():
    html = (APPBOOK / "frontend/index.html").read_text()
    assert html.index("/units.js") < html.index("/app.js") and html.index("/tokenomics.js") < html.index("/app.js")
    tokenomics_js = (APPBOOK / "frontend/tokenomics.js").read_text()
    for chart in ("tk-accuracy", "tk-latency", "tk-cost", "tk-tokens", "tk-tests", "tk-stacks"):
        assert chart in tokenomics_js
    assert 'naive: "Naive"' in tokenomics_js and "<polyline" in tokenomics_js and "stroke-dasharray" in tokenomics_js
    assert 'id="ctxrail-toggle"' in html and 'id="ctxrail"' in html and "zth-ctxrail" in html
    assert "function toggleCtxRail()" in APP_JS and "CTXRAIL_STORAGE_KEY" in APP_JS
    assert "/api/tokenomics/status" in tokenomics_js and "run-toast" in tokenomics_js and "tk.abort.signal" in tokenomics_js
    assert "tkRenderToast();" in APP_JS and "tkPollStatus();" in APP_JS
    assert "function unitTable(json)" in APP_JS and 'data-view="${view}"' in APP_JS and "zth-unit-view" in html
    assert "#/tokenomics" in APP_JS and "viewTokenomics()" in APP_JS and "unitCard(p)" in APP_JS
    units = (APPBOOK / "frontend/units.js").read_text()
    for part in range(2, 17):
        assert f'"{part}": {{' in units, part
    assert units.count('"definition"') == 15 and units.count('"uses"') == 15


def test_golden_references_match_questions_loosely():
    assert tokenomics.reference_for("what ticket prefix do oracle maintenance changes need") == "The ORAMNT prefix."
    assert tokenomics.reference_for("Who owns the embedding-worker service?") == "Lin."
    assert tokenomics.reference_for("What have we covered so far?") is None
    # Part-page references use only what setup gives both agents, never facts a user states in chat.
    assert not any("Ada" in reference or "SQL" in reference for reference in tokenomics.GOLDEN.values())


def test_memory_workload_is_coherent():
    workload = tokenomics.WORKLOAD
    assert len(workload) == 30 and set(item["test"] for item in workload) == set(tokenomics.TESTS)
    for item in workload:                                   # told turns are unscored; every probe has a reference
        assert (item["test"] == "told") == (item["reference"] is None), item["question"]
    told = [k for k, item in enumerate(workload) if item["test"] == "told"]
    first_probe = {"recall": 5, "update": 11, "cross-thread": 25, "preference": 24}
    for test, index in first_probe.items():                 # each memory probe comes after what it asks about
        assert workload[index]["test"] == test and any(k < index for k in told)
    assert workload[19]["reference"].startswith("21 November") and told[3] < 19   # the update precedes the probe
    assert 0 < tokenomics.COMPACT_AFTER < 20 + 1 and workload[tokenomics.COMPACT_AFTER]["test"] == "back-reference"
    new = [item for item in workload if item["thread"] == tokenomics.NEW_THREAD]
    assert len(new) == 4 and workload[-1]["thread"] == tokenomics.MAIN_THREAD
    cached = [item for item in workload if item["context"]]
    assert [item["test"] for item in cached] == ["grounding", "cache"]


class _FakeResponses:
    def __init__(self, payload):
        self.payload = payload

    def create(self, **kwargs):
        assert kwargs["model"] == settings.judge_model and "Reference (required facts)" in kwargs["input"]
        usage = type("U", (), {"input_tokens": 400, "output_tokens": 30, "input_tokens_details": None})()
        return type("R", (), {"output_text": self.payload, "usage": usage})()


def test_llm_judge_scores_and_prices_separately(monkeypatch):
    fake = type("C", (), {"responses": _FakeResponses('{"verdict": "incorrect", "missing": ["ORAMNT"], "reason": "No prefix."}')})()
    monkeypatch.setattr(scratch, "llm", lambda: fake)
    verdict = judge.grade("What ticket prefix?", "The ORAMNT prefix.", "Use a ticket.")
    assert verdict["score"] == 0 and verdict["missing"] == ["ORAMNT"] and verdict["judge_cost_usd"] > 0
    records = [tokenomics._record(turn=1, part=12, thread="t", question="q", agent=agent, model="gpt-5.5",
                                  total_ms=1, model_ms=0, memory_ms=0, tools_ms=0, calls=1, input_tokens=10,
                                  cached_tokens=0, output_tokens=1, cost=0.1, cost_note="", tool_calls=[],
                                  cache_hit=False) for agent in ("scratch", "memorizz")]
    fake.responses.payload = '{"verdict": "correct", "missing": [], "reason": "States ORAMNT."}'
    judge.grade_pair("What ticket prefix do Oracle maintenance changes need?", records,
                     {"scratch": "ORAMNT", "memorizz": "ORAMNT"})
    assert [r["accuracy"]["score"] for r in records] == [1, 1]
    summary = tokenomics.summary(records)
    assert summary["scratch"]["accuracy"] == 1.0 and summary["memorizz"]["correct"] == 1
    assert summary["scratch"]["total_cost_usd"] == 0.1 and summary["scratch"]["judge_cost_usd"] > 0

    records[0]["test"] = records[1]["test"] = "update"     # a workload probe brings its own reference
    judge.grade_pair("When is the cutover now?", records, {"scratch": "21 Nov", "memorizz": "21 Nov"},
                     "21 November.")
    assert summary["scratch"]["by_test"] == {"golden question": {"scored": 1, "correct": 1}}
    assert tokenomics.summary(records)["memorizz"]["by_test"] == {"update": {"scored": 1, "correct": 1}}
    judge.grade_pair("What have we covered so far?", records, {})          # no reference: left as it was
    assert records[0]["accuracy"]["score"] == 1
    assert "unless the reference says the right answer is to say so" in judge.RUBRIC

    def broken():
        raise RuntimeError("judge offline")
    monkeypatch.setattr(scratch, "llm", broken)
    judge.grade_pair("Who owns the embedding-worker service?", records, {"scratch": "Lin", "memorizz": "Lin"})
    assert all(r["accuracy"]["score"] is None and r["accuracy"]["verdict"] == "judge failed" for r in records)


def test_memorizz_rebuilds_name_their_knowledge_bases():
    # MemoRizz 0.17 keeps a stored agent's knowledge bases across rebuilds unless the builder names them, and
    # MemAgent.load(tools=...) restores governed tools: no re-attaching, add_tool or set_persona by hand.
    assert "with_knowledge_base(self.knowledge_ids if level >= 5 else [])" in (
        APPBOOK / "backend/core/memorizz_memo.py").read_text()
    for path in ("backend/core/memorizz_memo.py", "backend/core/session.py"):
        source = (APPBOOK / path).read_text()
        assert not any(call in source for call in ("attach_to_agent(", "add_tool(", "set_persona(")), path
    assert "tools=governed_tools()" in (APPBOOK / "backend/core/session.py").read_text()
    assert "memorizz[oracle]>=0.17.4,<0.18" in (APPBOOK / "requirements.txt").read_text()
    assert '(0, 17, 4) <= v < (0, 18)' in (APPBOOK / "run.sh").read_text()


def _usage(inputs: int, cached: int, outputs: int):
    from types import SimpleNamespace

    return SimpleNamespace(usage=SimpleNamespace(input_tokens=inputs, output_tokens=outputs,
                                                 input_tokens_details=SimpleNamespace(cached_tokens=cached)))


def test_context_window_splits_a_scratch_request_in_reading_order():
    from types import SimpleNamespace

    class Call(SimpleNamespace):          # stands in for an SDK output item appended by tool_loop
        def model_dump(self, exclude_none=True):
            return dict(vars(self))

    messages = [{"role": "user", "content": "I'm Ada."}, {"role": "assistant", "content": "Hi Ada."},
                {"role": "user", "content": "Check docs_hnsw."},
                Call(type="function_call", name="index_health", arguments='{"index_name": "docs_hnsw"}', call_id="c1"),
                {"type": "function_call_output", "call_id": "c1", "output": '{"status": "ready"}'}]
    request = {"instructions": "You are Memo.\n\n## Persona v1\nname: Memo\n\n## Request context (this turn only, "
                               "never stored)\n{}", "input": messages,
               "tools": [{"type": "function", "name": "index_health", "parameters": {}}]}
    with tokenomics.metering() as meter:
        tokenomics.record_model(_usage(900, 0, 40), 10.0, request)
        messages.append({"role": "user", "content": "changed after the call"})     # the record is a copy
        with tokenomics.layer_work("entities layer · write"):
            tokenomics.record_model(_usage(200, 0, 20), 5.0, {"instructions": "Extract facts.", "input": "I'm Ada."})
    calls = context_view.scratch_calls(meter.requests)
    assert [c["stage"] for c in calls] == ["step 1 · after tool results", "entities layer · write"]
    first = calls[0]
    assert [s["kind"] for s in first["sections"]] == ["system", "memory", "context", "tools", "history", "query",
                                                      "tool_io", "tool_io"]
    assert first["sections"][1]["label"] == "Persona v1" and first["sections"][3]["items"] == ["index_health"]
    assert len(first["sections"][4]["messages"]) == 2 and first["sections"][5]["text"] == "Check docs_hnsw."
    assert first["sections"][-1]["label"] == "Tool result · index_health"
    assert (first["input_tokens"], first["cached_tokens"], first["output_tokens"]) == (900, 0, 40)
    assert [s["kind"] for s in calls[1]["sections"]] == ["system", "query"]


def test_context_window_splits_a_memorizz_snapshot_in_reading_order():
    volatile = ("<memorizz:context>\nMEMORIZZ EVIDENCE PACK\n\nTreat these as retrieved evidence.\n\n"
                "[1] knowledge_base:k1 (score=0.5; trust=0.75)\nRebuild window.\n\n"
                "[2] entity_memory:e1 (score=0.3; trust=0.60)\nAda\nperson\n\n"
                "Recent tool outputs in this thread (use `retrieve_tool_log_entry('<id>')` to unpack):\n• t1  "
                "tool=index_health\n\nREQUEST CONTEXT (ephemeral, this turn only):\n{}\n</memorizz:context>\n\n"
                "Check docs_hnsw.")
    snapshot = {"messages": [{"role": "system", "content": "You are a MemAgent."},
                             {"role": "user", "content": "I'm Ada."}, {"role": "assistant", "content": "Hi Ada."},
                             {"role": "developer", "content": "<memorizz:approved-skills>x</memorizz:approved-skills>"},
                             {"role": "user", "content": volatile},
                             {"role": "assistant", "content": None, "tool_calls": [
                                 {"id": "c1", "type": "function",
                                  "function": {"name": "index_health", "arguments": "{}"}}]},
                             {"role": "tool", "tool_call_id": "c1", "content": "{}"}],
                "tools": [{"type": "function", "function": {"name": "index_health"}}]}
    collector = tokenomics.TraceCollector()
    collector({"type": "trace", "trace_kind": "context_snapshot", "span_id": "s1", "snapshot_id": "ctx-s1"})
    collector({"type": "trace", "trace_kind": "model_result", "span_id": "s1", "stage": "agent_run", "iteration": 2,
               "input_tokens": 7000, "cached_tokens": 5760, "output_tokens": 50, "duration_ms": 900})
    assert collector.calls == {"s1": {"snapshot_id": "ctx-s1", "stage": "agent_run", "iteration": 2,
                                      "input_tokens": 7000, "cached_tokens": 5760, "output_tokens": 50}}
    assert collector.intervals["model"]                     # the phase timing still sees the model call
    (call,) = context_view.memorizz_calls([(snapshot, collector.calls["s1"])])
    assert call["stage"] == "step 2 · after tool results" and call["cached_tokens"] == 5760
    assert [(s["kind"], s["label"]) for s in call["sections"]] == [
        ("system", "System prompt · framework, instruction, persona"), ("tools", "Tool schemas · 1"),
        ("history", "Conversation history · 2 messages"), ("memory", "Approved skills (developer message)"),
        ("memory", "Evidence pack · notice"), ("memory", "Evidence [1] · knowledge_base"),
        ("memory", "Evidence [2] · entity_memory"), ("memory", "Recent tool outputs (tool-log digest)"),
        ("context", "Request context"), ("query", "User message (this turn)"),
        ("tool_io", "Tool call · index_health"), ("tool_io", "Tool result · index_health")]
    assert call["sections"][9]["text"] == "Check docs_hnsw."
    (missing,) = context_view.memorizz_calls([({}, {"stage": "agent_run", "iteration": 1})])
    assert missing["sections"][0]["label"].startswith("No context snapshot")


def test_context_windows_are_kept_per_turn_and_cleared_with_the_measurements(offline_client):
    lab = session.LabSession()
    lab.contexts[1] = context_view.turn(turn=1, part=12, thread="t", question="q", test=None, scratch=[],
                                        memorizz=[])
    assert lab.contexts[1]["scratch"]["note"].startswith("No model call")
    assert lab.context_turns()[0]["memorizz"] == {"calls": 0, "input_tokens": 0, "cached_tokens": 0}
    lab.clear_metrics()
    assert lab.contexts == {} and lab.context(1) is None
    assert offline_client.get("/api/context").json() == {"turns": []}
    assert offline_client.get("/api/context/1").status_code == 404
    assert "capture_context_snapshots = True" in (APPBOOK / "backend/core/memorizz_memo.py").read_text()


def test_frontend_has_the_context_window_page():
    html = (APPBOOK / "frontend/index.html").read_text()
    assert html.index("/context.js") < html.index("/app.js")
    context_js = (APPBOOK / "frontend/context.js").read_text()
    assert "/api/context" in context_js and "function viewContext(" in context_js
    assert set(context_view.KINDS) <= set(re.findall(r"(\w+): \"#[0-9a-f]{6}\"", context_js.split("};")[0]))
    assert 'href="#/context"' in APP_JS and "viewContext(" in APP_JS and "#/context/${a.turn}" in APP_JS
    assert "#/context/${Number(r.turn)}" in (APPBOOK / "frontend/tokenomics.js").read_text()
