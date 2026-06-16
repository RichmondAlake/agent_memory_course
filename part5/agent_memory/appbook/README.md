# The Agent Memory Stack — App

A FastAPI + vanilla-JS application that turns the
[`agent_memory_zero_to_hero.ipynb`](../agent_memory_zero_to_hero.ipynb) workshop into an
interactive, sleek (light/dark) web app. The sidebar is the **memory stack**: each layer adds
one capability, climbing from a single conversation to a coordinating multi-agent team. It is
powered by **[memorizz](https://pypi.org/project/memorizz/)** on **Oracle AI Database** (with a
filesystem fallback), exactly like the notebook.

| # | Memory layer | Page | What it shows |
|---|--------------|------|----------------|
| 1 | **Conversation** | `#/conversation` | Episodic `CONVERSATION_MEMORY`; remembers across turns and across a restart (`MemAgent.load`). |
| 2 | **Persona & Entities** | `#/semantic` | Semantic memory: a stable `PERSONAS` identity + structured `ENTITY_MEMORY` facts. |
| 3 | **Knowledge Base** | `#/knowledge` | RAG over a `KnowledgeBase` (vector search) + a grounded, cited answer. |
| 4 | **Procedural** | `#/procedural` | Tools (`TOOLBOX`) + a recalled `WORKFLOW_MEMORY` runbook + a skillbox manifest. |
| 5 | **Coordination** | `#/coordination` | `SHARED_MEMORY`: a lead + Researcher + Reviewer collaborating, via `MultiAgentOrchestrator`. |

## Run

```bash
# from this directory
./run.sh
# → http://127.0.0.1:8000
```

`run.sh` activates the **`oracle_demos`** conda env if present, installs the requirements on
first run, and starts uvicorn. Or manually:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000   # run from appbook/
```

> [!IMPORTANT]
> **In a Codespace, open the app from the Ports panel → 🌐 Open in Browser.** Confirm it's up with
> `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/health` (`200` = up).

## Requirements & graceful degradation

- **`OPENAI_API_KEY`** — required (the LLM `gpt-5.5` **and** the embeddings
  `text-embedding-3-small` @ 256d). Read from `appbook/.env`, or the
  course's existing `../.env` / `../../.env`.
- **Oracle AI Database** — optional. The app builds a memorizz `OracleProvider` (auto-creating
  its memory stores). If Oracle is unset or unreachable it falls back to memorizz's
  **`FileSystemProvider`** (FAISS) under `~/.memorizz_appbook`, so the whole app still runs. The
  active backend is shown in the sidebar and on each page.

## Architecture

```
appbook/
├── backend/
│   ├── main.py              FastAPI app; warms the Memory Core; serves the SPA
│   ├── config.py            env loading, model, embeddings, Oracle creds
│   ├── schemas.py           Pydantic request bodies
│   ├── core/
│   │   ├── memory.py        the Memory Core: memorizz provider (Oracle→filesystem) + helpers
│   │   ├── knowledge.py     the Acme Cloud corpus, ingested via KnowledgeBase
│   │   └── sse.py           EventSourceResponse helper
│   └── routers/             one per memory layer + /api/health
└── frontend/                index.html · styles.css · app.js (no build step)
```

Every layer streams its output to the browser over Server-Sent Events. The frontend is a
dependency-free single-page app (hash router, theme toggle, SSE-over-`fetch`). The backend uses
memorizz primitives throughout — `MemAgent`, `Persona`, `EntityMemory`, `KnowledgeBase`,
`Toolbox`/`Workflow`, and `MultiAgentOrchestrator` — the same APIs taught in the notebook.
