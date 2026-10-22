"""Settings for the retrieval benchmark appbook: Oracle, the stored run, and the pinned local models.

The app reads what the notebook's run stored in Oracle (`BEIR7_` tables) and never writes to them. It loads
bge-small-en-v1.5 only to embed a typed query, and the ms-marco cross-encoder only to rerank one query's top
documents, at the notebook's pinned revisions.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent            # .../retrieval_evaluation/appbook
FRONTEND_DIR = APP_DIR / "frontend"
NOTEBOOK_IMG_DIR = APP_DIR.parent / "notebook" / "img"       # the notebook's diagrams, served read-only at /img
DEFAULT_PORT = 8725

for candidate in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

DATASETS = {
    "fiqa": {"name": "FiQA-2018", "bm25": 0.236},
    "scifact": {"name": "SciFact", "bm25": 0.665},
    "arguana": {"name": "ArguAna", "bm25": 0.315},
}
STRATEGIES = ["lexical", "vector", "hybrid", "graph", "rerank"]
EXCLUDE_SELF = {"arguana"}          # ArguAna's queries are corpus documents; BEIR drops the query's own document
METRICS = ["ndcg10", "p1", "p5", "p10", "r10", "r100", "mrr10", "map100", "hit10"]

# The notebook's pinned models (Hugging Face repository, revision, ONNX file).
PIN = {
    "bge": ("BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", "onnx/model.onnx"),
    "reranker": ("Xenova/ms-marco-MiniLM-L-6-v2", "a09144355adeed5f58c8ed011d209bf8ee5a1fec", "onnx/model.onnx"),
}
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Settings:
    oracle_user: str = os.environ.get("ORACLE_USER", "VECTOR")
    oracle_password: str = os.environ.get("ORACLE_PASSWORD", "VectorPwd_2025")
    oracle_dsn: str = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    oracle_connect_retries: int = int(os.environ.get("ORACLE_CONNECT_RETRIES", "3"))
    run_id: str | None = os.environ.get("BEIR7APP_RUN_ID") or None
    seed: int = 7                   # the notebook's SEED: bootstrap and randomisation tests reproduce its numbers


settings = Settings()
