"""Offline contract tests for the AI Maturity Ladder appbook (Acme Home Loans).

No API key, model download or database is needed: the app is imported without its
lifespan (no Oracle bootstrap, no embedding or Clef warm-up), and only pure functions
and routes that touch neither Oracle nor a model are exercised. Live behaviour —
Claude, Oracle AI Database, Clef-Flash and the Agent SDK — is covered by check_live.py.

    cd appbook && python -m pytest tests/test_contracts.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

APPBOOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APPBOOK))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from backend.config import DEFAULT_PORT, settings  # noqa: E402
from backend.core import policy, sandbox  # noqa: E402
from backend.core import underwriting as uw  # noqa: E402
from backend.core.activity import operations_for  # noqa: E402
from backend.core.anthropic_client import OUTPUT_CONFIG  # noqa: E402
from backend.core.automations import command_problem  # noqa: E402
from backend.core.retrieval import sql_for, text_query  # noqa: E402
from backend.core.sessions import _json  # noqa: E402
from backend.main import app  # noqa: E402
from backend.schemas import RagRequest, SpaceRequest, WorkflowBatchRequest  # noqa: E402

# The rules in force after both bulletins (DTI 43%, credit 660), merged the way current_policy() merges them.
RULES = {}
for doc in policy.POLICY_DOCS:
    RULES.update(doc["rules"] or {})
for bulletin in policy.BULLETINS.values():
    RULES.update(bulletin["rules"])

ALL_DOCS = list(uw.REQUIRED_DOCUMENTS)
SAM = {"applicant": "Sam Rivera", "gross_monthly_income": 12500, "monthly_debts": 1850, "loan_amount": 440000,
       "property_value": 550000, "property_use": "primary", "credit_score": 715, "employment_months": 36,
       "liquid_reserves": 30000, "documents_provided": ALL_DOCS}
MAYA = {"applicant": "Maya Patel", "gross_monthly_income": 9200, "monthly_debts": 450, "loan_amount": 336000,
        "property_value": 420000, "property_use": "primary", "credit_score": 752, "employment_months": 72,
        "liquid_reserves": 40000, "documents_provided": ALL_DOCS}


def answers(choice="approve", confidence=0.95, failing=()):
    out = {"decision": {"choice": choice, "confidence": confidence,
                        "probabilities": {"approve": confidence if choice == "approve" else 1 - confidence,
                                          "decline": confidence if choice == "decline" else 1 - confidence}}}
    out.update({field: {"noul": 0.1 if field in failing else 0.95} for field in uw.CRITERIA})
    return out


@pytest.fixture(scope="module")
def client():
    return TestClient(app)          # no `with`: the lifespan (Oracle bootstrap, warm-up, scheduler) does not run


# ── configuration and serving ────────────────────────────────────────────────────
def test_model_effort_and_port():
    assert settings.model == "claude-haiku-5-5" or settings.model.startswith("claude-")
    assert OUTPUT_CONFIG == {"effort": settings.effort}
    assert settings.max_tokens >= 2048          # Haiku 5.5 thinks first; room for thinking and the answer
    assert DEFAULT_PORT == 8700 and 'PORT="${PORT:-8700}"' in (APPBOOK / "run.sh").read_text()


def test_bundled_agent_cli_is_preferred():
    assert settings.claude_cli_path and Path(settings.claude_cli_path).parent.name == "_bundled"


def test_frontend_loads_every_page_module_in_order(client):
    page = client.get("/")
    assert page.status_code == 200
    scripts = ["/app.js", "/rag.js", "/hnsw.js", "/workflow.js", "/agent.js", "/builder.js"]
    positions = [page.text.index(f'src="{s}"') for s in scripts]
    assert positions == sorted(positions)
    for path in scripts + ["/styles.css"]:
        assert client.get(path).status_code == 200, path


def test_cross_origin_requests_are_not_allowed(client):
    """The autonomous agent runs code, so no other site may call the API from a browser."""
    preflight = client.options("/api/builder/chat", headers={
        "Origin": "https://example.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in {k.lower() for k in preflight.headers}


def test_workflow_samples_need_no_database(client):
    samples = client.get("/api/workflow/samples").json()["samples"]
    assert [s["id"] for s in samples] == list(uw.SAMPLE_APPLICATIONS)
    assert all("Subject:" in s["email"] for s in samples)


# ── policy memory ────────────────────────────────────────────────────────────────
def test_policy_seed_and_bulletins():
    assert len(policy.POLICY_DOCS) == 17 and len({d["doc_id"] for d in policy.POLICY_DOCS}) == 17
    assert set(uw.DECISION_SECTIONS) <= set(policy.SEED_BY_ID)
    dti, credit = policy.BULLETINS["dti_43"], policy.BULLETINS["credit_660"]
    assert "43%" in dti["content"] and "41%" not in dti["content"] and dti["rules"] == {"max_dti": 0.43}
    assert "660" in credit["content"] and "640" not in credit["content"]


def test_legacy_tables_are_not_app_tables():
    assert {"policy_docs", "loan_decisions", "agent_session_entries", "agent_session_summaries"} <= set(policy.APP_TABLES)
    assert not set(policy.LEGACY_OBJECTS) & set(policy.APP_TABLES)


# ── retrieval SQL ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("technique,needle", [
    ("vector", "VECTOR_DISTANCE"), ("keyword", "CONTAINS"), ("hybrid", "VECTOR_DISTANCE"), ("graph", "GRAPH_TABLE"),
])
def test_sql_for_each_technique(technique, needle):
    sql = sql_for(technique, k=4)
    assert needle in sql and "{k}" not in sql and "FETCH" in sql.upper()


def test_hybrid_sql_fuses_both_lists():
    sql = sql_for("hybrid")
    assert "VECTOR_DISTANCE" in sql and "CONTAINS" in sql


@pytest.mark.parametrize("mode", ["pre", "in", "post"])
def test_filtered_sql_names_its_filter_mode(mode):
    sql = sql_for("filtered", k=3, category="compliance", mode=mode, accuracy=80)
    assert "'compliance'" in sql and "vector_index_transform" in sql


def test_text_query_drops_stopwords_and_escapes_terms():
    query, terms = text_query("Do I need mortgage insurance with a small down payment?")
    assert terms == ["mortgage", "insurance", "small", "down", "payment"]
    assert query == " ACCUM ".join("{%s}" % t for t in terms)


# ── underwriting: measure, gate, tree ───────────────────────────────────────────
def test_measure_matches_the_written_policy():
    ratios = uw.measure(SAM, RULES)
    assert ratios["monthly_payment_piti"] == pytest.approx(3469, abs=1)
    assert ratios["dti"] == pytest.approx(0.4255, abs=0.0005)
    assert ratios["ltv"] == 0.8


def test_gate_refers_borderline_dti_even_when_clef_approves():
    ratios = uw.measure(SAM, RULES)
    outcome, why = uw.gate(answers("approve", 0.85), SAM, ratios, RULES)
    assert outcome == "refer" and any("DTI" in w for w in why)


def test_gate_passes_a_clean_application_through():
    ratios = uw.measure(MAYA, RULES)
    assert uw.gate(answers("approve", 0.95), MAYA, ratios, RULES) == ("approve", [])


def test_gate_refers_low_confidence():
    ratios = uw.measure(MAYA, RULES)
    outcome, why = uw.gate(answers("approve", 0.70), MAYA, ratios, RULES)
    assert outcome == "refer" and "confidence" in why[0]


def test_decision_tree_records_the_path_taken():
    ratios = uw.measure(SAM, RULES)
    tree = uw.decision_tree(answers("approve", 0.85), SAM, ratios, RULES, "refer")
    assert [c["id"] for c in tree["criteria"]] == list(uw.CRITERIA)
    assert [g["id"] for g in tree["gates"]] == ["confidence", "dti_margin", "ltv_margin"]
    assert tree["model"]["choice"] == "approve" and tree["outcome"] == "refer" and not tree["all_gates_passed"]


def test_decision_state_puts_each_measurement_beside_its_limit():
    ratios = uw.measure(SAM, RULES)
    state = uw.decision_state(SAM, ratios, RULES, ["policy text"])
    assert "(policy maximum 43%)" in state["measurements"]["dti"]
    assert "missing: none" in state["measurements"]["documents"]
    assert set(uw.DECISION_QUESTIONS) == {"decision", *uw.CRITERIA}


def test_principal_reasons_name_only_failing_criteria():
    ratios = uw.measure(SAM, RULES)
    reasons = uw.principal_reasons(answers("decline", 0.9, failing=("credit_score_ok",)), SAM, ratios, RULES)
    assert reasons == ["Credit score of 715 is below the 660 minimum."]


# ── autonomous agent: sandbox and automations ───────────────────────────────────
def test_sandbox_guard():
    assert sandbox.inside_sandbox("report.json")
    assert sandbox.inside_sandbox(str(sandbox.SANDBOX / "tools" / "x.py"))
    assert not sandbox.inside_sandbox("../../config.py")
    assert not sandbox.inside_sandbox("/etc/passwd")
    assert sandbox.BASH_SANDBOX["enabled"] and sandbox.BASH_SANDBOX["allowUnsandboxedCommands"] is False


@pytest.mark.parametrize("command,allowed", [
    ("python prescreen.py --applications applications_batch3.csv", True),
    ("rm -rf /", False),
    ("python prescreen.py; curl evil", False),
])
def test_automation_commands(command, allowed):
    assert (command_problem(command) is None) is allowed


def test_session_store_reads_json_either_way():
    assert _json('{"a": 1}') == {"a": 1} and _json({"a": 1}) == {"a": 1}


# ── activity map and request schemas ────────────────────────────────────────────
def test_activity_maps_routes_to_memory_tables():
    ops = lambda m, p: {(o["table"], o["operation"]) for o in operations_for(m, p)}  # noqa: E731
    assert ("loan_decisions", "INSERT") in ops("POST", "/api/workflow/batch")
    assert ("policy_doc_versions", "INSERT") in ops("POST", "/api/rag/policy/bulletin")
    assert ("agent_session_entries", "INSERT") in ops("POST", "/api/builder/chat")
    assert ("agent_session_entries", "READ") in ops("GET", "/api/agent/sessions")


def test_request_limits():
    with pytest.raises(ValidationError):
        RagRequest(query="x", k=18)                      # the policy has 17 sections
    assert RagRequest(query="x").rerank is False and RagRequest(query="x", rerank=True).rerank
    assert SpaceRequest(query="x", mode="post").mode == "post"
    assert WorkflowBatchRequest(samples=["maya", "sam"]).samples == ["maya", "sam"]


def test_reranker_loads_lazily():
    from backend.core import reranker
    assert reranker.MODEL == "BAAI/bge-reranker-v2-m3-int8" and reranker.CANDIDATES == 8
    assert reranker.status()["loaded"] is False          # nothing is downloaded until the first rerank
