"""A read-only Data Explorer over the evidence (MEMEVAL_*) and the appbook's scratch Memo tables (MEMAPP_*).

Only tables in this schema whose names start with those prefixes are listed or read; rows come back at most 200 at a
time, newest first where the table has an id.
"""
from __future__ import annotations

import array
import re
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.config import settings
from backend.core import db

router = APIRouter(prefix="/api/data_explorer", tags=["data_explorer"])
PREFIXES = ("MEMEVAL_", "MEMAPP_")
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")
ROLE = {"MEMEVAL_RUNS": "evidence · one row per run", "MEMEVAL_RESULTS": "evidence · one row per answer",
        "MEMEVAL_GRADES": "evidence · grader verdicts", "MEMEVAL_GATES": "evidence · release gates",
        "MEMEVAL_TURNS": "notebook scratch Memo · rounds", "MEMEVAL_FACTS": "notebook scratch Memo · facts",
        "MEMAPP_TURNS": "appbook scratch Memo · rounds", "MEMAPP_FACTS": "appbook scratch Memo · facts"}


def allowed(table: str) -> bool:
    return bool(_IDENTIFIER.fullmatch(table)) and table.upper().startswith(PREFIXES)


def _value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 2000 else value[:2000] + "…"
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, array.array):
        return f"VECTOR({len(value)}) [{', '.join(f'{float(v):.4f}' for v in value[:5])}, …]"
    if isinstance(value, (dict, list)):
        return db.plain(value)
    return str(value)


def _ready():
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")


@router.get("/tables")
def tables():
    _ready()
    names = [r["table_name"] for r in db.sql("""SELECT table_name FROM user_tables
                                                WHERE table_name LIKE 'MEMEVAL\\_%' ESCAPE '\\' OR table_name LIKE 'MEMAPP\\_%' ESCAPE '\\'
                                                ORDER BY table_name""")]
    out = []
    for name in names:
        try:
            count = int(db.sql(f'SELECT COUNT(*) AS n FROM "{name}"')[0]["n"])
        except Exception:  # noqa: BLE001
            count = -1
        out.append({"name": name.lower(), "rows": count, "role": ROLE.get(name, "evidence")})
    return {"schema": settings.oracle_user.upper(), "tables": out}


@router.get("/tables/{table}/rows")
def rows(table: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), run_id: str | None = None):
    _ready()
    if not allowed(table):
        raise HTTPException(400, "Only MEMEVAL_ and MEMAPP_ tables can be read here.")
    name = table.upper()
    columns = [r["column_name"] for r in db.sql("""SELECT column_name FROM user_tab_columns WHERE table_name = :t
                                                   ORDER BY column_id""", t=name)]
    if not columns:
        raise HTTPException(404, "No such table in this schema.")
    where = "WHERE run_id = :run_id" if run_id and "RUN_ID" in columns else ""
    order = "ORDER BY ID DESC" if "ID" in columns else ("ORDER BY STARTED_AT DESC" if "STARTED_AT" in columns else "")
    binds = {"run_id": run_id} if where else {}
    total = int(db.sql(f'SELECT COUNT(*) AS n FROM "{name}" {where}', **binds)[0]["n"])
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(f'SELECT * FROM "{name}" {where} {order} OFFSET :o ROWS FETCH NEXT :l ROWS ONLY',
                    {**binds, "o": offset, "l": limit})
        names = [d[0].lower() for d in cur.description]
        data = [{n: _value(v) for n, v in zip(names, row)} for row in cur.fetchall()]
    return {"table": name.lower(), "columns": names, "rows": data, "total": total, "offset": offset, "limit": limit}
