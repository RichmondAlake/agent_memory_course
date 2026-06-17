"""The filesystem substrate: agent memory as markdown files on disk.

Writes each note to ``workspace/semantic/<id>.md`` and searches them the way a
filesystem-backed agent does — literal keyword / grep-style matching. Fast to write,
human-readable, git-friendly; but it finds only what is *spelled* the way you asked.
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from backend.config import settings

_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "are", "do", "does",
    "i", "my", "for", "how", "what", "can", "me", "with", "be", "it", "you", "your",
    "this", "that", "from", "at", "as", "by", "if", "we", "our", "when", "why", "even",
    "sometimes", "without", "into", "out", "run", "runs", "use", "uses", "using",
}


def _terms(query: str) -> list[str]:
    toks = re.findall(r"[A-Za-z0-9]+", query.lower())
    meaningful = [t for t in toks if len(t) > 2 and t not in _STOP]
    return meaningful or toks[:1]


class FilesystemSubstrate:
    """Markdown-on-disk memory with literal keyword search."""

    def __init__(self) -> None:
        self.kb_dir = settings.workspace_dir / "semantic" / "knowledge_base"
        self._lock = threading.Lock()

    # ── lifecycle ───────────────────────────────────────────────────────────
    def reset(self) -> None:
        with self._lock:
            if self.kb_dir.exists():
                for f in self.kb_dir.glob("*.md"):
                    f.unlink()
            self.kb_dir.mkdir(parents=True, exist_ok=True)

    def stats(self) -> dict:
        files = list(self.kb_dir.glob("*.md")) if self.kb_dir.exists() else []
        return {
            "backend": "filesystem",
            "doc_count": len(files),
            "bytes": sum(f.stat().st_size for f in files),
            "path": str(self.kb_dir),
        }

    # ── writes ──────────────────────────────────────────────────────────────
    def write(self, doc: dict) -> float:
        """Write one note as a markdown file. Returns latency in milliseconds."""
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        path = self.kb_dir / f"{doc['doc_id']}.md"
        body = f"# {doc['title']}\n\n_Category: {doc['category']}_\n\n{doc['content']}\n"
        t0 = time.perf_counter()
        path.write_text(body, encoding="utf-8")
        return (time.perf_counter() - t0) * 1000

    def write_all(self, docs: list[dict]) -> dict:
        """Ingest the whole corpus. Returns timing + counts for the UI."""
        self.reset()
        t0 = time.perf_counter()
        per = [self.write(d) for d in docs]
        total = (time.perf_counter() - t0) * 1000
        return {
            "backend": "filesystem",
            "doc_count": len(docs),
            "total_ms": round(total, 2),
            "per_doc_ms": round(sum(per) / len(per), 3) if per else 0,
            "note": "Each note is a plain .md file — an instant local write, no indexing.",
        }

    # ── search (literal keyword / grep) ───────────────────────────────────────
    def search(self, query: str, k: int = 4) -> dict:
        """Score files by literal term frequency. Returns hits + latency + method."""
        terms = _terms(query)
        t0 = time.perf_counter()
        scored = []
        files = sorted(self.kb_dir.glob("*.md")) if self.kb_dir.exists() else []
        for f in files:
            text = f.read_text(encoding="utf-8", errors="ignore")
            low = text.lower()
            title = text.splitlines()[0].lstrip("# ").strip() if text else f.stem
            matched = {t: low.count(t) for t in terms if t in low}
            score = sum(matched.values()) + 2 * sum(1 for t in terms if t in title.lower())
            if score > 0:
                scored.append((score, f, title, matched, text))
        scored.sort(key=lambda x: -x[0])

        hits = []
        for score, f, title, matched, text in scored[:k]:
            hits.append({
                "doc_id": f.stem,
                "title": title,
                "score": float(score),
                "matched_terms": sorted(matched.keys()),
                "snippet": self._snippet(text, list(matched.keys())),
            })
        latency = (time.perf_counter() - t0) * 1000
        return {
            "backend": "filesystem",
            "method": "keyword (grep-style literal match)",
            "query_terms": terms,
            "hits": hits,
            "latency_ms": round(latency, 2),
            "command": f"grep -i -E '{'|'.join(terms)}' workspace/semantic/knowledge_base/*.md",
        }

    @staticmethod
    def _snippet(text: str, terms: list[str], width: int = 150) -> str:
        low = text.lower()
        pos = min([low.find(t) for t in terms if low.find(t) >= 0] or [-1])
        if pos < 0:
            return text.strip().replace("\n", " ")[:width] + "…"
        start = max(0, pos - 40)
        return ("…" if start else "") + text[start:start + width].replace("\n", " ").strip() + "…"


fs_substrate = FilesystemSubstrate()
