"""A read-only Data Explorer over the notebook's BEIR7_ tables.

Only tables on the allowlist (this schema's BEIR7_ tables) are listed or read. VECTOR columns are never sent: they
appear as a placeholder with their dimension. Long text is cut to 300 characters in the database, and rows come back
at most 200 at a time.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.config import settings
from backend.core import db
from backend.routers.meta import ready

router = APIRouter(prefix="/api/data_explorer", tags=["data_explorer"])
PREFIX = "BEIR7_"
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")
MAX_COLUMNS = 16
ROLE = {"BEIR7_RUNS": "evidence · one row per run", "BEIR7_RESULTS": "evidence · one graded query per configuration",
        "BEIR7_COSTS": "evidence · build steps", "BEIR7_CORPORA": "corpus registry and fingerprints",
        "BEIR7_CANDIDATES": "working table (emptied at the end of a run)"}


def allowed(table: str) -> bool:
    return bool(_IDENTIFIER.fullmatch(table or "")) and table.upper().startswith(PREFIX) and not table.upper().startswith("DR$")


def _role(name: str) -> str:
    if name in ROLE:
        return ROLE[name]
    for suffix, role in (("_DOCS", "corpus · documents"), ("_QUERIES", "dev and test queries"),
                         ("_QRELS", "relevance judgements"), ("_BGE_Q", "query vectors (not shown)"),
                         ("_MINILM_Q", "query vectors (not shown)"), ("_BGE", "document vectors (not shown)"),
                         ("_MINILM", "document vectors (not shown)"), ("_EDGES", "kNN graph edges")):
        if name.endswith(suffix):
            return role
    return "table"


def _value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, str):
        return value if len(value) <= 300 else value[:300] + "…"
    return str(value)[:300]


def _tables() -> list[str]:
    return [r["table_name"] for r in db.sql(
        "SELECT table_name FROM user_tables WHERE table_name LIKE 'BEIR7\\_%' ESCAPE '\\' ORDER BY table_name")]


@router.get("/tables")
def tables():
    ready()
    out = []
    for name in _tables():
        try:
            count = int(db.sql(f'SELECT COUNT(*) AS n FROM "{name}"')[0]["n"])
        except Exception:  # noqa: BLE001
            count = -1
        out.append({"name": name.lower(), "rows": count, "role": _role(name)})
    return {"schema": settings.oracle_user.upper(), "tables": out}


@router.get("/tables/{table}/rows")
def rows(table: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), run_id: str | None = None):
    ready()
    if not allowed(table):
        raise HTTPException(400, "Only this schema's BEIR7_ tables can be read here.")
    name = table.upper()
    if name not in _tables():
        raise HTTPException(404, "No such table in this schema.")
    columns = db.sql("""SELECT column_name, data_type FROM user_tab_columns WHERE table_name = :t
                        ORDER BY column_id""", t=name)
    select, names = [], []
    for c in columns[:MAX_COLUMNS]:
        col, kind = c["column_name"], c["data_type"]
        if not _IDENTIFIER.fullmatch(col):
            continue
        if kind == "VECTOR":
            select.append(f"'VECTOR (not shown)' AS \"{col}\"")
        elif kind in ("CLOB", "NCLOB"):
            select.append(f"DBMS_LOB.SUBSTR(\"{col}\", 300, 1) AS \"{col}\"")
        elif kind in ("JSON", "BLOB"):
            select.append(f"SUBSTR(JSON_SERIALIZE(\"{col}\"), 1, 300) AS \"{col}\"" if kind == "JSON"
                          else f"'{kind} (not shown)' AS \"{col}\"")
        else:
            select.append(f'"{col}"')
        names.append(col.lower())
    column_names = {c["column_name"] for c in columns}
    where = "WHERE run_id = :run_id" if run_id and "RUN_ID" in column_names else ""
    binds = {"run_id": run_id} if where else {}
    total = int(db.sql(f'SELECT COUNT(*) AS n FROM "{name}" {where}', **binds)[0]["n"])
    data = db.rows(f'SELECT {", ".join(select)} FROM "{name}" {where} OFFSET :o ROWS FETCH NEXT :l ROWS ONLY',
                   **binds, o=offset, l=limit)
    return {"table": name.lower(), "columns": names, "rows": [dict(zip(names, map(_value, r))) for r in data],
            "total": total, "offset": offset, "limit": limit, "hidden_columns": max(0, len(columns) - MAX_COLUMNS)}
