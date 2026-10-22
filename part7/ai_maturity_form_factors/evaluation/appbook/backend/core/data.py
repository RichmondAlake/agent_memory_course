"""The source of truth and the golden questions, exactly as in the evaluation notebook (Part 1).

Acme's written lending policy (seventeen synthetic sections, with the DTI limit already raised to 43% as version 2)
and 36 applicant questions labelled before the application answers any of them.
"""
from __future__ import annotations

POLICY_DOCS = [
    {"doc_id": "dti_limit", "title": "Debt-to-Income (DTI) Limit", "category": "affordability",
     "rules": {"max_dti": 0.41},
     "content": "Acme Home Loans caps the debt-to-income (DTI) ratio at 41%. DTI is all monthly debt payments, "
                "including the new mortgage payment of principal, interest, property tax and insurance (PITI), "
                "divided by gross monthly income. Applications above the limit are declined."},
    {"doc_id": "payment_estimate", "title": "How We Estimate the Mortgage Payment", "category": "affordability",
     "rules": {"rate": 0.065, "term_months": 360, "tax_insurance_rate_annual": 0.015},
     "content": "For affordability checks the monthly payment (PITI) is estimated at a 6.5% fixed rate over 30 "
                "years, plus property tax and homeowner's insurance of 1.5% of the property value per year."},
    {"doc_id": "reserves", "title": "Cash Reserves After Closing", "category": "affordability",
     "rules": {"min_reserve_months": {"primary": 2, "second_home": 2, "investment": 6}},
     "content": "After the down payment and closing costs, borrowers must hold liquid reserves worth at least two"
                " months of the new mortgage payment (PITI), or six months for an investment property."},
    {"doc_id": "ltv_limit", "title": "Loan-to-Value (LTV) Limits", "category": "collateral",
     "rules": {"max_ltv": {"primary": 0.95, "second_home": 0.85, "investment": 0.75}},
     "content": "The loan-to-value (LTV) ratio is the loan amount divided by the lower of the purchase price and "
                "the appraised value. Maximum LTV is 95% for a primary residence, 85% for a second home and 75% "
                "for an investment property."},
    {"doc_id": "pmi", "title": "Private Mortgage Insurance (PMI)", "category": "collateral", "rules": None,
     "content": "Any loan with an LTV above 80% requires private mortgage insurance (PMI). PMI is removed "
                "automatically once the balance reaches 78% of the original property value."},
    {"doc_id": "property_types", "title": "Eligible Property Types", "category": "collateral", "rules": None,
     "content": "Eligible properties are single-family homes, warrantable condominiums and two-to-four unit "
                "homes. Manufactured homes on leased land and mixed-use commercial properties are not eligible."},
    {"doc_id": "appraisal", "title": "Appraisal Requirement", "category": "collateral", "rules": None,
     "content": "Every purchase needs an independent appraisal ordered through Acme Home Loans. If the appraised "
                "value comes in below the purchase price, LTV is calculated on the appraised value."},
    {"doc_id": "credit_score", "title": "Minimum Credit Score", "category": "credit",
     "rules": {"min_credit_score": 640},
     "content": "Acme Home Loans requires a minimum credit score of 640, using the middle of the three bureau "
                "scores. Applications below 640 are declined."},
    {"doc_id": "bankruptcy", "title": "Bankruptcy and Foreclosure Waiting Periods", "category": "credit", "rules": None,
     "content": "A Chapter 7 bankruptcy must have been discharged at least four years before the application "
                "date, and a foreclosure completed at least seven years before."},
    {"doc_id": "employment", "title": "Employment History", "category": "eligibility",
     "rules": {"min_employment_months": 24},
     "content": "Borrowers need 24 months of continuous employment or self-employment income. A gap longer than "
                "six months needs a written explanation. Self-employed borrowers qualify on the 24-month average "
                "of net business income from their tax returns."},
    {"doc_id": "documents", "title": "Required Documents", "category": "documentation", "rules": None,
     "content": "A complete application includes government photo ID, the two most recent pay stubs, W-2 forms "
                "for the last two years (or two years of tax returns if self-employed), and the two most recent "
                "bank statements for every account used for the down payment or reserves."},
    {"doc_id": "fair_lending", "title": "Fair Lending", "category": "compliance", "rules": None,
     "content": "Credit decisions must never consider race, color, religion, national origin, sex, marital "
                "status, age, or the receipt of public assistance income. Every applicant is assessed on the same"
                " written criteria."},
    {"doc_id": "adverse_action", "title": "Adverse Action Notices", "category": "compliance", "rules": None,
     "content": "When an application is declined, the applicant receives an adverse action notice within 30 days "
                "that states up to four specific principal reasons for the decision. Vague reasons such as 'did "
                "not meet our criteria' are not allowed."},
    {"doc_id": "human_review", "title": "Automated Decisions and Human Review", "category": "process",
     "rules": {"confidence_floor": 0.8, "borderline_margin": 0.01},
     "content": "An automated decision is final only when the decision model's confidence is at least 0.80 and no"
                " ratio is within one percentage point of its limit. Every other application is referred to a "
                "human underwriter."},
    {"doc_id": "timelines", "title": "Processing Timelines", "category": "process", "rules": None,
     "content": "Pre-approval decisions are returned within two business days. Full underwriting takes up to ten "
                "business days after every required document is received."},
    {"doc_id": "products", "title": "Loan Products", "category": "products", "rules": None,
     "content": "Acme Home Loans offers 30-year fixed, 15-year fixed and 7/6 adjustable-rate mortgages. The "
                "minimum down payment is 5% for a primary residence."},
    {"doc_id": "rate_lock", "title": "Rate Locks", "category": "products", "rules": None,
     "content": "Interest rates can be locked for 45 days once an application is complete. One 15-day extension "
                "is available for a fee of 0.125% of the loan amount."},
]
# The policy changes the application has already received: (section, new text, new rules, reason).
POLICY_UPDATES = [
    ("dti_limit",
     "Acme Home Loans caps the debt-to-income (DTI) ratio at 43%. DTI is all monthly debt payments, including the new "
     "mortgage payment of principal, interest, property tax and insurance (PITI), divided by gross monthly income. "
     "Applications above the limit are declined.",
     {"max_dti": 0.43}, "Credit committee bulletin: DTI limit raised from 41% to 43% for new applications."),
]
CURRENT_TEXT = {d["doc_id"]: d["content"] for d in POLICY_DOCS} | {d: text for d, text, _, _ in POLICY_UPDATES}
RULES = {}
for doc in POLICY_DOCS:
    RULES.update(doc["rules"] or {})
for _, _, new_rules, _ in POLICY_UPDATES:
    RULES.update(new_rules)


GOLDEN = [
    # question, relevant sections (2 = answers it, 1 = helps), facts (statement, key phrase, wrong value), kind
    ("Which of my three credit bureau scores do you go by?", {"credit_score": 2},
     [("Acme uses the middle of the three bureau scores.", "middle", "highest")], "paraphrase"),
    ("Will the child support I receive from the state be held against me?", {"fair_lending": 2},
     [("Credit decisions never consider the receipt of public assistance income.", "never", "always")], "paraphrase"),
    ("How much does it cost to extend a rate lock?", {"rate_lock": 2},
     [("One 15-day rate lock extension costs 0.125% of the loan amount.", "0.125%", "0.25%")], "direct"),
    ("Do you offer adjustable-rate loans?", {"products": 2},
     [("Acme offers a 7/6 adjustable-rate mortgage.", "7/6", "5/1")], "direct"),
    ("How long does full underwriting take once I've sent everything?", {"timelines": 2},
     [("Full underwriting takes up to ten business days after every required document arrives.",
       "ten business days", "thirty business days")], "paraphrase"),
    ("Will an algorithm decide my loan on its own?", {"human_review": 2},
     [("An automated decision is final only when the model's confidence is at least 0.80 and no ratio is within one "
       "point of its limit; other applications go to a human underwriter.", "0.80", "0.50")], "paraphrase"),
    ("Can I buy a building with a shop downstairs and a flat upstairs?", {"property_types": 2},
     [("Mixed-use commercial properties are not eligible.", "not eligible", "eligible")], "paraphrase"),
    ("My foreclosure finished five years ago. Can I apply now?", {"bankruptcy": 2},
     [("A foreclosure must have been completed at least seven years before applying.", "seven years", "three years")],
     "paraphrase"),
    ("How do you work out my monthly payment for the affordability check?", {"payment_estimate": 2},
     [("The payment is estimated at a 6.5% fixed rate over 30 years.", "6.5%", "5.5%"),
      ("Property tax and insurance are added at 1.5% of the property value per year.", "1.5%", "2.5%")], "paraphrase"),
    ("What's the most you'll lend on a holiday home?", {"ltv_limit": 2},
     [("The maximum LTV for a second home is 85%.", "85%", "95%")], "paraphrase"),
    ("When does PMI come off my loan?", {"pmi": 2},
     [("PMI is removed automatically once the balance reaches 78% of the original property value.", "78%", "60%")],
     "paraphrase"),
    ("Do I need statements for the account my parents' gift sits in?", {"documents": 2},
     [("The two most recent bank statements are needed for every account used for the down payment or reserves.",
       "every account", "only the main account")], "paraphrase"),
    ("I had an eight-month gap between jobs last year. Is that a problem?", {"employment": 2},
     [("A gap longer than six months needs a written explanation.", "written explanation", "new application")],
     "paraphrase"),
    ("How many months of payments must I keep in the bank for a rental I'm buying?", {"reserves": 2},
     [("An investment property needs reserves of six months of payments.", "six months", "two months")], "paraphrase"),
    ("If you decline me, how long until I get the letter?", {"adverse_action": 2},
     [("The adverse action notice arrives within 30 days.", "30 days", "90 days")], "paraphrase"),
    ("Who orders the valuation of the house?", {"appraisal": 2},
     [("The independent appraisal is ordered through Acme Home Loans.", "through Acme Home Loans",
       "by the buyer's own agent")], "paraphrase"),
    ("Is my DTI counted with or without the new mortgage?", {"dti_limit": 2},
     [("DTI includes the new mortgage payment.", "includes the new mortgage payment",
       "excludes the new mortgage payment")], "paraphrase"),
    ("What's the maximum loan-to-value for the home I'll live in?", {"ltv_limit": 2},
     [("The maximum LTV for a primary residence is 95%.", "95%", "80%")], "direct"),
    ("I'm self-employed. How do you count my income?", {"employment": 2, "documents": 1},
     [("Self-employed income is the 24-month average of net business income from tax returns.", "24-month average",
       "12-month average")], "paraphrase"),
    ("If you turn me down, will you tell me why?", {"adverse_action": 2},
     [("The notice states up to four specific principal reasons.", "four", "ten")], "paraphrase"),
    ("Could my age or being divorced count against me?", {"fair_lending": 2},
     [("Credit decisions never consider age or marital status.", "never consider", "may consider")], "paraphrase"),
    ("What is your maximum debt-to-income ratio?", {"dti_limit": 2},
     [("The maximum DTI is 43%.", "43%", "41%")], "freshness"),
    ("What credit score do I need?", {"credit_score": 2},
     [("The minimum credit score is 640.", "640", "620")], "direct"),
    ("How long can I lock my rate for?", {"rate_lock": 2},
     [("A rate can be locked for 45 days once the application is complete.", "45 days", "60 days")], "direct"),
    ("What's the minimum down payment on a home I'll live in?", {"products": 2},
     [("The minimum down payment for a primary residence is 5%.", "5%", "10%")], "direct"),
    ("How quickly will I hear back about a pre-approval?", {"timelines": 2},
     [("Pre-approval decisions come back within two business days.", "two business days", "five business days")],
     "paraphrase"),
    ("Can I buy a manufactured home on leased land with you?", {"property_types": 2},
     [("Manufactured homes on leased land are not eligible.", "not eligible", "eligible")], "direct"),
    ("I'm buying a rental with 20% down. Is that within your LTV limit, and how much must I keep in reserves?",
     {"ltv_limit": 2, "reserves": 2},
     [("The maximum LTV for an investment property is 75%, so 20% down is over the limit.", "75%", "85%"),
      ("An investment property needs six months of reserves.", "six months", "two months")], "multi"),
    ("With 10% down on my main home, will I need PMI, and am I inside the LTV limit?", {"pmi": 2, "ltv_limit": 2},
     [("PMI is required when the LTV is above 80%.", "80%", "90%"),
      ("The maximum LTV for a primary residence is 95%.", "95%", "85%")], "multi"),
    ("What's the maximum DTI, and how do you estimate the mortgage payment that goes into it?",
     {"dti_limit": 2, "payment_estimate": 2},
     [("The maximum DTI is 43%.", "43%", "41%"),
      ("The payment is estimated at a 6.5% fixed rate over 30 years.", "6.5%", "7.5%")], "multi"),
    # The policy says nothing about these: the right answer says so.
    ("Do you charge a fee if I pay off my mortgage early?", {}, [], "unanswerable"),
    ("Do you lend on homes in Canada?", {}, [], "unanswerable"),
    ("What is the phone number of your Denver branch?", {}, [], "unanswerable"),
    ("Are your branches open on Saturdays?", {}, [], "unanswerable"),
    ("Is there a rate discount if I set up autopay?", {}, [], "unanswerable"),
    ("What is the late payment fee?", {}, [], "unanswerable"),
]


def golden_rows() -> list[dict]:
    """The golden questions with stable ids q01…q36."""
    return [{"qid": f"q{i:02d}", "question": q, "relevant": rel, "facts": facts, "kind": kind}
            for i, (q, rel, facts, kind) in enumerate(GOLDEN, 1)]
