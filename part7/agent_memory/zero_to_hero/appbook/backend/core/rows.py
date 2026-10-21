"""Read-only row access shared by the Part pages and the Data Explorer.

Only allowlisted tables are readable: your SCRATCH_* tables and the MemoRizz
tables. Identifiers are checked against the allowlist before they reach SQL.
"""
from __future__ import annotations

import array
import base64
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.core import scratch

MEMORIZZ_TABLES = [
    "conversation_memory", "summaries", "summary_message_links", "personas", "entity_memory", "knowledge_base",
    "toolbox", "tool_log", "workflow_memory", "skillbox", "short_term_memory", "semantic_cache", "shared_memory",
    "agents", "agent_memories", "agent_knowledge_bases", "agent_llm_configs", "agent_delegates",
]
ALLOWED_TABLES = set(scratch.SCRATCH_TABLES) | set(MEMORIZZ_TABLES)


def allowed(table: str) -> bool:
    return table.lower() in ALLOWED_TABLES


def layer_of(table: str) -> str:
    name = table.lower()
    if name.startswith("scratch_"):
        return "from scratch"
    if name in {"conversation_memory", "summaries", "summary_message_links"}:
        return "MemoRizz · episodic"
    if name in {"personas", "entity_memory", "knowledge_base"}:
        return "MemoRizz · semantic"
    if name in {"toolbox", "workflow_memory", "skillbox", "tool_log"}:
        return "MemoRizz · procedural"
    if name in {"short_term_memory", "semantic_cache"}:
        return "MemoRizz · working"
    if name == "shared_memory":
        return "MemoRizz · social"
    return "MemoRizz · agent definition"


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 4000 else value[:4000] + "…"
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ", timespec="seconds") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, array.array):
        preview = ", ".join(f"{float(item):.4f}" for item in value[:4])
        return f"VECTOR({len(value)}) [{preview}{', …' if len(value) > 4 else ''}]"
    if isinstance(value, bytes):
        if len(value) == 16:
            return value.hex()
        return f"BINARY({len(value)}) {base64.b64encode(value[:32]).decode('ascii')}…"
    if hasattr(value, "read"):
        return json_value(value.read())
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > 16 and all(isinstance(item, (int, float)) for item in value):
            return f"VECTOR({len(value)})"
        return [json_value(item) for item in value]
    return str(value)


def table_columns(table: str) -> list[str]:
    if not allowed(table):
        raise ValueError(f"{table} is not an allowlisted table")
    return [row["column_name"].lower() for row in scratch.columns(table)]


def run_filter(columns: list[str], scope: dict) -> tuple[str, dict]:
    """WHERE clause limiting a table to one lab session, from the columns it has."""
    clauses, binds = [], {}
    memory_ids = [scope["memory_id"], *scope.get("knowledge_ids", []), *scope.get("shared_ids", [])][:20]
    if "memory_id" in columns:
        names = [f"mem_{i}" for i in range(len(memory_ids))]
        clauses.append(f"memory_id IN ({', '.join(':' + n for n in names)})")
        binds.update(dict(zip(names, memory_ids)))
    if "user_id" in columns:
        clauses.append("user_id = :user_id")
        binds["user_id"] = scope["user_id"]
    if "session_id" in columns and scope.get("session_id"):
        clauses.append("session_id = :session_id")
        binds["session_id"] = scope["session_id"]
    agent_ids = list(scope.get("agent_ids", []))[:20]
    if "agent_id" in columns and agent_ids:
        names = [f"agent_{i}" for i in range(len(agent_ids))]
        clauses.append(f"agent_id IN ({', '.join(':' + n for n in names)})")
        binds.update(dict(zip(names, agent_ids)))
    if not clauses:
        return " WHERE 1 = 0", {}
    return " WHERE (" + " OR ".join(clauses) + ")", binds


def read_rows(table: str, scope: dict, limit: int = 12, order: str | None = None,
              hide: set[str] | frozenset = frozenset()) -> dict[str, Any]:
    """This session's newest rows of one allowlisted table."""
    columns = table_columns(table)
    if not columns:
        return {"table": table, "columns": [], "rows": [], "row_count": 0}
    where, binds = run_filter(columns, scope)
    order_by = order or ("id DESC" if "id" in columns and table.startswith("scratch_")
                         else "created_at DESC" if "created_at" in columns
                         else "timestamp DESC" if "timestamp" in columns else "ROWID")
    count = scratch.sql(f'SELECT COUNT(*) AS n FROM "{table.upper()}"{where}', **binds)[0]["n"]
    rows = scratch.sql(f'SELECT * FROM "{table.upper()}"{where} ORDER BY {order_by} FETCH FIRST :lim ROWS ONLY',
                       **binds, lim=limit)
    shown = [c for c in columns if c not in {"embedding", "query_embedding"} and c not in hide]
    return {"table": table, "columns": shown, "row_count": int(count),
            "rows": [{c: json_value(row.get(c)) for c in shown} for row in rows]}
