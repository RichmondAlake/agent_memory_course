"""Agent SDK session memory in Oracle (Form Factors 4 and 5), mirroring the notebook's §4.4.

``OracleSessionStore`` implements the SDK's ``SessionStore`` protocol over AGENT_SESSION_ENTRIES and
AGENT_SESSION_SUMMARIES, so every agent conversation in the appbook is mirrored into Oracle as it runs
and can be resumed, or branched from an earlier turn, after a page refresh or a server restart.
Database calls run in worker threads so the event loop serving the stream never blocks on SQL.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from claude_agent_sdk import SessionStore

from backend.core import db

MAIN = "-"  # Oracle stores '' as NULL, so the main transcript gets an explicit subpath marker
STORE_NAME = "appbook"


def _json(value):
    """IS JSON columns arrive parsed from python-oracledb; plain CLOBs arrive as LOBs."""
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value.read() if hasattr(value, "read") else value)


class OracleSessionStore(SessionStore):
    """Mirror Agent SDK session transcripts into Oracle so any host can resume them."""

    def __init__(self, store_name: str = STORE_NAME):
        self.store_name = store_name
        self._last_ms = 0

    def _now_ms(self) -> int:
        now = max(int(time.time() * 1000), self._last_ms + 1)
        self._last_ms = now
        return now

    def _key(self, key) -> dict:
        return {"store_name": self.store_name, "project_key": key["project_key"],
                "session_id": key["session_id"], "subpath": key.get("subpath") or MAIN}

    # ── SessionStore protocol ──────────────────────────────────────────────────────
    async def append(self, key, entries) -> None:
        await asyncio.to_thread(self._append, key, entries)

    async def load(self, key):
        return await asyncio.to_thread(self._load, key)

    async def list_sessions(self, project_key: str):
        return await asyncio.to_thread(self._list_sessions, project_key)

    async def list_session_summaries(self, project_key: str):
        return await asyncio.to_thread(self._list_summaries, project_key)

    async def delete(self, key) -> None:
        await asyncio.to_thread(self._delete, key)

    async def list_subkeys(self, key) -> list[str]:
        return await asyncio.to_thread(self._list_subkeys, key)

    # ── SQL ────────────────────────────────────────────────────────────────────────
    def _append(self, key, entries) -> None:
        import oracledb
        from claude_agent_sdk import fold_session_summary

        k = self._key(key)
        written_ms = self._now_ms()
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT entry_uuid FROM agent_session_entries
                               WHERE store_name = :store_name AND project_key = :project_key
                                 AND session_id = :session_id AND subpath = :subpath AND entry_uuid IS NOT NULL""", k)
                seen = {row[0] for row in cur.fetchall()}
                rows = [(k["store_name"], k["project_key"], k["session_id"], k["subpath"], e.get("uuid"), e.get("type"),
                         written_ms, json.dumps(e)) for e in entries if not e.get("uuid") or e["uuid"] not in seen]
                if rows:
                    cur.setinputsizes(None, None, None, None, None, None, None, oracledb.DB_TYPE_CLOB)
                    cur.executemany("""INSERT INTO agent_session_entries
                                       (store_name, project_key, session_id, subpath, entry_uuid, entry_type, written_ms, entry)
                                       VALUES (:1, :2, :3, :4, :5, :6, :7, :8)""", rows)
                if key.get("subpath") is None:
                    ids = {x: k[x] for x in ("store_name", "project_key", "session_id")}
                    cur.execute("""SELECT data FROM agent_session_summaries WHERE store_name = :store_name
                                   AND project_key = :project_key AND session_id = :session_id""", ids)
                    row = cur.fetchone()
                    summary = fold_session_summary(_json(row[0]) if row else None, key, entries)
                    summary["mtime"] = written_ms
                    cur.setinputsizes(data=oracledb.DB_TYPE_CLOB)
                    cur.execute("""MERGE INTO agent_session_summaries s
                                   USING (SELECT :store_name store_name, :project_key project_key, :session_id session_id FROM dual) n
                                   ON (s.store_name = n.store_name AND s.project_key = n.project_key AND s.session_id = n.session_id)
                                   WHEN MATCHED THEN UPDATE SET s.mtime = :mtime, s.data = :data
                                   WHEN NOT MATCHED THEN INSERT (store_name, project_key, session_id, mtime, data)
                                        VALUES (n.store_name, n.project_key, n.session_id, :mtime, :data)""",
                                {**ids, "mtime": written_ms, "data": json.dumps(summary)})
            conn.commit()

    def _load(self, key):
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT entry FROM agent_session_entries
                           WHERE store_name = :store_name AND project_key = :project_key
                             AND session_id = :session_id AND subpath = :subpath ORDER BY seq""", self._key(key))
            return [_json(value) for (value,) in cur.fetchall()] or None

    def _list_sessions(self, project_key: str):
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT session_id, MAX(written_ms) FROM agent_session_entries
                           WHERE store_name = :1 AND project_key = :2 AND subpath = :3 GROUP BY session_id""",
                        [self.store_name, project_key, MAIN])
            return [{"session_id": sid, "mtime": int(mtime)} for sid, mtime in cur.fetchall()]

    def _list_summaries(self, project_key: str):
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM agent_session_summaries WHERE store_name = :1 AND project_key = :2",
                        [self.store_name, project_key])
            return [_json(value) for (value,) in cur.fetchall()]

    def _delete(self, key) -> None:
        k = self._key(key)
        with db.connection() as conn:
            with conn.cursor() as cur:
                if key.get("subpath") is None:
                    ids = {x: k[x] for x in ("store_name", "project_key", "session_id")}
                    cur.execute("""DELETE FROM agent_session_entries WHERE store_name = :store_name
                                   AND project_key = :project_key AND session_id = :session_id""", ids)
                    cur.execute("""DELETE FROM agent_session_summaries WHERE store_name = :store_name
                                   AND project_key = :project_key AND session_id = :session_id""", ids)
                else:
                    cur.execute("""DELETE FROM agent_session_entries WHERE store_name = :store_name AND project_key = :project_key
                                   AND session_id = :session_id AND subpath = :subpath""", k)
            conn.commit()

    def _list_subkeys(self, key) -> list[str]:
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT subpath FROM agent_session_entries
                           WHERE store_name = :1 AND project_key = :2 AND session_id = :3 AND subpath != :4""",
                        [self.store_name, key["project_key"], key["session_id"], MAIN])
            return [row[0] for row in cur.fetchall()]


store = OracleSessionStore()


# ── helpers for the UI ───────────────────────────────────────────────────────────────
async def list_for(directory: str) -> list[dict]:
    """Sessions for one working directory, newest first, with title, tag and size."""
    from claude_agent_sdk import list_sessions_from_store

    sessions = await list_sessions_from_store(store, directory=directory)
    counts = await asyncio.to_thread(_entry_counts)
    return [{"session_id": s.session_id, "title": s.custom_title or s.summary or (s.first_prompt or "")[:80],
             "tag": s.tag, "first_prompt": s.first_prompt, "last_modified": s.last_modified,
             "entries": counts.get(s.session_id, 0)} for s in sessions]


def _entry_counts() -> dict[str, int]:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT session_id, COUNT(*) FROM agent_session_entries WHERE store_name = :1 GROUP BY session_id",
                    [STORE_NAME])
        return {sid: int(n) for sid, n in cur.fetchall()}


async def messages_for(session_id: str, directory: str) -> list[dict]:
    """The conversation as the agent would see it on resume: one item per text, tool call or tool result."""
    from claude_agent_sdk import get_session_messages_from_store

    out = []
    for m in await get_session_messages_from_store(store, session_id, directory=directory):
        content = m.message.get("content") if isinstance(m.message, dict) else m.message
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]
        for block in blocks:
            kind = block.get("type")
            if kind == "thinking" or (kind == "tool_use" and block.get("name") == "ToolSearch"):
                continue
            item: dict[str, Any] = {"uuid": m.uuid, "role": m.type, "kind": kind}
            if kind == "text":
                item["text"] = block.get("text", "")
            elif kind == "tool_use":
                item.update(name=block.get("name"), input=block.get("input"))
            elif kind == "tool_result":
                raw = block.get("content")
                item["text"] = raw if isinstance(raw, str) else "".join(
                    part.get("text", "") for part in (raw or []) if isinstance(part, dict))
            out.append(item)
    return out


async def branch(session_id: str, directory: str, up_to_message_id: str, title: str | None = None) -> str:
    """A new session holding the history up to (and including) one message; the original is untouched."""
    from claude_agent_sdk import fork_session_via_store

    result = await fork_session_via_store(store, session_id, directory=directory, up_to_message_id=up_to_message_id,
                                          title=title)
    return result.session_id


async def label(session_id: str, directory: str, title: str | None = None, tag: str | None = None) -> None:
    from claude_agent_sdk import rename_session_via_store, tag_session_via_store

    if title:
        await rename_session_via_store(store, session_id, title, directory=directory)
    if tag is not None:
        await tag_session_via_store(store, session_id, tag, directory=directory)


def stats() -> dict:
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT session_id), COUNT(*) FROM agent_session_entries WHERE store_name = :1",
                    [STORE_NAME])
        sessions, entries = cur.fetchone()
    return {"sessions": int(sessions), "entries": int(entries)}
