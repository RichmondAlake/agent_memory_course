"""Minimal Anthropic client for the optional 'answer from retrieved context' payoff.

Closes the retrieval lesson: feed each substrate's retrieved context to Claude and
let the user see that better retrieval yields a better-grounded answer. Entirely
optional — if no ANTHROPIC_API_KEY is set, the endpoint returns a clear message and
the rest of the app is unaffected.
"""
from __future__ import annotations

import anthropic

from backend.config import settings

_key = settings.anthropic_api_key or "ANTHROPIC_API_KEY_NOT_SET"
client = anthropic.Anthropic(api_key=_key)
MODEL = settings.model


def has_key() -> bool:
    return bool(settings.anthropic_api_key)


def text_of(response) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text")


def answer_from_context(query: str, context: str) -> str:
    """Answer a question using ONLY the supplied context (grounded, no outside knowledge)."""
    system = (
        "You answer strictly from the provided context. If the context does not contain "
        "the answer, reply exactly: 'The retrieved context does not contain this.' "
        "Keep the answer to 2-3 sentences."
    )
    user = f"Context:\n{context if context.strip() else '(no passages retrieved)'}\n\nQuestion: {query}"
    resp = client.messages.create(
        model=MODEL,
        max_tokens=settings.max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return text_of(resp).strip()
