"""The Memory Core — a single memorizz memory provider shared by every layer.

Mirrors the notebook's §0: try Oracle AI Database; if it's unset or unreachable,
fall back to memorizz's FileSystemProvider (FAISS) so the whole app still runs.
The active backend is reported to the UI via ``/api/health``.

Also exposes small helpers used by every router:
  • ``llm_config``       — the OpenAI config dict (gpt-4o-mini), like the notebook
  • ``build_agent(...)`` — a configured MemAgent on the shared provider
  • ``stream_text(...)`` — turn a (sync) MemAgent.run into SSE delta/done events
"""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Callable, Iterator

from fastapi.concurrency import run_in_threadpool

from backend.config import settings

_lock = threading.Lock()


class MemoryCore:
    """Lazily-initialised memorizz provider with graceful Oracle→filesystem fallback."""

    def __init__(self) -> None:
        self.provider: Any = None
        self.backend: str | None = None      # "oracle" | "filesystem"
        self.ready: bool = False
        self.error: str | None = None
        self._started = False

    # ── lifecycle ───────────────────────────────────────────────────────────
    def initialize(self) -> Any:
        with _lock:
            if self.ready:
                return self.provider
            if self._started and self.provider is not None:
                return self.provider
            self._started = True

        embedding_config = {
            "model": settings.embed_model,
            "dimensions": settings.embed_dimensions,
            "api_key": settings.openai_api_key,
        }

        provider, backend, err = None, None, None

        if settings.oracle_enabled:
            try:
                from memorizz.memory_provider.oracle import OracleConfig, OracleProvider

                provider = OracleProvider(
                    OracleConfig(
                        user=settings.oracle_user,
                        password=settings.oracle_password,
                        dsn=settings.oracle_dsn,
                        schema=settings.oracle_user,
                        lazy_vector_indexes=False,
                        embedding_provider="openai",
                        embedding_config=embedding_config,
                    )
                )
                backend = "oracle"
            except Exception as exc:  # noqa: BLE001 — any failure → fall back
                err = f"Oracle unavailable ({type(exc).__name__}); using filesystem fallback."

        if provider is None:
            from memorizz.memory_provider.filesystem import FileSystemConfig, FileSystemProvider

            root = Path(settings.fs_root).expanduser()
            root.mkdir(parents=True, exist_ok=True)
            provider = FileSystemProvider(
                FileSystemConfig(
                    root_path=root,
                    embedding_provider="openai",
                    embedding_config=embedding_config,
                )
            )
            backend = "filesystem"

        with _lock:
            self.provider, self.backend, self.error, self.ready = provider, backend, err, True
        return provider

    def require(self) -> Any:
        return self.provider if self.ready else self.initialize()

    def status(self) -> dict:
        return {"ready": self.ready, "backend": self.backend or "warming", "note": self.error}

    # ── shared config ───────────────────────────────────────────────────────
    @property
    def llm_config(self) -> dict:
        return {"provider": "openai", "model": settings.model, "api_key": settings.openai_api_key}

    def build_agent(
        self,
        instruction: str,
        *,
        name: str | None = None,
        tools: list | None = None,
        persona: Any = None,
        entity_memory: bool = False,
        semantic_cache: bool = False,
        application_mode: str | None = None,
        delegates: list | None = None,
    ):
        """Construct a MemAgent on the shared provider, mirroring the notebook's builder."""
        from memorizz.memagent.builders import MemAgentBuilder

        b = (
            MemAgentBuilder()
            .with_instruction(instruction)
            .with_memory_provider(self.require())
            .with_llm_config(self.llm_config)
        )
        if name:
            b = b.with_name(name)
        if tools:
            b = b.with_tools(tools)
        if persona is not None:
            b = b.with_persona(persona)
        if entity_memory:
            b = b.with_entity_memory(True)
        if semantic_cache:
            b = b.with_semantic_cache(enabled=True, threshold=0.9)
        if application_mode:
            b = b.with_application_mode(application_mode)
        if delegates:
            b = b.with_delegates(delegates)
        return b.build()


store = MemoryCore()


# ── streaming helpers ────────────────────────────────────────────────────────
def _word_chunks(text: str, size: int = 5) -> Iterator[str]:
    """Yield the text in small word groups so the UI types it out smoothly."""
    words = (text or "").split(" ")
    for i in range(0, len(words), size):
        piece = " ".join(words[i : i + size])
        yield piece if i == 0 else " " + piece


async def run_agent(run_callable: Callable[[], str]) -> str:
    """Run a blocking MemAgent call off the event loop."""
    answer = await run_in_threadpool(run_callable)
    return answer if isinstance(answer, str) else str(answer)


async def pseudo_stream(answer: str, *, delay: float = 0.012):
    """Type out an already-computed answer as ``delta`` events.

    Token-true streaming is available via ``MemAgent.run_stream``; we type out the
    final string here because it is robust regardless of provider/model. Routers
    pair this with their own trailing ``done`` event.
    """
    for piece in _word_chunks(answer):
        yield {"type": "delta", "text": piece}
        await asyncio.sleep(delay)


def unavailable_reason() -> str | None:
    """A human-friendly reason the AI layers can't run yet, or None if good to go.

    Lets routers fail with a clean SSE ``error`` event instead of an HTTP 500.
    """
    if not settings.openai_api_key:
        return ("OPENAI_API_KEY is not set, so the Memory Core can't embed or call the model. "
                "Add it to appbook/.env (OPENAI_API_KEY=sk-...) and restart the server.")
    return None


async def error_stream(message: str):
    """A one-event async generator that emits a single SSE error event."""
    yield {"type": "error", "message": message}


# ── context-window telemetry ─────────────────────────────────────────────────
# Drives the right-hand "Context Window" rail: a segmented view of what memory is
# packed into the agent's prompt this turn, prefilled segment-by-segment in real time.
def _estimate_tokens(text: Any) -> int:
    if not text:
        return 0
    return max(1, round(len(str(text)) / 4))   # ~4 chars/token heuristic


def compute_context_segments(
    agent,
    query: str,
    *,
    history_memory_id: str | None = None,
    kb_hits: list | None = None,
    tools_text: str | None = None,
    extra: list | None = None,
    base_instruction: str | None = None,
):
    """Best-effort breakdown of what fills the agent's context window this turn.

    Returns ``(window_tokens, segments)`` where each segment is
    ``{"label", "kind", "tokens"}``. Every probe is defensive so a missing
    attribute never breaks the run — this is a teaching visualization, not billing.
    """
    segs: list[dict] = []
    PREVIEW_CHARS = 1400   # cap per-segment content so the SSE payload stays small

    def add(label: str, kind: str, text: Any) -> None:
        text = "" if text is None else str(text)
        toks = _estimate_tokens(text)
        if toks:
            segs.append({
                "label": label,
                "kind": kind,
                "tokens": toks,
                "chars": len(text),
                "preview": text[:PREVIEW_CHARS],          # the ACTUAL content packed into the window
                "truncated": len(text) > PREVIEW_CHARS,
            })

    try:
        sys_text = base_instruction if base_instruction is not None else (getattr(agent, "instruction", "") or "")
        add("System prompt", "system", sys_text)
    except Exception:
        pass
    try:
        persona = getattr(agent, "persona", None)
        if persona is not None:
            if isinstance(persona, str):
                ptext = persona
            else:
                pd = persona.to_dict() if hasattr(persona, "to_dict") else getattr(persona, "__dict__", {})
                fields = [(k, pd.get(k)) for k in ("name", "role", "goals", "background") if pd.get(k)]
                ptext = "\n".join(f"{k}: {v}" for k, v in fields) or json.dumps(pd, default=str)
            add("Persona", "persona", ptext)
    except Exception:
        pass
    try:
        hist = (
            agent.load_conversation_history(history_memory_id)
            if history_memory_id
            else agent.load_conversation_history()
        ) or []
        if hist:
            txt = " ".join(
                str(h.get("content", "")) if isinstance(h, dict) else str(h) for h in hist
            )
            add(f"Conversation · {len(hist)} msgs", "history", txt)
    except Exception:
        pass
    try:
        from memorizz.long_term.semantic.entity_memory.entity_memory import EntityMemory

        ents = EntityMemory(store.require()).list_entities() or []
        if ents:
            lines = []
            for e in ents:
                if not isinstance(e, dict):
                    continue
                name = e.get("name") or e.get("entity_id") or "entity"
                etype = e.get("entity_type") or ""
                attrs = e.get("attributes") if isinstance(e.get("attributes"), list) else []
                pairs = [f"{a.get('name')}={a.get('value', '')}"
                         for a in attrs if isinstance(a, dict) and a.get("name") is not None]
                head = name + (f" ({etype})" if etype else "")
                lines.append(head + (": " + ", ".join(pairs) if pairs else ""))
            add(f"Entities · {len(ents)}", "entity", "\n".join(lines))
    except Exception:
        pass
    if kb_hits:
        txt = " ".join(h.get("content", "") for h in kb_hits if isinstance(h, dict))
        add(f"Knowledge · {len(kb_hits)} chunks", "knowledge", txt)
    try:
        sums = agent.list_context_summaries() or []
        if sums:
            txt = "\n".join(
                f"- {s.get('short_description', s)}" if isinstance(s, dict) else f"- {s}"
                for s in sums
            )
            add(f"Summaries · {len(sums)}", "summary", txt)
    except Exception:
        pass
    if tools_text:
        add("Tools", "tools", tools_text)
    for item in extra or []:
        add(item.get("label", "extra"), item.get("kind", "extra"), item.get("text", ""))
    add("User query", "query", query)

    window = None
    try:
        stats = agent.get_context_window_stats() or {}
        window = stats.get("context_window_tokens")
    except Exception:
        pass
    window = window or getattr(agent, "context_window_tokens", None) or 128000
    return int(window), segs


async def prefill_context_events(window: int, segments: list, *, delay: float = 0.14):
    """Emit ``context`` events one segment at a time, so the rail visibly fills up."""
    shown: list[dict] = []
    for seg in segments:
        shown.append(seg)
        yield {
            "type": "context",
            "stage": "prefill",
            "window": window,
            "used": sum(s["tokens"] for s in shown),
            "segments": list(shown),
        }
        await asyncio.sleep(delay)


def final_context_event(agent, window: int, segments: list) -> dict:
    """A trailing ``context`` event reconciled to the agent's real token counts."""
    used = sum(s["tokens"] for s in segments)
    try:
        stats = agent.get_context_window_stats() or {}
        used = stats.get("prompt_tokens") or stats.get("total_tokens") or used
        window = stats.get("context_window_tokens") or window
    except Exception:
        pass
    return {
        "type": "context",
        "stage": "final",
        "window": int(window),
        "used": int(used),
        "segments": segments,
    }
