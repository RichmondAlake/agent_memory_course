# Memory Substrate Evaluation — Filesystem vs Oracle AI Database

Once you've decided an agent *needs* memory, **where do you store it?** A folder of markdown
files is the tempting default. This module puts that choice to the test — the **filesystem**
(markdown files) vs the **Oracle AI Database** (rows + a vector column) as an agent-memory
**substrate** — and measures where each one wins and where it quietly breaks. Two surfaces:

- a **📓 notebook** ([`memory_substrate_evaluation.ipynb`](memory_substrate_evaluation.ipynb))
  that runs the benchmarks from first principles, and
- a **🚀 appbook** ([`appbook/`](appbook/), port **8004**) — a five-step guided progression
  over the same comparison, scored live.

## What gets measured

| Step | The comparison |
|---|---|
| **1 · Two Substrates** | An identical corpus of synthetic agent-memory notes, held as files vs as DB rows + vectors. |
| **2 · Write & Ingest** | **Write latency** — an instant file write vs embed-and-index. |
| **3 · Retrieval** | The headline: **literal keyword search** (files) vs **semantic vector search** (database). Paraphrased questions expose where `grep` goes blind. |
| **4 · Concurrency & ACID** | Race concurrent writers: a naive file loses writes, a locked file is safe-with-effort, a real database loses nothing by default. |
| **5 · Scorecard** | When to reach for files, when for a database — with your own measured numbers. |

## Stack & run

- **Embeddings:** local open-source **`nomic-embed-text-v1.5`** (768-dim, via `fastembed` — no
  API key). **Database:** Oracle AI Database Free (native `VECTOR` + `VECTOR_DISTANCE`), with an
  in-memory NumPy fallback for retrieval and SQLite for the ACID race. **Model:** Claude
  **`claude-opus-4-8`** — used only for the optional "answer from retrieved context" payoff in
  Step 3; everything else runs without a key.

```bash
# Notebook: run in the `oracle_demos` env (Jupyter or nbconvert).
# Appbook:
cd appbook
cp .env.example .env          # all keys optional — embeddings are local
./run.sh                      # → http://127.0.0.1:8004
```

The benchmark design is informed by the agent-memory architecture in the **Generative Agents**
paper (Park et al., 2023) — see the linked arXiv reference rather than a committed copy. The
full step-by-step walkthrough is in [`appbook/README.md`](appbook/README.md).
