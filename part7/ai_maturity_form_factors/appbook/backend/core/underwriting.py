"""Underwriting for Form Factors 3 and 4, mirroring the notebook's Part 3.

extract → measure → ground → decide (Clef) → gate → explain → review → record. The decision model is
loaded once, on first use, and guarded by a lock: it runs one request at a time on the GPU, so parallel
workflow lanes queue for it, and the UI shows that queue.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from typing import Any

from backend.config import settings
from backend.core import db
from backend.core.anthropic_client import ask, structured_json
from backend.core.policy import plain

DOCUMENT_TYPES = ["photo ID", "two pay stubs", "two years of W-2s", "two years of tax returns", "two bank statements"]
REQUIRED_DOCUMENTS = ["photo ID", "two pay stubs", "two years of W-2s", "two bank statements"]
DECISION_SECTIONS = ["dti_limit", "payment_estimate", "reserves", "ltv_limit", "credit_score", "employment", "documents"]

APPLICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "applicant": {"type": "string"},
        "gross_monthly_income": {"type": "number", "description": "Gross (pre-tax) monthly income in dollars."},
        "monthly_debts": {"type": "number", "description": "Total monthly payments on existing debts, excluding rent and the new mortgage."},
        "loan_amount": {"type": "number"},
        "property_value": {"type": "number", "description": "Purchase price, or the appraised value if lower."},
        "property_use": {"type": "string", "enum": ["primary", "second_home", "investment"]},
        "credit_score": {"type": "integer"},
        "employment_months": {"type": "integer", "description": "Months of continuous employment or self-employment."},
        "liquid_reserves": {"type": "number", "description": "Liquid savings left after the down payment and closing costs."},
        "documents_provided": {"type": "array", "items": {"type": "string", "enum": DOCUMENT_TYPES}},
        "notes": {"type": "string", "description": "Anything else an underwriter should know, in one sentence. "
                                                    "Do not comment on documents; documents_provided covers them."},
    },
    "required": ["applicant", "gross_monthly_income", "monthly_debts", "loan_amount", "property_value", "property_use",
                 "credit_score", "employment_months", "liquid_reserves", "documents_provided", "notes"],
    "additionalProperties": False,
}

CRITERIA = {
    "dti_within_limit": "Is the application's DTI at or below the policy's maximum DTI?",
    "ltv_within_limit": "Is the LTV at or below the policy maximum for this property use?",
    "credit_score_ok": "Is the credit score at or above the policy minimum?",
    "reserves_ok": "Do the reserves cover at least the policy's required months of payments for this property use?",
    "employment_ok": "Does the employment history meet the policy minimum?",
    "documents_complete": "Did the applicant provide every document the policy requires?",
}
CRITERIA_LABELS = {"dti_within_limit": "DTI within limit", "ltv_within_limit": "LTV within limit",
                   "credit_score_ok": "Credit score", "reserves_ok": "Cash reserves",
                   "employment_ok": "Employment history", "documents_complete": "Documents complete"}
DECISION_QUESTIONS = {
    "decision": {
        "type": "choice",
        "instructions": "Under the written lending policy in the state, should Acme Home Loans approve or decline this mortgage application?",
        "criteria": {"approve": "Every requirement of the written policy is met.",
                     "decline": "At least one requirement of the written policy is not met."},
    },
    **{field: {"type": "noul", "instructions": question} for field, question in CRITERIA.items()},
}

SAMPLE_APPLICATIONS = {
    "maya": ("Maya Patel", "clean application", """Subject: Mortgage application – 14 Alder Way
Hello Acme Home Loans, I'd like a mortgage on 14 Alder Way, which I'm buying as my home for $420,000. I'm putting
20% down, so I need to borrow $336,000. I'm a staff nurse and have worked at St. Anne's Hospital for six years; my
salary is $110,400 a year. My only debt is a student loan at $450 a month. My credit score is 752, and after the down
payment and closing costs I'll still have about $40,000 in savings. Attached: my passport, my last two pay stubs,
W-2s for the last two years and my last two bank statements. Thanks, Maya Patel"""),
    "jordan": ("Jordan Lee", "high debts", """Subject: Home loan for 9 Birch Court
Hi, I'm Jordan Lee. I'm buying 9 Birch Court to live in for $360,000 with 10% down, so the loan would be $324,000.
I earn $8,000 a month as a warehouse operations manager and have been with the same company for five years.
Monthly debts: car loan $650, credit cards $350, student loan $300. Credit score 705. I'll have $18,000 in savings
after closing. I've attached my driver's licence, two pay stubs, two years of W-2s and two bank statements."""),
    "sam": ("Sam Rivera", "DTI near the limit", """Subject: Mortgage application, 3 Cedar Rise
Hello, this is Sam Rivera. I'm buying 3 Cedar Rise as my main home for $550,000 and putting 20% down ($110,000), so
I'd borrow $440,000. I'm a senior engineer at a regional utility, three years in the role, earning $150,000 a year.
I pay $1,100 a month on a car loan and $750 a month on student loans. My credit score is 715 and I'll keep $30,000 in
savings after closing. Documents attached: photo ID, recent pay stubs (two), W-2s for two years, two bank statements."""),
    "priya": ("Priya Nair", "investment property", """Subject: Investment property loan – 22 Quay Street
Hi, I'm Priya Nair. I'd like to finance 22 Quay Street, a rental investment property, for $500,000 with 20% down, so
a $400,000 loan. I earn $168,000 a year as a product director (ten years with my employer) and pay $900 a month on a
car loan. Credit score 760; I'll keep $60,000 in reserves after closing. Attached: passport, two pay stubs, two years
of W-2s, two bank statements."""),
    "leo": ("Leo Grant", "low credit score", """Subject: First home – 5 Elm Row
Hello, I'm Leo Grant, buying my first home at 5 Elm Row for $300,000 with 10% down ($270,000 loan). I work as an
electrician, four years with the same contractor, earning $7,500 a month. My only debt is a $400 monthly car payment.
My credit score is 610 after a rough patch a couple of years ago. I'll have $12,000 left in savings. Attached: ID,
two pay stubs, W-2s for two years and two bank statements."""),
    "ana": ("Ana Souza", "second home", """Subject: Second home – Cabin 7, Lake Road
Hi, this is Ana Souza. I'm buying a lake cabin as a second home for $380,000 with 20% down, borrowing $304,000.
I'm an architect, eight years at my firm, earning $132,000 a year. Monthly debts: $1,200 (car and student loans).
Credit score 740 and $35,000 in savings after closing. Documents: photo ID, two pay stubs, two years of W-2s and two
bank statements."""),
}


# ── policy memory ─────────────────────────────────────────────────────────────────
def current_policy() -> tuple[dict, dict]:
    """The rules in force now (merged from every section's JSON) and each section's version."""
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, version, rules FROM policy_docs")
        rows = cur.fetchall()
    rules = {}
    for _, _, section_rules in rows:
        rules.update(plain(section_rules) or {})
    return rules, {doc_id: int(version) for doc_id, version, _ in rows}


def decision_policy_text() -> list[str]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, version, title, content FROM policy_docs")
        sections = {d: (int(v), t, c) for d, v, t, c in cur.fetchall()}
    return [f"{sections[d][1]} (v{sections[d][0]}): {sections[d][2]}" for d in DECISION_SECTIONS]


def policy_sections() -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, title, category, version, content, rules, TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') "
                    "FROM policy_docs ORDER BY category, doc_id")
        return [{"doc_id": d, "title": t, "category": c, "version": int(v), "content": body, "rules": plain(r), "updated_at": u}
                for d, t, c, v, body, r, u in cur.fetchall()]


def policy_history() -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_id, version, content, rules, TO_CHAR(valid_to, 'YYYY-MM-DD HH24:MI:SS'), change_reason "
                    "FROM policy_doc_versions ORDER BY valid_to DESC")
        return [{"doc_id": d, "version": int(v), "content": body, "rules": plain(r), "valid_to": t, "reason": why}
                for d, v, body, r, t, why in cur.fetchall()]


def update_policy(doc_id: str, content: str, rules: dict | None, reason: str) -> int:
    """Write a new version of one section: archive the current row, re-embed, update in place (one transaction),
    then recompute the graph edges, which are derived from the embeddings."""
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM policy_docs WHERE doc_id = :d", d=doc_id)
            title = cur.fetchone()[0]
            vector = db.embed_documents([f"{title}. {content}"])[0]
            cur.execute("""INSERT INTO policy_doc_versions (doc_id, version, title, category, content, rules, valid_from, change_reason)
                           SELECT doc_id, version, title, category, content, rules, updated_at, :reason
                           FROM policy_docs WHERE doc_id = :d""", reason=reason, d=doc_id)
            cur.execute("""UPDATE policy_docs SET content = :content, rules = :rules, embedding = :embedding,
                                  version = version + 1, updated_at = SYSTIMESTAMP WHERE doc_id = :d""",
                        content=content, rules=json.dumps(rules) if rules else None, embedding=db.as_vector(vector), d=doc_id)
            cur.execute("SELECT version FROM policy_docs WHERE doc_id = :d", d=doc_id)
            version = int(cur.fetchone()[0])
        conn.commit()
        db.rebuild_graph(conn)
    return version


# ── ① understand, ② measure ──────────────────────────────────────────────────────
def extract_application(email: str) -> dict:
    return structured_json(
        schema=APPLICATION_SCHEMA,
        system=("Extract the mortgage application from the email. Convert yearly amounts to monthly. "
                "monthly_debts is the sum of every existing monthly debt payment. Map each document mentioned "
                "to the closest allowed document type."),
        prompt=email,
    )


def measure(app: dict, rules: dict) -> dict:
    rate = rules["rate"] / 12
    principal_interest = app["loan_amount"] * rate / (1 - (1 + rate) ** -rules["term_months"])
    piti = principal_interest + app["property_value"] * rules["tax_insurance_rate_annual"] / 12
    return {
        "monthly_payment_piti": round(piti, 2),
        "dti": round((app["monthly_debts"] + piti) / app["gross_monthly_income"], 4),
        "ltv": round(app["loan_amount"] / app["property_value"], 4),
        "reserve_months": round(app["liquid_reserves"] / piti, 1),
    }


# ── ④ decide with Clef ───────────────────────────────────────────────────────────
_clef = {"model": None, "status": "not loaded", "error": None, "load_seconds": None}
_clef_load_lock = threading.Lock()
_clef_run_lock = threading.Lock()  # one GPU: one decision at a time


def clef_status() -> dict:
    if settings.clef_url:
        return {"status": "remote", "endpoint": settings.clef_url, "busy": _clef_run_lock.locked()}
    return {"status": _clef["status"], "error": _clef["error"], "load_seconds": _clef["load_seconds"],
            "model": f"{settings.clef_repo}@{settings.clef_revision[:7]}", "busy": _clef_run_lock.locked()}


def clef_id() -> str:
    return f"clef via {settings.clef_url}" if settings.clef_url else f"{settings.clef_repo}@{settings.clef_revision[:7]}"


def load_clef():
    """Download (pinned revision, no precompiled .pyc) and load the 4-bit MLX build once."""
    if _clef["model"] is not None:
        return _clef["model"]
    with _clef_load_lock:
        if _clef["model"] is not None:
            return _clef["model"]
        _clef["status"] = "loading"
        try:
            from huggingface_hub import snapshot_download
            from huggingface_hub.utils import disable_progress_bars

            disable_progress_bars()
            path = snapshot_download(settings.clef_repo, revision=settings.clef_revision,
                                     ignore_patterns=["__pycache__/*", "*.pyc", ".eval_results/*"])
            if path not in sys.path:
                sys.path.insert(0, path)
            import clef_mlx

            started = time.perf_counter()
            _clef["model"] = clef_mlx.load(path)
            _clef.update(status="ready", load_seconds=round(time.perf_counter() - started, 1), error=None)
        except Exception as exc:  # noqa: BLE001 — reported in /api/health and the step event
            _clef.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
    return _clef["model"]


def clef_busy() -> bool:
    return _clef_run_lock.locked()


def systemone(request: dict) -> dict:
    if settings.clef_url:
        import requests

        response = requests.post(f"{settings.clef_url}/v1/systemone", json=request, timeout=180)
        response.raise_for_status()
        return response.json()
    model = load_clef()
    with _clef_run_lock:
        return model.systemone(request)


def decision_state(app: dict, ratios: dict, rules: dict, policy_text: list[str]) -> dict:
    use = app["property_use"]
    missing = [d for d in REQUIRED_DOCUMENTS if d not in app["documents_provided"]]
    return {
        "task": "Underwrite this mortgage application against Acme Home Loans' written policy.",
        "application": app,
        "measurements": {
            "monthly_payment_piti": f"${ratios['monthly_payment_piti']:,.2f}",
            "dti": f"{ratios['dti']:.1%} (policy maximum {rules['max_dti']:.0%})",
            "ltv": f"{ratios['ltv']:.1%} (policy maximum for {use}: {rules['max_ltv'][use]:.0%})",
            "reserves": f"{ratios['reserve_months']} months of payments (policy minimum for {use}: "
                        f"{rules['min_reserve_months'][use]} months)",
            "credit_score": f"{app['credit_score']} (policy minimum {rules['min_credit_score']})",
            "employment": f"{app['employment_months']} months (policy minimum {rules['min_employment_months']} months)",
            "documents": f"provided: {', '.join(app['documents_provided']) or 'none'} (policy requires: "
                         f"{', '.join(REQUIRED_DOCUMENTS)}; missing: {', '.join(missing) or 'none'})",
        },
        "policy": policy_text,
    }


def decide(app: dict, ratios: dict, rules: dict, policy_text: list[str]) -> dict:
    request = {"model": "clef-flash", "state": decision_state(app, ratios, rules, policy_text), "questions": DECISION_QUESTIONS}
    started = time.perf_counter()
    response = systemone(request)
    response["latency_ms"] = round((time.perf_counter() - started) * 1000)
    response["request"] = request
    return response


# ── ⑤ gate, reasons, and the decision tree ─────────────────────────────────────────
def gate(answers: dict, app: dict, ratios: dict, rules: dict) -> tuple[str, list[str]]:
    confidence = answers["decision"]["confidence"]
    why = []
    if confidence < rules["confidence_floor"]:
        why.append(f"decision confidence {confidence:.2f} is below {rules['confidence_floor']:.2f}")
    limits = {"DTI": (ratios["dti"], rules["max_dti"]), "LTV": (ratios["ltv"], rules["max_ltv"][app["property_use"]])}
    for name, (value, limit) in limits.items():
        if abs(value - limit) <= rules["borderline_margin"]:
            why.append(f"{name} of {value:.1%} is within one point of its {limit:.0%} limit")
    return ("refer" if why else answers["decision"]["choice"]), why


def principal_reasons(answers: dict, app: dict, ratios: dict, rules: dict) -> list[str]:
    use = app["property_use"]
    missing = [d for d in REQUIRED_DOCUMENTS if d not in app["documents_provided"]]
    text = {
        "dti_within_limit": f"Debt-to-income ratio of {ratios['dti']:.1%} is above the {rules['max_dti']:.0%} maximum.",
        "ltv_within_limit": f"Loan-to-value ratio of {ratios['ltv']:.1%} is above the {rules['max_ltv'][use]:.0%} "
                            f"maximum for a {use.replace('_', ' ')} property.",
        "credit_score_ok": f"Credit score of {app['credit_score']} is below the {rules['min_credit_score']} minimum.",
        "reserves_ok": f"Cash reserves cover {ratios['reserve_months']} months of payments; the policy requires "
                       f"{rules['min_reserve_months'][use]}.",
        "employment_ok": f"Employment history of {app['employment_months']} months is shorter than the required "
                         f"{rules['min_employment_months']} months.",
        "documents_complete": f"Required documents are missing: {', '.join(missing) or 'see checklist'}.",
    }
    return [text[field] for field in CRITERIA if answers[field]["noul"] < 0.5][:4]


def decision_tree(answers: dict, app: dict, ratios: dict, rules: dict, outcome: str) -> dict:
    """The path one application took: six criteria → Clef's choice → three gate checks → the outcome."""
    use = app["property_use"]
    evidence = {
        "dti_within_limit": f"{ratios['dti']:.1%} vs {rules['max_dti']:.0%}",
        "ltv_within_limit": f"{ratios['ltv']:.1%} vs {rules['max_ltv'][use]:.0%}",
        "credit_score_ok": f"{app['credit_score']} vs {rules['min_credit_score']}",
        "reserves_ok": f"{ratios['reserve_months']} vs {rules['min_reserve_months'][use]} mo",
        "employment_ok": f"{app['employment_months']} vs {rules['min_employment_months']} mo",
        "documents_complete": f"{len([d for d in REQUIRED_DOCUMENTS if d in app['documents_provided']])}/{len(REQUIRED_DOCUMENTS)} required",
    }
    criteria = [{"id": f, "label": CRITERIA_LABELS[f], "probability": round(answers[f]["noul"], 4),
                 "passed": answers[f]["noul"] >= 0.5, "evidence": evidence[f]} for f in CRITERIA]
    confidence = answers["decision"]["confidence"]
    gates = [
        {"id": "confidence", "label": f"confidence ≥ {rules['confidence_floor']:.2f}", "value": f"{confidence:.2f}",
         "passed": confidence >= rules["confidence_floor"]},
        {"id": "dti_margin", "label": f"DTI not within {rules['borderline_margin']:.0%} of {rules['max_dti']:.0%}",
         "value": f"{ratios['dti']:.1%}", "passed": abs(ratios["dti"] - rules["max_dti"]) > rules["borderline_margin"]},
        {"id": "ltv_margin", "label": f"LTV not within {rules['borderline_margin']:.0%} of {rules['max_ltv'][use]:.0%}",
         "value": f"{ratios['ltv']:.1%}", "passed": abs(ratios["ltv"] - rules["max_ltv"][use]) > rules["borderline_margin"]},
    ]
    return {"criteria": criteria,
            "model": {"choice": answers["decision"]["choice"], "confidence": confidence,
                      "probabilities": answers["decision"]["probabilities"]},
            "gates": gates, "outcome": outcome, "all_gates_passed": all(g["passed"] for g in gates)}


# ── ⑥ explain, ⑦ review ──────────────────────────────────────────────────────────
LETTER_SYSTEM = (
    "You write decision letters for Acme Home Loans. Use only the facts given. Keep it under 140 words, in plain, "
    "respectful language, signed 'Acme Home Loans Underwriting'. For a decline, list each principal reason exactly "
    "as given, as bullet points. For a referral, say the application has been referred to an underwriter who will "
    "review it within ten business days, and do not hint at the outcome. Never mention race, color, religion, "
    "national origin, sex, marital status, age or public assistance."
)
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"approved": {"type": "boolean"},
                   "feedback": {"type": "string", "description": "One specific fix if not approved; empty if approved."}},
    "required": ["approved", "feedback"],
    "additionalProperties": False,
}


def draft_letter(app: dict, outcome: str, reasons: list[str], feedback: str = "") -> str:
    facts = {"applicant": app["applicant"], "loan_amount": app["loan_amount"], "outcome": outcome, "principal_reasons": reasons}
    prompt = f"Write the letter for this decision:\n{json.dumps(facts, indent=2)}"
    if feedback:
        prompt += f"\n\nA compliance reviewer asked for this fix: {feedback}"
    return ask(LETTER_SYSTEM, prompt)


def review_letter(outcome: str, reasons: list[str], letter: str) -> dict:
    return structured_json(
        schema=REVIEW_SCHEMA,
        system=("You are Acme Home Loans' compliance reviewer. Approve the letter only if it states the given "
                "outcome; for a decline, lists every given principal reason specifically; states no facts beyond "
                "those given; and mentions no race, color, religion, national origin, sex, marital status, age or "
                "public assistance. If you approve, return empty feedback; otherwise give one fix in at most 40 words."),
        prompt=f"Outcome: {outcome}\nPrincipal reasons: {json.dumps(reasons)}\n\nLetter:\n{letter}",
    )


# ── ⑧ record: episodic memory ────────────────────────────────────────────────────
def save_application(app: dict, source_text: str) -> str:
    application_id = str(uuid.uuid4())
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO loan_applications (application_id, applicant, source_text, facts) VALUES (:1, :2, :3, :4)",
                        [application_id, app["applicant"], source_text, json.dumps(app)])
        conn.commit()
    return application_id


def save_decision(application_id: str, outcome: str, answers: dict, ratios: dict, reasons: list[str],
                  review_reasons: list[str], versions: dict, decided_by: str, letter: str | None = None) -> int:
    import oracledb

    criteria = {field: round(answers[field]["noul"], 4) for field in CRITERIA}
    with db.connection() as conn:
        with conn.cursor() as cur:
            decision_id = cur.var(oracledb.NUMBER)
            cur.execute("""INSERT INTO loan_decisions (application_id, outcome, model_choice, confidence, criteria, ratios,
                                                       reasons, review_reasons, policy_versions, decided_by, letter)
                           VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11) RETURNING decision_id INTO :12""",
                        [application_id, outcome, answers["decision"]["choice"], answers["decision"]["confidence"],
                         json.dumps(criteria), json.dumps(ratios), json.dumps(reasons), json.dumps(review_reasons),
                         json.dumps({d: versions[d] for d in DECISION_SECTIONS}), decided_by, letter, decision_id])
        conn.commit()
    return int(decision_id.getvalue()[0])


def record_human_decision(application_id: str, outcome: str, note: str, underwriter: str = "human underwriter") -> dict:
    """An underwriter resolves a referral: append the decision and a case note."""
    import oracledb

    with db.connection() as conn:
        with conn.cursor() as cur:
            decision_id = cur.var(oracledb.NUMBER)
            cur.execute("""INSERT INTO loan_decisions (application_id, outcome, reasons, decided_by)
                           VALUES (:1, :2, :3, :4) RETURNING decision_id INTO :5""",
                        [application_id, outcome, json.dumps([note] if note else []), underwriter, decision_id])
            cur.execute("INSERT INTO case_notes (application_id, author, note) VALUES (:1, :2, :3)",
                        [application_id, underwriter, note or f"Referral resolved: {outcome}."])
        conn.commit()
    return {"decision_id": int(decision_id.getvalue()[0])}


def case_history(applicant: str) -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT application_id, applicant, facts FROM loan_applications WHERE UPPER(applicant) LIKE UPPER(:n) "
                    "ORDER BY received_at", n=f"%{applicant.strip()}%")
        files = [{"application_id": a, "applicant": name, "current_facts": plain(f), "decisions": [], "notes": []}
                 for a, name, f in cur.fetchall()]
        for f in files:
            cur.execute("""SELECT decision_id, TO_CHAR(decided_at, 'YYYY-MM-DD HH24:MI'), outcome, ROUND(confidence, 2),
                                  reasons, review_reasons, ratios, decided_by
                           FROM loan_decisions WHERE application_id = :a ORDER BY decision_id""", a=f["application_id"])
            f["decisions"] = [{"decision_id": int(i), "decided_at": t, "outcome": o,
                               "confidence": float(c) if c is not None else None, "reasons": plain(r),
                               "review_reasons": plain(rr), "ratios": plain(ra), "decided_by": by}
                              for i, t, o, c, r, rr, ra, by in cur.fetchall()]
            cur.execute("SELECT TO_CHAR(written_at, 'YYYY-MM-DD HH24:MI'), author, note FROM case_notes "
                        "WHERE application_id = :a ORDER BY note_id", a=f["application_id"])
            f["notes"] = [{"written_at": t, "author": who, "note": n} for t, who, n in cur.fetchall()]
    return files


def reassess(application_id: str, changes: dict, record: bool = True, decided_by: str = "agent") -> dict:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT facts FROM loan_applications WHERE application_id = :a", a=application_id)
        row = cur.fetchone()
    if row is None:
        return {"error": f"No application {application_id}."}
    app = {**plain(row[0]), **changes}
    rules, versions = current_policy()
    ratios = measure(app, rules)
    answers = decide(app, ratios, rules, decision_policy_text())["answers"]
    outcome, review_reasons = gate(answers, app, ratios, rules)
    reasons = principal_reasons(answers, app, ratios, rules) if outcome == "decline" else []
    result = {"application_id": application_id, "changes": changes, "outcome": outcome,
              "model_choice": answers["decision"]["choice"], "confidence": answers["decision"]["confidence"],
              "ratios": ratios, "reasons": reasons, "review_reasons": review_reasons, "recorded": record}
    if record:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE loan_applications SET facts = :f, updated_at = SYSTIMESTAMP WHERE application_id = :a",
                            f=json.dumps(app), a=application_id)
            conn.commit()
        result["decision_id"] = save_decision(application_id, outcome, answers, ratios, reasons, review_reasons, versions,
                                              decided_by=f"{decided_by} · {clef_id()}")
    return result


def write_case_note(application_id: str, note: str, author: str = "underwriting agent") -> int:
    import oracledb

    with db.connection() as conn:
        with conn.cursor() as cur:
            note_id = cur.var(oracledb.NUMBER)
            cur.execute("INSERT INTO case_notes (application_id, author, note) VALUES (:1, :2, :3) RETURNING note_id INTO :4",
                        [application_id, author, note, note_id])
        conn.commit()
    return int(note_id.getvalue()[0])


def recent_decisions(limit: int = 30) -> list[dict]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT d.decision_id, a.applicant, d.outcome, d.model_choice, ROUND(d.confidence, 2),
                               JSON_VALUE(d.ratios, '$.dti'), JSON_VALUE(d.policy_versions, '$.dti_limit'),
                               d.decided_by, TO_CHAR(d.decided_at, 'YYYY-MM-DD HH24:MI:SS'), a.application_id
                        FROM loan_decisions d JOIN loan_applications a ON a.application_id = d.application_id
                        ORDER BY d.decision_id DESC FETCH FIRST {int(limit)} ROWS ONLY""")
        return [{"decision_id": int(i), "applicant": n, "outcome": o, "model_choice": m,
                 "confidence": float(c) if c is not None else None, "dti": float(dti) if dti else None,
                 "dti_policy_version": int(v) if v else None, "decided_by": by, "decided_at": t, "application_id": a}
                for i, n, o, m, c, dti, v, by, t, a in cur.fetchall()]


def sample_list() -> list[dict]:
    return [{"id": key, "applicant": name, "label": label, "email": email}
            for key, (name, label, email) in SAMPLE_APPLICATIONS.items()]


def to_json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))
