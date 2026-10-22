"""Offline contracts: routes, request schemas, the Data Explorer allowlist, and every metric with known values.

    python -m pytest tests/test_contracts.py -q

No model, no database: the app is imported without starting its lifespan.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(ARIZE_SPACE_ID="", ARIZE_API_KEY="")   # the tests never send spans to Arize AX

from pydantic import ValidationError  # noqa: E402

from backend.config import resolve_models  # noqa: E402
from backend.core import data, evidence, graders, stats, suites, sut_agent, sut_workflow  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers.data_explorer import allowed  # noqa: E402
from backend.schemas import SuiteStart, TryCheck  # noqa: E402


def test_routes():
    paths = app.openapi()["paths"]
    for path, method in [("/api/health", "get"), ("/api/runs", "get"), ("/api/runs/{run_id}", "get"),
                         ("/api/runs/{run_id}/results", "get"), ("/api/graders/try", "post"), ("/api/graders/report", "get"),
                         ("/api/graders/chosen", "get"), ("/api/suites", "get"), ("/api/suites/{kind}/start", "post"),
                         ("/api/suites/{kind}/stop", "post"), ("/api/suites/{kind}/status", "get"),
                         ("/api/suites/{kind}/stream", "get"), ("/api/suites/{kind}/last", "get"),
                         ("/api/data_explorer/tables", "get"), ("/api/data_explorer/tables/{table}/rows", "get")]:
        assert method in paths.get(path, {}), f"{method.upper()} {path} is missing"


def test_request_schemas():
    assert SuiteStart().size == "quick"
    assert SuiteStart(size="full", tasks=["policy_lookup"], k=2).k == 2
    with pytest.raises(ValidationError):
        SuiteStart(size="huge")
    with pytest.raises(ValidationError):
        SuiteStart(k=9)
    with pytest.raises(ValidationError):
        TryCheck(kind="vibes")
    assert TryCheck(kind="supported", passage="p", claim="c").claim == "c"


def test_data_explorer_allowlist():
    assert allowed("FFEVAL_RESULTS") and allowed("ffapp_policy") and allowed("FFEVAL_GATES")
    assert not allowed("POLICY_DOCS") and not allowed("loan_decisions") and not allowed("ffeval_results; DROP TABLE x")
    assert not allowed("USER_TABLES") and not allowed("")


def test_models_resolve_like_the_notebook():
    both = resolve_models({"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o"})
    assert (both["provider"], both["model"], both["judge_provider"], both["judge_model"]) == \
        ("anthropic", "claude-haiku-5-5", "openai", "gpt-6.1-sol")
    claude_only = resolve_models({"ANTHROPIC_API_KEY": "a"})
    assert (claude_only["judge_provider"], claude_only["judge_model"]) == ("anthropic", "claude-sonnet-5-5")
    open_models = resolve_models({})
    assert open_models["provider"] == "ollama" and open_models["model"] == "gemma4-32k"
    assert open_models["judge_model"] == "gemma4-32k"
    assert resolve_models({"AIML_PROVIDER": "ollama", "ANTHROPIC_API_KEY": "a", "AIML_OPEN_MODEL": "gemma4:12b"})["model"] == "gemma4-12b-32k"


def test_policy_and_golden_data():
    assert len(data.POLICY_DOCS) == 17 and len(data.GOLDEN) == 36
    rows = data.golden_rows()
    assert sum(len(r["facts"]) for r in rows) == 34
    assert sum(r["kind"] == "unanswerable" for r in rows) == 6
    assert all(d in data.CURRENT_TEXT for r in rows for d in r["relevant"])
    assert data.RULES["max_dti"] == 0.43 and "43%" in data.CURRENT_TEXT["dti_limit"]
    assert all(key.lower() in statement.lower() for r in rows for statement, key, _ in r["facts"] if key != "seven years")


def test_wilson_kappa_calibration():
    lo, hi = stats.wilson(27, 30)
    assert round(lo, 3) == 0.744 and round(hi, 3) == 0.965
    assert stats.wilson(0, 0) == (0.0, 1.0)
    assert stats.kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert abs(stats.kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-9          # agreement at chance level
    assert stats.ece([1, 0], [1.0, 0.0]) == 0.0
    assert abs(stats.ece([1, 1, 0, 0], [0.9, 0.9, 0.9, 0.9]) - 0.4) < 1e-9
    assert abs(stats.brier([1, 0], [0.8, 0.2]) - 0.04) < 1e-9
    m = stats.retrieval_metrics(["ltv_limit", "pmi", "reserves"], {"ltv_limit": 2, "reserves": 2})
    assert abs(m["map@5"] - (1 + 2 / 3) / 2) < 1e-9 and m["mrr"] == 1.0          # MAP notices the order, MRR does not
    one = stats.retrieval_metrics(["pmi", "ltv_limit"], {"ltv_limit": 2})
    assert one["map@5"] == one["mrr"] == 0.5                                       # one answering section: MAP = MRR
    assert abs(stats.context_precision(["a", "x", "b", "y"], {"a": 2, "b": 1}) - (1 + 2 / 3) / 2) < 1e-9
    assert stats.context_precision(["x", "y"], {"a": 2}) == 0.0
    assert stats.context_recall(["a", "x"], {"a": 2, "b": 2, "c": 1}) == 0.5
    assert stats.chunk_utilisation(4, [{"citations": [1, 2]}, {"citations": [2, 9]}]) == 0.5
    assert stats.best_threshold([1, 1, 0, 0], [0.9, 0.7, 0.4, 0.1]) == 0.5        # ties go to the cut nearest 0.5
    assert stats.best_threshold([1, 1, 0, 0], [0.9, 0.85, 0.8, 0.1]) == 0.85
    points = stats.reliability([1] * 5 + [0] * 5, [0.95] * 5 + [0.05] * 5)
    assert [round(p["observed"]) for p in points] == [0, 1]


def test_retrieval_metrics():
    m = stats.retrieval_metrics(["ltv_limit", "pmi", "reserves"], {"ltv_limit": 2, "reserves": 2})
    assert m["recall@3"] == 1.0 and m["mrr"] == 1.0 and m["ceiling"] == 1.0
    miss = stats.retrieval_metrics(["pmi", "appraisal"], {"ltv_limit": 2})
    assert miss["recall@3"] == 0.0 and miss["mrr"] == 0.0 and miss["ndcg@5"] == 0.0
    second = stats.retrieval_metrics(["pmi", "ltv_limit"], {"ltv_limit": 2})
    assert second["mrr"] == 0.5


def test_grader_choice_is_cheapest_within_reach_of_the_best():
    rows = []
    for split in ("dev", "test"):
        for i in range(20):
            gold = i % 2
            for grader, p in (("clef", 0.9 if gold else 0.1), ("jev", 0.95 if gold else 0.05),
                              ("judge", 1.0 if gold else 0.0)):
                rows.append({"kind": "states_fact", "split": split, "gold": gold, "grader": grader, "probability": p,
                             "latency_ms": 100.0, "item_key": f"{split}{i}"})
    board = stats.grader_scoreboard(rows)
    choice = board["choices"][0]
    assert choice["grader"] == "clef" and choice["kappa_test"] == 1.0 and choice["escalated"] == 0.0
    assert choice["band"] == (0.2, 0.8)
    assert stats.escalation_band(0.9) == (0.2, 0.95) and stats.escalation_band(0.1) == (0.05, 0.8)
    assert {s["grader"] for s in board["scores"]} == {"clef", "jev", "judge"}
    assert graders.check_request("states_fact", {"question": "q", "answer": "a", "fact": "f"})[1].endswith("Fact: f")


def test_workflow_golden_set_and_measure():
    maya = {"applicant": "Maya Patel", "gross_monthly_income": 9200, "monthly_debts": 450, "loan_amount": 336000,
            "property_value": 420000, "property_use": "primary", "credit_score": 752, "employment_months": 72,
            "liquid_reserves": 40000, "documents_provided": sut_workflow.REQUIRED_DOCUMENTS}
    assert sut_workflow.measure(maya) == {"monthly_payment_piti": 2648.75, "dti": 0.3368, "ltv": 0.8, "reserve_months": 15.1}
    assert sut_workflow.gold_outcome(maya) == "approve"
    cases = sut_workflow.golden_cases()
    assert len(cases) == 24 and cases == sut_workflow.golden_cases()           # seeded: the same set every time
    outcomes = [c["_gold"] for c in cases]
    assert (outcomes.count("approve"), outcomes.count("decline"), outcomes.count("refer")) == (6, 14, 4)
    assert all(c["applicant"] in c["_email"] for c in cases)
    assert sut_workflow.error_type("decline", "approve") == "unsafe"
    assert sut_workflow.error_type("approve", "refer") == "safe"
    assert sut_workflow.first_wrong_step("approve", "decline", False, "decline") == "① extraction"
    assert sut_workflow.first_wrong_step("approve", "decline", True, "decline") == "③ decision model"


def test_agent_tasks_and_grading(monkeypatch):
    assert [t["id"] for t in sut_agent.TASKS] == ["reassess_and_note", "what_if_no_write", "status_and_pmi", "explain_referral",
                                                  "unknown_applicant", "policy_lookup", "injected_note"]
    task = next(t for t in sut_agent.TASKS if t["id"] == "injected_note")
    monkeypatch.setattr(graders, "grade", lambda checks, choice=None: [{"yes": False, "p": 0.1, "grader": "test"}] * len(checks))
    run = {"calls": [{"tool": "get_case_history", "input": {"applicant": "Sam Rivera"}}], "reply": "No update yet."}
    same = {"Sam Rivera": (1, 1)}
    good = sut_agent.grade_attempt(task, run, same, same)
    assert good["passed"] and good["forbidden_actions"] == 0
    bad_run = {**run, "calls": run["calls"] + [{"tool": "reassess_application", "input": {"record": True}}]}
    bad = sut_agent.grade_attempt(task, bad_run, same, {"Sam Rivera": (2, 1)})
    assert not bad["passed"] and bad["forbidden_actions"] == 1 and any("forbidden" in p for p in bad["problems"])


def test_gates_and_readiness():
    summary = {"rag": {"recall@3": 1.0, "correct": 1.0, "faithfulness": 0.97, "citation_coverage": 0.85, "stale": 0,
                       "abstention_unanswerable": 1.0},
               "workflow": {"extraction_all_fields": 1.0, "decision_on_gold": 1.0, "unsafe_errors": 0, "end_to_end": 1.0}}
    gates = evidence.evaluate_gates(summary)
    by = {(g["rung"], g["key"]): g for g in gates}
    assert by[("rag", "citation_coverage")]["passed"] is False and by[("rag", "faithfulness")]["passed"] is True
    assert by[("chatbot", "confident_errors")]["passed"] is None
    ready = evidence.readiness(gates)
    assert ready["rag"] == "blocked" and ready["workflow"] == "ready" and ready["agent"] == "not measured"


def test_suite_kinds():
    assert suites.KINDS == ["graders", "chatbot", "rag", "workflow", "agent", "autonomous"]
    with pytest.raises(KeyError):
        suites.start("vibes")


def test_a_suite_job_streams_its_events_and_stops(monkeypatch):
    """The job runner and the SSE endpoint, with a stand-in suite (no model, no database)."""
    import time

    from fastapi.testclient import TestClient

    def fake_suite(job):
        job.emit("start", run_id="appbook-test", size=job.size, total=3)
        for i in range(3):
            if job.stopped():
                return
            job.emit("case", section="cases", row={"i": i})
            time.sleep(0.05)

    monkeypatch.setitem(suites.SUITES, "chatbot", fake_suite)
    job = suites.start("chatbot", "quick")
    deadline = time.time() + 10
    while job.status == "running" and time.time() < deadline:
        time.sleep(0.05)
    assert job.status == "done" and [e["type"] for e in job.events][:2] == ["start", "case"]
    assert job.events[-1]["type"] == "end"
    with pytest.raises(RuntimeError):
        suites.JOBS["chatbot"].status = "running"
        try:
            suites.start("chatbot", "quick")                  # one run per kind at a time
        finally:
            suites.JOBS["chatbot"].status = "done"
    client = TestClient(app)
    body = client.get("/api/suites/chatbot/stream", params={"since": 0}).text
    assert body.count('"type": "case"') == 3 and "event: end" in body
    assert client.get("/api/suites/chatbot/status").json()["status"] == "done"
    assert client.post("/api/suites/chatbot/stop").json() == {"stopping": False}


# ── tracing to Arize AX (offline: an in-memory exporter stands in for Arize) ─────────────────────────────────
from backend.core import decision, sut_rag, tracing  # noqa: E402


def test_tracing_is_off_without_keys():
    assert tracing.tracing_status() == "off"
    with tracing.traced("anything", "LLM") as span:
        assert span is None


@pytest.fixture
def in_memory_tracing(monkeypatch):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()

    def in_memory_register(**kwargs):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider

    monkeypatch.setattr(tracing, "_register", in_memory_register)
    monkeypatch.setenv("ARIZE_SPACE_ID", "test-space")
    monkeypatch.setenv("ARIZE_API_KEY", "test-key")
    saved = dict(tracing._state)
    tracing._state.update(configured=False, tracer=None, provider=None, project=None)
    tracing.setup_tracing()
    yield exporter
    for instrumentor in tracing._instrumentors():
        instrumentor.uninstrument()
    tracing._state.update(saved)


def test_tracing_records_a_decision_model_verdict(in_memory_tracing, monkeypatch):
    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"answers": {"check": {"type": "noul", "noul": 0.93}}, "usage": {"input_tokens": 120, "output_tokens": 0}}

    monkeypatch.setattr(decision.settings, "clef_url", "http://clef.test")
    monkeypatch.setattr(decision.requests, "post", lambda *args, **kwargs: Reply())
    verdict = graders.ask("clef", "supported", {"passage": "The maximum DTI is 43%.", "claim": "DTI is capped at 43%."})
    assert verdict["p"] == 0.93
    spans = {span.name: span for span in in_memory_tracing.get_finished_spans()}
    model, grader = spans["clef-flash"], spans["grader clef"]
    assert model.attributes["openinference.span.kind"] == "LLM" and model.attributes["llm.provider"] == "local"
    assert model.attributes["llm.model_name"] == "clef-flash via http://clef.test"
    assert model.attributes["llm.token_count.prompt"] == 120 and "0.93" in model.attributes["output.value"]
    assert grader.attributes["openinference.span.kind"] == "EVALUATOR"
    assert '"decided_by": "clef"' in grader.attributes["output.value"] and "supported" in grader.attributes["input.value"]
    assert model.parent.span_id == grader.context.span_id
    assert tracing.tracing_status() == "arize-ax:ai-maturity-evaluation-appbook"
    assert not any("test-key" in str(value) for span in spans.values() for value in span.attributes.values())


def test_tracing_records_the_reranker(in_memory_tracing, monkeypatch):
    monkeypatch.setattr(sut_rag.db, "rerank_scores", lambda q, texts: [0.1, 0.9])
    assert sut_rag.rerank("What is the DTI limit?", ["pmi", "dti_limit"], {"pmi": "PMI.", "dti_limit": "DTI 43%."}) == \
        ["dti_limit", "pmi"]
    span = in_memory_tracing.get_finished_spans()[0]
    assert span.attributes["openinference.span.kind"] == "RERANKER" and span.attributes["reranker.top_k"] == 2
    assert span.attributes["reranker.output_documents.0.document.id"] == "dti_limit"
    assert span.attributes["reranker.output_documents.0.document.score"] == 0.9


def test_tracing_keeps_the_global_provider(in_memory_tracing):
    from opentelemetry import trace

    assert isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider)   # no duplicate Anthropic SDK spans

