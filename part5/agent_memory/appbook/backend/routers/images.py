"""Concept-diagram gallery — lists this module's overview diagrams for the UI."""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import IMAGES_DIR

router = APIRouter(prefix="/api", tags=["images"])

_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_CAPTION = {"agent_memory_types": "The agent memory stack — types of memory"}


def _humanize(stem: str) -> str:
    return stem.replace("_", " ").strip().capitalize()


@router.get("/images")
def images() -> dict:
    """Overview diagrams, shown on the home/overview page's gallery."""
    pages: dict[str, list] = {}
    if not IMAGES_DIR.exists():
        return {"pages": pages}
    for p in sorted(IMAGES_DIR.iterdir()):
        if p.suffix.lower() in _IMG_EXT:
            pages.setdefault("home", []).append(
                {"src": f"/images/{p.name}", "caption": _CAPTION.get(p.stem, _humanize(p.stem))}
            )
    return {"pages": pages}
