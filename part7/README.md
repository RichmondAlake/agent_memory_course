# Part 7 · From AI application form factors to agent memory, from scratch to MemoRizz

Part 7 answers two questions with runnable code on one Oracle AI Database:

1. **What shape should an AI application take?** The maturity ladder builds
   one mortgage application, Acme Home Loans, as a chatbot, a RAG system, a
   workflow with a decision model, a tool-using agent and an autonomous agent.
2. **How does an agent remember?** Every memory unit is built twice: first
   from scratch with SQL on Oracle, then with MemoRizz 0.17. The agent grows by
   one memory unit at a time, ending with memory routing by a decision model
   (TypeSafe Jev).

Then it asks a third question: **how well does each of them work, and how do you
know?** Each module has an evaluation notebook that measures it step by step,
with graders (code, decision models and an LLM judge) that are themselves
validated before they are trusted. A retrieval benchmark on BEIR datasets compares keyword,
vector, hybrid and graph retrieval on Oracle, plus a reranker, and shows which
strategy to use for your own data.

Every notebook has a companion appbook: the same ideas as a FastAPI web app
with a read-only Data Explorer over the tables it writes.

| Order | Module | Notebook | Appbook | Port |
|---|---|---|---|---|
| 1 | [`ai_maturity_form_factors/`](ai_maturity_form_factors/) | [`ai_maturity_form_factors_notebook.ipynb`](ai_maturity_form_factors/notebook/ai_maturity_form_factors_notebook.ipynb) | [`appbook/`](ai_maturity_form_factors/appbook/) | 8700 |
| 2 | [`agent_memory/zero_to_hero/`](agent_memory/zero_to_hero/) | [`agent_memory_zero_to_hero.ipynb`](agent_memory/zero_to_hero/notebook/agent_memory_zero_to_hero.ipynb) | [`appbook/`](agent_memory/zero_to_hero/appbook/) | 8710 |
| 3 | [`ai_maturity_form_factors/evaluation/`](ai_maturity_form_factors/evaluation/) | [`ai_maturity_evaluation.ipynb`](ai_maturity_form_factors/evaluation/notebook/ai_maturity_evaluation.ipynb) | [`appbook/`](ai_maturity_form_factors/evaluation/appbook/) | 8705 |
| 4 | [`agent_memory/evaluation/`](agent_memory/evaluation/) | [`agent_memory_evaluation.ipynb`](agent_memory/evaluation/notebook/agent_memory_evaluation.ipynb) | [`appbook/`](agent_memory/evaluation/appbook/) | 8715 |
| 5 | [`retrieval_evaluation/`](retrieval_evaluation/) | [`beir_retrieval_benchmark.ipynb`](retrieval_evaluation/notebook/beir_retrieval_benchmark.ipynb) | [`appbook/`](retrieval_evaluation/appbook/) | 8725 |

The appbooks use different ports, so all five can run at once (memory allowing). The retrieval benchmark and its appbook need no API key; the appbook reads what the full retrieval study (`retrieval_evaluation/notes/backup/`) stored in Oracle.

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
| `ANTHROPIC_API_KEY` | maturity notebook and appbook (`claude-haiku-5-5`) |
| `OPENAI_API_KEY` | the agent-memory module (notebook: `gpt-6.1-sol` and `gpt-6-luna`; appbook: `gpt-5.5`; `text-embedding-3-small` at 256 dimensions) |
| `TYPESAFE_API_KEY` | zero-to-hero memory routing with the Jev decision model (optional on open models); Jev as a grader in both evaluations (optional) |
| `OPENAI_API_KEY` *(evaluation)* | the maturity evaluation's LLM judge, `gpt-6.1-sol`, a different model family from the Claude application it grades (optional: it falls back to `claude-sonnet-5-5`) |
| `ANTHROPIC_API_KEY` *(evaluation)* | the agent-memory evaluation's LLM judge, `claude-sonnet-5-5`, a different family from the OpenAI agents it grades (optional: it falls back to `gpt-6.1-sol`) |
| `ARIZE_SPACE_ID`, `ARIZE_API_KEY` | optional: send traces of every notebook and appbook to [Arize AX](https://arize.com) (see *Tracing* below); `ARIZE_PROJECT_NAME` overrides the project name |

**4. Or no keys at all: open models.** Every notebook and appbook can run its
model calls on open models on your own machine instead, through
[Ollama](https://ollama.com) (install it and start it):

| Module | Open models | How to choose it |
|---|---|---|
| maturity | **Gemma 4** (Google, Apache 2.0) for every call, including the agents' Claude Code runtime, through Ollama's Anthropic-compatible API. Embeddings, reranker and the Clef decision model were already open and local | press Enter at the key prompt, or `AIML_PROVIDER=ollama`; the appbook switches when `ANTHROPIC_API_KEY` is empty |
| zero-to-hero | **Gemma 4** for both agents and their background work, **nomic-embed-text** (Apache 2.0) for the 256-dimensional vectors, through Ollama's OpenAI-compatible API | press Enter at the key prompt, or `MEMO_PROVIDER=ollama`; the appbook switches when `OPENAI_API_KEY` is empty |
| both evaluations | the same as the module they evaluate, and **Gemma 4 as the LLM judge** too; Clef-Flash grades locally and Jev is skipped without a key. A small model judging a small model is a weak grader, which the grader-validation Parts measure | the same switches: `AIML_PROVIDER=ollama` (maturity evaluation), `MEMO_PROVIDER=ollama` (memory evaluation) |

The default is `gemma4`, the E4B model (about 10 GB): it runs on a 16 GB laptop.
The notebooks and appbooks pull what is missing the first time and create
`gemma4-32k`, the same model with a 32k-token context window, because Ollama's
default of 4k cuts longer requests without an error. `AIML_OPEN_MODEL` and
`MEMO_OPEN_MODEL` pick a larger Gemma (`gemma4:12b`, `gemma4:26b`) where memory
allows, and `OLLAMA_URL` another host. Open models cost nothing per call but are
slower on a laptop, and a small model follows agent instructions less reliably
than Claude or GPT. The notebooks run the same steps on both paths; their saved
outputs come from the API path, so answers you get on Gemma will read differently.

## Run

```bash
jupyter lab                                   # open a notebook and run it top to bottom
cd ai_maturity_form_factors/appbook && ./run.sh      # http://127.0.0.1:8700
cd agent_memory/zero_to_hero/appbook && ./run.sh     # http://127.0.0.1:8710
cd ai_maturity_form_factors/evaluation/appbook && ./run.sh   # http://127.0.0.1:8705
cd agent_memory/evaluation/appbook && ./run.sh               # http://127.0.0.1:8715
cd retrieval_evaluation/appbook && ./run.sh                  # http://127.0.0.1:8725
```

Clef-Flash (about 7 GB of memory) runs inside each process that uses it. To run
several of them on a 16 GB machine, serve it once and point the others at it with
`CLEF_URL` (`python clef_mlx.py serve --port 8790` from its Hugging Face snapshot,
then `CLEF_URL=http://127.0.0.1:8790`).

## Test

Notebooks run end to end against the real providers and database, and a
passing run saves its outputs into the notebook itself:

```bash
.venv/bin/python tests/run_notebooks.py --env-file path/to/.env              # every notebook
.venv/bin/python tests/run_notebooks.py --env-file path/to/.env zero_to_hero # maturity, zero_to_hero, maturity_eval, memory_eval or retrieval_benchmark
```

Each appbook has three test layers in `appbook/tests/`:

```bash
python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlists
python tests/check_live.py                    # against the running app: real models and Oracle
python tests/check_browser.py                 # headless Chromium: every page, no console errors
```

## Tracing to Arize AX (optional)

Every notebook and appbook can send a trace of each run to [Arize AX](https://arize.com): every Claude and OpenAI
call (MemoRizz's included) and every Claude Agent SDK turn is captured automatically through OpenInference, and the
steps those libraries cannot see are added by hand: Clef-Flash and Jev calls, Ollama calls on the open path, the
graders' verdicts, Oracle retrieval, the reranker and query embeddings. It is off unless `ARIZE_SPACE_ID` and
`ARIZE_API_KEY` are set (for example in `~/.ppa_workshop/keys.env`), so runs without them are unchanged. Each
notebook and appbook writes to its own project (`ai-maturity-evaluation`, `agent-memory-evaluation-appbook`, …).
A full evaluation run sends several thousand spans; the BEIR notebook traces one example question, not its
head-to-head run or its sweep.

## Small open models vs frontier models

Everything in Part 7 runs on a small open model (Gemma 4 E4B through Ollama) as well
as on frontier models (Claude Haiku 5.5, GPT-5.5 and gpt-6.1-sol). The memory
engineering does not change with the model: tables, scopes, supersession, caches,
sessions and the agents' sandbox behave the same way. What changes is the model's
judgement, and on a 16 GB laptop we measured these differences:

| | Frontier model (API) | Gemma 4 E4B (laptop) |
|---|---|---|
| Accuracy on the 30-turn memory workload (LLM judge) | 88–97% | 61% for both Memos, 16% for the naive agent |
| Full notebook run | 5 min (maturity), 9 min (zero-to-hero) | 26 min, 11 min |
| One agent turn through the Claude Code runtime | a few seconds | 45–70 s (a long system prompt processed locally) |
| Structured extraction | every field right | drops facts, misreads figures (Maya's months of employment, a monthly income) |
| Cost | cents per run | none per call |

**Where a small model falls short, and what to do about it**

- **Extraction and arithmetic.** It can miss a fact or misread a number, and the
  error flows into every later step (a wrong `employment_months` turns an approval
  into a decline). Check extracted data with deterministic rules, and keep
  arithmetic in code, as the workflow in Part 3 of the maturity notebook does.
- **Tool use.** It reuses tools less (fewer repeated workflows, so fewer skills), now
  and then ends its turn right after a tool result without answering (both notebooks
  nudge it once), and once picked an unrelated installed skill and then reported a
  file it never wrote. Give agents only the tools they need, and verify what an
  agent claims to have done (the files, the rows) instead of trusting its summary.
- **Judgement calls.** Go/no-go decisions and policy readings are less reliable. Put
  decisions that must be right in a decision model (Clef) or in code, and use a
  strong model, or a decision model, as the judge when you evaluate.
- **Context.** Gemma 4 E4B supports 128k tokens, but Ollama serves 4k by default and
  cuts longer requests without an error; Part 7 creates a 32k variant. Long agent
  prompts are slow on a laptop; keep instructions and tool lists short.
- **Retrieval tuning.** A different embedding model (nomic-embed-text) ranks passages
  differently, so `k`, distance thresholds and cache thresholds tuned on one
  embedding model need re-checking on another.

Larger open models close part of the gap where memory allows (`gemma4:12b`,
`gemma4:26b`). Whatever the model, evaluate on your own workload before you choose:
the agent-memory Tokenomics page compares accuracy, latency and cost on the same
30 turns, and both evaluation notebooks run on either path, so the same golden sets,
graders and release gates measure a small open model against a frontier one.

## Design choices

- **Oracle first.** Agent memory has no fallback store: without Oracle or a key,
  the notebooks stop and the appbooks report a clear error. The maturity
  appbook alone degrades to an in-memory retriever so its non-database rungs
  still run.
- **Scope everywhere.** Every memory row carries `memory_id`, `user_id` and
  `thread_id` from the application, never from the model.
- **Real runs.** Saved notebook outputs come from live runs. Assertions check
  mechanics (rows, links, counters); answer quality needs an evaluation, not a
  single run, which is what the two evaluation modules provide.
- **Graders are measured too.** Every grader (decision model or LLM judge) is
  scored against labels built by construction before it grades anything, per
  kind of question; the cheapest one that is good enough is used, and uncertain
  answers escalate to the judge.
- **Diagrams as images.** Mermaid diagrams are embedded as PNG with their source
  in a collapsed block, so they render in VS Code and Jupyter alike.
