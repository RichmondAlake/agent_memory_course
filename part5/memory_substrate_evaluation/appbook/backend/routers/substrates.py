"""Substrate endpoints: ingest the corpus, search both substrates, answer, reset."""
from __future__ import annotations

from fastapi import APIRouter

from backend.core import anthropic_client
from backend.core.corpus import DOCS
from backend.core.db_substrate import db_substrate
from backend.core.fs_substrate import fs_substrate
from backend.schemas import AnswerRequest, SearchRequest

router = APIRouter(prefix="/api")


@router.post("/ingest")
def ingest():
    """Write the identical corpus into BOTH substrates and report the timing gap."""
    fs_res = fs_substrate.write_all(DOCS)
    db_res = db_substrate.write_all(DOCS)
    return {"fs": fs_res, "db": db_res}


@router.post("/search")
def search(req: SearchRequest):
    """Run the same query against both substrates: keyword (FS) vs semantic (DB)."""
    return {
        "query": req.query,
        "fs": fs_substrate.search(req.query, req.k),
        "db": db_substrate.search(req.query, req.k),
    }


@router.post("/answer")
def answer(req: AnswerRequest):
    """Retrieve from each substrate, then let Claude answer ONLY from that context.

    The payoff of the retrieval lesson: identical model, identical question — the
    answer quality tracks the retrieval quality.
    """
    fs_search = fs_substrate.search(req.query, req.k)
    db_search = db_substrate.search(req.query, req.k)
    fs_ctx = "\n\n".join(f"- {h['title']}: {h.get('snippet', '')}" for h in fs_search["hits"])
    db_ctx = "\n\n".join(f"- {h['title']}: {h.get('snippet', '')}" for h in db_search["hits"])

    out = {
        "query": req.query,
        "model_present": anthropic_client.has_key(),
        "fs": {"hits": fs_search["hits"], "answer": None},
        "db": {"hits": db_search["hits"], "answer": None},
    }
    if anthropic_client.has_key():
        out["fs"]["answer"] = anthropic_client.answer_from_context(req.query, fs_ctx)
        out["db"]["answer"] = anthropic_client.answer_from_context(req.query, db_ctx)
    else:
        msg = "Set ANTHROPIC_API_KEY to see Claude answer from each substrate's retrieved context."
        out["fs"]["answer"] = out["db"]["answer"] = msg
    return out


@router.post("/reset")
def reset():
    """Clear both substrates so the demo can be re-run from scratch."""
    fs_substrate.reset()
    db_substrate.reset()
    return {"ok": True, "fs": fs_substrate.stats(), "db": db_substrate.status()}
