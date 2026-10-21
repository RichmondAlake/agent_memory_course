"""Read-only Data Explorer: your SCRATCH_* tables next to MemoRizz's tables.

Only allowlisted tables are listed and readable. Rows can be limited to the
current lab session or shown across the schema. There is no SQL surface.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
from backend.core import rows, scratch
from backend.core.activity import activity
from backend.core.memorizz_memo import runtime
from backend.core.session import sessions

router = APIRouter(prefix="/api/data_explorer", tags=["data_explorer"])
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def _require() -> None:
    if runtime.initialize() is None:
        raise HTTPException(503, runtime.error or "Oracle AI Database is unavailable")


def _column_type(data_type: str, length: int | None, precision: int | None, scale: int | None) -> str:
    if data_type in {"VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR", "RAW"} and length:
        return f"{data_type}({length})"
    if data_type == "NUMBER" and precision:
        return f"NUMBER({precision}{',' + str(scale) if scale is not None else ''})"
    return data_type


def _catalog() -> list[dict[str, Any]]:
    _require()
    names = [row["table_name"] for row in scratch.sql("SELECT table_name FROM user_tables ORDER BY table_name")
             if rows.allowed(row["table_name"])]
    columns = scratch.sql("""SELECT table_name, column_name, data_type, nullable, data_length, data_precision, data_scale
                             FROM user_tab_columns ORDER BY table_name, column_id""")
    primary = scratch.sql("""SELECT cols.table_name, cols.column_name FROM user_constraints cons
                             JOIN user_cons_columns cols ON cons.constraint_name = cols.constraint_name
                             WHERE cons.constraint_type = 'P' ORDER BY cols.table_name, cols.position""")
    keys: dict[str, list[str]] = {}
    for row in primary:
        keys.setdefault(row["table_name"], []).append(row["column_name"].lower())
    result = []
    for name in names:
        cols = [{"name": c["column_name"].lower(),
                 "type": _column_type(c["data_type"], c["data_length"], c["data_precision"], c["data_scale"]),
                 "nullable": c["nullable"] == "Y", "primary_key": c["column_name"].lower() in keys.get(name, [])}
                for c in columns if c["table_name"] == name]
        count = scratch.sql(f'SELECT COUNT(*) AS n FROM "{name}"')[0]["n"]
        result.append({"name": name.lower(), "row_count": int(count), "columns": cols,
                       "primary_keys": keys.get(name, []), "layer": rows.layer_of(name)})
    # Your tables first, then MemoRizz's, so the two sit side by side.
    return sorted(result, key=lambda item: (not item["name"].startswith("scratch_"), item["name"]))


def _definition(table: str) -> dict[str, Any]:
    if not _IDENTIFIER.fullmatch(table) or not rows.allowed(table):
        raise HTTPException(404, "Table is not in the appbook's allowlist")
    for item in _catalog():
        if item["name"] == table.lower():
            return item
    raise HTTPException(404, "Table does not exist yet; run a page that creates it")


@router.get("/status")
def explorer_status():
    try:
        tables = _catalog()
    except HTTPException as exc:
        return {"ready": False, "backend": "unavailable", "error": exc.detail, "tables": 0, "rows": 0,
                "stream": "/api/data_explorer/activity", "access": "read-only allowlisted browser"}
    return {"ready": True, "backend": "oracle", "schema": settings.oracle_user.upper(), "tables": len(tables),
            "rows": sum(item["row_count"] for item in tables), "stream": "/api/data_explorer/activity",
            "access": "read-only allowlisted browser"}


@router.get("/tables")
def tables():
    return {"backend": "oracle", "schema": settings.oracle_user.upper(), "tables": _catalog()}


@router.get("/tables/{table}/rows")
def table_rows(
    table: str,
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    scope: str = Query("run", pattern="^(run|all)$"),
):
    definition = _definition(table)
    names = [column["name"] for column in definition["columns"]]
    where, binds = rows.run_filter(names, sessions.current.row_scope()) if scope == "run" else ("", {})
    keys = definition["primary_keys"]
    order = ",".join(f'"{key.upper()}"' for key in keys) if keys else "ROWID"
    count = scratch.sql(f'SELECT COUNT(*) AS n FROM "{table.upper()}"{where}', **binds)[0]["n"]
    data = scratch.sql(f'SELECT * FROM "{table.upper()}"{where} ORDER BY {order} '
                       "OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY", **binds, off=offset, lim=limit)
    result = [{name: rows.json_value(row.get(name)) for name in names} for row in data]
    row_keys = ["|".join(str(row.get(key, "")) for key in keys) if keys else str(offset + index + 1)
                for index, row in enumerate(result)]
    return {"table": definition["name"], "columns": definition["columns"], "primary_keys": keys,
            "row_count": int(count), "scope": scope, "offset": offset, "limit": limit,
            "rows": result, "row_keys": row_keys}


@router.get("/activity/recent")
def recent_activity(limit: int = Query(30, ge=1, le=100)):
    return {"events": activity.recent(limit)}


@router.get("/activity")
async def activity_stream(request: Request):
    async def generate():
        queue = activity.subscribe()
        try:
            yield {"event": "ready", "data": json.dumps({"status": "connected"})}
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield {"event": "transaction", "data": json.dumps(event)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": json.dumps({"status": "alive"})}
        finally:
            activity.unsubscribe(queue)

    return EventSourceResponse(generate())
