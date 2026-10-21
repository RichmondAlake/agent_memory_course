"""Live, human-readable database activity for the footer Data Explorer.

This is application telemetry for the appbook UI, not a replacement for Oracle
auditing. It reports only the allowlisted tables touched by public app routes.
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


def operations_for(method: str, path: str) -> list[dict[str, str | None]]:
    """Map public app operations to the Oracle tables they touch (the memory each form factor uses)."""
    operations: list[tuple[str, str]] = []
    row_key: str | None = None

    if path.startswith("/api/data_explorer/tables/") and path.endswith("/rows"):
        operations = [(path.split("/")[4], "READ")]
    elif path.startswith("/api/rag/policy/"):
        operations = [("policy_doc_versions", "INSERT"), ("policy_docs", "UPDATE"),
                      ("policy_doc_similarities", "UPDATE")]
    elif path.startswith("/api/rag/"):
        operations = [("policy_docs", "READ")]
        if path.startswith("/api/rag/explain"):
            operations.append(("policy_doc_similarities", "READ"))
    elif path.startswith(("/api/workflow/run", "/api/workflow/batch")):
        operations = [("policy_docs", "READ"), ("loan_applications", "INSERT"), ("loan_decisions", "INSERT")]
    elif path.startswith("/api/workflow/underwriter"):
        operations = [("loan_decisions", "INSERT"), ("case_notes", "INSERT")]
    elif path.startswith("/api/workflow/decisions"):
        operations = [("loan_decisions", "READ"), ("loan_applications", "READ")]
    elif path.startswith("/api/agent/run"):
        operations = [("loan_applications", "READ"), ("loan_decisions", "READ"), ("loan_decisions", "INSERT"),
                      ("case_notes", "INSERT"), ("agent_session_entries", "INSERT")]
    elif path.startswith(("/api/agent/sessions", "/api/builder/sessions")):
        operations = [("agent_session_entries", "READ"), ("agent_session_summaries", "READ")]
    elif path.startswith(("/api/agent/branch", "/api/builder/branch")):
        operations = [("agent_session_entries", "INSERT")]
    elif path.startswith("/api/builder/chat"):
        operations = [("agent_session_entries", "INSERT"), ("agent_session_summaries", "UPDATE")]
    elif path == "/api/reset" and method == "POST":
        operations = [(t, "RESET") for t in ("policy_docs", "loan_applications", "loan_decisions", "case_notes",
                                             "agent_session_entries")]

    seen: set[tuple[str, str]] = set()
    result = []
    for table, operation in operations:
        key = (table.lower(), operation)
        if key not in seen:
            result.append({"table": table.lower(), "operation": operation, "row_key": row_key})
            seen.add(key)
    return result
