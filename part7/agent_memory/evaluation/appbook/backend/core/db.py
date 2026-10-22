"""Oracle AI Database: one connection pool, a small `sql()` helper, the evidence tables and the app's agent tables.

The evidence tables (`MEMEVAL_RUNS`, `MEMEVAL_RESULTS`, `MEMEVAL_GRADES`, `MEMEVAL_GATES`) are the evaluation
notebook's, so notebook runs and appbook runs sit side by side. The scratch Memo the appbook evaluates keeps its
memory in its own `MEMAPP_` tables, and MemoRizz writes under `memapp-…` memory ids, so the appbook never touches what
a notebook run wrote.
"""
from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

from backend.config import settings

_state = {"ready": False, "backend": "starting", "error": None}
_lock = threading.Lock()
_pool = None

DDL = [
    """CREATE TABLE IF NOT EXISTS memeval_runs (
         run_id     VARCHAR2(40) PRIMARY KEY,
         started_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
         settings   JSON NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS memeval_results (
         id            NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
         run_id        VARCHAR2(40)  NOT NULL,
         part          VARCHAR2(40)  NOT NULL,
         system        VARCHAR2(40)  NOT NULL,
         item_id       VARCHAR2(200) NOT NULL,
         category      VARCHAR2(100),
         correct       NUMBER(1),
         input_tokens  NUMBER, cached_tokens NUMBER, output_tokens NUMBER,
         latency_ms    NUMBER, cost_usd NUMBER,
         detail        JSON)""",
    """CREATE TABLE IF NOT EXISTS memeval_grades (
         id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
         run_id      VARCHAR2(40)  NOT NULL,
         part        VARCHAR2(40)  NOT NULL,
         item_id     VARCHAR2(200) NOT NULL,
         check_type  VARCHAR2(40)  NOT NULL,
         grader      VARCHAR2(60)  NOT NULL,
         label       NUMBER(1),
         verdict     NUMBER(1),
         probability NUMBER,
         latency_ms  NUMBER, cost_usd NUMBER)""",
    """CREATE TABLE IF NOT EXISTS memeval_gates (
         run_id    VARCHAR2(40)  NOT NULL,
         gate      VARCHAR2(100) NOT NULL,
         system    VARCHAR2(40)  NOT NULL,
         threshold VARCHAR2(40),
         value     NUMBER,
         passed    NUMBER(1),
         CONSTRAINT memeval_gates_pk PRIMARY KEY (run_id, gate, system))""",
    """CREATE TABLE IF NOT EXISTS memapp_turns (
         id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
         memory_id    VARCHAR2(100) NOT NULL,
         user_id      VARCHAR2(100) NOT NULL,
         thread_id    VARCHAR2(100) NOT NULL,
         sealed       NUMBER(1) DEFAULT 0 NOT NULL,
         session_date VARCHAR2(40),
         content      CLOB NOT NULL,
         has_answer   NUMBER(1) DEFAULT 0 NOT NULL,
         embedding    VECTOR(256, FLOAT32) NOT NULL,
         created_at   TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS memapp_turns_scope ON memapp_turns (memory_id, user_id, thread_id)",
    """CREATE TABLE IF NOT EXISTS memapp_facts (
         id            NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
         memory_id     VARCHAR2(100)  NOT NULL,
         user_id       VARCHAR2(100)  NOT NULL,
         thread_id     VARCHAR2(100),
         entity        VARCHAR2(300)  NOT NULL,
         attribute     VARCHAR2(200)  NOT NULL,
         value         VARCHAR2(1000) NOT NULL,
         source        VARCHAR2(200),
         embedding     VECTOR(256, FLOAT32) NOT NULL,
         created_at    TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
         superseded_at TIMESTAMP WITH TIME ZONE)""",
    "CREATE INDEX IF NOT EXISTS memapp_facts_scope ON memapp_facts (memory_id, user_id, entity, attribute)",
]
TEXT_INDEX = """CREATE INDEX memapp_turns_text ON memapp_turns (content)
                INDEXTYPE IS CTXSYS.CONTEXT PARAMETERS ('SYNC (ON COMMIT)')"""


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
    """One statement: queries return a list of dicts (JSON columns as plain Python), writes commit and return the count.
    Only the binds the statement uses are sent, so a caller can pass a whole scope."""
    binds = {k: v for k, v in binds.items() if re.search(rf":{k}\b", statement)}
    with connection() as conn, conn.cursor() as cur:
        cur.execute(statement, binds)
        if cur.description is None:
            conn.commit()
            return cur.rowcount
        names = [d[0].lower() for d in cur.description]
        return [{name: plain(value) for name, value in zip(names, row)} for row in cur.fetchall()]


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
    """Open the pool and create the evidence and agent tables if they are missing (idempotent)."""
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
                                                 dsn=settings.oracle_dsn, min=1, max=10, increment=1,
                                                 getmode=oracledb.POOL_GETMODE_TIMEDWAIT, wait_timeout=60000)
                    with connection() as conn, conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM dual")
                    break
                except Exception as exc:  # noqa: BLE001 — retry while the database starts
                    last, _pool = exc, None
                    time.sleep(3)
            if _pool is None:
                raise last or RuntimeError("could not connect")
            for statement in DDL:
                sql(statement)
            if not sql("SELECT 1 FROM user_indexes WHERE index_name = 'MEMAPP_TURNS_TEXT'"):
                sql(TEXT_INDEX)
            _state.update(ready=True, backend="oracle", error=None)
        except Exception as exc:  # noqa: BLE001 — shown by /api/health
            _state.update(ready=False, backend="unavailable", error=str(exc).splitlines()[0][:240])


def json_dumps(value) -> str:
    return json.dumps(value, default=str)
