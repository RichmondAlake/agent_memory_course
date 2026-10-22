# Agent memory evaluation studio (appbook)

The evaluation notebook as a web app. Three agents (a naive full-history agent, a scratch Memo on Oracle tables and a
MemoRizz Memo) are evaluated live, suite by suite, with graders that are validated before they are trusted. Every
run, from the notebook or from this app, sits in the same Oracle evidence tables and can be compared on the Overview
and Gates pages.

## Run

```bash
cp .env.example .env        # add the keys (or leave OPENAI_API_KEY empty for Gemma 4 on Ollama)
./run.sh                    # http://127.0.0.1:8715
```

`run.sh` uses `$PYTHON`, else `part7/.venv`, else `python3`, and installs `requirements.txt` when an import check
fails (MemoRizz must be 0.17.8 or newer). `HOST` and `PORT` override the address. Oracle must be running
(`./oracle.sh start` in `part7/`); the app uses the `MEMORIZZ` schema.

## Pages

| Page | What it does |
|---|---|
| **Overview** | Every run in `MEMEVAL_RUNS` (notebook and appbook), and the scorecard of the one you pick: accuracy with Wilson intervals, recall@10, tokens, p50/p95 latency and $ per answer, write recall, updates, leaks, forgetting, per agent |
| **Graders** | The validation set built by construction (24 facts × 5 answers × 3 checks) run live over SSE for Clef-Flash, Jev and the LLM judge; κ, ECE and Brier per check; a reliability chart; trust-or-escalate per decision model; blind spots by variant; a playground that asks every grader one check |
| **1. LongMemEval** | A live run of n questions per type (plus unanswerable ones) from LongMemEval-S cleaned @98d7416: ingest, answer, LongMemEval's own judge prompt, session recall@10; accuracy per ability; McNemar between agents |
| **2. FactConsolidation** | MemoryAgentBench's 455 numbered facts as turns (8 per message), then questions about the current values; stale answers |
| **3. Memory operations** | Ten generated turns per Memo, a canary for another user and one in a sealed thread; write recall, false-memory resistance and updates (measured here only), leakage, two-stage forgetting |
| **Release gates** | The notebook's gates for both Memos on any run: READY, BLOCKED or not measured |
| **Data Explorer** | Read-only view of `MEMEVAL_*` (evidence) and `MEMAPP_*` (the app's scratch Memo) |

Each suite page streams its run live (Stop ends it after the current item) and otherwise shows the latest stored run
of that suite, from the notebook or this app. A run keeps going if you leave the page; coming back reattaches.

## How it relates to the notebook

- **Evidence is shared.** Suites write to the notebook's `MEMEVAL_RUNS`, `MEMEVAL_RESULTS`, `MEMEVAL_GRADES` and
  `MEMEVAL_GATES` under `appbook-…` run ids, with the notebook's `part` names. The app adds `7-writes` rows (write quality
  and each store's contents) and update checks in `7-operations`, which the notebook does not measure.
- **Agent memory is separate.** The app's scratch Memo writes `MEMAPP_TURNS` and `MEMAPP_FACTS`; its MemoRizz Memo
  writes under `memapp-…` memory ids. A run keeps what it wrote, so its MemoRizz traces appear in the MemoRizz UI
  (Traces, filtered by agent) when the UI reads this schema, which needs MemoRizz's `oracle` extra; set
  `MEMO_CLEANUP=1` to delete this run's rows. The evidence stays either way.
- **The grading policy comes from the latest full validation run** (all 24 facts, notebook or app; a quick run's 8
  facts set it only when no full run exists). Per check, the grader is the cheapest (Clef-Flash, Jev, the judge)
  whose κ on the dev facts is within 0.05 of the best. A decision-model probability strictly inside the escalation
  band, `(min(0.2, threshold − 0.05), max(0.8, threshold + 0.05))`, goes to the LLM judge, whose verdict replaces
  it. That is the rule of the notebook and of the maturity evaluation. The memory operations page logs how many
  verdicts were escalated. Without a validation run the suites use Jev at 0.5 (or the judge).
- **The same MemoRizz setup.** FactConsolidation runs MemoRizz with entity memory on, as the notebook does. MemoRizz
  0.17.4 failed there (an entity over about 8 KB could not be saved, then the pool hung), and 0.17.8 fixes it. Facts
  arrive 8 per message to stay under MemoRizz's 600-character recall cap (`max_chars_per_item`, still fixed in 0.17.8).
  Every model call has a 180 s timeout (`MEMEVAL_TIMEOUT`).

## Configuration

| Variable | Default | Role |
|---|---|---|
| `OPENAI_API_KEY` | | the agents (`gpt-6.1-sol`, `gpt-6-luna`) and embeddings (`text-embedding-3-small` @ 256); empty → Gemma 4 on Ollama |
| `ANTHROPIC_API_KEY` | | the judge (`claude-sonnet-5-5`); without it the judge is `gpt-6.1-sol` |
| `TYPESAFE_API_KEY` | | Jev (optional) |
| `CLEF_URL` | | a SystemOne endpoint serving Clef-Flash; without it Clef loads in this process on Apple silicon (about 7 GB) |
| `MEMO_PROVIDER`, `OLLAMA_URL`, `MEMO_OPEN_MODEL` | | the open-model path, as in the notebook |
| `MEMO_CLEANUP` | | `1` deletes what a suite run wrote; by default a run keeps it for the MemoRizz UI |
| `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN` | `MEMORIZZ`, `MemorizzPwd_2026`, `localhost:1521/FREEPDB1` | the database |

## Tracing to Arize AX

Set `ARIZE_SPACE_ID` and `ARIZE_API_KEY` (in the environment, `~/.ppa_workshop/keys.env` or `.env`), and every OpenAI and
Anthropic call is traced to the Arize AX project `agent-memory-evaluation-appbook` (`ARIZE_PROJECT_NAME` overrides it).
Manual spans add what the instrumentors cannot see: SystemOne requests to Clef-Flash and Jev, Ollama chat calls, grader
verdicts (who decided: `clef`, `clef→judge` or `judge`), the scratch Memo's Oracle recall, and each MemoRizz turn.
Without the keys tracing is off; `/api/health` reports `tracing`. A full suite sends hundreds of spans.

## Tests

```bash
python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlist, metrics, grader analysis, gates, data
python tests/check_live.py                    # against the running app: every suite at its quick size, the evidence
python tests/check_browser.py                 # headless Chromium: every page, the playground, the Data Explorer
```

## Layout

```
backend/
  config.py            settings: the MEMO_PROVIDER switch, judge, Clef/Jev, Oracle
  main.py              FastAPI app, warm-up (open models, Oracle), routers, static frontend
  schemas.py           request bodies
  core/db.py           pool, sql(), the MEMEVAL_ evidence tables and the MEMAPP_ agent tables
  core/llm.py          chat, embeddings, the judge, prices and spend, Ollama
  core/decision.py     Clef-Flash (local or CLEF_URL) and Jev
  core/graders.py      checks, LongMemEval's prompts, the validation set, its analysis, the grading policy
  core/agents.py       naive, scratch Memo, MemoRizz Memo, and the per-run Team that cleans up after itself
  core/datasets.py     LongMemEval and FactConsolidation (pinned), and the generated scenario
  core/evidence.py     runs, summaries, gates and readiness from the evidence tables
  core/suites.py       the four suites as background jobs with SSE events
  routers/             meta, graders, suites, data_explorer
frontend/              index.html, app.js (shell, Overview, Gates, Data Explorer), pages.js (Graders and suites), styles
tests/                 test_contracts.py, check_live.py, check_browser.py
```
