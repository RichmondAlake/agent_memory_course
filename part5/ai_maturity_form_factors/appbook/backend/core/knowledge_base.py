"""The Acme Cloud knowledge base — the shared corpus for RAG (FF2), the
workflow (FF3) and the support agent (FF4). Copied verbatim from the notebook."""
from __future__ import annotations

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
