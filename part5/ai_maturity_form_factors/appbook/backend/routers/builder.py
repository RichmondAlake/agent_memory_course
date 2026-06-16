"""Form Factor 5 — The Autonomous Agent.

The top rung: an agent with file + shell tools that *writes and runs code* to
build durable automation, fixing its own errors until it works. All file/shell
ops are confined to a sandbox directory. Mirrors the notebook's builder run.

⚠️  This form factor executes code (Bash/Write/Edit) with permissions bypassed,
    scoped to ``backend/sandbox``. That is the point of the demo — keep it local.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.core.agent_runtime import AGENT_AVAILABLE, agent_env, run_agent_events
from backend.core.anthropic_client import MODEL
from backend.core.automations import automation_store
from backend.core.sandbox import SANDBOX, reset_sandbox
from backend.core.sse import sse_response
from backend.schemas import AutomationSaveRequest, BuilderRequest, ScheduleRequest

router = APIRouter(prefix="/api/builder", tags=["builder"])

SYSTEM_PROMPT = (
    "You are an automation engineer. Build the smallest correct, *reusable* solution "
    "(a re-runnable CLI), then verify it runs."
)

DEFAULT_TASK = (
    "In the current directory there is `support_messages.csv` (columns id,category,priority,message).\n"
    "1. Write a minimal, well-documented Python CLI `triage.py` (standard library only) that:\n"
    "   - accepts `--input <path>` and `--output <path>` (default `report.json`),\n"
    "   - counts messages per category and per priority, each sorted by count descending,\n"
    "   - writes both breakdowns to the output path as JSON,\n"
    "   - validates input and exits non-zero on a missing file or wrong columns,\n"
    "   - uses NO hardcoded paths, so it can be scheduled and reused on any batch.\n"
    "2. Run it:  python triage.py --input support_messages.csv --output report.json\n"
    "3. If it errors, fix it and re-run until it succeeds.\n"
    "4. Confirm what you built and show report.json."
)

# Suggested run command when saving a build as an automation (the UI pre-fills it).
DEFAULT_COMMAND = "python triage.py --input support_messages.csv --output report.json"

_TEXT_EXT = {".py", ".json", ".csv", ".txt", ".md", ".cfg", ".ini", ".sh", ".yaml", ".yml", ".log"}
_MAX_FILE_BYTES = 20_000


@router.get("/default-task")
def default_task() -> dict:
    return {"task": DEFAULT_TASK}


@router.get("/artifacts")
def artifacts() -> dict:
    """List sandbox files and return text contents (so the UI can show what was built)."""
    if not SANDBOX.exists():
        return {"files": []}
    files = []
    for p in sorted(SANDBOX.iterdir()):
        if not p.is_file():
            continue
        entry = {"name": p.name, "size": p.stat().st_size, "content": None, "truncated": False}
        if p.suffix.lower() in _TEXT_EXT and p.stat().st_size <= _MAX_FILE_BYTES:
            try:
                entry["content"] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                entry["content"] = None
        elif p.suffix.lower() in _TEXT_EXT:
            entry["truncated"] = True
        files.append(entry)
    return {"files": files, "sandbox": str(SANDBOX)}


@router.post("/run")
async def run(req: BuilderRequest):
    if not AGENT_AVAILABLE:
        async def unavailable():
            yield {"type": "error",
                   "message": "The Claude Agent SDK CLI was not found. Install it with "
                              "`npm i -g @anthropic-ai/claude-code` to enable Form Factors 4 & 5."}
        return sse_response(unavailable())

    reset_sandbox()

    from claude_agent_sdk import ClaudeAgentOptions

    options = ClaudeAgentOptions(
        model=MODEL,
        cwd=str(SANDBOX),
        allowed_tools=["Read", "Write", "Edit", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=30,
        setting_sources=[],
        system_prompt=SYSTEM_PROMPT,
        cli_path=settings.claude_cli_path,
        env=agent_env(),
    )
    task = (req.task or DEFAULT_TASK).strip()

    async def events():
        async for ev in run_agent_events(task, options):
            yield ev
        yield {"type": "artifacts_ready"}

    return sse_response(events())


@router.get("/default-command")
def default_command() -> dict:
    return {"command": DEFAULT_COMMAND}


# ── Automations: save the built script, then run / schedule / re-run it ─────────
@router.get("/automations")
def list_automations() -> dict:
    return {"automations": automation_store.list()}


@router.post("/automations/save")
def save_automation(req: AutomationSaveRequest) -> dict:
    """Snapshot the current sandbox (the agent's built script + data) as a re-runnable automation."""
    return automation_store.save(req.name, req.command or DEFAULT_COMMAND)


@router.post("/automations/{aid}/run")
async def run_automation(aid: str) -> dict:
    run = await run_in_threadpool(automation_store.run, aid, trigger="manual")
    if run is None:
        return {"error": "not found"}
    return {"run": run, "automation": automation_store.get(aid)}


@router.post("/automations/{aid}/schedule")
def schedule_automation(aid: str, req: ScheduleRequest) -> dict:
    sched = {"type": req.type, "every_minutes": req.every_minutes,
             "delay_minutes": req.delay_minutes, "at": req.at}
    return automation_store.set_schedule(aid, sched) or {"error": "not found"}


@router.get("/automations/{aid}/runs")
def automation_runs(aid: str) -> dict:
    return {"runs": automation_store.runs(aid)}


@router.delete("/automations/{aid}")
def delete_automation(aid: str) -> dict:
    return {"ok": automation_store.delete(aid)}
