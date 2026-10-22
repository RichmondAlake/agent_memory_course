# The AI Maturity Ladder — Five Form Factors of AI Applications

A single running example — **Acme Home Loans** handling a mortgage application — built **five different ways**, each rung adding one capability over the last, and one kind of memory. It climbs from a plain LLM chatbot to an autonomous agent that writes and runs its own code, using **Claude Haiku 5.5** (`claude-haiku-5-5`, the latest and lowest-cost Claude model; overridable with `AIML_MODEL`), the open-source **Clef-Flash** decision model, and **Oracle AI Database** as the converged data store.

| # | Form factor | Mortgage use case | Who controls the flow? | Memory it adds |
|---|-------------|-------------------|------------------------|----------------|
| 1 | **Chatbot** | Answers an applicant's questions from training knowledge | You (one call) | Short-term: the conversation re-sent each turn |
| 2 | **RAG** | Answers from Acme's written lending policy | You (retrieve → generate) | Semantic: the policy in Oracle, updated in place with versions |
| 3 | **Workflow** | Approves, declines or refers an application with a decision model | **Your code** (fixed steps) | Episodic: decisions and case notes |
| 4 | **Agent** | Answers an applicant's follow-ups with lender tools | **The model** (dynamic) | Session: the agent's own transcript, stored in Oracle |
| 5 | **Autonomous Agent** | Builds a reusable pre-screen tool, charts and automations | **The model** (dynamic) | Procedural: tools and READMEs reused by later sessions |

This folder has two surfaces that teach the same ladder from two angles:

> **📓 Start with the [`notebook/`](notebook/) — it builds every concept up programmatically, cell by cell.**
>
> **🚀 Then open the [`appbook/`](appbook/) — it shows what those same five form factors look like as a real application.**

---

## 1. Start here — the notebook (learn it from first principles)

[`notebook/ai_maturity_form_factors_notebook.ipynb`](notebook/ai_maturity_form_factors_notebook.ipynb)

The notebook is the **starting point**. It opens with a table that plans the five form factors, then breaks every idea down to runnable code you can read, execute and modify, one capability at a time. It is organised as **Part 0 (setup) → Parts 1–5 (one per form factor) → Part 6 (where to next)**, with numbered sections, a reference architecture, a takeaway box per part, a **memory ledger** that grows as you climb, and a **⭐ live path** at the top. Diagrams are embedded images in [`notebook/img/`](notebook/img/) (their Mermaid source sits in a collapsed block), so they render in VS Code as well as Jupyter. The saved outputs come from a full live run.

**Form Factor 1 — The Chatbot**
- A single Claude call with the `anthropic` SDK; Haiku 5.5 thinks first, at `low` effort
- **Memory by re-sending the conversation**: why LLM calls are stateless, and how input tokens grow each turn
- The **ceiling** of a chatbot: it cannot know Acme's own lending rules

**Form Factor 2 — RAG on Oracle AI Database** (the deepest section)
- Acme's 17-section lending policy stored with native `VECTOR` embeddings (local, torch-free `fastembed` / nomic) and machine-readable rules as JSON
- **Oracle Text** and an **HNSW vector index**, then every retrieval technique in SQL against one table: keyword (`CONTAINS`, `SCORE`), vector (`VECTOR_DISTANCE`), attribute filtering *pre / in / post*, hybrid (RRF), and graph (SQL/PGQ `GRAPH_TABLE … MATCH`)
- A grounded, cited answer, then a **policy bulletin** that updates the memory in place (DTI limit 41% → 43%) with the old version archived

**Form Factor 3 — The LLM-Driven Workflow, with a Decision Model**
- **Structured output** turns an applicant's email into an application; Python measures DTI, LTV and reserves against the policy in memory
- **[Clef-Flash](https://huggingface.co/Cloudflare/clef)** (Apache-2.0) decides approve or decline in one forward pass, with a probability per policy criterion; checked against the written policy on twelve applications
- A gate refers low-confidence and borderline cases to a person; Claude explains and reviews the letter; the decision is recorded

**Form Factor 4 — The Agent**
- Lender tools on an in-process MCP server; the model chooses which to call (`claude-agent-sdk`)
- **Session memory** as the SDK provides it: resume, fork, list and read sessions, then an `OracleSessionStore` that keeps every transcript in Oracle

**Form Factor 5 — The Autonomous Agent**
- An agent that writes a pre-screen tool to disk, runs it, fixes its own errors, and documents it
- **Confinement:** a `PreToolUse` hook keeps the file tools inside the sandbox folder and the SDK's OS sandbox confines shell commands — `cwd` alone is not a boundary
- **Procedural memory:** a new session finds the tool and reuses it instead of writing another

It closes with **Where to next?** — how to decide which form factor fits a given problem (climb only as high as you need).

### Run the notebook
1. **Start the database** (shared by every Part 7 module, see §4): from `part7/`, `./oracle.sh start`
2. Set `ANTHROPIC_API_KEY` (in your shell, or in `appbook/.env`, which the notebook reads); otherwise the notebook prompts for it. **No key?** Press Enter at the prompt (or set `AIML_PROVIDER=ollama`) and every model call runs on Gemma 4 on your machine through [Ollama](https://ollama.com); the notebook pulls it the first time (about 10 GB)
3. Open `notebook/ai_maturity_form_factors_notebook.ipynb` and run the cells top to bottom (≈6 minutes on Apple silicon, plus a one-time Clef-Flash download)

To re-run it unattended and save the outputs into the notebook (from `part7/`):

```bash
.venv/bin/python tests/run_notebooks.py --env-file ~/path/to/keys.env maturity
```

---

## 2. Then — the appbook (see it as an application)

[`appbook/`](appbook/)

Once the concepts click in the notebook, the **appbook** shows what they become when you ship them: a **FastAPI + vanilla-JS** application whose sidebar is a literal ladder — one page per form factor — with everything **streamed to the browser over Server-Sent Events**.

| # | Page | What the application version adds |
|---|------|-----------------------------------|
| 1 | **LLM Chatbot** | Streamed chat with the re-sent conversation and input tokens per turn in a side pane |
| 2 | **RAG Chatbot** | A side pane that draws each technique at work (keyword postings, vector distances, RRF fusion, the graph walk), a **latent space viewer** with pre / in / post filtering, and policy bulletins with versions |
| 3 | **LLM Workflow** | The pipeline streamed step by step, a **decision tree** of the path taken, a **parallel batch** whose lanes queue for Clef, and an underwriter handoff |
| 4 | **Tool-Using Agent** | A chat whose sessions live in Oracle: refresh and resume, fork a what-if, or branch from an earlier reply |
| 5 | **Autonomous Agent** | A chat that builds tools, charts, images and scheduled automations in a sandbox, a live architecture pane, and a **reference architecture** with scenario simulations |

What the appbook demonstrates beyond the notebook — the concerns that matter in production:
- **Memory you can see**: a memory ledger on the overview, and a read-only **Data Explorer** over the allowlisted Oracle tables with a live activity rail
- **Streaming everywhere** (SSE) for responsive, step-by-step output
- **Concurrency**: parallel workflow lanes sharing one decision model, which serves one request at a time
- **Clean separation** — one router per form factor, shared Anthropic client, validated request schemas, config/secret loading
- **A confined code-execution agent** (Form Factor 5): hook + OS sandbox around `backend/sandbox/`, saved automations limited to the built script, and no cross-origin API access
- A dependency-free single-page frontend (hash router, light/dark theme, SVG and canvas visualizations) — no build step
- **Three test layers**: offline contracts, live API checks, and headless browser checks

### Run the app
```bash
./oracle.sh start          # from part7/ — the same database the notebook uses (required)
cd ai_maturity_form_factors/appbook
cp .env.example .env       # add your ANTHROPIC_API_KEY, or leave it empty for Gemma 4 through Ollama
./run.sh                   # → http://127.0.0.1:8700
```
See [`appbook/README.md`](appbook/README.md) for the architecture, safety model, tests, and Codespaces notes.

---

## 3. Finally — evaluate it, step by step

[`evaluation/`](evaluation/)

A demo shows that a form factor *can* work; an evaluation measures *how often* it does, at what cost. The evaluation notebook rebuilds the five rungs and evaluates each one the way its own failures demand: closed-book answers and the conversation buffer for the chatbot; retrieval metrics per technique, faithfulness, citations and freshness for RAG; each workflow step on gold inputs, then end to end with unsafe errors; agent tasks judged by the state they leave in Oracle, repeated for pass^k, with a prompt-injection test; and hidden tests plus an audit of every tool call for the autonomous agent. Three graders (code, the Clef and Jev decision models, and an LLM judge from another model family) are validated against labels built by construction before any of them grades the application. The run ends with a scorecard and release gates, and every result is stored in Oracle (`FFEVAL_*` tables).

| Surface | What it is |
|---|---|
| [`evaluation/notebook/ai_maturity_evaluation.ipynb`](evaluation/notebook/ai_maturity_evaluation.ipynb) | the evaluation, Parts 0 to 8, saved with a live run's outputs |
| [`evaluation/appbook/`](evaluation/appbook/) | the evaluation studio on port 8705: run the suites live, explore the graders, compare runs, read the evidence |

See [`evaluation/README.md`](evaluation/README.md).

---

## 4. Shared setup — one Oracle AI Database for Part 7

Every Part 7 notebook and appbook uses the **same** Oracle AI Database, started
by `part7/oracle.sh` (run it from the `part7/` folder):

```bash
./oracle.sh start      # create/start, wait for FREEPDB1, provision both schemas
./oracle.sh status     # container state, health, and whether FREEPDB1 is open
./oracle.sh sql        # open SQL*Plus as the VECTOR user
./oracle.sh sql-memory # open SQL*Plus as the MEMORIZZ user
./oracle.sh stop       # stop it (data is kept)
```

It runs the [`gvenzl/oracle-free`](https://hub.docker.com/r/gvenzl/oracle-free)
image and provisions two intentionally separate schemas: `VECTOR` for this
module's 768-dimensional lending policy, decisions and agent sessions, and `MEMORIZZ` for the agent-memory
modules' 256-dimensional MemoRizz stores. It also enables Oracle Text, the AI
Vector Search memory pool, and property-graph privileges. `start` waits until
the pluggable database is open and the schema accepts a login before it
provisions anything, and stops with an error if provisioning fails. The
credentials match the appbook `.env.example` files. **Prerequisite:** Docker
must be installed and running. Oracle is required by both the notebook and the appbook.

Beyond Oracle you need an **`ANTHROPIC_API_KEY`**, or Ollama with Gemma 4 for the open path (no key). Form Factors 3 and 4 use Clef-Flash, which runs in-process on Apple silicon (MLX) or at a SystemOne endpoint set in `CLEF_URL`. Form Factors 4 and 5 use the `claude-agent-sdk`, whose wheel bundles the `claude` CLI.

---

## Folder layout

```
ai_maturity_form_factors/
├── README.md          ← you are here
├── notebook/          ← START HERE: every concept, built up programmatically
│   ├── ai_maturity_form_factors_notebook.ipynb
│   └── img/           diagrams (PNG on a black background)
├── appbook/           ← THEN: the same five form factors as an application
│   ├── backend/       FastAPI app — one router per form factor, Oracle memory, Clef, Agent SDK
│   ├── frontend/      dependency-free single-page UI (no build step)
│   ├── tests/         offline contracts · live API checks · browser checks
│   ├── run.sh         launch the app (port 8700)
│   ├── .env.example   ANTHROPIC_API_KEY + Oracle connection settings
│   └── README.md      app architecture, safety model & tests
└── evaluation/        ← FINALLY: evaluate each form factor, step by step
    ├── notebook/      ai_maturity_evaluation.ipynb + img/
    └── appbook/       the evaluation studio (port 8705)
```

The database helper lives one level up, at `part7/oracle.sh`.

**The path:** read and run the **notebook** to understand each form factor from first principles → explore the **appbook** to see those same five rungs wired together as something you could actually ship.
