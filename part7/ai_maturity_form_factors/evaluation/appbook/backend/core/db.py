"""Oracle AI Database: one connection pool, a small `sql()` helper, the evidence tables, and the open models.

The evidence tables (`FFEVAL_RUNS`, `FFEVAL_RESULTS`, `FFEVAL_GRADER_CHECKS`, `FFEVAL_TOOL_EVENTS`, `FFEVAL_GATES`)
are shared with the evaluation notebook, so notebook runs and appbook runs sit side by side. The application under
test keeps its own memory in `FFAPP_` tables, so the appbook never touches the notebook's application tables.
"""
from __future__ import annotations

import array
import json
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

import numpy as np

from backend.config import settings

_state = {"ready": False, "backend": "starting", "error": None}
_lock = threading.Lock()
_model_lock = threading.Lock()
_pool = None
_embedder = None
_reranker = None

EVIDENCE_DDL = """
CREATE TABLE IF NOT EXISTS ffeval_runs (
    run_id      VARCHAR2(64) PRIMARY KEY,
    started_at  TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    provider    VARCHAR2(32),
    model       VARCHAR2(100),
    judge_model VARCHAR2(100),
    graders     JSON
)
/
CREATE TABLE IF NOT EXISTS ffeval_results (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      VARCHAR2(64)  NOT NULL,
    form_factor VARCHAR2(32)  NOT NULL,
    case_id     VARCHAR2(100) NOT NULL,
    metric      VARCHAR2(100) NOT NULL,
    value       NUMBER,
    detail      JSON,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL
)
/
CREATE INDEX IF NOT EXISTS ffeval_results_run ON ffeval_results (run_id, form_factor, metric)
/
CREATE TABLE IF NOT EXISTS ffeval_grader_checks (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      VARCHAR2(64)  NOT NULL,
    check_kind  VARCHAR2(40)  NOT NULL,
    item_id     VARCHAR2(100) NOT NULL,
    variant     VARCHAR2(40),
    split       VARCHAR2(8),
    gold        NUMBER(1)     NOT NULL,
    grader      VARCHAR2(40)  NOT NULL,
    probability NUMBER,
    latency_ms  NUMBER
)
/
CREATE TABLE IF NOT EXISTS ffeval_tool_events (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      VARCHAR2(64)  NOT NULL,
    form_factor VARCHAR2(32)  NOT NULL,
    task_id     VARCHAR2(64)  NOT NULL,
    attempt     NUMBER        NOT NULL,
    seq         NUMBER        NOT NULL,
    tool_name   VARCHAR2(100) NOT NULL,
    tool_input  JSON,
    decision    VARCHAR2(200)
)
/
CREATE TABLE IF NOT EXISTS ffeval_gates (
    run_id     VARCHAR2(64)  NOT NULL,
    gate       VARCHAR2(200) NOT NULL,
    metric     VARCHAR2(100),
    op         VARCHAR2(4),
    threshold  NUMBER,
    value      NUMBER,
    passed     NUMBER(1),
    CONSTRAINT ffeval_gates_pk PRIMARY KEY (run_id, gate)
)
"""


def plain(value):
    """Native JSON columns come back with Decimal numbers; turn them into ints and floats."""
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


@contextmanager
def connection():
    if _pool is None:
        raise RuntimeError(f"Oracle AI Database is not available: {_state['error'] or 'still starting'}")
    conn = _pool.acquire()
    try:
        yield conn
    finally:
        _pool.release(conn)


def sql(statement: str, **binds):
    """One statement: queries return a list of dicts (JSON columns as plain Python), writes commit and return the count."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(statement, binds)
        if cur.description is None:
            conn.commit()
            return cur.rowcount
        names = [d[0].lower() for d in cur.description]
        return [{name: plain(value) for name, value in zip(names, row)} for row in cur.fetchall()]


def run_ddl(script: str) -> None:
    """Statements separated by lines holding only '/'."""
    with connection() as conn, conn.cursor() as cur:
        for statement in script.split("\n/\n"):
            if statement.strip():
                cur.execute(statement)
        conn.commit()


def executemany(statement: str, rows: list, json_positions: tuple[int, ...] = ()) -> int:
    if not rows:
        return 0
    import oracledb

    with connection() as conn, conn.cursor() as cur:
        if json_positions:
            width = len(rows[0])
            cur.setinputsizes(*[oracledb.DB_TYPE_JSON if i in json_positions else None for i in range(width)])
        cur.executemany(statement, rows)
        conn.commit()
    return len(rows)


def status() -> dict:
    return dict(_state)


def ready() -> bool:
    return _state["ready"]


def bootstrap() -> None:
    """Open the pool and create the evidence tables if they are missing (idempotent)."""
    global _pool
    with _lock:
        if _state["ready"]:
            return
        try:
            import oracledb

            oracledb.defaults.fetch_lobs = False
            last = None
            for _ in range(max(1, settings.oracle_connect_retries)):
                try:
                    _pool = oracledb.create_pool(user=settings.oracle_user, password=settings.oracle_password,
                                                 dsn=settings.oracle_dsn, min=1, max=8, increment=1)
                    with connection() as conn, conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM dual")
                    break
                except Exception as exc:  # noqa: BLE001 — retry while the database starts
                    last, _pool = exc, None
                    time.sleep(3)
            if _pool is None:
                raise last or RuntimeError("could not connect")
            run_ddl(EVIDENCE_DDL)
            _state.update(ready=True, backend="oracle", error=None)
        except Exception as exc:  # noqa: BLE001 — shown by /api/health
            _state.update(ready=False, backend="unavailable", error=str(exc).splitlines()[0][:240])


# ── the open models the application uses: embeddings and the reranker (loaded on first use) ──────────────────
def embedder():
    global _embedder
    with _model_lock:
        if _embedder is None:
            from fastembed import TextEmbedding

            _embedder = TextEmbedding(model_name=settings.embed_model)
    return _embedder


def reranker():
    global _reranker
    with _model_lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            _reranker = TextCrossEncoder(model_name=settings.reranker_model)
    return _reranker


_embed_lock = threading.Lock()


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def embed_documents(texts: list[str]) -> np.ndarray:
    model = embedder()
    with _embed_lock:
        return np.array([unit(v) for v in model.embed(texts)], dtype=np.float32)


def query_vector(text: str) -> array.array:
    model = embedder()
    with _embed_lock:
        return array.array("f", unit(next(model.query_embed(text))).tolist())


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    model = reranker()
    with _embed_lock:
        return [float(s) for s in model.rerank(query, texts)]


def models_status() -> dict:
    return {"embedder": "loaded" if _embedder is not None else "on first use",
            "reranker": "loaded" if _reranker is not None else "on first use"}


def json_dumps(value) -> str:
    return json.dumps(value, default=str)
