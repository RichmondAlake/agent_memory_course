"""Oracle AI Database: one connection pool and a read-only `sql()` helper.

The app only reads. Every statement it runs is a SELECT with bind variables; table names that vary come from
fixed allowlists (the three datasets), never from user input.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from decimal import Decimal

from backend.config import DATASETS, settings

_state = {"ready": False, "backend": "starting", "error": None}
_lock = threading.Lock()
_pool = None


def plain(value):
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


def sql(statement: str, **binds) -> list[dict]:
    """One read-only query: rows as dicts with lower-case keys."""
    if not statement.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("read-only: only SELECT statements are allowed")
    with connection() as conn, conn.cursor() as cur:
        cur.arraysize = 2000
        cur.execute(statement, binds)
        names = [d[0].lower() for d in cur.description]
        return [{name: plain(value) for name, value in zip(names, row)} for row in cur.fetchall()]


def rows(statement: str, **binds) -> list[tuple]:
    """One read-only query: raw tuples (for the larger reads)."""
    if not statement.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("read-only: only SELECT statements are allowed")
    with connection() as conn, conn.cursor() as cur:
        cur.arraysize = 5000
        cur.execute(statement, binds)
        return cur.fetchall()


def timed(statement: str, **binds) -> tuple[list[tuple], float]:
    """Execute and fetch one search; return the rows and the milliseconds the database took."""
    if not statement.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("read-only: only SELECT statements are allowed")
    with connection() as conn, conn.cursor() as cur:
        started = time.perf_counter()
        cur.execute(statement, binds)
        result = cur.fetchall()
        return result, (time.perf_counter() - started) * 1000


def status() -> dict:
    return dict(_state)


def ready() -> bool:
    return _state["ready"]


def bootstrap() -> None:
    """Open the pool (idempotent). No DDL: the app never creates or changes a table."""
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
                                                 dsn=settings.oracle_dsn, min=1, max=6, increment=1)
                    with connection() as conn, conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM dual")
                    break
                except Exception as exc:  # noqa: BLE001 — retry while the database starts
                    last, _pool = exc, None
                    time.sleep(3)
            if _pool is None:
                raise last or RuntimeError("could not connect")
            _state.update(ready=True, backend="oracle", error=None)
        except Exception as exc:  # noqa: BLE001 — shown by /api/health
            _state.update(ready=False, backend="unavailable", error=str(exc).splitlines()[0][:240])


def inventory() -> dict:
    """What the notebook's run left in Oracle: per dataset, the corpus, vectors, text index, edges and graph."""
    tables = {r["table_name"]: None for r in sql(
        "SELECT table_name FROM user_tables WHERE table_name LIKE 'BEIR7\\_%' ESCAPE '\\'")}
    objects = {(r["object_type"], r["object_name"]) for r in sql(
        "SELECT object_type, object_name FROM user_objects WHERE object_name LIKE 'BEIR7\\_%' ESCAPE '\\' "
        "AND object_type IN ('INDEX', 'PROPERTY GRAPH')")}

    def count(table: str) -> int | None:
        if table.upper() not in tables:
            return None
        return int(sql(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])

    out = {}
    for ds in DATASETS:
        out[ds] = {"documents": count(f"beir7_{ds}_docs"), "vectors": count(f"beir7_{ds}_bge"),
                   "query_vectors": count(f"beir7_{ds}_bge_q"), "edges": count(f"beir7_{ds}_edges"),
                   "text_index": ("INDEX", f"BEIR7_{ds.upper()}_DOCS_TXT") in objects,
                   "graph": ("PROPERTY GRAPH", f"BEIR7_{ds.upper()}_GRAPH") in objects}
        out[ds]["complete"] = bool(out[ds]["documents"] and out[ds]["vectors"] == out[ds]["documents"]
                                   and out[ds]["edges"] and out[ds]["text_index"] and out[ds]["graph"])
    out["evidence"] = {"runs": count("beir7_runs"), "results": count("beir7_results"), "costs": count("beir7_costs")}
    return out
