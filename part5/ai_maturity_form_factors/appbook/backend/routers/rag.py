"""Form Factor 2 — Retrieval-Augmented Generation.

Retrieve from Oracle AI Database (or the in-memory fallback) using a chosen
technique, then generate an answer grounded **only** in the retrieved context,
with bracketed citations. Exposes retrieval on its own (`/search`) so the UI can
show *what* was retrieved and let users compare vector / keyword / hybrid.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.anthropic_client import MAX_TOKENS, MODEL, async_client
from backend.core.retrieval import RAG_SQL, store
from backend.core.sse import sse_response
from backend.schemas import RagRequest

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/sql")
def sql(technique: str = "vector") -> dict:
    """The Oracle SQL each retrieval technique runs — shown in the UI's SQL pane.
    (When the in-memory fallback is active, this is still the Oracle SQL it mirrors.)"""
    technique = (technique or "vector").lower()
    return {
        "technique": technique,
        "sql": RAG_SQL.get(technique, RAG_SQL["vector"]),
        "backend": store.backend,
    }


@router.post("/search")
async def search(req: RagRequest) -> dict:
    """Retrieval only — returns the ranked hits for the chosen technique."""
    hits = await run_in_threadpool(store.search, req.query, req.technique, req.k)
    return {
        "backend": store.backend,
        "technique": req.technique,
        "hits": [h.as_dict() for h in hits],
    }


@router.post("/answer")
async def answer(req: RagRequest):
    """Retrieve, then stream a grounded, cited answer."""

    async def events():
        hits = await run_in_threadpool(store.search, req.query, req.technique, req.k)
        yield {
            "type": "sources",
            "backend": store.backend,
            "technique": req.technique,
            "hits": [h.as_dict() for h in hits],
        }

        context = "\n".join(f"[{i + 1}] {h.content}" for i, h in enumerate(hits))
        system = (
            "You are the Acme Cloud support assistant. Answer the question using ONLY the "
            "context below. Cite the sources you use with bracketed numbers like [1]. "
            "If the answer is not in the context, say you don't have that information.\n\n"
            f"Context:\n{context}"
        )
        async with async_client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": req.query}],
        ) as stream:
            async for text in stream.text_stream:
                yield {"type": "delta", "text": text}
        yield {"type": "done"}

    return sse_response(events())
