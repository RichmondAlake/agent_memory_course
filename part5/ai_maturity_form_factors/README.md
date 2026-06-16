# The AI Maturity Ladder — Five Form Factors of AI Applications

A single running example — a support assistant for a fictional product, **Acme Cloud** — built **five different ways**, each rung adding exactly one capability over the last. It climbs from a plain LLM chatbot to an autonomous agent that writes and runs its own code, all on the latest Claude models (`claude-opus-4-8`) and **Oracle AI Database** as the converged data store.

| # | Form factor | New capability | Who controls the flow? | Data access |
|---|-------------|----------------|------------------------|-------------|
| 1 | **Chatbot** | Generate text | You (one call) | Training data only |
| 2 | **RAG** | Ground in *your* data | You (retrieve → generate) | + Your documents (Oracle) |
| 3 | **Workflow** | Reliable multi-step pipelines | **Your code** (fixed steps) | + Your documents |
| 4 | **Agent** | Model-chosen tool use | **The model** (dynamic) | + Tools you provide |
| 5 | **Autonomous Agent** | Write & run code | **The model** (dynamic) | + Files & shell |

This folder has two surfaces that teach the same ladder from two angles:

> **📓 Start with the [`notebook/`](notebook/) — it builds every concept up programmatically, cell by cell.**
>
> **🚀 Then open the [`appbook/`](appbook/) — it shows what those same five form factors look like as a real production application.**

---

## 1. Start here — the notebook (learn it from first principles)

[`notebook/ai_maturity_form_factors_notebook.ipynb`](notebook/ai_maturity_form_factors_notebook.ipynb)

The notebook is the **starting point**. It breaks every idea down to runnable code you can read, execute, and modify — no framework magic, one capability at a time. What it covers, rung by rung:

**Form Factor 1 — The Chatbot**
- A single-shot Claude call with the `anthropic` SDK (one prompt in, one response out)
- **Memory by re-sending the conversation** — why LLM calls are *stateless* and how a multi-turn chat is just an accumulating `messages` list
- The **ceiling** of a chatbot: it only knows its training data

**Form Factor 2 — RAG on Oracle AI Database** (the deepest section)
- Connecting to Oracle and storing docs as native `VECTOR` embeddings (local, torch-free `fastembed` / nomic, unit-normalized so cosine = dot product)
- Building the two indexes that power retrieval: **Oracle Text** (`CTXSYS.CONTEXT`) and an **HNSW vector index**
- The full menu of **retrieval techniques**, side by side, all in SQL against one table:
  - **Keyword** search (Oracle Text `CONTAINS`, `SCORE`)
  - **Vector** / semantic search (`VECTOR_DISTANCE … COSINE`)
  - **Attribute filtering** — *pre / in / post* (`VECTOR_INDEX_TRANSFORM` hint) and why the order of filter-vs-search matters
  - **Hybrid** search — Reciprocal Rank Fusion (RRF), plus the native `DBMS_HYBRID_VECTOR.SEARCH`
  - **Graph** retrieval — a SQL property graph queried with SQL/PGQ `GRAPH_TABLE … MATCH`
- Augmenting the prompt with retrieved context, then **generating a grounded, cited answer**

**Form Factor 3 — The LLM-Driven Workflow**
- **Structured output** to classify the incoming message
- A deterministic, code-controlled pipeline: **classify → retrieve → draft → review/revise**

**Form Factor 4 — The Agent**
- Giving an agent **tools** and letting the *model* decide which to call, looping until done (`claude-agent-sdk`)
- The four faculties of an agent (perception, reasoning, action, memory)

**Form Factor 5 — The Autonomous Agent**
- An agent that doesn't just answer but **writes a script to disk, runs it, and fixes its own errors**
- Inspecting the artifacts it produced

It closes with **Where to Next?** — how to decide which form factor fits a given problem (climb only as high as you need).

### Run the notebook
1. **Start the database** (shared, see §3): from this folder, `./oracle.sh start`
2. Set `ANTHROPIC_API_KEY` (e.g. in a `.env` the notebook reads)
3. Open `notebook/ai_maturity_form_factors_notebook.ipynb` and run the cells top to bottom

---

## 2. Then — the appbook (see it in production)

[`appbook/`](appbook/)

Once the concepts click in the notebook, the **appbook** shows what they become when you ship them: a **FastAPI + vanilla-JS** application whose sidebar is a literal ladder — one page per form factor — with everything **streamed to the browser over Server-Sent Events**.

| # | Page | What the production version adds |
|---|------|----------------------------------|
| 1 | **LLM Chatbot** | Streamed multi-turn chat; "memory" = the growing message list re-sent each turn |
| 2 | **RAG Chatbot** | Retrieval (vector / keyword / hybrid) + grounded, cited answers, against Oracle |
| 3 | **LLM Workflow** | The classify → route → retrieve → draft → review pipeline, streamed stage by stage |
| 4 | **Autonomous Agent** | A tool-using agent (`search_docs`, `create_support_ticket`) that chooses its own path |
| 5 | **Agent That Builds** | Writes a Python script, runs it, and fixes its own errors in a confined sandbox |

What the appbook demonstrates beyond the notebook — the concerns that matter in production:
- **One shared retriever** (`VectorStore`) with **graceful degradation**: it uses Oracle when reachable and transparently falls back to an **in-memory NumPy** cosine index otherwise, so the app always runs. The active backend is shown in the UI.
- **Streaming everywhere** (SSE) for responsive, stage-by-stage output
- **Clean separation** — one router per form factor, shared Anthropic client, schemas, config/secret loading, and CLI discovery
- **A sandboxed code-execution agent** (Form Factor 5) confined to `backend/sandbox/`, reset on each run
- A dependency-free single-page frontend (hash router, light/dark theme) — no build step

### Run the app
```bash
./oracle.sh start          # from this folder — same database the notebook uses (optional; app degrades gracefully)
cd appbook
cp .env.example .env       # add your ANTHROPIC_API_KEY
./run.sh                   # → http://127.0.0.1:8000
```
See [`appbook/README.md`](appbook/README.md) for the full architecture, requirements, and Codespaces notes.

---

## 3. Shared setup — one Oracle AI Database for both

Both surfaces talk to the **same** Oracle AI Database, started by a single script that lives here (deliberately *outside* `notebook/` and `appbook/` so they share it):

```bash
./oracle.sh start      # create/start + provision the DB
./oracle.sh status     # health + connection details
./oracle.sh sql        # open SQL*Plus as the VECTOR user
./oracle.sh stop       # stop it (data is kept)
```

It runs the [`gvenzl/oracle-free`](https://hub.docker.com/r/gvenzl/oracle-free) image (Oracle Database 23ai Free) and provisions exactly what Form Factor 2 needs — a `VECTOR` user at `localhost:1521/FREEPDB1`, **Oracle Text**, the **AI Vector Search** memory pool (so HNSW indexes build), and the **`CREATE PROPERTY GRAPH`** privilege. The credentials match `appbook/.env.example`, so the notebook and the app connect with no extra configuration. **Prerequisite:** [Docker](https://docs.docker.com/get-docker/) installed and running. Oracle is optional for the app (it falls back to NumPy) but required for the notebook's RAG section.

Beyond Oracle you need an **`ANTHROPIC_API_KEY`**; Form Factors 4 & 5 additionally use the `claude-agent-sdk` and the `claude` CLI.

---

## Folder layout

```
ai_maturity_form_factors/
├── README.md          ← you are here
├── oracle.sh          ← shared local Oracle AI Database (Docker) — start here
├── notebook/          ← START HERE: every concept, built up programmatically
│   └── ai_maturity_form_factors_notebook.ipynb
└── appbook/           ← THEN: the same five form factors as a production app
    ├── backend/       FastAPI app — one router per form factor, shared retriever
    ├── frontend/      dependency-free single-page UI (no build step)
    ├── run.sh         launch the app
    ├── .env.example   ANTHROPIC_API_KEY + Oracle connection settings
    └── README.md      full app architecture & run notes
```

**The path:** read and run the **notebook** to understand each form factor from first principles → explore the **appbook** to see those same five rungs wired together as something you could actually ship.
