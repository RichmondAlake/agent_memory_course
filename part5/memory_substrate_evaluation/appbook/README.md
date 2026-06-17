# Memory Substrate Evaluation — Appbook

An interactive companion to the `memory_substrate_evaluation` notebook. It puts the
two agent-memory substrates side by side and runs the notebook's key benchmarks live,
as a guided progression:

| Step | What it shows |
|------|---------------|
| **1 · Two Substrates** | The filesystem (markdown files) vs the Oracle AI Database (rows + vector column), holding an identical corpus of synthetic agent-memory notes. |
| **2 · Write & Ingest** | Write the corpus into both and compare **write latency** — an instant file write vs embed-and-index. |
| **3 · Retrieval** | The headline: **literal keyword search** (filesystem) vs **semantic vector search** (database). Paraphrased questions expose where grep goes blind. |
| **4 · Concurrency & ACID** | Race concurrent writers: a naive file loses writes, a locked file is safe-with-effort, a real database loses nothing by default. |
| **5 · Scorecard** | When to reach for files, when to reach for a database — with your own measured numbers. |

## Stack

- **Agent / judge LLM:** Anthropic **Claude Opus 4.8** (only for the optional "answer from retrieved context" payoff in Step 3).
- **Embeddings:** open-source **nomic-embed-text-v1.5** (768-dim) via `fastembed` — local, torch-free, no API key.
- **Database:** Oracle AI Database Free (native `VECTOR` + `VECTOR_DISTANCE`). Falls back to an in-memory NumPy index if Oracle is unreachable; the ACID race falls back to SQLite. The active backend is shown in the sidebar.

## Run

```bash
cd appbook
./run.sh            # → http://127.0.0.1:8004  (activates the oracle_demos conda env)
```

Ports across Part 5: `8001` AI Maturity Ladder · `8002` Agent Memory · `8003` AI Application Evaluation · **`8004` Memory Substrate Evaluation**.

## Configuration

All optional — copy `.env.example` to `.env` (or reuse the notebook folder's `.env` one level up):

- `ANTHROPIC_API_KEY` — only powers the Step 3 grounded-answer payoff; everything else runs without it.
- `ORACLE_*` — point at the local Oracle Free container. If omitted/unreachable, the app uses its in-memory fallbacks and still runs end to end.

Embeddings are always local (nomic) — there is no embedding key to set.
