# Retrieval evaluation · which strategy to use

[`notebook/beir_retrieval_benchmark.ipynb`](notebook/beir_retrieval_benchmark.ipynb) shows which retrieval strategy
to use, by measurement. Four strategies, plus a reranker, run as SQL on Oracle AI Database over two public BEIR
datasets, and the results become a decision table.

| Strategy | Oracle feature | Setting |
|---|---|---|
| **Keyword** | Oracle Text `CONTAINS` / `SCORE`, `ACCUM` | the question's 10 rarest content words, no stemming |
| **Vector** | `VECTOR_DISTANCE`, `FETCH EXACT` | `bge-small-en-v1.5`, cosine |
| **Hybrid** | weighted score fusion in one SQL statement | α = 0.8 toward vector, top 50 of each list |
| **Graph** | SQL property graph over a kNN document graph, `GRAPH_TABLE … MATCH` | 10 seeds, 5 neighbours each, decay 0.005 |
| **+ Reranker** | local cross-encoder (`ms-marco-MiniLM-L-6-v2`) | reorders the hybrid top 10 |

Four Parts, 56 cells:

0. **Setup:** Oracle, the two local models, optional Arize AX tracing.
1. **The data and the question:** FiQA-2018 (personal finance; a 20,000-post sample: every judged post plus seeded
   distractors) and SciFact (scientific claims; full corpus), test queries only; nDCG@10, Recall@10, Precision@10,
   MRR@10 and latency, defined once with a worked example.
2. **Four strategies, plus a reranker:** each one's SQL, then one question through all five side by side (the cell
   that sends one trace when tracing is on).
3. **Head-to-head:** one results table per dataset with 95% bootstrap intervals and p50 latency, one chart, a sweep
   of the hybrid weight α, and Oracle Text next to BEIR's published BM25.
4. **Which strategy to use:** a decision table with this run's evidence, and a diagram.

No API key is needed: the models run locally through FastEmbed. The datasets are published by the BEIR authors
under CC BY-SA 4.0 (Thakur et al., NeurIPS 2021) and read with pandas at pinned revisions.

## Run it

```bash
cd ..                      # the part7 folder
./oracle.sh start          # Oracle AI Database Free on localhost:1521, VECTOR schema
.venv/bin/python tests/run_notebooks.py retrieval_benchmark      # or open the notebook with the part7/.venv kernel
```

It reuses the `BEIR7_` corpus, vector, Oracle Text and graph tables when they are in Oracle, embeds only missing
rows, and writes no result tables. The saved run took 6.3 minutes (378 s in the runner) with the tables in place; on an empty database
it also embeds 25,183 documents.

## Results of the saved run (test queries, nDCG@10)

| Dataset | Keyword | Vector | Hybrid | Graph | Hybrid + reranker |
|---|---|---|---|---|---|
| FiQA-2018 (20,000-post sample, 648 queries) | 0.208 | 0.492 | **0.502** | 0.491 | 0.485 |
| SciFact (full corpus, 300 queries) | 0.576 | 0.713 | **0.719** | 0.714 | 0.703 |

Hybrid leads on both by at most 0.010, inside the 95% intervals; equal weighting (α = 0.5) loses to vector search
alone on both. FiQA's scores are on a sampled corpus, so they are higher than, and not comparable with, published
full-corpus numbers.

## The full study and the appbook

- **The full study**, [`notes/backup/beir_retrieval_benchmark.full_study.ipynb`](notes/backup/beir_retrieval_benchmark.full_study.ipynb):
  three datasets (with ArguAna), every setting tuned on dev queries and reported on test queries, significance
  tests with Holm correction, a second embedding model, HNSW, corpus-size effects and dataset diagnostics. Its run
  stored `BEIR7_RUNS`, `BEIR7_RESULTS` and `BEIR7_COSTS`.
- **The appbook**, [`appbook/`](appbook/) on port **8725**: a read-only FastAPI app over the full study's stored
  run (leaderboard, query explorer, tuning playground, decision guide, Data Explorer). See
  [`appbook/README.md`](appbook/README.md).

```bash
cd appbook && ./run.sh        # http://127.0.0.1:8725
```
