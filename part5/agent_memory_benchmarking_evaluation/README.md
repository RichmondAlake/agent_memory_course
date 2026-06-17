# Agent Memory Benchmarking — OAMP vs Naive Memory

How should an agent **remember**? Re-send the whole conversation every turn, or persist it
and retrieve only what matters? This module **benchmarks the trade-off** head-to-head on
**Claude Opus 4.8** and **Oracle AI Agent Memory (OAMP)**, in **two surfaces**:

- a **📓 notebook** ([`notebook/oracle_agent_memory_benchmarks.ipynb`](notebook/oracle_agent_memory_benchmarks.ipynb))
  that measures **naive (full-history)** vs **OAMP (retrieved context card)** vs a
  **cache-friendly hybrid** across four benchmarks, and
- a **🚀 appbook** ([`appbook/`](appbook/), port **8004**) — a four-stop **progressive
  journey** (Naive → Oracle Agent Memory → live Head-to-Head → Pick Any Two).

## The four benchmarks

| # | Benchmark | The finding |
|---|---|---|
| 1 | **Token consumption** | Naive grows linearly; OAMP stays flat (a fixed-size context card). |
| 2 | **Latency** | Naive stays cheap via **Anthropic prompt caching**; OAMP-basic pays for inline extraction. |
| 3 | **Response quality** | An LLM-as-judge (`claude-opus-4-8`) scores both, blind. |
| 4 | **A cache-friendly hybrid** | Recover low latency *and* durable memory — by giving the token savings back. |

The lesson: agent memory is a choice among **low tokens, low latency, durable memory** — you
can cleanly have any **two**.

## Stack & run

- **Agents + judge:** `claude-opus-4-8`. **Off-critical-path work** (compaction, offline batch
  extraction): `claude-haiku-4-5`. **OAMP's extraction LLM:** routed via LiteLLM's `anthropic/`
  provider. **Embeddings:** local open-source **`nomic-embed-text-v1.5`** (768-dim, via
  `fastembed` — Anthropic has no embeddings API). **Storage:** Oracle AI Database 26ai.

```bash
# Notebook: run in the `oracle_demos` env (Jupyter or nbconvert). Set ANTHROPIC_API_KEY.
# Appbook:
cd appbook
cp .env.example .env          # add ANTHROPIC_API_KEY
./run.sh                      # → http://127.0.0.1:8004
# (memory_substrate_evaluation also defaults to 8004 — set PORT=8005 to run both at once)
```

See [`appbook/README.md`](appbook/README.md) for the four stops, the live-benchmark design,
and the OAMP isolation details.
