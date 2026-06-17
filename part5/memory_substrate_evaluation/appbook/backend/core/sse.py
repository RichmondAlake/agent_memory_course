"""Tiny helper: turn an async generator of dict events into an SSE response.

Mirrors the helper used by the other Part 5 appbooks so the frontend can consume
benchmark progress the same way across the course.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from sse_starlette.sse import EventSourceResponse


def sse_response(events: AsyncIterator[dict[str, Any]]) -> EventSourceResponse:
    async def stream():
        async for event in events:
            yield {"data": json.dumps(event)}
        yield {"event": "end", "data": "{}"}

    return EventSourceResponse(stream())
