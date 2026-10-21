"""Acme Home Loans' lending policy and the application's memory tables, mirroring the notebook.

The same tables the notebook creates (POLICY_DOCS, POLICY_DOC_VERSIONS, the policy graph,
LOAN_APPLICATIONS, LOAN_DECISIONS, CASE_NOTES, AGENT_SESSION_*) back every form factor here.
``ensure_schema`` creates anything missing and seeds the policy when it is empty, so the appbook
never wipes what the notebook wrote; ``reset_demo`` rebuilds everything from the seed on request.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

POLICY_DOCS: list[dict[str, Any]] = [
    {"doc_id": "dti_limit", "title": "Debt-to-Income (DTI) Limit", "category": "affordability",
     "rules": {"max_dti": 0.41},
     "content": "Acme Home Loans caps the debt-to-income (DTI) ratio at 41%. DTI is all monthly debt payments, "
                "including the new mortgage payment of principal, interest, property tax and insurance (PITI), "
                "divided by gross monthly income. Applications above the limit are declined."},
    {"doc_id": "payment_estimate", "title": "How We Estimate the Mortgage Payment", "category": "affordability",
     "rules": {"rate": 0.065, "term_months": 360, "tax_insurance_rate_annual": 0.015},
     "content": "For affordability checks the monthly payment (PITI) is estimated at a 6.5% fixed rate over 30 years, "
                "plus property tax and homeowner's insurance of 1.5% of the property value per year."},
    {"doc_id": "reserves", "title": "Cash Reserves After Closing", "category": "affordability",
     "rules": {"min_reserve_months": {"primary": 2, "second_home": 2, "investment": 6}},
     "content": "After the down payment and closing costs, borrowers must hold liquid reserves worth at least two "
                "months of the new mortgage payment (PITI), or six months for an investment property."},
    {"doc_id": "ltv_limit", "title": "Loan-to-Value (LTV) Limits", "category": "collateral",
     "rules": {"max_ltv": {"primary": 0.95, "second_home": 0.85, "investment": 0.75}},
     "content": "The loan-to-value (LTV) ratio is the loan amount divided by the lower of the purchase price and the "
                "appraised value. Maximum LTV is 95% for a primary residence, 85% for a second home and 75% for an "
                "investment property."},
    {"doc_id": "pmi", "title": "Private Mortgage Insurance (PMI)", "category": "collateral", "rules": None,
     "content": "Any loan with an LTV above 80% requires private mortgage insurance (PMI). PMI is removed "
                "automatically once the balance reaches 78% of the original property value."},
    {"doc_id": "property_types", "title": "Eligible Property Types", "category": "collateral", "rules": None,
     "content": "Eligible properties are single-family homes, warrantable condominiums and two-to-four unit homes. "
                "Manufactured homes on leased land and mixed-use commercial properties are not eligible."},
    {"doc_id": "appraisal", "title": "Appraisal Requirement", "category": "collateral", "rules": None,
     "content": "Every purchase needs an independent appraisal ordered through Acme Home Loans. If the appraised "
                "value comes in below the purchase price, LTV is calculated on the appraised value."},
    {"doc_id": "credit_score", "title": "Minimum Credit Score", "category": "credit",
     "rules": {"min_credit_score": 640},
     "content": "Acme Home Loans requires a minimum credit score of 640, using the middle of the three bureau scores. "
                "Applications below 640 are declined."},
    {"doc_id": "bankruptcy", "title": "Bankruptcy and Foreclosure Waiting Periods", "category": "credit",
     "rules": None,
     "content": "A Chapter 7 bankruptcy must have been discharged at least four years before the application date, "
                "and a foreclosure completed at least seven years before."},
    {"doc_id": "employment", "title": "Employment History", "category": "eligibility",
     "rules": {"min_employment_months": 24},
     "content": "Borrowers need 24 months of continuous employment or self-employment income. A gap longer than six "
                "months needs a written explanation. Self-employed borrowers qualify on the 24-month average of net "
                "business income from their tax returns."},
    {"doc_id": "documents", "title": "Required Documents", "category": "documentation", "rules": None,
     "content": "A complete application includes government photo ID, the two most recent pay stubs, W-2 forms for "
                "the last two years (or two years of tax returns if self-employed), and the two most recent bank "
                "statements for every account used for the down payment or reserves."},
    {"doc_id": "fair_lending", "title": "Fair Lending", "category": "compliance", "rules": None,
     "content": "Credit decisions must never consider race, color, religion, national origin, sex, marital status, "
                "age, or the receipt of public assistance income. Every applicant is assessed on the same written "
                "criteria."},
    {"doc_id": "adverse_action", "title": "Adverse Action Notices", "category": "compliance", "rules": None,
     "content": "When an application is declined, the applicant receives an adverse action notice within 30 days "
                "that states up to four specific principal reasons for the decision. Vague reasons such as 'did not "
                "meet our criteria' are not allowed."},
    {"doc_id": "human_review", "title": "Automated Decisions and Human Review", "category": "process",
     "rules": {"confidence_floor": 0.80, "borderline_margin": 0.01},
     "content": "An automated decision is final only when the decision model's confidence is at least 0.80 and no "
                "ratio is within one percentage point of its limit. Every other application is referred to a human "
                "underwriter."},
    {"doc_id": "timelines", "title": "Processing Timelines", "category": "process", "rules": None,
     "content": "Pre-approval decisions are returned within two business days. Full underwriting takes up to ten "
                "business days after every required document is received."},
    {"doc_id": "products", "title": "Loan Products", "category": "products", "rules": None,
     "content": "Acme Home Loans offers 30-year fixed, 15-year fixed and 7/6 adjustable-rate mortgages. The minimum "
                "down payment is 5% for a primary residence."},
    {"doc_id": "rate_lock", "title": "Rate Locks", "category": "products", "rules": None,
     "content": "Interest rates can be locked for 45 days once an application is complete. One 15-day extension is "
                "available for a fee of 0.125% of the loan amount."},
]
SEED_BY_ID = {d["doc_id"]: d for d in POLICY_DOCS}
CATEGORIES = sorted({d["category"] for d in POLICY_DOCS})

# The two policy bulletins the notebook applies (§2.8 and §5.5), offered as one-click updates.
BULLETINS = {
    "dti_43": {"doc_id": "dti_limit", "rules": {"max_dti": 0.43},
               "label": "Raise the DTI limit from 41% to 43%",
               "reason": "Credit committee bulletin: DTI limit raised from 41% to 43% for new applications.",
               "content": SEED_BY_ID["dti_limit"]["content"].replace("41%", "43%")},
    "credit_660": {"doc_id": "credit_score", "rules": {"min_credit_score": 660},
                   "label": "Raise the minimum credit score from 640 to 660",
                   "reason": "Credit committee bulletin: minimum credit score raised from 640 to 660.",
                   "content": SEED_BY_ID["credit_score"]["content"].replace("640", "660")},
}

# Tables this appbook reads and writes (also the Data Explorer allowlist), in dependency order.
APP_TABLES = [
    "policy_docs", "policy_doc_versions", "policy_categories", "policy_doc_categories", "policy_doc_similarities",
    "loan_applications", "loan_decisions", "case_notes", "agent_session_entries", "agent_session_summaries",
]

_DROP = "BEGIN EXECUTE IMMEDIATE 'DROP TABLE {t} CASCADE CONSTRAINTS PURGE'; " \
        "EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;"

TABLE_DDL = {
    "policy_docs": """CREATE TABLE policy_docs (
        doc_id     VARCHAR2(64) PRIMARY KEY,
        title      VARCHAR2(400),
        category   VARCHAR2(64),
        content    VARCHAR2(4000),
        rules      JSON,
        version    NUMBER DEFAULT 1 NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
        embedding  VECTOR({dim}, FLOAT32))""",
    "policy_doc_versions": """CREATE TABLE policy_doc_versions (
        doc_id        VARCHAR2(64),
        version       NUMBER,
        title         VARCHAR2(400),
        category      VARCHAR2(64),
        content       VARCHAR2(4000),
        rules         JSON,
        valid_from    TIMESTAMP WITH TIME ZONE,
        valid_to      TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP,
        change_reason VARCHAR2(400),
        CONSTRAINT pk_policy_doc_versions PRIMARY KEY (doc_id, version))""",
    "policy_categories": "CREATE TABLE policy_categories (category VARCHAR2(64) PRIMARY KEY)",
    "policy_doc_categories": """CREATE TABLE policy_doc_categories (
        doc_id   VARCHAR2(64) NOT NULL,
        category VARCHAR2(64) NOT NULL,
        CONSTRAINT pk_policy_doc_categories PRIMARY KEY (doc_id, category),
        CONSTRAINT fk_pdc_doc FOREIGN KEY (doc_id) REFERENCES policy_docs(doc_id),
        CONSTRAINT fk_pdc_cat FOREIGN KEY (category) REFERENCES policy_categories(category))""",
    "policy_doc_similarities": """CREATE TABLE policy_doc_similarities (
        source_doc_id VARCHAR2(64) NOT NULL,
        target_doc_id VARCHAR2(64) NOT NULL,
        sim_score NUMBER(8,6) NOT NULL,
        rank_no   NUMBER(5) NOT NULL,
        CONSTRAINT pk_policy_doc_similarities PRIMARY KEY (source_doc_id, target_doc_id),
        CONSTRAINT fk_pds_src FOREIGN KEY (source_doc_id) REFERENCES policy_docs(doc_id),
        CONSTRAINT fk_pds_tgt FOREIGN KEY (target_doc_id) REFERENCES policy_docs(doc_id),
        CONSTRAINT ck_pds_not_self CHECK (source_doc_id <> target_doc_id))""",
    "loan_applications": """CREATE TABLE loan_applications (
        application_id VARCHAR2(36) PRIMARY KEY,
        applicant      VARCHAR2(200) NOT NULL,
        received_at    TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
        updated_at     TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
        source_text    CLOB,
        facts          JSON)""",
    "loan_decisions": """CREATE TABLE loan_decisions (
        decision_id     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id  VARCHAR2(36) NOT NULL REFERENCES loan_applications(application_id),
        decided_at      TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
        outcome         VARCHAR2(16) NOT NULL,
        model_choice    VARCHAR2(16),
        confidence      NUMBER,
        criteria        JSON,
        ratios          JSON,
        reasons         JSON,
        review_reasons  JSON,
        policy_versions JSON,
        decided_by      VARCHAR2(200),
        letter          CLOB)""",
    "case_notes": """CREATE TABLE case_notes (
        note_id        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        application_id VARCHAR2(36) NOT NULL REFERENCES loan_applications(application_id),
        written_at     TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
        author         VARCHAR2(100),
        note           VARCHAR2(4000))""",
    "agent_session_entries": """CREATE TABLE agent_session_entries (
        store_name  VARCHAR2(64)  NOT NULL,
        project_key VARCHAR2(512) NOT NULL,
        session_id  VARCHAR2(64)  NOT NULL,
        subpath     VARCHAR2(512) NOT NULL,
        seq         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        entry_uuid  VARCHAR2(64),
        entry_type  VARCHAR2(64),
        written_ms  NUMBER        NOT NULL,
        entry       CLOB          CHECK (entry IS JSON))""",
    "agent_session_summaries": """CREATE TABLE agent_session_summaries (
        store_name  VARCHAR2(64)  NOT NULL,
        project_key VARCHAR2(512) NOT NULL,
        session_id  VARCHAR2(64)  NOT NULL,
        mtime       NUMBER        NOT NULL,
        data        CLOB          CHECK (data IS JSON),
        CONSTRAINT pk_agent_session_summaries PRIMARY KEY (store_name, project_key, session_id))""",
}

# The pre-mortgage appbook's tables; removed once so the schema only holds the current dataset.
LEGACY_OBJECTS = ["doc_similarities", "doc_categories", "categories", "acme_docs"]


def plain(value: Any) -> Any:
    """JSON columns come back with Decimal numbers; turn them into ints and floats."""
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def doc_text(doc: dict) -> str:
    """What is embedded for a policy section: its title and its text, as one sentence-like string."""
    return f"{doc['title']}. {doc['content']}"


def existing_tables(cur) -> set[str]:
    cur.execute("SELECT LOWER(table_name) FROM user_tables")
    return {name for (name,) in cur.fetchall()}


def drop_legacy(conn) -> list[str]:
    """Remove the old Acme Cloud dataset (tables, text index, graph) if it is still there."""
    removed = []
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_property_graphs WHERE graph_name = 'ACME_GRAPH'")
        if cur.fetchone()[0]:
            cur.execute("DROP PROPERTY GRAPH acme_graph")
            removed.append("acme_graph")
        present = existing_tables(cur)
        for table in LEGACY_OBJECTS:
            if table in present:
                cur.execute(_DROP.format(t=table))
                removed.append(table)
        if removed:
            cur.execute("PURGE RECYCLEBIN")
    conn.commit()
    return removed
