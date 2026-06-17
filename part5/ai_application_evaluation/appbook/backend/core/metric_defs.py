"""Human-readable definitions for every evaluation metric, surfaced in the UI when
a metric chip is clicked. Each entry: family (how it's computed), what it measures,
which direction is "good", and an optional formula.
"""
from __future__ import annotations

# family → {label, blurb} for the little badge + one-line "how it's computed".
FAMILIES = {
    "heuristic":   {"label": "Heuristic",        "blurb": "a cheap, deterministic rule — no LLM"},
    "ir":          {"label": "IR metric",        "blurb": "classic information-retrieval math over ranked results"},
    "llm-judge":   {"label": "LLM-as-judge",     "blurb": "Claude grades the output against a rubric"},
    "template":    {"label": "LangSmith template", "blurb": "a ready-made LangSmith LLM-as-judge evaluator"},
    "exact":       {"label": "Exact match",      "blurb": "compares the prediction to a gold label"},
    "trajectory":  {"label": "Trajectory",       "blurb": "scores the agent's path of tool calls"},
    "outcome":     {"label": "Outcome / executed", "blurb": "runs the artifact and checks the real result"},
}

# want: "high" (↑ better), "low" (↓ better — a risk), "detector" (should fire on the bad input)
METRICS = {
    "abstention_heuristic": {"family": "heuristic", "want": "high",
        "def": "A keyword check: did the answer contain a hedge ('I don't have…') exactly when it should have abstained? Cheap and deterministic, but fooled by phrasing."},
    "abstention_judge": {"family": "llm-judge", "want": "high",
        "def": "An LLM judge reads the answer, decides whether it ABSTAINED or ANSWERED, and checks that against what the question warranted. Robust to wording."},
    "memory_recall": {"family": "template", "want": "high",
        "def": "LangSmith 'Knowledge Retention': did the reply use a fact stated earlier in the conversation? Measures whether multi-turn memory actually worked."},
    "recall@3": {"family": "ir", "want": "high", "formula": "recall@k = |relevant ∩ top-k| / |relevant|",
        "def": "Did a relevant document make the top-3? The key RAG metric: if the right doc isn't retrieved, no answer can be grounded in it."},
    "mrr": {"family": "ir", "want": "high", "formula": "MRR = mean(1 / rank of first relevant doc)",
        "def": "How high did the first relevant doc rank? Rewards putting the right document first."},
    "precision@10": {"family": "ir", "want": "high", "formula": "precision@k = |relevant ∩ top-k| / k",
        "def": "Of the top-10 returned, what fraction are relevant. Capped near 0.1 when a query has ~1 relevant doc — read it in context."},
    "recall@10": {"family": "ir", "want": "high", "formula": "recall@k = |relevant ∩ top-k| / |relevant|",
        "def": "Of all documents that should have been found, what fraction made the top-10. The headline coverage metric for retrieval."},
    "NDCG@10": {"family": "ir", "want": "high", "formula": "DCG@k = Σ rel_i / log₂(i+1);  NDCG = DCG / IDCG",
        "def": "Rank-aware quality: a hit at rank 1 is worth more than the same hit at rank 5. Normalized so 1.0 = a perfect ranking."},
    "correctness": {"family": "template", "want": "high",
        "def": "LangSmith 'Correctness': does the answer match a known-good reference — the same key facts, wording aside?"},
    "context_relevance": {"family": "template", "want": "high",
        "def": "RAG triad #1 — is the RETRIEVED CONTEXT relevant to the question? Grades retrieval: irrelevant context is where hallucinations sneak in. Reference-free (TruLens/RAGAS)."},
    "groundedness": {"family": "llm-judge", "want": "high",
        "def": "RAG triad #2 — is EVERY claim in the answer supported by the retrieved context (no hallucination)? Separates a retrieval problem from a generation problem."},
    "hallucination": {"family": "template", "want": "low",
        "def": "LangSmith 'Hallucination': does the answer assert any fact NOT supported by the context? A risk score — lower is better, 0 is ideal."},
    "answer_relevance": {"family": "template", "want": "high",
        "def": "RAG triad #3 — is the output on-topic and actually addressing the question that was asked? (also a LangSmith 'Answer Relevance' template)"},
    "category_match": {"family": "exact", "want": "high", "formula": "score = 1 if pred == gold else 0",
        "def": "Exact match: did the classifier's category equal the gold label? Deterministic and free."},
    "urgency_match": {"family": "exact", "want": "high", "formula": "score = 1 if pred == gold else 0",
        "def": "Exact match on the urgency label. Per-field scoring localizes which part of the classifier drifts."},
    "helpfulness": {"family": "llm-judge", "want": "high",
        "def": "Does the drafted reply clearly and directly address the customer's question with a usable answer?"},
    "prompt_injection": {"family": "template", "want": "detector",
        "def": "LangSmith 'Prompt Injection': does the INPUT try to override instructions, exfiltrate the system prompt, or jailbreak? A detector — it should fire on attacks, stay 0 on benign input."},
    "pii_leakage": {"family": "template", "want": "low",
        "def": "LangSmith 'PII Leakage': does the OUTPUT disclose personal data (names + emails + addresses, etc.)? A risk score — want 0."},
    "toxicity": {"family": "template", "want": "low",
        "def": "LangSmith 'Toxicity': is the OUTPUT insulting, hateful, or harassing? A risk score — want 0."},
    "final_response": {"family": "llm-judge", "want": "high",
        "def": "Lens 1 — final response: did the agent's end reply satisfy the goal (correct, grounded, escalating only when warranted)?"},
    "trajectory_subseq": {"family": "trajectory", "want": "high", "formula": "fraction of expected tools found, in order",
        "def": "Lens 2 — trajectory: how many of the expected tool calls appear, in order, in what the agent actually did. Gives partial credit for a partly-right path."},
    "exact_tool_set": {"family": "trajectory", "want": "high",
        "def": "Lens 2 — trajectory: did the SET of tools used exactly equal the expected set — nothing missing, nothing extra?"},
    "correct_first_tool": {"family": "trajectory", "want": "high",
        "def": "Lens 3 — single step: did the agent pick the right FIRST tool (e.g. search the docs before answering)?"},
    "no_unwarranted_action": {"family": "trajectory", "want": "high",
        "def": "Lens 3 — single step: did it avoid every forbidden tool (e.g. NOT open a support ticket on a pure information request)?"},
    "tool_selection": {"family": "template", "want": "high",
        "def": "LangSmith 'Tool Selection': did the agent choose the right tools for the task — the needed ones, none wrong or wasteful?"},
    "trajectory_accuracy": {"family": "template", "want": "high",
        "def": "LangSmith 'Trajectory Accuracy': was the path logical, progressive, and efficient — no wasteful, circular, or out-of-order steps?"},
    "runs_clean": {"family": "outcome", "want": "high",
        "def": "Did the CLI the agent wrote exit 0 when WE ran it ourselves on this batch (including a batch it never saw at build time)?"},
    "functional_correctness": {"family": "outcome", "want": "high",
        "def": "Do the report's category/priority counts match a breakdown we computed independently in plain Python? Execution is the ultimate evaluator."},
    "code_quality": {"family": "llm-judge", "want": "high",
        "def": "An LLM judge on the source: standard-library only, validates input, no hardcoded paths, documented."},
}


def catalog() -> dict:
    """The metric + family catalog the UI uses to explain chips on click."""
    return {"families": FAMILIES, "metrics": METRICS}
