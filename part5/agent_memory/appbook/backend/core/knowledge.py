"""Knowledge Base layer — the Acme Cloud corpus, ingested via memorizz `KnowledgeBase`.

Mirrors notebook §5: each doc is ingested as a single document (``chunking_strategy
="none"``) into one namespace, then retrieved by vector similarity. Seeding is
idempotent and cached, so the first call warms it and later calls are instant.
The docs are the same synthetic Acme Cloud corpus used across the workshop.
"""
from __future__ import annotations

import threading
from typing import Any

NAMESPACE = "acme-docs"

DOCS: list[dict[str, str]] = [
    {"doc_id": "plans", "title": "Plans & Pricing", "category": "billing",
     "content": "Acme Cloud offers three plans. Free includes 1 project and community support. "
                "Pro is $49 per user per month with email support and advanced analytics. "
                "Enterprise has custom pricing, SSO, and a dedicated support engineer."},
    {"doc_id": "rate_limits", "title": "API Rate Limits", "category": "api",
     "content": "Acme Cloud enforces API rate limits per plan. The Free plan allows 60 requests "
                "per minute. The Pro plan allows 1,000 requests per minute. Enterprise rate limits "
                "are negotiated per contract."},
    {"doc_id": "upgrade", "title": "Upgrading Your Plan", "category": "billing",
     "content": "To upgrade, open Settings, then Billing, then Change Plan. Upgrades take effect "
                "immediately and are pro-rated for the current billing cycle."},
    {"doc_id": "regions", "title": "Data Residency & Regions", "category": "data",
     "content": "Acme Cloud stores data in US, EU (Frankfurt), and APAC (Singapore) regions. "
                "The region is chosen at project creation and cannot be changed afterward."},
    {"doc_id": "sla", "title": "Service Level Agreement", "category": "reliability",
     "content": "Acme Cloud guarantees 99.9% uptime on the Pro plan and 99.99% on Enterprise. "
                "SLA credits are issued automatically when monthly uptime falls below target."},
    {"doc_id": "support", "title": "Support Channels & Response Times", "category": "support",
     "content": "Free plan customers use the community forum. Pro email support responds within one "
                "business day. Enterprise includes 24/7 support with a one-hour response target for "
                "critical issues."},
    {"doc_id": "api_keys", "title": "Creating & Rotating API Keys", "category": "api",
     "content": "Create and rotate API keys under Settings, then API Keys. Rotating a key immediately "
                "revokes the previous one, so update your applications before rotating."},
    {"doc_id": "sso", "title": "Single Sign-On (SSO)", "category": "security",
     "content": "SSO is available on the Enterprise plan and supports SAML 2.0 and OIDC. An "
                "administrator configures the identity provider under Settings, then Security, then SSO."},
    {"doc_id": "webhooks", "title": "Webhooks", "category": "integrations",
     "content": "Acme Cloud can send webhooks on project events. Configure endpoint URLs under "
                "Settings, then Webhooks. Failed deliveries are retried with exponential backoff for "
                "up to 24 hours."},
    {"doc_id": "backups", "title": "Backups & Recovery", "category": "data",
     "content": "Acme Cloud takes automated daily backups retained for 30 days on Pro and 90 days on "
                "Enterprise. Point-in-time recovery is available on the Enterprise plan."},
    {"doc_id": "roles", "title": "Team Roles & Permissions", "category": "account",
     "content": "Acme Cloud supports Owner, Admin, Member, and Viewer roles. Only Owners and Admins "
                "can manage billing, invite teammates, or rotate API keys."},
    {"doc_id": "export", "title": "Exporting Your Data", "category": "data",
     "content": "You can export project data as JSON or CSV from Settings, then Export. Large exports "
                "are emailed as a downloadable archive when ready."},
]

_lock = threading.Lock()
_state: dict[str, Any] = {"kb": None, "by_kb_id": {}, "seeded": False}


def seed(provider) -> Any:
    """Ingest the corpus once into the shared provider; return the KnowledgeBase."""
    with _lock:
        if _state["seeded"] and _state["kb"] is not None:
            return _state["kb"]
    from memorizz import KnowledgeBase

    kb = KnowledgeBase(provider)
    # Idempotent: drop anything previously ingested into this namespace.
    try:
        prior = kb.retrieve_knowledge_by_query("acme cloud", namespace=NAMESPACE, limit=100)
        for kid in {h.get("knowledge_base_id") for h in prior if h.get("knowledge_base_id")}:
            kb.delete_knowledge(kid)
    except Exception:
        pass

    by_kb_id: dict[str, dict] = {}
    for doc in DOCS:
        kb_id = kb.ingest_knowledge(corpus=doc["content"], namespace=NAMESPACE, chunking_strategy="none")
        by_kb_id[kb_id] = doc

    with _lock:
        _state.update(kb=kb, by_kb_id=by_kb_id, seeded=True)
    return kb


def search(provider, query: str, k: int = 4) -> list[dict]:
    """Vector search the corpus; return hits in the shape the SPA's source cards expect."""
    kb = seed(provider)
    hits = kb.retrieve_knowledge_by_query(query, namespace=NAMESPACE, limit=k)
    out: list[dict] = []
    for i, h in enumerate(hits):
        doc = _state["by_kb_id"].get(h.get("knowledge_base_id"), {})
        score = h.get("score", h.get("similarity"))
        if score is None:                       # provider didn't surface a distance — use rank
            score = round(1.0 - i * (0.6 / max(k, 1)), 3)
        out.append({
            "doc_id": doc.get("doc_id", ""),
            "title": doc.get("title") or h.get("namespace", "document"),
            "category": doc.get("category", ""),
            "content": h.get("content", doc.get("content", "")),
            "score": float(score),
        })
    return out
