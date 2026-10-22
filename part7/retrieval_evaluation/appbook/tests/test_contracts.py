"""Offline contracts: routes, request schemas, the Data Explorer allowlist, read-only SQL, configuration parsing, the
lexical query builder, fusion and graph arithmetic, and every metric with known values.

    python -m pytest tests/test_contracts.py -q

No model, no database: the app is imported without starting its lifespan.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Offline: no Arize keys from the environment or ~/.ppa_workshop/keys.env, so importing the app leaves tracing off.
for _name in ("ARIZE_SPACE_ID", "ARIZE_API_KEY", "ARIZE_PROJECT_NAME"):
    os.environ.pop(_name, None)
os.environ["HOME"] = tempfile.mkdtemp(prefix="beir7app-test-home-")

from pydantic import ValidationError  # noqa: E402

from backend.core import db, evidence, metrics, models, playground, search, text, tracing  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers.data_explorer import allowed  # noqa: E402
from backend.schemas import ExploreRequest, ScoreRequest  # noqa: E402


def test_routes():
    paths = app.openapi()["paths"]
    for path, method in [("/api/health", "get"), ("/api/runs", "get"), ("/api/inventory", "get"),
                         ("/api/runs/{run_id}/configs", "get"), ("/api/leaderboard", "get"),
                         ("/api/explore/queries", "get"), ("/api/explore/run", "post"),
                         ("/api/playground/{dataset}/status", "get"), ("/api/playground/{dataset}/prepare", "post"),
                         ("/api/playground/{dataset}/stream", "get"), ("/api/playground/score", "post"),
                         ("/api/playground/{dataset}/reach", "get"), ("/api/guide/diagnostics/{dataset}", "get"),
                         ("/api/guide/evidence", "get"), ("/api/data_explorer/tables", "get"),
                         ("/api/data_explorer/tables/{table}/rows", "get")]:
        assert method in paths.get(path, {}), f"{method.upper()} {path} is missing"


def test_no_route_writes():
    """Every POST only reads or computes: there is no route that creates, changes or deletes data."""
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            assert method in ("get", "post"), (path, method)


def test_request_schemas():
    assert ExploreRequest(dataset="fiqa", query_id="8").query_id == "8"
    with pytest.raises(ValidationError):
        ExploreRequest(dataset="msmarco", text="x")
    with pytest.raises(ValidationError):
        ExploreRequest(dataset="fiqa", text="x" * 5000)
    assert ScoreRequest(dataset="scifact", kind="graph").decay == 0.005
    with pytest.raises(ValidationError):
        ScoreRequest(dataset="fiqa", kind="weighted", alpha=1.5)
    with pytest.raises(ValidationError):
        ScoreRequest(dataset="fiqa", kind="graph", m=50)
    with pytest.raises(ValidationError):
        ScoreRequest(dataset="fiqa", kind="bm25")


def test_data_explorer_allowlist():
    assert allowed("BEIR7_RESULTS") and allowed("beir7_fiqa_docs") and allowed("BEIR7_COSTS")
    assert not allowed("FFEVAL_RESULTS") and not allowed("USER_TABLES") and not allowed("")
    assert not allowed("beir7_results; DROP TABLE x") and not allowed("DR$BEIR7_FIQA_DOCS_TXT$I")


def test_sql_is_read_only():
    for statement in ("DELETE FROM beir7_results", "UPDATE beir7_runs SET minutes = 0", "DROP TABLE beir7_costs",
                      "INSERT INTO beir7_runs VALUES (1)", "CREATE TABLE x (a NUMBER)"):
        with pytest.raises(ValueError):
            db.sql(statement)
        with pytest.raises(ValueError):
            db.rows(statement)
        with pytest.raises(ValueError):
            db.timed(statement)


def test_worked_example_matches_the_notebook():
    """The notebook's §1.4: d1 (grade 2) at rank 2, d4 at rank 4, d7 missing."""
    qrels = {"d1": 2, "d4": 1, "d7": 1}
    m = metrics.score_ranking(["d3", "d1", "d5", "d4", "d9", "d2", "d8", "d6", "d10", "d11"], qrels)
    assert round(m["ndcg10"], 3) == 0.541 and m["p1"] == 0 and m["p5"] == 0.4 and m["p10"] == 0.2
    assert round(m["r10"], 3) == 0.667 and m["mrr10"] == 0.5 and round(m["map100"], 3) == 0.333 and m["hit10"] == 1
    better = metrics.score_ranking(["d1", "d3", "d5", "d4", "d9", "d2", "d8", "d6", "d10", "d11"], qrels)
    assert round(better["ndcg10"], 3) == 0.776 and better["mrr10"] == 1 and better["map100"] == 0.5
    assert metrics.score_ranking(["x"], {})["ndcg10"] is None


def test_bootstrap_and_paired_test_match_the_notebook():
    """The notebook's §1.5 demonstration, with its seed."""
    import numpy as np

    rng = np.random.default_rng(7)
    baseline = rng.uniform(0, 1, 300)
    improved = np.clip(baseline + rng.normal(0.03, 0.05, 300), 0, 1)
    lo, hi = metrics.bootstrap_ci(baseline)
    assert (round(lo, 3), round(hi, 3)) == (0.471, 0.537)
    test = metrics.paired_test(improved, baseline)
    assert round(test["mean_diff"], 3) == 0.023 and round(test["p_value"], 4) == 0.0001


def test_holm():
    assert metrics.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert metrics.holm([0.5]) == [0.5]


def test_parse_stored_configurations():
    assert search.parse_config("lexical", "ACCUM · no stem · rarest 10") == {"op": "ACCUM", "stem": False, "keep": 10}
    assert search.parse_config("lexical", "ACCUM · stem · all terms") == {"op": "ACCUM", "stem": True, "keep": None}
    assert search.parse_config("hybrid", "weighted · alpha=0.8 · depth=50") == {"method": "weighted", "alpha": 0.8, "depth": 50}
    assert search.parse_config("hybrid", "RRF · k=10 · w=0.7 · depth=100") == {"method": "RRF", "k": 10, "w": 0.7, "depth": 100}
    assert search.parse_config("graph", "M=10 · seeds=5 · decay=0.0025") == {"m": 10, "seeds": 5, "decay": 0.0025}
    assert search.parse_config("rerank", "graph + cross-encoder top 10") == {"first_stage": "graph", "depth": 10}
    assert search.parse_config("vector", "bge-small-en-v1.5 · exact")["exact"]


def test_text_query_escapes_and_selects(monkeypatch):
    monkeypatch.setattr(text, "_STOPWORDS", {"the", "a", "is", "to", "of"})
    monkeypatch.setitem(text._DF, "fiqa", Counter({"index": 900, "fund": 800, "betterment": 3, "robo": 5, "near": 40}))
    q = "Is the robo-advisor near Betterment, or an index fund?"
    assert text.content_words(q) == ["robo", "advisor", "near", "betterment", "or", "an", "index", "fund"]
    accum = text.text_query("fiqa", q)
    assert accum.startswith("{robo} ACCUM {advisor} ACCUM {near}") and "{or}" in accum
    stemmed = text.text_query("fiqa", q, op="OR", stem=True)
    assert "$robo" in stemmed and "{near}" in stemmed and "{or}" in stemmed     # operator words are never stemmed
    assert text.text_query("fiqa", q, keep=2) == "{advisor} ACCUM {an}"      # unseen words have frequency 0
    assert text.template("").endswith('<score datatype="FLOAT"/></query>') and "{zzzzzz}" in text.template("")


def test_fusion_and_graph_arithmetic():
    lex = [("a", 9.0), ("b", 5.0), ("c", 1.0)]
    vec = [("b", 0.9), ("d", 0.8), ("a", 0.7)]
    assert playground.fuse_rrf(lex, vec, k=60, w=0.5, depth=3)[:2] == ["b", "a"]   # ranks 2 + 1 beat ranks 1 + 3
    assert playground.fuse_rrf(lex, vec, k=1, w=1.0, depth=3) == ["b", "d", "a", "c"]  # w = 1 is vector order
    weighted = playground.fuse_weighted(lex, vec, alpha=1.0, depth=3)
    assert weighted[:3] == ["b", "d", "a"]                                    # α = 1 is vector order
    assert playground.fuse_weighted(lex, vec, alpha=0.0, depth=3)[:3] == ["a", "b", "c"]
    edges = {"b": [("z", 0.9, 1), ("a", 0.8, 2)], "d": [("z", 0.95, 1)]}
    assert playground.expand(vec, edges, m=2, seeds=2, decay=0.0, exclude=None)[:3] == ["b", "d", "a"]
    expanded = playground.expand(vec, edges, m=2, seeds=2, decay=1.0, exclude=None)
    assert expanded[0] == "z"                                                 # vouched for by both seeds
    assert "z" not in playground.expand(vec, edges, m=2, seeds=2, decay=1.0, exclude="z")


def test_query_order_follows_the_notebook():
    ids = ["q3", "q1", "q2"]
    assert evidence.query_order("fiqa", ids, 7) == ["q1", "q2", "q3"]
    expected = sorted(ids, key=lambda q: hashlib.sha1(f"7:{q}".encode()).hexdigest())
    assert evidence.query_order("arguana", ids, 7) == expected


def test_frontend_files_and_wording():
    root = Path(__file__).resolve().parents[1]
    for name in ("index.html", "app.js", "pages.js", "styles.css", "bench.css"):
        assert (root / "frontend" / name).exists(), name
    banned = ("course", "lesson", "workshop", "webinar", "classroom", "derived", "adapted", "duckdb", "sqlite")
    for path in [*(root / "frontend").glob("*.js"), *(root / "frontend").glob("*.css"), root / "frontend" / "index.html",
                 root / "README.md",
                 *(root / "backend").rglob("*.py")]:
        body = path.read_text().lower().replace(".ppa_workshop", "")      # the keys folder's name is a path
        for word in banned:
            assert word not in body, f"{word!r} in {path.name}"


# ── tracing to Arize AX ──────────────────────────────────────────────────────────────────────────────────────────
def test_tracing_is_off_by_default():
    assert tracing.tracing_status() == "off"
    with tracing.traced("anything", "CHAIN") as span:
        assert span is None
    with tracing.traced_request("explore · test") as chain:
        assert chain is None
        with tracing.traced("lexical search", "RETRIEVER") as span:
            assert span is None


@pytest.fixture
def in_memory_tracing(monkeypatch):
    """Tracing on, with register() replaced by an in-memory provider: nothing leaves the machine."""
    import arize.otel
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    calls = []

    def fake_register(**kwargs):
        calls.append(kwargs)
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider

    monkeypatch.setattr(arize.otel, "register", fake_register)
    monkeypatch.setenv("ARIZE_SPACE_ID", "test-space")
    monkeypatch.setenv("ARIZE_API_KEY", "test-key")
    monkeypatch.setitem(tracing._state, "ready", False)
    monkeypatch.setitem(tracing._state, "tracer", None)
    assert tracing.setup_tracing() == "arize-ax:beir-retrieval-benchmark-appbook"
    assert calls[0]["set_global_tracer_provider"] is False and calls[0]["project_name"] == "beir-retrieval-benchmark-appbook"
    yield exporter


def test_traced_explorer_path_spans(in_memory_tracing, monkeypatch):
    exporter = in_memory_tracing
    monkeypatch.setattr(text, "_STOPWORDS", {"the", "of"})
    monkeypatch.setitem(text._DF, "fiqa", Counter({"robo": 3, "advisor": 9, "fees": 40}))
    monkeypatch.setattr(db, "timed", lambda statement, **binds: ([("d1", 9.5), ("d2", 3.0)], 1.5))
    monkeypatch.setattr(search, "bodies", lambda ds, ids: {d: f"text of {d} " * 40 for d in ids})
    monkeypatch.setattr(models, "rerank_scores", lambda query, texts: ([0.1, 0.9], 2.0))
    cfg = {"op": "ACCUM", "stem": False, "keep": None}

    search.lexical("fiqa", "robo advisor fees", cfg, qid="q1")            # outside a request: the playground's case
    assert exporter.get_finished_spans() == ()

    with tracing.traced_request("explore · FiQA-2018", **{"input.value": "robo advisor fees"}):
        ranked, _ = search.lexical("fiqa", "robo advisor fees", cfg, qid="q1")
        reranked, _ = search.rerank("fiqa", "robo advisor fees", ranked, 2)
    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert set(spans) == {"explore · FiQA-2018", "lexical search", "rerank"}
    chain, retriever, reranker = spans["explore · FiQA-2018"], spans["lexical search"], spans["rerank"]
    assert chain.attributes["openinference.span.kind"] == "CHAIN"
    assert retriever.attributes["openinference.span.kind"] == "RETRIEVER"
    assert retriever.parent.span_id == chain.context.span_id
    assert retriever.attributes["input.value"] == "robo advisor fees"
    assert retriever.attributes["retrieval.documents.0.document.id"] == "d1"
    assert retriever.attributes["retrieval.documents.0.document.score"] == 9.5
    assert len(retriever.attributes["retrieval.documents.0.document.content"]) == 300
    assert reranker.attributes["openinference.span.kind"] == "RERANKER"
    assert reranker.attributes["reranker.model_name"] == "Xenova/ms-marco-MiniLM-L-6-v2"
    assert reranker.attributes["reranker.top_k"] == 2
    assert reranker.attributes["reranker.output_documents.0.document.id"] == "d2"
    assert [d for d, _ in reranked] == ["d2", "d1"]
    assert not any("key" in k.lower() or "password" in k.lower() for s in spans.values() for k in s.attributes)


def test_global_tracer_provider_stays_the_default_proxy(in_memory_tracing):
    from opentelemetry import trace

    assert isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider)
