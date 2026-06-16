"""Tavily web search for the Deep Research mode. Optional — degrades to None."""
from __future__ import annotations

from backend.config import settings

WEB_AVAILABLE = bool(settings.tavily_api_key)

_client = None


def _get_client():
    global _client
    if _client is None:
        from tavily import TavilyClient
        _client = TavilyClient(api_key=settings.tavily_api_key)
    return _client


def web_search(query: str, max_results: int = 4) -> dict:
    """Return {answer, results:[{title,url,content}]}. Empty on failure / no key."""
    if not WEB_AVAILABLE:
        return {"answer": "", "results": []}
    try:
        resp = _get_client().search(
            query=query, max_results=max_results,
            search_depth="advanced", include_answer=True,
        )
        return {
            "answer": resp.get("answer", "") or "",
            "results": [
                {"title": r.get("title", ""), "url": r.get("url", ""),
                 "content": (r.get("content", "") or "")[:400]}
                for r in resp.get("results", [])
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"answer": "", "results": [], "error": f"{type(exc).__name__}: {exc}"}
