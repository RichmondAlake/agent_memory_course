# Application Modes — App

A FastAPI + vanilla-JS application that turns the three
[`application_modes`](../) notebooks into an interactive, sleek (light/dark) web
app. The sidebar lists the three operational modes a memory-backed agent can
take; each page **explains** the mode and **demos** it live, with a right-hand
**Memory panel** that fills as records are recalled and written to
[Oracle AI Agent Memory](https://www.oracle.com/database/ai-agent-memory/).

| # | Mode | Page | Memory profile | What it shows |
|---|------|------|----------------|----------------|
| 1 | **Assistant** | `#/assistant` | short-term context **+ long-term preference retrieval** | A turn-by-turn ops copilot that recalls `preference` / `memory` records before each reply, then writes the turn back. |
| 2 | **Workflow** | `#/workflow` | **working state + tool outputs** | A mortgage pipeline (identity → credit → income → DTI → decide) that recalls policy (`fact` / `guideline`) and writes an audit `memory` per stage. |
| 3 | **Deep Research** | `#/research` | **episodic + semantic + working** | A research analyst that recalls prior `fact` findings, searches the web, synthesises a cited answer, saves new findings, and consolidates a digest. |

## Run

```bash
# from this directory
./run.sh
# → http://127.0.0.1:8000
```

`run.sh` activates the **`oracle_demos`** conda env (which already has
`oracleagentmemory`, `oracledb`, `anthropic`, `openai`, `tavily-python`) and
installs the web-server packages (`fastapi`, `uvicorn`, `sse-starlette`,
`python-dotenv`) if missing. Or manually:

```bash
conda activate oracle_demos
pip install "fastapi>=0.110" "uvicorn>=0.27" "sse-starlette>=2.0" "python-dotenv>=1.0" "fastembed>=0.8"
uvicorn backend.main:app --reload --port 8000   # run from appbook/
```

## Requirements & graceful degradation

- **`ANTHROPIC_API_KEY`** — the only key the app needs. Runs every mode's LLM work
  *and* Oracle AI Agent Memory's extraction/summary helper (`claude-sonnet-4-6`).
  Read from `appbook/.env`, or the course's existing `../.env` / `../../.env`.
  Model defaults to `claude-opus-4-8`. **No OpenAI key anywhere.**
- **Embeddings are local & open-source** — `nomic-embed-text-v1.5` (768-dim) via
  `fastembed` (ONNX, torch-free). No key, no network call.
- **Oracle AI Database** — optional but recommended. When reachable, the app uses
  **Oracle AI Agent Memory** (Oracle stores the records; nomic supplies the
  vectors). If unreachable, memory falls back to an **in-process keyword store** —
  the app still runs fully, and the sidebar shows which backend is live.
- **`TAVILY_API_KEY`** — optional. Enables live web search in Deep Research; without
  it, that mode answers from model knowledge + memory only.

## Architecture

```
appbook/
├── backend/
│   ├── main.py              FastAPI app; warms memory; serves the SPA
│   ├── config.py            env loading, model, OpenAI/Oracle/Tavily creds
│   ├── schemas.py           Pydantic request bodies
│   ├── core/
│   │   ├── anthropic_client.py   shared client, text_of, structured_json
│   │   ├── memory.py             MemoryStore: Oracle AI Agent Memory + in-process fallback
│   │   ├── websearch.py          Tavily wrapper (optional)
│   │   └── sse.py                EventSourceResponse helper
│   └── routers/             one per mode + /api/health
└── frontend/                index.html · styles.css · app.js (no build step)
```

All three modes stream their output to the browser over Server-Sent Events, and
every routine emits explicit `memory_recall` / `memory_write` events so the UI
can show exactly what the agent read from and wrote to memory. The frontend is a
dependency-free single-page app (hash router, theme toggle, SSE-over-`fetch`).

> The notebooks implement each mode in a different framework (Claude Agent SDK,
> LangGraph, OpenAI Agents). This app re-presents the *modes and their memory
> profiles* through one unified runtime so they can be compared side by side —
> the constant across all three is **Oracle AI Agent Memory**.
