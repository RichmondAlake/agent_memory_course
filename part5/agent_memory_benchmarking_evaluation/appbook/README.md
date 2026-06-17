# Agent Memory Benchmarks — App

A FastAPI + vanilla-JS app that turns the companion
[`oracle_agent_memory_benchmarks.ipynb`](../notebook/oracle_agent_memory_benchmarks.ipynb)
notebook into a live, four-stop **journey** through agent memory — naive vs.
Oracle Agent Memory (OAMP) — measured on **Claude Opus 4.8** and **Oracle AI
Database 26ai**. The sidebar is the path; each stop adds one idea.

| # | Stop | Page | What it shows |
|---|------|------|----------------|
| — | **Overview** | `#/` | The memory trilemma — low tokens vs low latency vs durable memory — and the path. |
| 1 | **Naive Memory** | `#/naive` | Chat where "memory" = the full message list re-sent each turn; the context-window meter climbs. |
| 2 | **Oracle Agent Memory** | `#/memory` | The same model, but each turn persists to Oracle, extracts durable facts, and retrieves a small **context card**. Watch the memory store fill. |
| 3 | **Head-to-Head** | `#/benchmark` | A scripted conversation through both agents at once — live token & latency charts plus an LLM-as-judge quality verdict. |
| 4 | **Pick Any Two** | `#/patterns` | The central trade-off, the cache-friendly hybrid, offline extraction, and the recommended production pattern. |

## Run

```bash
# from this directory
./run.sh
# → http://127.0.0.1:8004
```

`run.sh` activates the **`oracle_demos`** conda env (Python 3.11), which already
has `oracleagentmemory`, `anthropic`, `litellm`, `fastembed`, `oracledb`,
`fastapi`, `uvicorn`, and `sse-starlette`. Or manually:

```bash
conda activate oracle_demos
uvicorn backend.main:app --reload --port 8004   # run from appbook/
```

## Requirements & graceful degradation

- **`ANTHROPIC_API_KEY`** — required. Read from `appbook/.env` (gitignored), or
  the workshop's `../.env` / `../../.env`. Models default to `claude-opus-4-8`
  (agents + judge) and `claude-haiku-4-5` (extraction).
- **Oracle AI Database** — required for stops 2 & 3 (OAMP needs vector storage).
  The app connects to the local `oracle-free` container (VECTOR/FREEPDB1) and
  warms the embedder + connection in the background on startup; the sidebar shows
  the status. **Stop 1 (naive) works without Oracle.** Embeddings are generated
  locally with the open-source `nomic-embed-text-v1.5` model — no OpenAI key.

## Architecture

```
appbook/
├── backend/
│   ├── main.py            FastAPI app; warms OAMP in the background; serves the SPA
│   ├── config.py          env loading, models, Oracle creds, embed model
│   ├── core_anthropic.py  shared Claude client + call_claude (caching + retries)
│   ├── memory_core.py     the OAMP layer — embedder, client, per-thread step()
│   ├── sse.py             EventSourceResponse helper
│   ├── schemas.py         Pydantic request bodies
│   └── routers/           meta · naive · memory · benchmark
└── frontend/              index.html · styles.css · app.js (no build step)
```

Every interactive stop streams over Server-Sent Events. The frontend is a
dependency-free single-page app (hash router, theme toggle, SSE-over-`fetch`,
inline-SVG charts).

> **Note on the live benchmark.** Stop 3 runs a short (~8-turn) scripted
> conversation so it finishes in a couple of minutes; the notebook runs the full
> 30. Because OAMP does inline extraction, its turns are slower than naive's —
> that latency *is* one of the things being measured.
