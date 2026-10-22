# Retrieval benchmark appbook — BEIR on Oracle AI Database

A FastAPI + vanilla-JS app over what the full retrieval study stored in Oracle: the leaderboard of lexical,
vector, hybrid, graph and reranked retrieval on FiQA-2018, SciFact and ArguAna, single queries through all five
strategies side by side, a playground for the fusion and graph parameters, and the decision guide with its evidence.
Port **8725**. No API key: every strategy runs as SQL on Oracle, and the two local models only embed or rerank one
query at a time.

In this README, "the notebook" is the full study, `../notes/backup/beir_retrieval_benchmark.full_study.ipynb`, and
its § numbers are that notebook's. The short notebook in `../notebook/` reuses the same corpus, vector and graph
tables and stores no results, so it leaves this app's data unchanged.

## Run

```bash
cd part7 && ./oracle.sh start                 # Oracle AI Database, once
# run the full study once: it stores the corpora, vectors, graphs and results this app reads
cd retrieval_evaluation/appbook
./run.sh                                      # http://127.0.0.1:8725
```

`run.sh` uses `$PYTHON` if set, otherwise `part7/.venv`, otherwise `python3`, and installs `requirements.txt` when an
import check fails. `PORT` and `HOST` override the address.

## Pages

| Page | What it shows |
|---|---|
| **Leaderboard** | Per dataset and strategy, the best tuned configuration on the held-out test queries: nDCG@10, P@1, P@5, P@10, R@10, R@100, MRR@10, MAP@100 and hit rate@10, each with its 95% bootstrap interval, and p50/p95 latency. Then the Holm-corrected paired tests, the dev-to-test gap, the build cost of every index, and Oracle Text against BEIR's published BM25. A run picker appears when `BEIR7_RUNS` holds more than one run |
| **Query explorer** | Pick a dataset and a test query, or type your own. The top 10 of all five strategies side by side, each with its stored best configuration and its time; relevant documents marked with their grade; per-query nDCG@10, P@5 and R@10 next to the value the run stored; a table of where each relevant document landed. Click a document to read it. A typed query has no judgements, so no marks or metrics, and the page says so |
| **Tuning playground** | Sliders for hybrid fusion (weighted α, or RRF k and weight, and list depth) and for graph expansion (neighbours, seeds, decay). nDCG@10, MRR@10 and R@100 over the dev queries recompute live from candidate lists cached in memory per dataset; the first visit builds the cache with progress streamed over SSE and says how long it took. A yellow tick marks the notebook's chosen setting, and a grid point the notebook tried shows its stored value |
| **Decision guide** | The dataset diagnostics (query and document length, word overlap, vocabulary mismatch, relevant documents per query, cohesion, one-hop reach) next to the notebook's flowchart, with the measured evidence behind each step from the stored results |
| **Data Explorer** | Read-only rows of the `BEIR7_` tables (the drawer at the bottom, or the sidebar link): at most 16 columns and 200 rows at a time, vectors never sent, long text cut to 300 characters |

Every leaderboard number is recomputed from the per-query rows in `BEIR7_RESULTS` with the notebook's own metric code
and seed, so it matches the notebook's §9.2 and §9.5. A stored query in the explorer uses its stored vector and
reproduces the nDCG@10 the run stored for it.

### What it reads, and what it never does

| Source | Used for |
|---|---|
| `BEIR7_RUNS`, `BEIR7_RESULTS`, `BEIR7_COSTS` | the leaderboard, the best configurations, the dev grid, the guide's evidence |
| `BEIR7_<DS>_DOCS` (+ Oracle Text index), `_QUERIES`, `_QRELS` | lexical search, document text, judgements, diagnostics |
| `BEIR7_<DS>_BGE`, `BEIR7_<DS>_BGE_Q` | exact vector search; stored query vectors |
| `BEIR7_<DS>_EDGES`, property graph `BEIR7_<DS>_GRAPH` | graph expansion (`GRAPH_TABLE … MATCH`) |

The app runs only `SELECT` statements with bind variables, never re-embeds a corpus and never writes to a `BEIR7_`
table: its caches (document frequencies, the playground's candidate lists, the diagnostics) live in memory. If the
notebook's cleanup switch `BEIR7_DROP_CORPORA=1` removed the corpora, the status card and every page say so.

## Tracing to Arize AX

Set `ARIZE_SPACE_ID` and `ARIZE_API_KEY` (environment, `~/.ppa_workshop/keys.env` or `.env`) to send spans to the
Arize AX project `beir-retrieval-benchmark-appbook` (`ARIZE_PROJECT_NAME` overrides it); `/api/health` reports
`tracing`. Only the query explorer is traced: one CHAIN per request with the query embedding, a RETRIEVER span per
strategy (top 10 documents with ids, text and scores) and the RERANKER span. The playground and the leaderboard send
none. Without the keys nothing is sent and nothing changes.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN` | `VECTOR`, `VectorPwd_2025`, `localhost:1521/FREEPDB1` | the database |
| `BEIR7APP_RUN_ID` | the latest run with test results | the run to open first |
| `PORT`, `HOST` | `8725`, `127.0.0.1` | the address (`run.sh`) |
| `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, `ARIZE_PROJECT_NAME` | — | optional tracing to Arize AX (above) |

The models are the notebook's, at the same pinned revisions: `BAAI/bge-small-en-v1.5` (`5c38ec7`) for typed queries
and `Xenova/ms-marco-MiniLM-L-6-v2` (`a091443`) for reranking. Each loads on first use.

## Layout

```
appbook/
├── run.sh · requirements.txt · .env.example
├── backend/
│   ├── main.py · config.py · schemas.py
│   ├── core/
│   │   ├── db.py            the pool, read-only sql(), and the inventory of what the run left in Oracle
│   │   ├── metrics.py       the notebook's metrics, bootstrap, paired test and Holm correction
│   │   ├── text.py          Oracle Text's stoplist, content words, document frequencies, safe CONTAINS queries
│   │   ├── search.py        the five strategies as the notebook's live SQL; stored configurations parsed
│   │   ├── models.py        bge-small-en-v1.5 and the cross-encoder, pinned, loaded on first use
│   │   ├── evidence.py      runs, best configurations, the leaderboard, the dev-to-test gap, costs
│   │   ├── explore.py       one query through all five strategies
│   │   ├── playground.py    the dev candidate cache, fusion and graph arithmetic, one-hop reach
│   │   ├── diagnostics.py   the notebook's Part 3 diagnostics from the stored corpora
│   │   └── tracing.py       optional Arize AX spans for the query explorer
│   └── routers/             meta, leaderboard, explore, playground (SSE), guide, data_explorer
├── frontend/                index.html · app.js (core, leaderboard, explorer drawer) · pages.js · styles.css · bench.css
└── tests/                   test_contracts.py · check_live.py · check_browser.py
```

The decision guide's flowchart is the notebook's `notebook/img/decision_guide.png`, served read-only at `/img`.

## Tests

```bash
python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlist, read-only SQL, configuration
                                              # parsing, the query builder, fusion and graph arithmetic, metrics
python tests/check_live.py                    # against the running app: inventory, the leaderboard's numbers,
                                              # stored queries reproducing their stored nDCG@10, a typed query, the
                                              # playground's SSE cache and dev scores, diagnostics, the Data Explorer
python tests/check_browser.py                 # headless Chromium: every page, the explorer, a slider, the guide,
                                              # the Data Explorer, a phone-width page, no console errors
```
