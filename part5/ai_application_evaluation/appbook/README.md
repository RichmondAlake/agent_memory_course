# AI Application Evaluation — Appbook

A full-stack companion to the **AI Maturity Ladder** app. Where that app *builds* the five
form factors, this one **evaluates** them — chatbot, RAG, workflow, agent, autonomous agent —
each with the metric that fits how it actually fails, scored **live** in the browser.

It is the interactive counterpart to `../notebook/ai_application_evaluation_notebook.ipynb`:
same systems under test (Oracle-backed retrieval, Claude Opus 4.8 as the model **and** the
LLM-as-judge, the `claude-agent-sdk`), same evaluators, streamed over SSE.

## What it shows

| Rung | Page | Evaluators (the lens) |
|---|---|---|
| FF1 Chatbot | **Chatbot** | honesty / **abstention** on unknown data (heuristic + judge); memory **stateless vs. with-history** — the cost of statelessness; **safety templates** — Prompt Injection, PII Leakage, Toxicity |
| FF2 RAG | **RAG** | recall@k / MRR (heuristic); **correctness + the RAG triad** — context relevance, groundedness, answer relevance (judge); **BEIR** bake-off (scifact + FiQA) — precision/recall/NDCG@10 |
| FF3 Workflow | **Workflow** | category/urgency exact-match (heuristic); reply helpfulness & groundedness (judge) |
| FF4 Agent | **Agent** | LangSmith's three lenses — **final response**, **trajectory** (subsequence + exact tool set), **single step** (first tool, no wrong action) — plus the **Tool Selection** & **Trajectory Accuracy** templates |
| FF5 Autonomous Agent | **Autonomous Agent** | **functional correctness** (run the generated CLI vs. independent ground truth, incl. an unseen batch) + code-quality judge |

Every evaluation follows the LangSmith shape — **dataset → target → evaluators → experiment** —
and streams one result per example as it lands, then aggregate metric cards. **Click any metric chip**
(or scorecard label) to see that metric's definition, which direction is "good", its formula, and a
small visual depiction of how it's computed.

The Chatbot page runs the *stateless* memory check **before** the *with-history* one, so the gap
between them (recall ~0 → ~1) quantifies what conversation memory actually buys.

## Run

```bash
cd part5/ai_application_evaluation/appbook
cp .env.example .env          # add your ANTHROPIC_API_KEY (LangSmith key optional)
PORT=8003 bash run.sh         # → http://127.0.0.1:8003   (8001 = ladder, 8002 = agent memory)
```

`run.sh` activates the **`oracle_demos`** conda env (which has every dependency) and starts
uvicorn. It connects to the local Oracle AI Database (`VECTOR`/`FREEPDB1`); if Oracle is
unreachable, retrieval transparently falls back to an in-memory NumPy index. The active
backend, agent-SDK availability, and LangSmith status are shown in the bottom-left status card.

## Credentials

- **`ANTHROPIC_API_KEY`** — required (the model under test **and** the judge).
- **`LANGSMITH_API_KEY`** — optional. The app computes every metric locally regardless; the
  notebook is where the same datasets/targets/evaluators upload as versioned LangSmith
  experiments. The bottom-left status card validates the key on startup and shows one of
  **on** (authenticated), **key set · unauthorized** (present but rejected — re-issue it), or
  **local-only** (no key).
- **Oracle** (optional) — `ORACLE_ENABLED/USER/PASSWORD/DSN`; falls back to in-memory if absent.

## Notes

- **FF4 / FF5 need the `claude` CLI** on PATH (`npm i -g @anthropic-ai/claude-code`). Without it,
  those two pages report the SDK as unavailable; FF1–FF3 and the BEIR bake-off still work.
- **BEIR** loads the precomputed corpus + 768-dim vectors from
  `../notebook/data/beir_scifact_seed.npz` (skipping the ~11-minute embed) and pulls the tiny
  queries + qrels from the Hugging Face Hub. Retrieval for the bake-off runs in-memory over the
  seed; the notebook runs the identical comparison against Oracle `beir_docs`.
- **FF5 executes code** (`Bash`/`Write`/`Edit`) with permissions bypassed, confined to a local
  sandbox directory (default `/tmp/aieval-ff5-workspace`, override with `AIEVAL_SANDBOX`). The
  sandbox is a neutral path on purpose, so the builder agent works in place rather than guessing a
  project root. That code execution is the point of the demo — keep it local.

## Layout

```
backend/
  main.py                 FastAPI app — mounts routers, warms the retriever, serves the SPA
  config.py               settings (Anthropic, LangSmith, Oracle, BEIR seed) from .env
  core/
    evaluation.py         FF1–FF3 engine: judge, datasets, targets, evaluators, suite registry
    beir.py               FF2 BEIR bake-off over the seed (precision/recall/NDCG)
    agent_eval.py         FF4 trajectory eval + FF5 functional/outcome eval
    retrieval.py          Oracle (or in-memory) vector/keyword/hybrid store — the system under test
    anthropic_client.py   shared Claude client + structured-output judge helper
    agent_runtime.py      normalizes the agent SDK stream into SSE events (hides ToolSearch)
  routers/                meta · suites (FF1–3) · benchmark (BEIR) · agentff (FF4/5) · images
frontend/                 vanilla-JS SPA (hash router, SSE-over-fetch, live score tables)
```
