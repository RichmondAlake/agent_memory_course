# Part 5 — Agentic AI Applications on Oracle AI Database

The "put it all together" part of the course. Part 5 contains **three self‑contained
modules**, each teaching a different facet of building real agentic AI applications —
and each shipped in **two surfaces**:

- a **📓 notebook** that builds every concept up from first principles, cell by cell, and
- an **🚀 appbook** — a companion web app (FastAPI + dependency‑free vanilla JS, with
  server‑sent‑event streaming and a light/dark theme) that shows those same concepts
  running as a real, interactive application.

> **notebook = learn it from first principles · appbook = see it as a production app.**
> Start with the notebook, then open the appbook to see the same ideas wired into a UI.

Everything runs on the latest **Claude** models and **Oracle AI Database** (native
vector + full‑text + graph search, and Oracle AI Agent Memory), with **graceful
fallbacks** so each piece still runs if the database — or an API key — isn't available.

---

## The three modules

| Module | Teaches | Notebook(s) | Built on |
|---|---|---|---|
| [`ai_maturity_form_factors/`](ai_maturity_form_factors/) | The **AI maturity ladder** — five form factors, each adding one capability: **Chatbot → RAG → Workflow → Agent → Autonomous Agent** | `ai_maturity_form_factors_notebook.ipynb` | Claude Agent SDK · Oracle **vector / text / graph** retrieval |
| [`agent_memory/`](agent_memory/) | The **agent memory stack** — conversation, persona & entities, knowledge base, procedural, multi‑agent coordination | `agent_memory_zero_to_hero.ipynb` | **[memorizz](https://pypi.org/project/memorizz/)** · Oracle (FAISS fallback) · OpenAI |
| [`application_modes/`](application_modes/) | The **three operational modes** of a memory‑backed agent — **Assistant · Workflow · Deep Research** | `assistant_supply_chain_claude_agent_sdk.ipynb`, `workflow_mortgage_langgraph.ipynb`, `deep_research_openai_agents.ipynb` | **Oracle AI Agent Memory** (`oracleagentmemory`) · Claude |

### 1. `ai_maturity_form_factors/` — the ladder
One running example (a support assistant for the fictional **Acme Cloud**) built **five
different ways**, each rung adding exactly one capability over the last. The RAG rung goes
deep on Oracle: native `VECTOR` columns, an **HNSW** index, **Oracle Text**, and side‑by‑side
**keyword / vector / hybrid (RRF) / graph (SQL property graph)** retrieval. The top rungs use
the **Claude Agent SDK** for tool‑using and code‑writing agents. See
[`ai_maturity_form_factors/README.md`](ai_maturity_form_factors/README.md).

### 2. `agent_memory/` — the memory stack
Builds a memory‑augmented copilot **one memory type at a time** with the **memorizz** library:
episodic conversation, semantic persona/entities, a vector knowledge base, procedural
tools/runbooks, and shared memory for a coordinating multi‑agent team. Uses **OpenAI**
(`gpt-5.5` + embeddings) on Oracle, with a filesystem/FAISS fallback. See
[`agent_memory/appbook/README.md`](agent_memory/appbook/README.md).

### 3. `application_modes/` — the three modes
The three shapes an agent application takes, each on **Oracle AI Agent Memory**:
- **Assistant** — a supply‑chain ops copilot (Claude Agent SDK) that recalls long‑term preferences before each reply.
- **Workflow** — a deterministic mortgage‑approval pipeline (LangGraph) that recalls policy and writes an audit trail per stage.
- **Deep Research** — a genome‑research analyst (OpenAI Agents SDK driven by Claude via LiteLLM + **Tavily** web search) that recalls findings, searches, synthesises, and consolidates.

See [`application_modes/appbook/README.md`](application_modes/appbook/README.md).

---

## Directory layout

```
part5/
├── README.md                          ← you are here
├── ai_maturity_form_factors/
│   ├── README.md                      module guide (start here)
│   ├── oracle.sh                      shared local Oracle DB helper (start/stop/status)
│   ├── images/                        diagrams (the five-form-factor figure)
│   ├── notebook/                      ai_maturity_form_factors_notebook.ipynb
│   └── appbook/                       FastAPI + JS app (5 form-factor pages)
├── agent_memory/
│   ├── agent_memory_zero_to_hero.ipynb
│   └── appbook/                       FastAPI + JS app (5 memory-layer pages)
└── application_modes/
    ├── assistant_supply_chain_claude_agent_sdk.ipynb
    ├── workflow_mortgage_langgraph.ipynb
    ├── deep_research_openai_agents.ipynb
    └── appbook/                       FastAPI + JS app (3 mode pages)
```

Each `appbook/` follows the same shape: `backend/` (FastAPI — `main.py`, `config.py`,
`core/`, one router per page), `frontend/` (`index.html` · `styles.css` · `app.js`, no
build step), a `run.sh`, `requirements.txt`, and a `.env.example`.

---

## Prerequisites

- **Docker** — to run the local **Oracle AI Database (23ai/26ai Free)** container.
- **Python 3.11+** with the conda envs the `run.sh` scripts expect: **`oracle_demos`**
  (agent_memory, application_modes) and **`dbtlabs`** (ai_maturity_form_factors). Each
  appbook's `requirements.txt` lists what it needs if you'd rather use your own env.
- **API keys** (see the per‑module table below). Each appbook reads them from
  `appbook/.env`, or the course's `../.env` / `../../.env` — copy the module's
  `.env.example` to `.env` and fill it in.

---

## Quickstart

```bash
# 1. Start the shared local Oracle AI Database (provisions the VECTOR user,
#    Oracle Text, the vector pool, and property-graph support):
cd part5/ai_maturity_form_factors
./oracle.sh start          # ./oracle.sh status | stop | logs

# 2. Provide your API key(s) — e.g. an appbook .env:
cp appbook/.env.example appbook/.env   # then edit it

# 3a. Run a NOTEBOOK: open the .ipynb in Jupyter and run top-to-bottom.
# 3b. Run an APPBOOK:
cd appbook
PORT=8001 ./run.sh         # → http://127.0.0.1:8001
```

Oracle is **optional everywhere** — if it's not reachable, each module falls back (see
below) so you can still run the notebooks and apps.

---

## Per‑module run reference

| Module | `run.sh` conda env | API key(s) | If Oracle is down, falls back to… |
|---|---|---|---|
| `ai_maturity_form_factors` | `dbtlabs` | `ANTHROPIC_API_KEY` | in‑memory NumPy vector index |
| `agent_memory` | `oracle_demos` | `OPENAI_API_KEY` | memorizz **FileSystem/FAISS** provider |
| `application_modes` | `oracle_demos` | `ANTHROPIC_API_KEY` (+ `TAVILY_API_KEY` for Deep Research web search) | in‑process keyword memory store |

Notes:
- **Models:** the ladder and application‑modes work runs on **`claude-opus-4-8`** with
  **local, torch‑free `nomic` embeddings** (via `fastembed`). The agent‑memory module uses
  **OpenAI** (`gpt-5.5` + `text-embedding-3-small`).
- **Database connection:** all modules target the same local instance
  (`localhost:1521/FREEPDB1`, `VECTOR` user); credentials are in each appbook's
  `.env.example` and are overridable via env vars.

---

## Important details

- **Ports.** Every appbook serves on **`http://127.0.0.1:8000`** by default. To run more
  than one at once, set `PORT` — e.g. ai_maturity on `8001`, agent_memory on `8002`,
  application_modes on `8003`. Hot reload during development: `PORT=8001 ./run.sh --reload`.
- **`.env` resolution.** Appbooks load, in order, `part5/.env` → `<module>/.env` →
  `appbook/.env` (later wins). Put a shared key once in `part5/.env`, or override per app.
- **`.env` files are gitignored** (along with generated artifacts: `ff5_sandbox/`, the
  builder's `appbook/backend/automations/`, `__pycache__/`). Don't commit real keys.
- **Graceful degradation.** Each appbook's sidebar/health endpoint shows the active
  backend (Oracle vs fallback) and whether agent features are available — nothing hard‑fails
  on a missing DB or key; you get a clear status instead.
- **⚠️ Autonomous agents execute code.** The ladder's Form Factor 5 (and any "builder"
  surface) writes files and runs shell commands with permissions bypassed, confined to a
  sandbox directory. That's the point of the demo — **keep it local**, never point it at a
  directory or system you care about.
- **Health check.** `curl -s http://127.0.0.1:<port>/api/health` returns the model, the
  retrieval/memory backend, and capability flags for any appbook.

---

For the deepest detail on any module, read its own `README.md` (linked above). Happy climbing. 🧗
