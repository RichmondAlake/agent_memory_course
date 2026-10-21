"""Live, human-readable memory-database activity for the Data Explorer.

This is application telemetry for teaching. It deliberately reports only the
tables (your SCRATCH_* tables and MemoRizz's) associated with public app routes and is not Oracle audit
data.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any


class ActivityBroker:
    def __init__(self) -> None:
        self._recent: deque[dict[str, Any]] = deque(maxlen=160)
        self._subscribers: set[asyncio.Queue] = set()
        self._sequence = 0

    def transaction_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def publish(
        self,
        *,
        transaction_id: str,
        table: str,
        operation: str,
        status: str,
        route: str,
        row_key: str | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        self._sequence += 1
        event = {
            "sequence": self._sequence,
            "transaction_id": transaction_id,
            "table": table.lower(),
            "operation": operation.upper(),
            "status": status,
            "route": route,
            "row_key": row_key,
            "detail": detail,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        self._recent.appendleft(event)
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        return event

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=96)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        return list(self._recent)[: min(max(limit, 1), 100)]


activity = ActivityBroker()


# The tables each Part reads (READ) and writes (WRITE): scratch first, then MemoRizz.
PART_TABLES: dict[int, list[tuple[str, str]]] = {
    1: [],
    2: [("scratch_conversation", "READ"), ("scratch_conversation", "WRITE"), ("conversation_memory", "READ"),
        ("conversation_memory", "WRITE"), ("agents", "WRITE")],
    3: [("scratch_persona", "READ"), ("scratch_persona", "WRITE"), ("personas", "READ"), ("personas", "WRITE")],
    4: [("scratch_entity", "READ"), ("scratch_entity", "WRITE"), ("entity_memory", "READ"), ("entity_memory", "WRITE")],
    5: [("scratch_knowledge", "READ"), ("scratch_knowledge", "WRITE"), ("knowledge_base", "READ"),
        ("knowledge_base", "WRITE")],
    6: [("scratch_toolbox", "READ"), ("scratch_toolbox", "WRITE"), ("toolbox", "READ"), ("toolbox", "WRITE")],
    7: [("scratch_tool_log", "READ"), ("scratch_tool_log", "WRITE"), ("tool_log", "READ"), ("tool_log", "WRITE")],
    8: [("scratch_workflow", "READ"), ("scratch_workflow", "WRITE"), ("workflow_memory", "WRITE")],
    9: [("scratch_skill", "READ"), ("scratch_skill", "WRITE"), ("skillbox", "READ"), ("skillbox", "WRITE")],
    10: [("scratch_conversation", "READ"), ("conversation_memory", "READ"), ("short_term_memory", "READ")],
    11: [("scratch_summary", "READ"), ("scratch_summary", "WRITE"), ("scratch_conversation", "WRITE"),
         ("summaries", "READ"), ("summaries", "WRITE")],
    12: [("scratch_cache", "READ"), ("scratch_cache", "WRITE"), ("semantic_cache", "READ"), ("semantic_cache", "WRITE")],
    13: [("scratch_blackboard", "READ"), ("scratch_blackboard", "WRITE"), ("shared_memory", "READ"),
         ("shared_memory", "WRITE")],
    14: [("scratch_knowledge", "READ"), ("scratch_knowledge", "WRITE"), ("conversation_memory", "READ"),
         ("conversation_memory", "WRITE")],
    15: [("scratch_routing", "WRITE"), ("scratch_knowledge", "WRITE"), ("knowledge_base", "WRITE"),
         ("short_term_memory", "WRITE")],
    16: [("scratch_agent", "READ"), ("scratch_agent", "WRITE"), ("agents", "READ"), ("agents", "WRITE")],
}
ALL_TABLES = sorted({table for items in PART_TABLES.values() for table, _ in items})


def operations_for(method: str, path: str) -> list[dict[str, str | None]]:
    """Map each appbook route to the tables it may touch."""
    operations: list[tuple[str, str]] = []
    parts = path.strip("/").split("/")
    if path.startswith("/api/data_explorer/tables/") and path.endswith("/rows"):
        operations = [(parts[3], "READ")]
    elif method.upper() == "POST" and len(parts) >= 4 and parts[:2] == ["api", "parts"] and parts[2].isdigit():
        operations = PART_TABLES.get(int(parts[2]), [])
        if parts[3] == "chat" and int(parts[2]) >= 2:      # MemoRizz stores a context snapshot per model call
            operations = operations + [("shared_memory", "WRITE")]
    elif method.upper() == "POST" and path == "/api/tokenomics/workload":    # the full stack, every turn
        operations = [item for part in (2, 4, 5, 7, 8, 9, 12, 15) for item in PART_TABLES[part]]
        operations.append(("shared_memory", "WRITE"))
    elif method.upper() == "POST" and path == "/api/session/reset":
        operations = [(table, "DELETE") for table in ALL_TABLES]

    seen: set[tuple[str, str]] = set()
    result = []
    for table, operation in operations:
        key = (table.lower(), operation)
        if key not in seen:
            result.append({"table": table.lower(), "operation": operation, "row_key": None})
            seen.add(key)
    return result
