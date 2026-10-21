"""The Form Factor 5 sandbox: a workspace seeded with broker batches and the policy exported from Oracle.

Kept import-light (no Anthropic client, no agent SDK) so it can be seeded before any key is configured.
The folder persists between conversations on purpose: a tool the agent builds there is procedural memory
that later sessions can find and reuse. ``reset_sandbox`` starts it over.
"""
from __future__ import annotations

import csv
import json
import mimetypes
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

SANDBOX = settings.sandbox_dir.resolve()
FIELDS = ["id", "applicant", "gross_monthly_income", "monthly_debts", "loan_amount", "property_value",
          "property_use", "credit_score", "liquid_reserves", "employment_months"]
BATCHES = {
    "applications_batch1.csv": [
        (1, "Ada Okafor", 9800, 600, 352000, 440000, "primary", 760, 45000, 84),
        (2, "Ben Chen", 6500, 900, 300000, 320000, "primary", 690, 9000, 30),
        (3, "Clara Duarte", 11000, 1200, 400000, 500000, "investment", 720, 20000, 120),
        (4, "Ella Farah", 8800, 300, 330000, 360000, "second_home", 735, 25000, 60),
        (5, "Felix Gomez", 10400, 1500, 380000, 475000, "primary", 702, 15000, 18),
        (6, "Gina Haddad", 12000, 800, 420000, 525000, "primary", 780, 50000, 96),
    ],
    "applications_batch2.csv": [
        (7, "Hiro Ito", 5600, 400, 230000, 250000, "primary", 628, 7000, 40),
        (8, "Iris Jensen", 9000, 1000, 340000, 400000, "primary", 744, 3000, 50),
        (9, "Jan Kowalski", 9500, 700, 361000, 380000, "primary", 725, 20000, 70),
        (10, "Kai Lindqvist", 15000, 2000, 600000, 800000, "investment", 790, 70000, 150),
        (11, "Lena Moreau", 10200, 600, 360000, 450000, "primary", 668, 30000, 48),
    ],
    "applications_batch3.csv": [
        (12, "Dev Evans", 7600, 500, 270000, 300000, "primary", 655, 8000, 26),
        (13, "Mira Nakamura", 7000, 1100, 250000, 280000, "primary", 700, 12000, 36),
        (14, "Noah Osei", 8300, 450, 272000, 320000, "primary", 646, 15000, 60),
        (15, "Omar Patel", 10200, 600, 360000, 450000, "primary", 668, 30000, 48),
    ],
}
_TEXT = {".py", ".json", ".csv", ".txt", ".md", ".cfg", ".ini", ".sh", ".yaml", ".yml", ".log", ".html", ".svg"}
_IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_MAX_TEXT = 40_000


def export_policy(rules: dict, versions: dict) -> dict:
    """Write the rules in force (from Oracle's POLICY_DOCS) to policy.json, as the notebook's §5.1 does."""
    exported = {"source": "Oracle POLICY_DOCS", "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "versions": versions, "rules": rules}
    SANDBOX.mkdir(parents=True, exist_ok=True)
    (SANDBOX / "policy.json").write_text(json.dumps(exported, indent=2))
    return exported


def seed_batches() -> None:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    for name, rows in BATCHES.items():
        with open(SANDBOX / name, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(FIELDS)
            writer.writerows(rows)


def reset_sandbox(policy: tuple[dict, dict] | None = None) -> None:
    """Empty the sandbox and write the broker batches (and policy.json when the rules are given)."""
    SANDBOX.mkdir(parents=True, exist_ok=True)
    for child in SANDBOX.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
        else:
            shutil.rmtree(child, ignore_errors=True)
    seed_batches()
    if policy:
        export_policy(*policy)


def seed_if_empty() -> None:
    if not (SANDBOX / "applications_batch1.csv").exists():
        reset_sandbox()


# ── confinement for the agent ─────────────────────────────────────────────────────
# `cwd` only sets where the agent starts; it is not a boundary. A PreToolUse hook guards the file
# tools, and the SDK's OS-level sandbox confines Bash (Seatbelt on macOS, bubblewrap on Linux).
FILE_TOOLS = "Read|Write|Edit|Glob|Grep"
BASH_SANDBOX: dict[str, Any] = {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False}


def inside_sandbox(path: str) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = SANDBOX / candidate
    return candidate.resolve().is_relative_to(SANDBOX)


def file_list() -> list[dict]:
    """Every file in the sandbox (recursively), newest first, with its kind."""
    if not SANDBOX.exists():
        return []
    files = []
    for p in SANDBOX.rglob("*"):
        if not p.is_file() or any(part.startswith(".") for part in p.relative_to(SANDBOX).parts):
            continue
        suffix = p.suffix.lower()
        files.append({"path": str(p.relative_to(SANDBOX)), "size": p.stat().st_size, "mtime": p.stat().st_mtime,
                      "kind": "image" if suffix in _IMAGE else "text" if suffix in _TEXT else "binary"})
    return sorted(files, key=lambda f: -f["mtime"])


def snapshot() -> dict[str, float]:
    return {f["path"]: f["mtime"] for f in file_list()}


def resolve(path: str) -> Path | None:
    """A sandbox file by relative path, or None if it escapes the sandbox or does not exist."""
    candidate = (SANDBOX / path).resolve()
    if not candidate.is_relative_to(SANDBOX) or not candidate.is_file():
        return None
    return candidate


def read_text(path: str) -> dict | None:
    p = resolve(path)
    if p is None:
        return None
    data = p.read_bytes()
    return {"path": path, "size": len(data), "truncated": len(data) > _MAX_TEXT,
            "content": data[:_MAX_TEXT].decode("utf-8", errors="replace"),
            "mime": mimetypes.guess_type(p.name)[0] or "text/plain"}
