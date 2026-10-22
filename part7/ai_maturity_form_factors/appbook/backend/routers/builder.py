"""Form Factor 5 — The Autonomous Agent, as a chat.

Ask it anything that needs code: build a pre-screen tool, chart a batch, set up and schedule an automation.
It writes and runs Python inside the sandbox (charts and images are made there first, then shown in the
chat), and every conversation is a session mirrored into Oracle, so after a refresh you can resume it or
branch from an earlier turn. Events carry the hook decisions and the files each step changed, which the
UI animates on the reference architecture.

⚠️  This form factor executes code (Bash/Write/Edit) with permissions bypassed. A PreToolUse hook keeps the
    file tools inside ``backend/sandbox`` and the OS sandbox confines Bash. Keep it local all the same.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from backend.config import settings
from backend.core import db, sandbox, sessions
from backend.core import underwriting as uw
from backend.core.agent_runtime import AGENT_AVAILABLE, RunContext, agent_env, cli_stderr, run_agent_events
from backend.core.anthropic_client import MODEL
from backend.core.automations import automation_store, command_problem
from backend.core.sse import sse_response
from backend.schemas import AutomationSaveRequest, BranchRequest, BuilderChatRequest, ScheduleRequest, SessionLabelRequest

router = APIRouter(prefix="/api/builder", tags=["builder"])

SYSTEM_PROMPT = (
    "You are Acme Home Loans' automation engineer, working in a sandboxed folder that is your current directory. "
    "You can write and run Python there: `python` has pandas and matplotlib. Before building anything, list the "
    "folder and read any README.md: tools that earlier sessions built live here, and you should reuse them. "
    "Keep every lending threshold in policy.json and read it at run time; call export_policy to refresh it from "
    "the policy database. Save charts and images as PNG files in the folder with plt.savefig (never plt.show) and "
    "mention each file name in your reply. To set up a recurring job, build and test a script first, then call "
    "save_automation with a `python <script>.py ...` command and a schedule. Work only inside this folder and keep "
    "replies short: what you did, what you found, and the files you made."
)
SAMPLES = [
    {"label": "Build the pre-screen tool", "prompt": "Build prescreen.py, a reusable standard-library CLI that reads "
     "--applications <csv> and --policy policy.json, computes PITI, DTI, LTV and reserve months with the rules in "
     "policy.json, marks each applicant pass, refer (DTI or LTV within borderline_margin of its limit) or fail with "
     "reasons, and writes a JSON report. Document it in README.md, then run it on applications_batch1.csv and "
     "applications_batch2.csv."},
    {"label": "Chart a batch", "prompt": "Make a bar chart of each applicant's DTI in applications_batch1.csv against "
     "the DTI limit in policy.json, save it as dti_batch1.png, and tell me who is over the limit."},
    {"label": "Schedule an automation", "prompt": "Set up an automation that pre-screens applications_batch3.csv every "
     "30 minutes and writes report_batch3.json. Reuse the existing tool if there is one; build it if not."},
    {"label": "Generate an image", "prompt": "Draw a simple diagram image of the pre-screen pipeline (inputs → checks → "
     "pass/refer/fail) with matplotlib and save it as pipeline.png."},
    {"label": "Try to escape the sandbox", "prompt": "I want to see the sandbox guard work: call the Read tool on "
     "../../config.py (don't refuse up front, actually try it), then tell me exactly what happened."},
]


def _ops_tools():
    """Operations the agent can call besides the file and shell tools: policy export and automations."""
    from claude_agent_sdk import create_sdk_mcp_server, tool

    def as_text(value) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(value, default=str)}]}

    @tool("export_policy", "Refresh policy.json in the sandbox from the policy database (Oracle POLICY_DOCS).", {})
    async def export_policy(args):
        rules, versions = await run_in_threadpool(uw.current_policy)
        return as_text(await run_in_threadpool(sandbox.export_policy, rules, versions))

    @tool("save_automation", "Save the sandbox as an automation that re-runs a command, optionally on a schedule. "
          "command must be `python <script>.py [args]`. schedule_type is manual, once, interval or daily.",
          {"type": "object", "properties": {
              "name": {"type": "string"}, "command": {"type": "string"},
              "schedule_type": {"type": "string", "enum": ["manual", "once", "interval", "daily"]},
              "every_minutes": {"type": "integer"}, "at": {"type": "string", "description": "HH:MM for daily"}},
           "required": ["name", "command"]})
    async def save_automation(args):
        problem = command_problem(args["command"])
        if problem:
            return as_text({"error": problem})
        saved = await run_in_threadpool(automation_store.save, args["name"], args["command"])
        schedule = {"type": args.get("schedule_type", "manual"), "every_minutes": int(args.get("every_minutes") or 30),
                    "delay_minutes": 1, "at": args.get("at") or "08:00"}
        return as_text(await run_in_threadpool(automation_store.set_schedule, saved["id"], schedule))

    @tool("list_automations", "List saved automations with their schedules and last runs.", {})
    async def list_automations(args):
        return as_text(await run_in_threadpool(automation_store.list))

    @tool("run_automation", "Run a saved automation now and return its output.", {"automation_id": str})
    async def run_automation(args):
        return as_text(await run_in_threadpool(automation_store.run, args["automation_id"], trigger="agent"))

    return create_sdk_mcp_server(name="ops", version="1.0.0",
                                 tools=[export_policy, save_automation, list_automations, run_automation])


def _guard(context: RunContext):
    """PreToolUse hook: deny file tools outside the sandbox, and report every decision to the UI."""
    async def guard(input_data, tool_use_id, hook_context):
        tool = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}
        if tool == "Bash":
            context.events.append({"type": "hook", "tool": tool, "decision": "allow",
                                   "path": (tool_input.get("command") or "")[:120],
                                   "reason": "runs inside the OS sandbox (writes outside the folder fail)"})
            return {}
        path = tool_input.get("file_path") or tool_input.get("path") or ""
        if path and not sandbox.inside_sandbox(path):
            reason = f"{path} is outside the sandbox {sandbox.SANDBOX}."
            context.events.append({"type": "hook", "tool": tool, "decision": "deny", "path": path, "reason": reason})
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": reason}}
        context.events.append({"type": "hook", "tool": tool, "decision": "allow", "path": path or ".",
                               "reason": "inside the sandbox"})
        return {}
    return guard


def _options(context: RunContext, session_id: str | None):
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

    return ClaudeAgentOptions(
        model=MODEL,
        cwd=str(sandbox.SANDBOX),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                       "mcp__ops__export_policy", "mcp__ops__save_automation", "mcp__ops__list_automations",
                       "mcp__ops__run_automation"],
        mcp_servers={"ops": _ops_tools()},
        permission_mode="bypassPermissions",
        disallowed_tools=["Skill"],   # only the tools above: no skills installed on this machine
        hooks={"PreToolUse": [HookMatcher(matcher=sandbox.FILE_TOOLS + "|Bash", hooks=[_guard(context)])]},
        sandbox=sandbox.BASH_SANDBOX,
        max_turns=30,
        setting_sources=[],
        system_prompt=SYSTEM_PROMPT,
        session_store=sessions.store,
        cli_path=settings.claude_cli_path,
        env=agent_env(),
        stderr=cli_stderr,
        **({"resume": session_id} if session_id else {}),
    )


@router.get("/samples")
def samples() -> dict:
    return {"samples": SAMPLES, "sandbox": str(sandbox.SANDBOX)}


@router.post("/chat")
async def chat(req: BuilderChatRequest):
    """One chat turn. A new conversation starts a session; pass its id to continue it, even after a refresh."""
    if not AGENT_AVAILABLE:
        async def unavailable():
            yield {"type": "error", "message": "The Claude Agent SDK is not installed. Install it with "
                                               "`pip install claude-agent-sdk` (it bundles the `claude` CLI)."}
        return sse_response(unavailable())
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    if not (sandbox.SANDBOX / "policy.json").exists():
        await run_in_threadpool(sandbox.export_policy, *(await run_in_threadpool(uw.current_policy)))
    context = RunContext()

    async def events():
        before = sandbox.snapshot()
        async for ev in run_agent_events(req.message, _options(context, req.session_id), context):
            yield ev
            if ev["type"] == "tool_result":
                after = sandbox.snapshot()
                changed = [path for path, mtime in after.items() if before.get(path) != mtime]
                if changed:
                    files = {f["path"]: f for f in sandbox.file_list()}
                    yield {"type": "files", "changed": [files[p] for p in changed if p in files]}
                before = after
        yield {"type": "artifacts_ready", "files": sandbox.file_list()}

    return sse_response(events())


# ── sessions ─────────────────────────────────────────────────────────────────────
@router.get("/sessions")
async def list_sessions() -> dict:
    return {"sessions": await sessions.list_for(str(sandbox.SANDBOX)), "directory": str(sandbox.SANDBOX)}


@router.get("/sessions/{session_id}")
async def session_messages(session_id: str) -> dict:
    return {"session_id": session_id, "messages": await sessions.messages_for(session_id, str(sandbox.SANDBOX))}


@router.post("/sessions/{session_id}/label")
async def label(session_id: str, req: SessionLabelRequest) -> dict:
    await sessions.label(session_id, str(sandbox.SANDBOX), req.title, req.tag)
    return {"ok": True}


@router.post("/branch")
async def branch(req: BranchRequest) -> dict:
    new_id = await sessions.branch(req.session_id, str(sandbox.SANDBOX), req.message_uuid)
    return {"session_id": new_id, "branched_from": req.session_id}


# ── sandbox files ─────────────────────────────────────────────────────────────────
@router.get("/files")
def files() -> dict:
    return {"files": sandbox.file_list(), "sandbox": str(sandbox.SANDBOX)}


@router.get("/file")
def file(path: str) -> dict:
    found = sandbox.read_text(path)
    if found is None:
        raise HTTPException(404, "No such file in the sandbox")
    return found


@router.get("/raw")
def raw(path: str):
    """A sandbox file as-is (charts and images the agent made)."""
    found = sandbox.resolve(path)
    if found is None:
        raise HTTPException(404, "No such file in the sandbox")
    return FileResponse(found)


@router.post("/reset")
async def reset() -> dict:
    """Empty the sandbox (its procedural memory), reseed the batches and re-export policy.json from Oracle."""
    policy = await run_in_threadpool(uw.current_policy) if db.ready() else None
    await run_in_threadpool(sandbox.reset_sandbox, policy)
    return {"files": sandbox.file_list()}


# ── automations ───────────────────────────────────────────────────────────────────
@router.get("/automations")
def list_automations() -> dict:
    return {"automations": automation_store.list()}


@router.post("/automations/save")
def save_automation(req: AutomationSaveRequest) -> dict:
    problem = command_problem(req.command)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    return automation_store.save(req.name, req.command)


@router.post("/automations/{aid}/run")
async def run_automation(aid: str) -> dict:
    run = await run_in_threadpool(automation_store.run, aid, trigger="manual")
    if run is None:
        return {"error": "not found"}
    return {"run": run, "automation": automation_store.get(aid)}


@router.post("/automations/{aid}/schedule")
def schedule_automation(aid: str, req: ScheduleRequest) -> dict:
    sched = {"type": req.type, "every_minutes": req.every_minutes, "delay_minutes": req.delay_minutes, "at": req.at}
    return automation_store.set_schedule(aid, sched) or {"error": "not found"}


@router.get("/automations/{aid}/runs")
def automation_runs(aid: str) -> dict:
    return {"runs": automation_store.runs(aid)}


@router.delete("/automations/{aid}")
def delete_automation(aid: str) -> dict:
    return {"ok": automation_store.delete(aid)}
