"""Form Factor 2 — Retrieval-Augmented Generation over Acme's lending policy in Oracle AI Database.

Retrieval on its own (``/search``), the intermediate data behind each technique's visualization
(``/explain``), the latent-space viewer with the pre/in/post filter strategies (``/space``), a
grounded, cited answer (``/answer``), and versioned updates to the policy memory (``/policy``).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.core import db, hnsw_lab, reranker, retrieval, underwriting
from backend.core.anthropic_client import MAX_TOKENS, MODEL, OUTPUT_CONFIG, THINKING, async_client
from backend.core.policy import BULLETINS, CATEGORIES
from backend.core.sse import sse_response
from backend.schemas import HnswQueryRequest, PolicyBulletinRequest, PolicyUpdateRequest, RagRequest, SpaceRequest

router = APIRouter(prefix="/api/rag", tags=["rag"])

RAG_SYSTEM = ("You are Acme Home Loans' mortgage assistant. Answer using ONLY the numbered policy context. "
              "Cite every fact with its bracketed number, like [1]. If the context does not contain the answer, say so.")


def _require_db() -> None:
    if not db.ready():
        raise HTTPException(503, f"Oracle AI Database is not ready: {db.status()['error'] or 'still starting'}")


@router.get("/sql")
def sql(technique: str = "vector", k: int = 4, category: str = "collateral", mode: str = "pre") -> dict:
    return {"technique": technique, "sql": retrieval.sql_for(technique, k, category, mode)}


@router.post("/search")
async def search(req: RagRequest) -> dict:
    _require_db()
    hits = await run_in_threadpool(retrieval.search, req.query, req.technique, req.k)
    return {"technique": req.technique, "hits": [h.as_dict() for h in hits]}


@router.post("/explain")
async def explain(req: RagRequest) -> dict:
    """The intermediate data behind one technique: terms and postings, distances, both RRF lists, or graph hops."""
    _require_db()
    return await run_in_threadpool(retrieval.EXPLAINERS[req.technique], req.query, req.k)


@router.post("/space")
async def space(req: SpaceRequest) -> dict:
    """The latent-space viewer: PCA projection, true cosine distances, and the chosen filter strategy run for real."""
    _require_db()
    return await run_in_threadpool(retrieval.space, req.query, req.k, req.category or None, req.mode, req.accuracy)


@router.get("/hnsw/corpus")
async def hnsw_corpus() -> dict:
    """The policy, one sentence per row, with real embeddings: the HNSW lab ingests these in the browser."""
    _require_db()
    return await run_in_threadpool(hnsw_lab.corpus)


@router.post("/hnsw/query")
async def hnsw_query(req: HnswQueryRequest) -> dict:
    _require_db()
    return await run_in_threadpool(hnsw_lab.query, req.query)


@router.post("/answer")
async def answer(req: RagRequest):
    """Retrieve with the chosen technique, then stream a grounded, cited answer."""
    _require_db()

    async def events():
        if req.rerank:
            candidates = await run_in_threadpool(retrieval.search, req.query, req.technique, max(req.k, reranker.CANDIDATES))
            yield {"type": "status", "text": f"reranking {len(candidates)} candidates with {reranker.MODEL}…"}
            ranked = await run_in_threadpool(reranker.rerank, req.query, candidates, req.k)
            hits = ranked["hits"]
            yield {"type": "rerank", "technique": req.technique, "rows": ranked["rows"], "ms": ranked["ms"], "model": ranked["model"]}
        else:
            hits = await run_in_threadpool(retrieval.search, req.query, req.technique, req.k)
        yield {"type": "sources", "technique": req.technique + (" → rerank" if req.rerank else ""), "hits": [h.as_dict() for h in hits]}
        context = retrieval.context_block([h.as_dict() for h in hits])
        async with async_client.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, output_config=OUTPUT_CONFIG, **THINKING,
                                                system=f"{RAG_SYSTEM}\n\nPolicy context:\n{context}",
                                                messages=[{"role": "user", "content": req.query}]) as stream:
            async for text in stream.text_stream:
                yield {"type": "delta", "text": text}
        yield {"type": "done"}

    return sse_response(events())


@router.get("/policy")
async def policy() -> dict:
    """The policy memory as it stands: every section with its version, the archive, and the bulletins on offer."""
    _require_db()
    sections = await run_in_threadpool(underwriting.policy_sections)
    history = await run_in_threadpool(underwriting.policy_history)
    applied = {h["doc_id"] for h in history}
    return {"sections": sections, "history": history, "categories": CATEGORIES,
            "bulletins": [{"id": key, "label": b["label"], "doc_id": b["doc_id"],
                           "applied": any(s["doc_id"] == b["doc_id"] and s["rules"] == b["rules"] for s in sections)}
                          for key, b in BULLETINS.items()],
            "updated_sections": sorted(applied)}


@router.post("/policy/bulletin")
async def apply_bulletin(req: PolicyBulletinRequest) -> dict:
    """Apply one of the notebook's policy bulletins as a new version of its section."""
    _require_db()
    bulletin = BULLETINS.get(req.bulletin_id)
    if bulletin is None:
        raise HTTPException(404, "Unknown bulletin")
    version = await run_in_threadpool(underwriting.update_policy, bulletin["doc_id"], bulletin["content"],
                                      bulletin["rules"], bulletin["reason"])
    return {"doc_id": bulletin["doc_id"], "version": version}


@router.post("/policy/update")
async def update_section(req: PolicyUpdateRequest) -> dict:
    """Rewrite one section's text (its rules stay as they are) as a new version."""
    _require_db()
    sections = {s["doc_id"]: s for s in await run_in_threadpool(underwriting.policy_sections)}
    if req.doc_id not in sections:
        raise HTTPException(404, "Unknown policy section")
    version = await run_in_threadpool(underwriting.update_policy, req.doc_id, req.content.strip(),
                                      sections[req.doc_id]["rules"], req.reason.strip() or "Edited in the appbook.")
    return {"doc_id": req.doc_id, "version": version}
