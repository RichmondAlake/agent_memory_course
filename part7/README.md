# Part 7 · From AI application form factors to agent memory, from scratch to MemoRizz

Part 7 answers two questions with runnable code on one Oracle AI Database:

1. **What shape should an AI application take?** The maturity ladder builds
   one support assistant as a chatbot, a RAG system, a workflow, a tool-using
   agent and an autonomous agent.
2. **How does an agent remember?** Every memory unit is built twice: first
   from scratch with SQL on Oracle, then with MemoRizz 0.17. The agent grows by
   one memory unit at a time, ending with memory routing by a decision model
   (TypeSafe Jev).

Every notebook has a companion appbook: the same ideas as a FastAPI web app
with a read-only Data Explorer over the tables it writes.

| Order | Module | Notebook | Appbook | Port |
|---|---|---|---|---|
| 1 | [`ai_maturity_form_factors/`](ai_maturity_form_factors/) | [`ai_maturity_form_factors_notebook.ipynb`](ai_maturity_form_factors/notebook/ai_maturity_form_factors_notebook.ipynb) | [`appbook/`](ai_maturity_form_factors/appbook/) | 8700 |
| 2 | [`agent_memory/zero_to_hero/`](agent_memory/zero_to_hero/) | [`agent_memory_zero_to_hero.ipynb`](agent_memory/zero_to_hero/notebook/agent_memory_zero_to_hero.ipynb) | [`appbook/`](agent_memory/zero_to_hero/appbook/) | 8710 |

The appbooks use different ports, so both can run at once.

## Setup

**1. Oracle AI Database.** Docker must be running. From this folder:

```bash
./oracle.sh start      # create or start the container, provision both schemas
./oracle.sh status     # health, PDB state and connection details
```

`oracle.sh` runs one `gvenzl/oracle-free` container on `localhost:1521` with two
schemas: `VECTOR` for the maturity module's 768-dimensional RAG corpus, and
`MEMORIZZ` for the agent-memory module (256-dimensional vectors; the scratch
`SCRATCH_*` tables and MemoRizz's own tables live side by side there).

**2. Python.** One environment serves every notebook and appbook:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium     # only for the browser checks
```

Each appbook's `run.sh` uses `$PYTHON` if set, otherwise `part7/.venv`, otherwise
`python3`.

**3. Keys.** Copy each appbook's `.env.example` to `.env` (ignored by git), or
export the variables. Notebooks read the same files and ask with `getpass` for
anything missing; no key is ever written into a notebook.

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | maturity notebook and appbook (`claude-sonnet-5`) |
| `OPENAI_API_KEY` | the agent-memory module (notebook: `gpt-6.1-sol` and `gpt-6-luna`; appbook: `gpt-5.5`; `text-embedding-3-small` at 256 dimensions) |
| `TYPESAFE_API_KEY` | zero-to-hero memory routing with the Jev decision model |

## Run

```bash
jupyter lab                                   # open a notebook and run it top to bottom
cd ai_maturity_form_factors/appbook && ./run.sh      # http://127.0.0.1:8700
cd agent_memory/zero_to_hero/appbook && ./run.sh     # http://127.0.0.1:8710
```

## Test

Notebooks run end to end against the real providers and database, and a
passing run saves its outputs into the notebook itself:

```bash
.venv/bin/python tests/run_notebooks.py --env-file path/to/.env              # both
.venv/bin/python tests/run_notebooks.py --env-file path/to/.env zero_to_hero # one of: maturity, zero_to_hero
```

Each appbook has three test layers in `appbook/tests/`:

```bash
python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlists
python tests/check_live.py                    # against the running app: real models and Oracle
python tests/check_browser.py                 # headless Chromium: every page, no console errors
```

## Design choices

- **Oracle first.** Agent memory has no fallback store: without Oracle or a key,
  the notebooks stop and the appbooks report a clear error. The maturity
  appbook alone degrades to an in-memory retriever so its non-database rungs
  still run.
- **Scope everywhere.** Every memory row carries `memory_id`, `user_id` and
  `thread_id` from the application, never from the model.
- **Real runs.** Saved notebook outputs come from live runs. Assertions check
  mechanics (rows, links, counters); answer quality needs an evaluation, not a
  single run.
- **Diagrams as images.** Mermaid diagrams are embedded as PNG with their source
  in a collapsed block, so they render in VS Code and Jupyter alike.
