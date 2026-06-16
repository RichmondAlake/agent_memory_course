"""Automation store + lightweight in-process scheduler for Form Factor 5.

After the builder agent writes a re-runnable script, the user can **save it as an
automation**: we snapshot the sandbox into ``automations/<id>/work`` and record a
run command. The automation can then be run on demand or on a schedule
(once / interval / daily). Every run records its exit code and output. State
persists to ``registry.json`` so saved automations survive a restart.

This is what makes Form Factor 5 an agent that *creates automation*: the built
script is remembered, stored, and re-run later — not a one-shot answer.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from backend.config import BACKEND_DIR, settings

try:
    import json
except ImportError:  # pragma: no cover
    raise

AUTOMATIONS_DIR = BACKEND_DIR / "automations"
REGISTRY = AUTOMATIONS_DIR / "registry.json"
SANDBOX = settings.sandbox_dir

_MAX_OUTPUT = 4000        # chars of stdout/stderr kept per run
_MAX_RUNS = 20            # runs kept per automation
_RUN_TIMEOUT = 60         # seconds per run


def _now() -> float:
    return time.time()


def _next_daily(hhmm: str) -> float:
    """Epoch of the next occurrence of HH:MM (today if still ahead, else tomorrow)."""
    try:
        hh, mm = (int(x) for x in hhmm.split(":"))
    except Exception:  # noqa: BLE001
        hh, mm = 8, 0
    now = datetime.now()
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.timestamp()


def _compute_next_run(schedule: dict) -> float | None:
    kind = (schedule or {}).get("type", "manual")
    now = _now()
    if kind == "once":
        return now + float(schedule.get("delay_minutes", 0)) * 60
    if kind == "interval":
        return now + max(1.0, float(schedule.get("every_minutes", 5))) * 60
    if kind == "daily":
        return _next_daily(schedule.get("at", "08:00"))
    return None  # manual


def _advance(schedule: dict, prev_next: float) -> float | None:
    """Next run after a fire (or None for one-shot / manual)."""
    kind = (schedule or {}).get("type", "manual")
    if kind == "interval":
        step = max(1.0, float(schedule.get("every_minutes", 5))) * 60
        nxt = prev_next + step
        while nxt <= _now():        # catch up if we were asleep
            nxt += step
        return nxt
    if kind == "daily":
        return _next_daily(schedule.get("at", "08:00"))
    return None  # once / manual → no further runs


def _schedule_label(schedule: dict) -> str:
    kind = (schedule or {}).get("type", "manual")
    if kind == "once":
        return f"once, in {schedule.get('delay_minutes', 0)} min"
    if kind == "interval":
        return f"every {schedule.get('every_minutes', 5)} min"
    if kind == "daily":
        return f"daily at {schedule.get('at', '08:00')}"
    return "manual"


class AutomationStore:
    """Thread-safe registry of saved automations + their scheduled runs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, dict] = {}
        AUTOMATIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────
    def _load(self) -> None:
        if REGISTRY.exists():
            try:
                data = json.loads(REGISTRY.read_text(encoding="utf-8"))
                self._items = {a["id"]: a for a in data.get("automations", [])}
            except Exception:  # noqa: BLE001
                self._items = {}

    def _save(self) -> None:
        REGISTRY.write_text(
            json.dumps({"automations": list(self._items.values())}, indent=2),
            encoding="utf-8",
        )

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _workdir(aid: str) -> Path:
        return AUTOMATIONS_DIR / aid / "work"

    def _public(self, a: dict) -> dict:
        """Shape an automation for the API (latest run summary + next-run hint)."""
        runs = a.get("runs", [])
        last = runs[-1] if runs else None
        return {
            "id": a["id"],
            "name": a["name"],
            "command": a["command"],
            "created": a["created"],
            "schedule": a.get("schedule", {"type": "manual"}),
            "schedule_label": _schedule_label(a.get("schedule", {})),
            "next_run": a.get("next_run"),
            "run_count": len(runs),
            "last_run": last,
        }

    # ── public API ───────────────────────────────────────────────────────────
    def list(self) -> list[dict]:
        with self._lock:
            return [self._public(a) for a in sorted(
                self._items.values(), key=lambda x: x["created"], reverse=True)]

    def get(self, aid: str) -> dict | None:
        with self._lock:
            a = self._items.get(aid)
            return self._public(a) if a else None

    def save(self, name: str, command: str) -> dict:
        """Snapshot the current sandbox and register it as a runnable automation."""
        with self._lock:
            aid = uuid.uuid4().hex[:10]
            work = self._workdir(aid)
            work.mkdir(parents=True, exist_ok=True)
            if SANDBOX.exists():
                for p in SANDBOX.iterdir():
                    if p.is_file():
                        shutil.copy2(p, work / p.name)
            item = {
                "id": aid,
                "name": (name or "automation").strip()[:60],
                "command": (command or "").strip(),
                "created": _now(),
                "schedule": {"type": "manual"},
                "next_run": None,
                "runs": [],
            }
            self._items[aid] = item
            self._save()
            return self._public(item)

    def delete(self, aid: str) -> bool:
        with self._lock:
            if aid not in self._items:
                return False
            self._items.pop(aid, None)
            shutil.rmtree(AUTOMATIONS_DIR / aid, ignore_errors=True)
            self._save()
            return True

    def set_schedule(self, aid: str, schedule: dict) -> dict | None:
        with self._lock:
            a = self._items.get(aid)
            if not a:
                return None
            a["schedule"] = schedule or {"type": "manual"}
            a["next_run"] = _compute_next_run(a["schedule"])
            self._save()
            return self._public(a)

    def run(self, aid: str, *, trigger: str = "manual") -> dict | None:
        """Execute the automation's command in its work dir; record the run."""
        with self._lock:
            a = self._items.get(aid)
            if not a:
                return None
            command = a["command"]
            work = self._workdir(aid)

        argv = shlex.split(command)
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable     # use this interpreter (script is stdlib-only)

        started = _now()
        try:
            proc = subprocess.run(
                argv, cwd=str(work), capture_output=True, text=True, timeout=_RUN_TIMEOUT,
            )
            output = ((proc.stdout or "") + (proc.stderr or "")).strip()
            exit_code = proc.returncode
        except Exception as exc:  # noqa: BLE001 — record the failure as a run
            output = f"{type(exc).__name__}: {exc}"
            exit_code = -1

        files = []
        if work.exists():
            for p in sorted(work.iterdir()):
                if p.is_file():
                    files.append({"name": p.name, "size": p.stat().st_size})

        run = {
            "time": started,
            "trigger": trigger,
            "ok": exit_code == 0,
            "exit_code": exit_code,
            "output": output[-_MAX_OUTPUT:],
            "files": files,
        }
        with self._lock:
            a = self._items.get(aid)
            if a is not None:
                a.setdefault("runs", []).append(run)
                a["runs"] = a["runs"][-_MAX_RUNS:]
                self._save()
        return run

    def runs(self, aid: str) -> list[dict]:
        with self._lock:
            a = self._items.get(aid)
            return list(reversed(a.get("runs", []))) if a else []

    # ── scheduler ────────────────────────────────────────────────────────────
    def tick(self) -> None:
        """Run any automations whose next_run is due, then advance their schedule.
        Called periodically by the app's background scheduler loop."""
        now = _now()
        with self._lock:
            due = [(a["id"], dict(a.get("schedule", {})), a.get("next_run"))
                   for a in self._items.values()
                   if a.get("next_run") and a["next_run"] <= now]
        for aid, schedule, prev_next in due:
            self.run(aid, trigger="scheduled")
            with self._lock:
                a = self._items.get(aid)
                if a is not None:
                    a["next_run"] = _advance(schedule, prev_next or now)
                    self._save()


# Module-level singleton.
automation_store = AutomationStore()
