"""The Oracle Agent Memory (OAMP) layer for the app.

Wraps a single ``OracleAgentMemory`` client (one Oracle connection, a local
fastembed embedder, and a Haiku extraction LLM) and exposes a small, thread-safe
surface the routers call from threadpool workers:

    store.create_thread()      -> thread_id        (one per chat session / benchmark run)
    store.step(thread_id, q)   -> dict(metrics)    (one OAMP-basic turn)
    store.delete_thread(tid)

The OAMP/oracledb thin connection is not concurrency-safe, so every DB touch is
serialised under a lock; the Claude generation call happens outside the lock.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np

from backend.config import settings
from backend.core_anthropic import SYSTEM_PROMPT, call_claude, prompt_tokens

_LOCK = threading.RLock()


class _FastEmbedEmbedder:
    """Local, open-source embedder (nomic-embed-text-v1.5, 768-dim) — Anthropic
    has no embeddings API, so OAMP's vector search gets its vectors from here."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding  # imported lazily so the app starts fast

        from oracleagentmemory.apis import IEmbedder

        self._model = TextEmbedding(model_name=model_name)

        # Build the OAMP-required subclass dynamically (IEmbedder import is lazy).
        class _Impl(IEmbedder):
            def __init__(inner, model):
                inner._m = model

            def embed(inner, texts, *, is_query: bool = False) -> np.ndarray:
                gen = inner._m.query_embed(texts) if is_query else inner._m.embed(texts)
                arr = np.asarray(list(gen), dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                return arr / norms

            async def embed_async(inner, texts, *, is_query: bool = False) -> np.ndarray:
                return inner.embed(texts, is_query=is_query)

        self.impl = _Impl(self._model)


class MemoryStore:
    """Lazy, background-initialised OAMP client + per-thread helpers."""

    def __init__(self):
        self.ready = False
        self.backend = "warming"          # warming | oracle | error
        self.error: str | None = None
        self._client = None
        self._Message = None
        self._threads: dict[str, Any] = {}

    # ── lifecycle ────────────────────────────────────────────────────────────
    def initialize(self) -> None:
        """Connect to Oracle and build the OAMP client. Safe to call in a thread."""
        try:
            import oracledb
            from oracleagentmemory.core import OracleAgentMemory
            from oracleagentmemory.core.llms import Llm
            from oracleagentmemory.apis.thread import Message

            # Bound OAMP's internal LLM calls (litellm/Opus for extraction + summary)
            # so a slow or hung call can't hold the global OAMP lock indefinitely.
            try:
                import litellm
                litellm.request_timeout = 120   # Opus extraction runs a touch slower than Haiku
                litellm.num_retries = 2
            except Exception:  # noqa: BLE001
                pass

            embedder = _FastEmbedEmbedder(settings.embed_model)
            connection = oracledb.connect(
                user=settings.oracle_user,
                password=settings.oracle_password,
                dsn=settings.oracle_dsn,
            )
            client = OracleAgentMemory(
                connection=connection,
                embedder=embedder.impl,
                # Live extraction + summarisation feed the OAMP agent's ONLY recall surface
                # (the context card), so use the capable model here — a cheap extractor
                # silently drops sub-facts the agent is later asked to recall. (Mirrors the
                # notebook fix: the live extractor is the agent model, not the small tier.)
                llm=Llm("anthropic/" + settings.agent_model),
                extract_memories=True,
                schema_policy="create_if_necessary",
                table_name_prefix=settings.oamp_prefix,
            )
            for fn, eid, info in [
                (client.add_user, "app-user", "Agent-memory benchmarks app user."),
                (client.add_agent, "app-agent", "OAMP-backed research assistant."),
                # Separate identity for the head-to-head benchmark so each run can be wiped
                # for a pristine start without touching the interactive /memory chat's memories.
                (client.add_user, "bench-user", "Isolated identity for the head-to-head benchmark."),
                (client.add_agent, "bench-agent", "Isolated identity for the head-to-head benchmark."),
            ]:
                try:
                    fn(eid, info)
                except ValueError as exc:
                    if "already exists" not in str(exc):
                        raise
            self._client = client
            self._Message = Message
            self.backend = "oracle"
            self.ready = True
        except Exception as exc:  # noqa: BLE001 — surface as status, keep app alive
            self.error = f"{type(exc).__name__}: {exc}"
            self.backend = "error"
            self.ready = False

    def status(self) -> dict:
        return {"ready": self.ready, "backend": self.backend, "error": self.error}

    # ── threads ──────────────────────────────────────────────────────────────
    def create_thread(self, user_id: str = "app-user", agent_id: str = "app-agent") -> str:
        if not self.ready:
            raise RuntimeError(self.error or "Oracle Agent Memory is still warming up.")
        with _LOCK:
            thread = self._client.create_thread(
                user_id=user_id,
                agent_id=agent_id,
                enable_context_summary=True,
                context_summary_update_frequency=2,
                memory_extraction_frequency=2,
                memory_extraction_window=4,
            )
            self._threads[thread.thread_id] = thread
            return thread.thread_id

    def _thread(self, thread_id: str):
        thread = self._threads.get(thread_id)
        if thread is None:
            with _LOCK:
                thread = self._client.get_thread(thread_id)
                self._threads[thread_id] = thread
        return thread

    def delete_thread(self, thread_id: str) -> None:
        if not self.ready:
            return
        with _LOCK:
            try:
                self._client.delete_thread(thread_id)
            except Exception:  # noqa: BLE001
                pass
            self._threads.pop(thread_id, None)

    def reset_identity(self, user_id: str, agent_id: str,
                       user_info: str = "benchmark identity",
                       agent_info: str = "benchmark identity") -> None:
        """Pristine run: wipe a (user, agent) identity's threads + memories, then recreate
        the identity — so a benchmark run never inherits facts from a previous run. Scoped
        to the given identity, so the interactive /memory chat (app-user/app-agent) is left
        untouched. This is the appbook analogue of the notebook's schema_policy='recreate'."""
        if not self.ready:
            return
        with _LOCK:
            for delete_fn, eid in [(self._client.delete_agent, agent_id),
                                   (self._client.delete_user, user_id)]:
                try:
                    delete_fn(eid, cascade=True)     # cascade: drop the identity's threads + memories
                except Exception:  # noqa: BLE001 — first run: nothing to delete yet
                    pass
            for add_fn, eid, info in [(self._client.add_user, user_id, user_info),
                                      (self._client.add_agent, agent_id, agent_info)]:
                try:
                    add_fn(eid, info)
                except ValueError as exc:
                    if "already exists" not in str(exc):
                        raise

    # ── one OAMP-basic turn ──────────────────────────────────────────────────
    def step(self, thread_id: str, query: str, *, model: str | None = None,
             user_id: str = "app-user", agent_id: str = "app-agent") -> dict:
        """Persist the turn, retrieve a context card, answer with Claude, persist the
        reply, and return the metrics + what was retrieved (for the UI)."""
        from backend.core_anthropic import AGENT_MODEL

        model = model or AGENT_MODEL
        thread = self._thread(thread_id)
        Message = self._Message

        t_start = time.perf_counter()
        with _LOCK:
            thread.add_messages([Message(role="user", content=query)])
            # A lean card (few verbatim recent messages, lean on retrieved memories)
            # keeps OAMP's prompt bounded so the token-vs-naive divergence is clear.
            card = thread.get_context_card(max_recent_messages=2, max_relevant_results=5)
            context_text = (getattr(card, "formatted_content", None)
                            or getattr(card, "content", "") or "(no prior context)")
            memories = self._client.search(
                query, user_id=user_id, agent_id=agent_id,
                max_results=5, record_types=["memory"],
            )
            mem_list = [m.content for m in memories]
        t_retrieved = time.perf_counter()

        answer, usage = call_claude(
            [{"role": "user", "content": f"Relevant memory:\n{context_text}\n\nCurrent question: {query}"}],
            model=model, system=SYSTEM_PROMPT,
        )

        with _LOCK:
            thread.add_messages([Message(role="assistant", content=answer)])
        t_end = time.perf_counter()

        return {
            "answer": answer,
            "context_card": str(context_text),
            "memories": mem_list,
            "input_tokens": prompt_tokens(usage),
            "retrieval_s": round(t_retrieved - t_start, 3),
            "total_s": round(t_end - t_start, 3),
        }


store = MemoryStore()
