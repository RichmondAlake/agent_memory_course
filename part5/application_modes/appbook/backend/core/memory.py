"""The memory layer — the thing this whole app is about.

A single ``store`` object wraps **Oracle AI Agent Memory** (OAMP) on Oracle AI
Database and exposes the small set of operations the three modes need:

    - typed records:  memory / fact / guideline / preference
    - semantic search with a ``record_types`` filter and scope controls
    - threads with LLM-consolidated working memory (summary + context card)

Embeddings are local and open-source (nomic-embed-text-v1.5 via fastembed) — no
OpenAI key. If Oracle is unavailable, it transparently falls back to an in-process
keyword store implementing the same interface, so the app always runs.
``status()`` tells the UI which backend is live.

Every routine returns plain dicts/strings so the routers can stream them as SSE
events without any OAMP types leaking to the browser.
"""
from __future__ import annotations

import re
import threading
import uuid
from typing import Any

from backend.config import settings

# Record types are first-class in OAMP; we surface the four the demos use.
RECORD_TYPES = ("memory", "fact", "guideline", "preference")


def _fmt(record_type: str, content: str, timestamp: str | None = None) -> str:
    """A prompt-ready, type-tagged rendering (mirrors OAMP's formatted_content)."""
    ts = f"\n  <timestamp>{timestamp}</timestamp>" if timestamp else ""
    return f"<{record_type}>{ts}\n  <content>{content}</content>\n</{record_type}>"


def _make_nomic_embedder():
    """Open-source, local embeddings for OAMP — nomic-embed-text-v1.5 (768-dim) via
    fastembed ONNX. No API key, no network. Heavy imports stay lazy (only when the
    Oracle backend is built), so a missing fastembed just degrades to the fallback."""
    import numpy as np
    from fastembed import TextEmbedding
    from oracleagentmemory.apis.embedders.embedder import IEmbedder

    def _unit(v):
        v = np.asarray(v, dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else v

    class NomicEmbedder(IEmbedder):
        def __init__(self, model_name):
            self._m = TextEmbedding(model_name=model_name)

        def embed(self, texts, *, is_query=False):
            gen = self._m.query_embed(texts) if is_query else self._m.embed(texts)
            return np.asarray([_unit(v) for v in gen], dtype=np.float32)

        async def embed_async(self, texts, *, is_query=False):
            return self.embed(texts, is_query=is_query)

    return NomicEmbedder(settings.embed_model)


# ───────────────────────────────────────────────────────────────────────────
# In-process fallback backend (no Oracle, no embeddings — keyword scoring)
# ───────────────────────────────────────────────────────────────────────────
class _MemoryBackend:
    backend = "memory"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._threads: dict[str, list[dict[str, str]]] = {}

    def ensure_scope(self, user_id: str, agent_id: str) -> None:  # noqa: D401
        pass

    def _add(self, content, record_type, user_id, agent_id, thread_id, metadata):
        rid = uuid.uuid4().hex[:12]
        self._records.append({
            "id": rid, "content": content, "record_type": record_type,
            "user_id": user_id, "agent_id": agent_id, "thread_id": thread_id,
            "metadata": metadata or {},
        })
        return rid

    def add_memory(self, content, *, user_id, agent_id, thread_id=None, metadata=None):
        return self._add(content, "memory", user_id, agent_id, thread_id, metadata)

    def add_typed(self, contents, record_type, *, user_id, agent_id, metadata=None):
        return [self._add(c, record_type, user_id, agent_id, None, metadata) for c in contents]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def search(self, query, *, user_id, agent_id, record_types=None, max_results=5,
               exact_thread_match=False, thread_id=None):
        q = self._tokens(query)
        scored = []
        for r in self._records:
            if r["user_id"] != user_id or r["agent_id"] != agent_id:
                continue
            if record_types and r["record_type"] not in record_types:
                continue
            if exact_thread_match and r["thread_id"] != thread_id:
                continue
            overlap = len(q & self._tokens(r["content"]))
            if overlap:
                scored.append((overlap, r))
        scored.sort(key=lambda x: -x[0])
        return [{
            "id": r["id"], "content": r["content"], "record_type": r["record_type"],
            "formatted_content": _fmt(r["record_type"], r["content"]),
        } for _, r in scored[:max_results]]

    def delete_memory(self, memory_id):
        before = len(self._records)
        self._records = [r for r in self._records if r["id"] != memory_id]
        return before - len(self._records)

    def thread_create(self, thread_id, *, user_id, agent_id):
        self._threads.setdefault(thread_id, [])

    def thread_add(self, thread_id, role, content, *, user_id, agent_id):
        self._threads.setdefault(thread_id, []).append({"role": role, "content": content})

    def thread_len(self, thread_id):
        return len(self._threads.get(thread_id, []))

    def _thread_text(self, thread_id):
        return "\n".join(f"{m['role']}: {m['content']}" for m in self._threads.get(thread_id, []))

    def thread_summary(self, thread_id, *, user_id, agent_id):
        text = self._thread_text(thread_id)
        if not text.strip():
            return ""
        from backend.core.anthropic_client import summarize
        return summarize(text, instruction="Summarize this conversation in 2-3 sentences.")

    def thread_context_card(self, thread_id, *, user_id, agent_id):
        summary = self.thread_summary(thread_id, user_id=user_id, agent_id=agent_id)
        return _fmt("context_card", summary) if summary else ""


# ───────────────────────────────────────────────────────────────────────────
# Oracle AI Agent Memory backend (the real thing)
# ───────────────────────────────────────────────────────────────────────────
class _OracleBackend:
    backend = "oracle"

    def __init__(self) -> None:
        import oracledb
        from oracleagentmemory.core import OracleAgentMemory
        from oracleagentmemory.core.llms import Llm

        self._conn = oracledb.connect(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
        )
        # Local nomic embeddings (no OpenAI) + Claude Sonnet 4.6 as OAMP's
        # extraction/summary helper. Building the client probes the embedder; any failure
        # (e.g. fastembed missing) is caught by the caller, which falls back.
        self._client = OracleAgentMemory(
            connection=self._conn,
            embedder=_make_nomic_embedder(),
            llm=Llm(settings.extract_model, temperature=0.2),
            extract_memories=False,          # the app writes memories explicitly
            schema_policy="create_if_necessary",
            table_name_prefix=settings.table_name_prefix,
        )
        self._store = self._client._store
        self._threads: dict[str, Any] = {}
        self._scopes: set[tuple[str, str]] = set()
        self.detail = self._conn.version

    def ensure_scope(self, user_id: str, agent_id: str) -> None:
        key = (user_id, agent_id)
        if key in self._scopes:
            return
        for fn, eid, info in (
            (self._client.add_user, user_id, "App Modes demo user."),
            (self._client.add_agent, agent_id, "App Modes demo agent."),
        ):
            try:
                fn(eid, info)
            except ValueError:
                pass
        self._scopes.add(key)

    def add_memory(self, content, *, user_id, agent_id, thread_id=None, metadata=None):
        return self._client.add_memory(
            content, user_id=user_id, agent_id=agent_id,
            thread_id=thread_id, metadata=metadata or {},
        )

    def add_typed(self, contents, record_type, *, user_id, agent_id, metadata=None):
        meta = [metadata or {} for _ in contents]
        return self._store.add(
            contents=list(contents), record_type=record_type,
            user_ids=user_id, agent_ids=agent_id, metadata=meta,
        )

    def search(self, query, *, user_id, agent_id, record_types=None, max_results=5,
               exact_thread_match=False, thread_id=None):
        kwargs = dict(user_id=user_id, agent_id=agent_id, max_results=max_results)
        if record_types:
            kwargs["record_types"] = list(record_types)
        if exact_thread_match:
            kwargs["thread_id"] = thread_id
            kwargs["exact_thread_match"] = True
        results = self._client.search(query, **kwargs)
        out = []
        for r in results:
            rt = getattr(getattr(r, "record", None), "record_type", None) or "memory"
            out.append({
                "id": getattr(r, "id", None),
                "content": r.content,
                "record_type": rt,
                "formatted_content": r.formatted_content,
            })
        return out

    def delete_memory(self, memory_id):
        return self._client.delete_memory(memory_id)

    def _thread(self, thread_id, user_id, agent_id):
        th = self._threads.get(thread_id)
        if th is None:
            try:
                th = self._client.create_thread(thread_id=thread_id, user_id=user_id, agent_id=agent_id)
            except ValueError:
                th = self._client.get_thread(thread_id)
            self._threads[thread_id] = th
        return th

    def thread_create(self, thread_id, *, user_id, agent_id):
        self._thread(thread_id, user_id, agent_id)

    def thread_add(self, thread_id, role, content, *, user_id, agent_id):
        from oracleagentmemory.apis.thread import Message
        self._thread(thread_id, user_id, agent_id).add_messages([Message(role=role, content=content)])

    def thread_len(self, thread_id):
        th = self._threads.get(thread_id)
        return len(th.get_messages()) if th else 0

    def thread_summary(self, thread_id, *, user_id, agent_id):
        th = self._thread(thread_id, user_id, agent_id)
        try:
            return str(th.get_summary().content)
        except Exception:  # noqa: BLE001 — empty / no messages yet
            return ""

    def thread_context_card(self, thread_id, *, user_id, agent_id):
        th = self._thread(thread_id, user_id, agent_id)
        try:
            return str(th.get_context_card().formatted_content)
        except Exception:  # noqa: BLE001
            return ""


# ───────────────────────────────────────────────────────────────────────────
# Facade — picks a backend at startup, delegates everything to it
# ───────────────────────────────────────────────────────────────────────────
class MemoryStore:
    def __init__(self) -> None:
        self._impl: _OracleBackend | _MemoryBackend | None = None
        self._lock = threading.Lock()
        self._error: str | None = None

    # -- lifecycle -----------------------------------------------------------
    def initialize(self) -> None:
        if self._impl is not None:
            return
        with self._lock:
            if self._impl is not None:
                return
            if settings.oracle_enabled:
                try:
                    self._impl = _OracleBackend()
                    return
                except Exception as exc:  # noqa: BLE001 — degrade gracefully
                    self._error = f"{type(exc).__name__}: {exc}"
            self._impl = _MemoryBackend()

    @property
    def impl(self):
        if self._impl is None:
            self.initialize()
        return self._impl

    def status(self) -> dict:
        impl = self._impl
        return {
            "ready": impl is not None,
            "backend": impl.backend if impl else None,
            "detail": getattr(impl, "detail", None) if impl else None,
            "fallback_reason": self._error,
        }

    # -- delegation ----------------------------------------------------------
    def ensure_scope(self, *a, **k): return self.impl.ensure_scope(*a, **k)
    def add_memory(self, *a, **k): return self.impl.add_memory(*a, **k)
    def add_typed(self, *a, **k): return self.impl.add_typed(*a, **k)
    def search(self, *a, **k): return self.impl.search(*a, **k)
    def delete_memory(self, *a, **k): return self.impl.delete_memory(*a, **k)
    def thread_create(self, *a, **k): return self.impl.thread_create(*a, **k)
    def thread_add(self, *a, **k): return self.impl.thread_add(*a, **k)
    def thread_len(self, *a, **k): return self.impl.thread_len(*a, **k)
    def thread_summary(self, *a, **k): return self.impl.thread_summary(*a, **k)
    def thread_context_card(self, *a, **k): return self.impl.thread_context_card(*a, **k)


store = MemoryStore()
