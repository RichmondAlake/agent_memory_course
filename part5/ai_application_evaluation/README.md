# AI Application Evaluation — Measuring Every Rung of the Ladder

Where [`ai_maturity_form_factors/`](../ai_maturity_form_factors/) **builds** the five form
factors, this module **evaluates** them — Chatbot → RAG → Workflow → Agent → Autonomous
Agent — each with the metric that fits how it actually fails. Shipped in **two surfaces**:

- a **📓 notebook** ([`notebook/ai_application_evaluation_notebook.ipynb`](notebook/ai_application_evaluation_notebook.ipynb))
  that derives each evaluator from first principles and uploads the datasets, targets, and
  evaluators as **versioned LangSmith experiments**, and
- a **🚀 appbook** ([`appbook/`](appbook/), port **8003**) that runs the same evaluators
  **live in the browser**, streaming one result per example and then aggregate scorecards.

Every evaluation follows the LangSmith shape — **dataset → target → evaluators → experiment**.

## What gets measured

| Rung | The lens |
|---|---|
| **FF1 Chatbot** | honesty / **abstention** on unknown data; **stateless vs. with-history** memory (the cost of statelessness); safety templates — prompt injection, PII leakage, toxicity |
| **FF2 RAG** | recall@k / MRR; **correctness + the RAG triad** (context relevance, groundedness, answer relevance); a **BEIR** bake-off (scifact + FiQA) — precision / recall / NDCG@10 |
| **FF3 Workflow** | category / urgency exact-match; reply helpfulness & groundedness |
| **FF4 Agent** | LangSmith's three lenses — **final response**, **trajectory**, **single step** — plus tool-selection & trajectory-accuracy templates |
| **FF5 Autonomous Agent** | **functional correctness** (run the generated CLI vs. independent ground truth) + a code-quality judge |

## Stack & run

- **Model under test *and* LLM-as-judge:** Claude **`claude-opus-4-8`**. **Retrieval:** Oracle
  AI Database (`VECTOR` + Oracle Text), with an in-memory NumPy fallback. **Agents:**
  `claude-agent-sdk` (FF4/FF5 need the `claude` CLI on PATH). **Evaluation framework:**
  LangSmith (optional — every metric is also computed locally).

```bash
# Notebook: open it in Jupyter (oracle_demos env) and run top-to-bottom.
# Appbook:
cd appbook
cp .env.example .env          # add ANTHROPIC_API_KEY (LANGSMITH_API_KEY optional)
PORT=8003 ./run.sh            # → http://127.0.0.1:8003
```

See [`appbook/README.md`](appbook/README.md) for the full evaluator catalog, the BEIR seed,
and the FF5 sandbox details.
