"""Offline contracts: routes, request schemas, the Data Explorer allowlist, the model switch, every metric with known
values, the grader analysis, the gates, and the generated data.

    python -m pytest tests/test_contracts.py -q

No model, no database, no download: the app is imported without starting its lifespan.
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Offline: an empty variable wins over ~/.ppa_workshop/keys.env, so importing the app never turns Arize AX tracing on.
os.environ["ARIZE_SPACE_ID"] = os.environ["ARIZE_API_KEY"] = ""

from pydantic import ValidationError  # noqa: E402

from backend.config import resolve_models  # noqa: E402
from backend.core import agents, datasets, evidence, graders, stats, suites  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers.data_explorer import allowed  # noqa: E402
from backend.schemas import SuiteStart, TryCheck  # noqa: E402


def test_routes():
    paths = app.openapi()["paths"]
    for path, method in [("/api/health", "get"), ("/api/runs", "get"), ("/api/runs/{run_id}", "get"),
                         ("/api/runs/{run_id}/results", "get"), ("/api/graders/try", "post"), ("/api/graders/policy", "get"),
                         ("/api/suites", "get"), ("/api/suites/{kind}/start", "post"), ("/api/suites/{kind}/stop", "post"),
                         ("/api/suites/{kind}/status", "get"), ("/api/suites/{kind}/stream", "get"), ("/api/suites/{kind}/last", "get"),
                         ("/api/data_explorer/tables", "get"), ("/api/data_explorer/tables/{table}/rows", "get")]:
        assert method in paths.get(path, {}), f"{method.upper()} {path} is missing"
    assert suites.KINDS == ["graders", "longmemeval", "factconsolidation", "operations"]


def test_request_schemas():
    assert SuiteStart().size == "quick"
    assert SuiteStart(size="full", per_type=2, abstention=0).per_type == 2
    for bad in ({"size": "huge"}, {"per_type": 0}, {"questions": 500}):
        with pytest.raises(ValidationError):
            SuiteStart(**bad)
    with pytest.raises(ValidationError):
        TryCheck(check="vibes", question="q", answer="a")
    assert TryCheck(check="uses_old_value", question="q", answer="a", old="Porto").old == "Porto"


def test_data_explorer_allowlist():
    assert allowed("MEMEVAL_RESULTS") and allowed("memapp_turns") and allowed("MEMEVAL_GATES")
    assert not allowed("CONVERSATION_MEMORY") and not allowed("scratch_entity") and not allowed("memeval_results; DROP TABLE x")
    assert not allowed("USER_TABLES") and not allowed("")


def test_models_resolve_like_the_notebook():
    both = resolve_models({"OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"})
    assert (both["provider"], both["model"], both["cheap_model"], both["embed_model"], both["judge_provider"], both["judge_model"]) == \
        ("openai", "gpt-6.1-sol", "gpt-6-luna", "text-embedding-3-small", "anthropic", "claude-sonnet-5-5")
    openai_only = resolve_models({"OPENAI_API_KEY": "o"})
    assert (openai_only["judge_provider"], openai_only["judge_model"]) == ("openai", "gpt-6.1-sol")
    open_models = resolve_models({})
    assert (open_models["provider"], open_models["model"], open_models["embed_model"], open_models["judge_model"]) == \
        ("ollama", "gemma4-32k", "nomic-embed-text", "gemma4-32k")
    assert resolve_models({"OPENAI_API_KEY": "o", "MEMO_PROVIDER": "ollama", "MEMO_OPEN_MODEL": "gemma4:12b"})["model"] == "gemma4-12b-32k"


def test_metrics_with_known_values():
    assert stats.contains_answer("You graduated in Business Administration.", ["business administration"])
    assert not stats.contains_answer("You studied economics.", ["business administration"])
    r = stats.retrieval_metrics(["s3", "s1", "s3", "s9"], ["s1", "s7"], k=3)
    assert r["recall_any"] == 1.0 and r["recall_all"] == 0.0 and math.isclose(r["ndcg"], (1 / math.log2(3)) / (1 + 1 / math.log2(3)))
    p, low, high = stats.wilson(25, 36)
    assert math.isclose(p, 25 / 36) and 0.53 < low < 0.54 and 0.81 < high < 0.83
    p, low, high = stats.wilson(36, 36)
    assert p == 1.0 and high == 1.0 and low < 1.0            # never rounded past p
    assert stats.mcnemar([1, 1, 0, 1, 0, 1], [1, 0, 0, 0, 0, 1]) == {"only_a": 2, "only_b": 0, "p": 0.5}
    assert math.isclose(stats.kappa([1, 1, 0, 0], [1, 0, 0, 0]), 0.5)
    assert math.isclose(stats.ece([0.9, 0.8, 0.2], [1, 0, 0]), (0.1 + 0.8 + 0.2) / 3)
    assert math.isclose(stats.brier([1.0, 0.0], [1, 0]), 0.0)
    assert stats.pctl([1, 2, 3, 4], 50) == 2.5 and stats.pctl([], 50) is None


def test_validation_items_are_labelled_by_construction():
    items = graders.validation_items()
    assert len(items) == 24 * 5 and len(graders.validation_items(limit_facts=8)) == 40
    update = next(i for i in items if i["item_id"] == "v00-update")
    assert update["label"] == {"states_fact": 1, "uses_old_value": 0, "abstains": 0} and "Porto" in update["answer"]
    assert next(i for i in items if i["item_id"] == "v03-superseded")["label"]["uses_old_value"] == 1
    assert len(graders.DEV_FACTS) == 12 and graders.DEV_FACTS <= set(range(24))


def _rows(grader, p_of, n_facts=24):
    rows = []
    for item in graders.validation_items(limit_facts=n_facts):
        for check, label in item["label"].items():
            p = p_of(check, label, item["variant"])
            rows.append({"item_id": item["item_id"], "check_type": check, "grader": grader, "label": label, "verdict": p >= 0.5,
                         "probability": float(p), "latency_ms": 100.0 if grader != "judge" else 2000.0, "cost_usd": 0.0,
                         "fact_index": item["fact_index"], "variant": item["variant"]})
    return rows


def test_grader_analysis_picks_a_threshold_and_a_cascade():
    perfect = _rows("judge", lambda c, l, v: float(l))
    shy = _rows("clef", lambda c, l, v: (0.35 if l else 0.05) if c == "uses_old_value" else (0.9 if l else 0.1))
    analysis = graders.analyse(perfect + shy)
    old = next(s for s in analysis["scores"] if s["check"] == "uses_old_value" and s["grader"] == "clef")
    assert old["kappa"] < 0.5                                        # at 0.5 it misses every positive
    choice = next(c for c in analysis["choices"] if c["check"] == "uses_old_value")
    # chosen on dev as the cheapest grader within 0.05 κ of the best; its positives (P = 0.35) fall inside the band and
    # go to the judge, so the cascade is perfect while a fifth of its verdicts are escalated
    assert choice["grader"] == "clef" and choice["threshold"] < 0.35 and choice["uses"] == "clef"
    assert choice["band"] == [0.2, 0.8] and choice["kappa_cascade"] == 1.0 and math.isclose(choice["escalated"], 0.2)
    assert {v["variant"] for v in analysis["variants"]} == {"paraphrase", "update", "superseded", "wrong", "abstain"}


def test_escalation_band_is_anchored_on_the_threshold():
    assert stats.escalation_band(0.5) == (0.2, 0.8)
    assert stats.escalation_band(0.25) == (0.2, 0.8)      # the 0.33 and 0.77 misfires of the saved run fall inside it
    assert stats.escalation_band(0.9) == (0.2, 0.95)      # a model that needs 0.9 to say yes is not sure at 0.85
    assert stats.escalation_band(0.1) == (0.05, 0.8)


def test_grade_sends_in_band_probabilities_to_the_judge(monkeypatch):
    probabilities = {"a": 0.33, "b": 0.77, "c": 0.9, "d": 0.1, "e": 0.2, "f": 0.8}
    monkeypatch.setattr(graders, "policy", lambda refresh=False: {
        "uses_old_value": {"grader": "clef", "threshold": 0.25, "band": [0.2, 0.8], "source": "test"}})
    monkeypatch.setattr(graders, "dm_check", lambda model, question, answer, fact=None, old=None, checks=():
                        ({"uses_old_value": probabilities[answer]}, 0.1, {"cost_usd": 0.0}))
    monkeypatch.setattr(graders, "judge_checks", lambda question, answer, fact, old:
                        ({"uses_old_value": False, "reason": "names only the new value"}, {"seconds": 1.0, "cost_usd": 0.001}))
    out = graders.grade("uses_old_value", [{"question": "q", "answer": k, "old": "Omar"} for k in probabilities], workers=1)
    by = dict(zip(probabilities, out))
    assert by["a"]["grader"] == by["b"]["grader"] == "clef→judge" and not by["a"]["verdict"] and not by["b"]["verdict"]
    assert by["a"]["probability"] == 0.33                  # the decision model's probability is kept as evidence
    assert by["c"] == {**by["c"], "grader": "clef", "verdict": True} and by["d"]["grader"] == "clef" and not by["d"]["verdict"]
    assert by["e"]["grader"] == by["f"]["grader"] == "clef"   # the band is open: 0.2 and 0.8 themselves are trusted
    assert graders.escalation_count("uses_old_value", out) == {"check": "uses_old_value", "grader": "clef", "verdicts": 6, "escalated": 2}


def test_memorizz_pin_and_entity_memory_on():
    import importlib.metadata
    import inspect
    import re

    root = Path(__file__).resolve().parents[1]
    assert "memorizz[oracle]>=0.17.8,<0.18" in (root / "requirements.txt").read_text()
    assert "(0, 17, 8)" in (root / "run.sh").read_text()
    assert tuple(int(x) for x in re.findall(r"\d+", importlib.metadata.version("memorizz"))[:3]) >= (0, 17, 8)
    # 0.17.8 stores entities of any size, so FactConsolidation runs MemoRizz as designed: entity memory on
    assert inspect.signature(agents.Team).parameters["memorizz_entity_memory"].default is True
    assert "memorizz_entity_memory=False" not in inspect.getsource(suites.suite_factconsolidation)


class _FakeTeam:
    def __init__(self):
        self.calls = []

    def close(self):
        self.calls.append("close")
        return {"memory_id": "memapp-x", "agent_id": "agent-x", "agent": "Memo appbook x", "users": ["ada"]}

    def cleanup(self):
        self.calls.append("cleanup")
        return {"memapp_turns": 1}


def _run_with(monkeypatch, cleanup_flag):
    team = _FakeTeam()
    monkeypatch.setattr(suites.settings, "cleanup", cleanup_flag)
    monkeypatch.setitem(suites.SUITES, "operations", lambda job: team)
    job = suites.Job("operations", "quick", {})
    suites._run(job)
    return team, [e["type"] for e in job.events]


def test_a_run_keeps_what_it_wrote_by_default(monkeypatch):
    import os
    from backend.config import Settings

    assert os.environ.get("MEMO_CLEANUP") != "1" and Settings.cleanup is False
    team, types = _run_with(monkeypatch, False)
    assert team.calls == ["close"] and "kept" in types and "cleanup" not in types and types[-1] == "end"
    team, types = _run_with(monkeypatch, True)                     # MEMO_CLEANUP=1 opts in to deleting
    assert team.calls == ["cleanup"] and "cleanup" in types and "kept" not in types
    notebook = json.loads((Path(__file__).resolve().parents[2] / "notebook" / "agent_memory_evaluation.ipynb").read_text())
    final = next("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code" and "MEMO_CLEANUP" in "".join(c["source"]))
    tree = ast.parse(final)
    guarded = {id(n) for node in ast.walk(tree) if isinstance(node, ast.If) and "CLEANUP" in ast.unparse(node.test)
               for n in ast.walk(node)}
    deletes = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and "delete_scope" in ast.unparse(n.func)]
    assert deletes and all(id(n) in guarded for n in deletes)   # the notebook deletes MemoRizz rows only when asked
    assert "MEMO_KEEP_DATA" not in final


def test_gates_and_readiness():
    summary = {"longmemeval": {"systems": {"scratch": {"accuracy": {"p": 0.97}, "p95_s": 7.2},
                                           "memorizz": {"accuracy": {"p": 0.6}, "p95_s": 14.9}}},
               "operations": {"systems": {"scratch": {"leaks": 0, "forgetting_every_copy": 1.0}}}}
    gates = evidence.evaluate_gates(summary)
    assert len(gates) == 2 * len(evidence.GATES)
    ready = evidence.readiness(gates)
    assert ready == {"scratch": "ready", "memorizz": "blocked"}
    assert evidence.readiness(evidence.evaluate_gates({})) == {"scratch": "not measured", "memorizz": "not measured"}
    notebook = json.loads((Path(__file__).resolve().parents[2] / "notebook" / "agent_memory_evaluation.ipynb").read_text())
    cell = next("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code" and "GATES = [" in "".join(c["source"]))
    assert [g for g, *_ in evidence.GATES] == re.findall(r'^    \("([^"]+)", "[<>]=",', cell, re.M)   # the notebook's gates, in order


def test_generated_data_is_deterministic():
    assert datasets.scenario("7-x") == datasets.scenario("7-x") and datasets.scenario("7-x") != datasets.scenario("7-y")
    s = datasets.scenario("7-x")
    assert len(s["turns"]) == 10 and sum(k == "update" for k, _ in s["turns"]) == 3 and s["canary_ben"].startswith("ZEPHYR-")
    facts = [(i, f"The capital of Country{i} is City{i}.") for i in range(455)]
    messages = datasets.fc_messages(facts)
    assert len(messages) == 57 and max(len(m) for m in messages) < 600   # under MemoRizz's 600-character recall cap


def test_history_of_finds_the_overwritten_value():
    facts = [(0, "The capital of Romania is Bucharest."), (5, "The capital of Romania is Rajanpur."), (7, "Rajanpur is in Asia.")]
    number, prefix, stale = datasets.history_of(facts, ["Rajanpur"])
    assert number == 5 and prefix == "The capital of Romania is " and stale == ["Bucharest"]


def test_scratch_helpers():
    assert agents.text_terms("How many days passed between my visit to MoMA?") == "{days} ACCUM {passed} ACCUM {between} ACCUM {visit} ACCUM {moma}"
    assert agents.text_terms("what is it?") is None
    rounds = agents.rounds_of([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b", "has_answer": True},
                               {"role": "user", "content": "c"}])
    assert rounds == [{"user": "a", "assistant": "b", "has_answer": True}, {"user": "c", "assistant": "", "has_answer": False}]
    assert agents.fingerprint("abc") == __import__("hashlib").sha256(b'"abc"').hexdigest()


# ── tracing to Arize AX ────────────────────────────────────────────────────────────────────────────────────────
from backend.core import decision, tracing  # noqa: E402


def test_tracing_is_off_without_keys():
    assert os.environ["ARIZE_SPACE_ID"] == "" and tracing.tracing_status() == "off"
    with tracing.traced("anything", "CHAIN") as span:
        assert span is None


@pytest.fixture
def in_memory_tracing(monkeypatch):
    """Tracing on, with an in-memory exporter in place of Arize's register(): nothing leaves the process."""
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()

    def fake_register(**kwargs):
        assert kwargs["set_global_tracer_provider"] is False and kwargs["project_name"] == "agent-memory-evaluation-appbook"
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider

    monkeypatch.setenv("ARIZE_SPACE_ID", "space-for-tests")
    monkeypatch.setenv("ARIZE_API_KEY", "key-for-tests")
    monkeypatch.delenv("ARIZE_PROJECT_NAME", raising=False)
    monkeypatch.setattr(tracing, "_load_keys", lambda: None)
    saved = dict(tracing._state)
    tracing._state.update(tracer=None, provider=None, project=None, done=False)
    assert tracing.setup_tracing(register=fake_register) == "arize-ax:agent-memory-evaluation-appbook"
    yield exporter
    OpenAIInstrumentor().uninstrument()
    AnthropicInstrumentor().uninstrument()
    tracing._state.update(saved)


def test_a_systemone_request_is_an_llm_span(in_memory_tracing, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"answers": {"states_fact": {"noul": 0.91}}, "usage": {"input_tokens": 120, "output_tokens": 3}}

    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-for-tests")
    monkeypatch.setattr(decision.requests, "post", lambda *args, **kwargs: FakeResponse())
    answers, _, usage = decision.systemone("jev", {"question": "Where does Ada live?", "answer_to_check": "Lisbon."},
                                           {"states_fact": {"type": "noul", "instructions": "Does it say Lisbon?"}})
    assert answers["states_fact"]["noul"] == 0.91 and usage["input_tokens"] == 120
    (span,) = in_memory_tracing.get_finished_spans()
    a = span.attributes
    assert span.name == "systemone jev-latest" and a["openinference.span.kind"] == "LLM"
    assert a["llm.model_name"] == "jev-latest" and a["llm.provider"] == "typesafe" and a["llm.token_count.prompt"] == 120
    assert "Lisbon" in a["input.value"] and "0.91" in a["output.value"] and a["input.mime_type"] == "application/json"
    assert "typesafe-for-tests" not in json.dumps(dict(a)) and "key-for-tests" not in json.dumps(dict(a))


def test_a_policy_verdict_is_an_evaluator_span_that_says_who_decided(in_memory_tracing, monkeypatch):
    monkeypatch.setattr(graders, "policy", lambda refresh=False: {
        "uses_old_value": {"grader": "clef", "threshold": 0.25, "band": [0.2, 0.8], "source": "test"}})
    monkeypatch.setattr(graders, "dm_check", lambda *args, **kwargs: ({"uses_old_value": 0.48}, 0.1, {"cost_usd": 0.0}))
    monkeypatch.setattr(graders.llm, "judge_json", lambda *args, **kwargs: (
        {"states_fact": True, "uses_old_value": False, "abstains": False, "reason": "new value only"}, {"seconds": 1.0, "cost_usd": 0.0}))
    (verdict,) = graders.grade("uses_old_value", [{"question": "Who is my manager?", "answer": "Omar.", "old": "Marco"}], workers=1)
    assert verdict["grader"] == "clef→judge" and verdict["verdict"] is False
    spans = {s.name: s for s in in_memory_tracing.get_finished_spans()}
    assert spans["grade uses_old_value"].attributes["openinference.span.kind"] == "EVALUATOR"
    assert '"decided_by": "clef→judge"' in spans["grade uses_old_value"].attributes["output.value"]
    assert spans["judge checks"].attributes["openinference.span.kind"] == "EVALUATOR"
    assert spans["judge checks"].parent.span_id == spans["grade uses_old_value"].context.span_id


def test_tracing_never_replaces_the_global_tracer_provider(in_memory_tracing):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    # still the default proxy: the Anthropic SDK's own spans (global provider) are dropped, not duplicated
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)
    assert type(trace.get_tracer_provider()).__name__ == "ProxyTracerProvider"
