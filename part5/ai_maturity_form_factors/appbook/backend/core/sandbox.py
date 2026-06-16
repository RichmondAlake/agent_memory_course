"""The Form Factor 5 sandbox — a disposable workspace seeded with a sample dataset.

Kept import-light (no Anthropic client, no agent SDK) so it can be seeded at
container-create time, before any API key is configured.
"""
from __future__ import annotations

import csv
import shutil

from backend.config import settings

SANDBOX = settings.sandbox_dir
SEED_FILE = "support_messages.csv"
# Columns id,category,priority,message — matches the notebook's Form Factor 5.
SEED_ROWS = [
    {"id": 1, "category": "billing",   "priority": "high",   "message": "I was double charged for my Pro seats"},
    {"id": 2, "category": "technical", "priority": "high",   "message": "API returns 500 on /v1/sync"},
    {"id": 3, "category": "billing",   "priority": "low",    "message": "How do I upgrade to Pro?"},
    {"id": 4, "category": "account",   "priority": "medium", "message": "Need to add a teammate"},
    {"id": 5, "category": "technical", "priority": "medium", "message": "Webhooks are not firing"},
    {"id": 6, "category": "billing",   "priority": "medium", "message": "Invoice VAT amount looks wrong"},
    {"id": 7, "category": "account",   "priority": "low",    "message": "Change the account owner"},
]


def reset_sandbox() -> None:
    """Clear the sandbox and (re)write the seed dataset, so each run starts clean."""
    SANDBOX.mkdir(parents=True, exist_ok=True)
    for child in SANDBOX.iterdir():
        if child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child, ignore_errors=True)
    with open(SANDBOX / SEED_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "priority", "message"])
        writer.writeheader()
        writer.writerows(SEED_ROWS)


def seed_if_empty() -> None:
    """Seed the sandbox only if it doesn't already contain the dataset (for setup-time use)."""
    if not (SANDBOX / SEED_FILE).exists():
        reset_sandbox()
