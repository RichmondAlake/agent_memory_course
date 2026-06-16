"""Concept-diagram gallery — lists the module's images grouped by page.

The image filenames use an ``ffN_`` prefix that reflects *slide-deck order*, not the
form factor (e.g. ``ff3_agent.png`` is a Form Factor 4 slide, ``ff3_chunking_strategies.png``
is a retrieval slide). So we map a few by content, and fall back to the prefix /
a humanised caption for anything new dropped into ``images/``.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import IMAGES_DIR

router = APIRouter(prefix="/api", tags=["images"])

_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

# Explicit content-based page placement (overrides the filename prefix).
_PAGE = {
    "form_factors": "home", "form_factors_use_case": "home",
    "ff1_stateless": "chatbot", "ff1_resending_whole_conversation": "chatbot", "ff1_anatomy": "chatbot",
    "ff2_rag": "rag", "ff2_anatomy": "rag", "ff2_text_to_vectors": "rag", "ff2_chunking": "rag",
    "ff2_vector_search": "rag", "ff2_hnsw": "rag", "ff2_retreival_approach": "rag",
    "ff2_rrf": "rag", "ff2_graphrag": "rag",
    "ff3_chunking_strategies": "rag",       # slide: "RETRIEVAL · CHUNKING STRATEGIES"
    "ff3_workflow": "workflow", "ff3_anatomy": "workflow", "ff3_human_in_the_loop": "workflow",
    "ff3_agent": "agent",                   # slide: "FORM FACTOR 4 · THE AGENT"
}

_CAPTION = {
    "form_factors": "The five form factors",
    "form_factors_use_case": "One use case, five ways",
    "ff1_stateless": "LLMs are stateless",
    "ff1_resending_whole_conversation": "Memory = re-sending the conversation",
    "ff1_anatomy": "Anatomy of a chatbot",
    "ff2_rag": "Retrieval-Augmented Generation",
    "ff2_anatomy": "Anatomy of RAG",
    "ff2_text_to_vectors": "From text to vectors",
    "ff2_chunking": "Chunking documents",
    "ff3_chunking_strategies": "Four ways to chunk",
    "ff2_vector_search": "Vector search",
    "ff2_hnsw": "The HNSW vector index",
    "ff2_retreival_approach": "Retrieval approaches compared",
    "ff2_rrf": "Hybrid search · Reciprocal Rank Fusion",
    "ff2_graphrag": "Graph retrieval",
    "ff3_workflow": "The LLM-driven workflow",
    "ff3_anatomy": "Anatomy of a workflow",
    "ff3_human_in_the_loop": "Human in the loop",
    "ff3_agent": "The four faculties of an agent",
}

# Display order within a page (anything unlisted sorts to the end, alphabetically).
_ORDER = [
    "form_factors", "form_factors_use_case",
    "ff1_stateless", "ff1_resending_whole_conversation", "ff1_anatomy",
    "ff2_rag", "ff2_anatomy", "ff2_text_to_vectors", "ff2_chunking", "ff3_chunking_strategies",
    "ff2_vector_search", "ff2_hnsw", "ff2_retreival_approach", "ff2_rrf", "ff2_graphrag",
    "ff3_workflow", "ff3_anatomy", "ff3_human_in_the_loop", "ff3_agent",
]

_PREFIX_PAGE = (("ff1_", "chatbot"), ("ff2_", "rag"), ("ff3_", "workflow"),
                ("ff4_", "agent"), ("ff5_", "builder"), ("form_factors", "home"))


def _humanize(stem: str) -> str:
    for p in ("ff1_", "ff2_", "ff3_", "ff4_", "ff5_"):
        if stem.startswith(p):
            stem = stem[len(p):]
            break
    return stem.replace("_", " ").strip().capitalize()


def _page_for(stem: str) -> str:
    if stem in _PAGE:
        return _PAGE[stem]
    for pre, pg in _PREFIX_PAGE:
        if stem.startswith(pre):
            return pg
    return "home"


@router.get("/images")
def images() -> dict:
    """Return {pages: {pageKey: [{src, caption}]}} for the UI's per-page gallery."""
    pages: dict[str, list] = {}
    if not IMAGES_DIR.exists():
        return {"pages": pages}
    files = [p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in _IMG_EXT]
    files.sort(key=lambda p: (_ORDER.index(p.stem) if p.stem in _ORDER else 999, p.name))
    for p in files:
        pages.setdefault(_page_for(p.stem), []).append(
            {"src": f"/images/{p.name}", "caption": _CAPTION.get(p.stem, _humanize(p.stem))}
        )
    return {"pages": pages}
