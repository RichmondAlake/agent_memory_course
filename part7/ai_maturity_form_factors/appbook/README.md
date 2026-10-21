# The AI Maturity Ladder — Appbook

A FastAPI + vanilla-JS application that turns the
[`ai_maturity_form_factors_notebook.ipynb`](../notebook/ai_maturity_form_factors_notebook.ipynb)
notebook into an interactive, light/dark web app. One use case runs through every page:
**Acme Home Loans** handling a mortgage application. The sidebar is a literal ladder: each
rung is one AI form factor, and each rung adds a kind of memory that the next ones build on.

| # | Form factor | Page | What it shows | Memory it adds |
|---|-------------|------|---------------|----------------|
| 1 | **LLM Chatbot** | `#/chatbot` | An applicant asks about a mortgage; the reply streams, and a side pane shows the whole conversation re-sent each turn, with input tokens per turn. | Short-term: the message list |
| 2 | **RAG Chatbot** | `#/rag` | Answers grounded in Acme's lending policy in Oracle. For each technique — keyword, vector, hybrid (RRF), graph — a side pane draws how the query moves through the index. A **latent space viewer** maps any query into the 768-d embedding space (2-D/3-D PCA) and compares pre-, in- and post-filtering. Policy bulletins update sections in place, with versions. | Semantic: `POLICY_DOCS` + versions |
| 3 | **LLM Workflow** | `#/workflow` | extract → measure ‖ ground → **decide (Clef-Flash)** → gate → explain → review → record. Every run ends in a **decision tree** showing the path taken. A **parallel batch** runs several applications at once, and they queue for the single decision model. Referrals go to an underwriter. | Episodic: `LOAN_DECISIONS`, `CASE_NOTES` |
| 4 | **Tool-Using Agent** | `#/agent` | A chat with an underwriting agent that has lender tools (search policy, case history, re-assess with Clef, add a note). Sessions live in Oracle: refresh the page and resume, fork a what-if, or **branch** from an earlier reply. | Session: `AGENT_SESSION_ENTRIES` |
| 5 | **Autonomous Agent** | `#/builder` | A chat with an agent that writes and runs Python in a sandbox. It builds tools, makes charts and images (created in the sandbox, then shown in the chat) and sets up scheduled automations. A live architecture pane lights up on every real event. A **reference architecture** runs scenario simulations: build a tool, chart → image, escape attempt, resume after refresh, schedule, policy change. | Procedural: tools + READMEs on disk |

A persistent, resizable **Data Explorer** sits at the bottom of every page. It browses
the ten allowlisted tables in the `VECTOR` schema, shows real columns, keys and paginated
rows, summarizes VECTOR cells, and highlights each read and write through a live SSE
activity rail. It is read-only: it cannot run arbitrary SQL or open any other table.

## Run

```bash
# from part7/ — one shared Oracle AI Database for every Part 7 module
./oracle.sh start

# from this folder
cp .env.example .env        # add your ANTHROPIC_API_KEY
./run.sh                    # → http://127.0.0.1:8700
```

`run.sh` picks its Python in this order: `$PYTHON`, then the shared
`part7/.venv`, then `python3` on your `PATH`. It installs `requirements.txt`
into that interpreter when an import check fails, then starts uvicorn.
`PORT=9000 ./run.sh` and `HOST=0.0.0.0 ./run.sh` override the defaults. Each
Part 7 appbook has its own default port, so they can run side by side.

On start the app connects to Oracle, drops the tables of the earlier support-desk
version of this appbook (`ACME_DOCS` and its graph) if they are still there, creates any
missing tables and indexes, and seeds the 17 policy sections only when `POLICY_DOCS` is
empty. Work saved by the notebook (decisions, sessions, policy versions) is kept.
**Reset demo data** on the overview page restores the seed policy and clears decisions,
notes and sessions.

> [!IMPORTANT]
> **In a Codespace, open the app from the Ports panel → port `8700` → 🌐 Open in Browser**
> (start it with `HOST=0.0.0.0 ./run.sh`). If the forwarded URL shows **HTTP 502**, it's the
> port-forward tunnel, not the app: confirm with
> `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8700/api/health` (`200` = up).

## Requirements

- **`ANTHROPIC_API_KEY`** — required for every model call. Read from the process
  environment first, then `appbook/.env`, `../.env` or `part7/.env`. The model is
  `claude-haiku-5-5` at `low` effort (`AIML_MODEL`, `AIML_EFFORT`).
- **Oracle AI Database** — required. Policy memory, decisions, case notes and agent
  sessions all live there. Pages that need it show a banner until it is ready.
- **Clef-Flash** — the open-source (Apache-2.0) decision model for Form Factors 3 and 4.
  On Apple silicon it is downloaded once (pinned revision, about 7 GB of memory at run time)
  and loaded on the first decision. Elsewhere, set `CLEF_URL` to a SystemOne endpoint.
- **Claude Agent SDK** — required for Form Factors 4 and 5 and installed by
  `requirements.txt`. The wheel bundles its own `claude` CLI, which the app uses
  in preference to any `claude` on your `PATH`.

## Safety

Form Factor 5 runs model-written code with permissions bypassed, so the app
confines it three ways:

- A `PreToolUse` **hook** denies `Read`/`Write`/`Edit`/`Glob`/`Grep` on any path outside
  `backend/sandbox/`, and the SDK's **OS sandbox** (Seatbelt on macOS,
  bubblewrap on Linux — `apt install bubblewrap socat`) makes shell writes
  outside it fail. `cwd` alone is only a starting directory, not a boundary.
- **Saved automations** may only run `python <script>.py [args]` for a script in
  their own folder, without a shell; anything else is refused with HTTP 400.
- **No CORS** headers: only the app's own page can call the API, so another
  website open in your browser cannot start the agent. The server listens on
  `127.0.0.1` unless you set `HOST`.

Keep it local all the same.

## Tests

Three layers, all from this folder with the Part 7 environment:

```bash
# 1. Offline contracts — no key, model download or database (≈3 s)
../../.venv/bin/python -m pytest tests/test_contracts.py -q

# 2. Live API checks against a running app — real Claude, Oracle, Clef and agent runs (≈6 min)
./run.sh &                                   # or use an already running app
../../.venv/bin/python tests/check_live.py   # --skip-agents skips Form Factors 4-5

# 3. Browser checks — every page and its main interaction in headless Chromium (≈8 min)
../../.venv/bin/python -m playwright install chromium   # once
../../.venv/bin/python tests/check_browser.py           # --skip-agents opens FF4-5 without sending
```

`APPBOOK_URL` points the live and browser checks at another address. Run them one
after the other, not at once: both write decisions and sessions. The browser check
fails on any console or uncaught page error and saves screenshots to
`tests/artifacts/` (gitignored).

## Architecture

```
appbook/
├── backend/
│   ├── main.py              FastAPI app; Oracle bootstrap in the background; automation scheduler; serves the SPA
│   ├── config.py            env loading, model + effort, Clef, Oracle creds, bundled-CLI discovery
│   ├── schemas.py           Pydantic request bodies (bounded, validated)
│   ├── core/
│   │   ├── policy.py             the 17 policy sections, bulletins, table DDL, legacy cleanup
│   │   ├── db.py                 connection pool, embeddings, schema, seeding, policy graph, reset
│   │   ├── retrieval.py          the four techniques + filtering in SQL, explainers, latent space (PCA)
│   │   ├── underwriting.py       extract, measure, Clef decide, gate, decision tree, letters, decision memory
│   │   ├── sessions.py           OracleSessionStore (Agent SDK SessionStore) + list/read/branch/label
│   │   ├── agent_runtime.py      claude-agent-sdk → normalized SSE events
│   │   ├── sandbox.py            FF5 sandbox: batches, policy.json export, path guard, file listing
│   │   ├── automations.py        saved automations, command check, scheduler
│   │   ├── anthropic_client.py   shared client, text_of, structured_json (Haiku 5.5, effort)
│   │   ├── activity.py           read/write activity broker for the explorer
│   │   └── sse.py                EventSourceResponse helper
│   └── routers/             one per form factor + meta (health, memory ledger, reset) + data_explorer
├── frontend/                index.html · styles.css · app.js · rag.js · workflow.js · agent.js · builder.js (no build step)
└── tests/                   test_contracts.py · check_live.py · check_browser.py
```

All five form factors stream their output to the browser over Server-Sent
Events. The frontend is a dependency-free single-page app (hash router, theme
toggle, SSE-over-`fetch`, SVG and canvas visualizations).
