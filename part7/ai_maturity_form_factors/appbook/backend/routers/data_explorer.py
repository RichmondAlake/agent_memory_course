"""Read-only Data Explorer for the AI Maturity application schema."""
from __future__ import annotations

import array
import asyncio
import base64
import json
import re
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from backend.core import db
from backend.core.activity import activity
from backend.core.policy import APP_TABLES

router = APIRouter(prefix="/api/data_explorer", tags=["data_explorer"])
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 4000 else value[:4000] + "…"
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, array.array):
        preview = ", ".join(f"{float(item):.4f}" for item in value[:6])
        return f"VECTOR({len(value)}) [{preview}{', …' if len(value) > 6 else ''}]"
    if isinstance(value, bytes):
        if len(value) == 16:
            return value.hex()
        preview = base64.b64encode(value[:48]).decode("ascii")
        return f"BINARY({len(value)}) {preview}{'…' if len(value) > 48 else ''}"
    if hasattr(value, "read"):
        return _json_value(value.read())
    if hasattr(value, "model_dump"):
        return _json_value(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > 16 and all(isinstance(item, (int, float)) for item in value):
            preview = ", ".join(f"{float(item):.4f}" for item in value[:6])
            return f"VECTOR({len(value)}) [{preview}, …]"
        return [_json_value(item) for item in value]
    return _json_value(str(value))


def _column_type(data_type: str, length: int | None, precision: int | None, scale: int | None) -> str:
    if data_type in {"VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR", "RAW"} and length:
        return f"{data_type}({length})"
    if data_type == "NUMBER" and precision:
        return f"NUMBER({precision}{',' + str(scale) if scale is not None else ''})"
    return data_type


LAYERS = {
    "policy_docs": "② semantic memory · policy",
    "policy_doc_versions": "② semantic memory · history",
    "policy_categories": "② property graph",
    "policy_doc_categories": "② property graph",
    "policy_doc_similarities": "② property graph",
    "loan_applications": "③ episodic memory",
    "loan_decisions": "③ episodic memory",
    "case_notes": "④ episodic memory",
    "agent_session_entries": "④ ⑤ session memory",
    "agent_session_summaries": "④ ⑤ session memory",
}
_ALLOWED_SQL = ", ".join(f"'{t.upper()}'" for t in APP_TABLES)


def _layer(table: str) -> str:
    return LAYERS.get(table.lower(), "application")


class _PooledConnection:
    """A pooled connection with the ``close()`` the callers below expect."""

    def __init__(self) -> None:
        self._context = db.connection()
        self.conn = self._context.__enter__()

    def cursor(self):
        return self.conn.cursor()

    def close(self) -> None:
        self._context.__exit__(None, None, None)


def _oracle_connection():
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    return _PooledConnection()


def _oracle_tables(connection) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT table_name FROM user_tables
               WHERE table_name IN (""" + _ALLOWED_SQL + """)
               ORDER BY table_name"""
        )
        names = [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """SELECT table_name, column_name, data_type, nullable, column_id,
                      data_length, data_precision, data_scale
               FROM user_tab_columns
               WHERE table_name IN (""" + _ALLOWED_SQL + """)
               ORDER BY table_name, column_id"""
        )
        columns_by_table: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
        for table_name, column_name, data_type, nullable, _, length, precision, scale in cursor.fetchall():
            if table_name in columns_by_table:
                columns_by_table[table_name].append({
                    "name": column_name.lower(),
                    "type": _column_type(data_type, length, precision, scale),
                    "nullable": nullable == "Y",
                    "primary_key": False,
                })
        cursor.execute(
            """SELECT cols.table_name, cols.column_name, cols.position
               FROM user_constraints cons
               JOIN user_cons_columns cols ON cons.constraint_name = cols.constraint_name
               WHERE cons.constraint_type = 'P'
                 AND cols.table_name IN (""" + _ALLOWED_SQL + """)
               ORDER BY cols.table_name, cols.position"""
        )
        primary: dict[str, list[tuple[int, str]]] = {}
        for table_name, column_name, position in cursor.fetchall():
            primary.setdefault(table_name, []).append((position, column_name.lower()))
        for table_name, items in primary.items():
            wanted = {name for _, name in items}
            for column in columns_by_table.get(table_name, []):
                column["primary_key"] = column["name"] in wanted

        result = []
        for name in names:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
                row_count = int(cursor.fetchone()[0])
            except Exception:
                row_count = -1
            result.append({
                "name": name.lower(),
                "row_count": row_count,
                "columns": columns_by_table[name],
                "primary_keys": [column for _, column in primary.get(name, [])],
                "layer": _layer(name),
            })
        return result


def _catalog() -> tuple[str, str, list[dict[str, Any]]]:
    from backend.config import settings

    connection = _oracle_connection()
    try:
        return "oracle", settings.oracle_user.upper(), _oracle_tables(connection)
    finally:
        connection.close()


def _definition(table: str) -> tuple[str, str, dict[str, Any]]:
    if not _IDENTIFIER.fullmatch(table):
        raise HTTPException(400, "Invalid table identifier")
    backend, schema, tables = _catalog()
    for item in tables:
        if item["name"].lower() == table.lower():
            return backend, schema, item
    raise HTTPException(404, "Table is not available in the application schema")


@router.get("/status")
def explorer_status():
    backend, schema, tables = _catalog()
    return {
        "ready": True,
        "backend": backend,
        "schema": schema,
        "tables": len(tables),
        "rows": sum(max(0, item["row_count"]) for item in tables),
        "stream": "/api/data_explorer/activity",
        "access": "read-only allowlisted browser",
    }


@router.get("/tables")
def tables():
    backend, schema, items = _catalog()
    return {"backend": backend, "schema": schema, "tables": items}


@router.get("/tables/{table}/rows")
def table_rows(table: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    backend, _, definition = _definition(table)
    primary_keys = definition["primary_keys"]
    if backend == "oracle":
        connection = _oracle_connection()
        order = ",".join(f'"{name.upper()}"' for name in primary_keys) if primary_keys else "ROWID"
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT * FROM "{table.upper()}" ORDER BY {order} '
                    "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY",
                    {"offset": offset, "limit": limit},
                )
                names = [item[0].lower() for item in cursor.description]
                rows = [
                    {name: _json_value(value) for name, value in zip(names, row)}
                    for row in cursor.fetchall()
                ]
        finally:
            connection.close()
    row_keys = [
        "|".join(str(row.get(key, "")) for key in primary_keys)
        if primary_keys else str(offset + index + 1)
        for index, row in enumerate(rows)
    ]
    return {
        "table": definition["name"],
        "columns": definition["columns"],
        "primary_keys": primary_keys,
        "row_count": definition["row_count"],
        "offset": offset,
        "limit": limit,
        "rows": rows,
        "row_keys": row_keys,
    }


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
