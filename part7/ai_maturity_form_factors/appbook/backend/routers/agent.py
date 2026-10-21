"""Form Factor 4 — The Agent, with Agent SDK session memory stored in Oracle.

An LLM in a loop with four lender tools on an in-process MCP server (search the policy, read a case
history, re-assess with Clef, file a case note), mirroring the notebook's Part 4. Every conversation is
a session mirrored into Oracle by ``OracleSessionStore``: resume it after a refresh, fork it for a
what-if, or branch from an earlier turn.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.config import BACKEND_DIR, settings
from backend.core import db, retrieval, sessions
from backend.core import underwriting as uw
from backend.core.agent_runtime import AGENT_AVAILABLE, agent_env, cli_stderr, run_agent_events
from backend.core.anthropic_client import MODEL
from backend.core.sse import sse_response
from backend.schemas import AgentRequest, BranchRequest, SessionLabelRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])

AGENT_DIR = BACKEND_DIR / "agent_home"   # the agent's cwd; it also keys its sessions in the store
AGENT_DIR.mkdir(exist_ok=True)
LENDER_TOOLS = ["search_policies", "get_case_history", "reassess_application", "add_case_note"]
SYSTEM_PROMPT = (
    "You are Acme Home Loans' underwriting assistant, talking with an applicant or a loan officer. "
    "Look up an applicant's history with get_case_history before discussing their application. "
    "Ground every policy fact in search_policies and cite the section id. When an applicant reports changed facts, "
    "call reassess_application with only the changed fields; never decide an application yourself. After a recorded "
    "re-assessment, add a one-sentence case note with what changed and the new outcome. Never say a decision or note "
    "exists unless a tool returned it. Keep replies under 120 words."
)
SAMPLES = [
    {"label": "Jordan returns", "prompt": "Hi, this is Jordan Lee. You declined my mortgage application because of my "
     "debts. I've since paid off my car loan and my credit cards, so my only monthly debt now is the $300 student loan. "
     "Can you check whether I qualify now, and put a note on my file about what changed?"},
    {"label": "Maya asks about PMI", "prompt": "Hi, it's Maya Patel. Was my application approved, and will my loan need PMI?"},
    {"label": "Sam's referral", "prompt": "Hi, I'm Sam Rivera. Why was my application referred, and how long will the review take?"},
    {"label": "Policy question", "prompt": "How many months of reserves do I need for an investment property, and what LTV can I get?"},
]


def _as_text(value) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(value, default=str)}]}


def _build_tools():
    """The lender MCP server. Defined lazily so importing this module never requires the agent SDK."""
    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool("search_policies", "Search Acme Home Loans' current lending policy. Use it to ground every policy fact you "
          "state; cite the section id.", {"query": str})
    async def search_policies(args):
        hits = await run_in_threadpool(retrieval.retrieve, args["query"], 3)
        return _as_text([{"section": h["doc_id"], "version": h["version"], "text": h["content"]} for h in hits])

    @tool("get_case_history", "Look up an applicant's applications, past decisions (with reasons) and case notes by "
          "name. Use it before discussing or re-assessing anyone's application.", {"applicant": str})
    async def get_case_history(args):
        files = await run_in_threadpool(uw.case_history, args["applicant"])
        return _as_text(files or {"error": f"No applications for {args['applicant']!r}."})

    @tool("reassess_application", "Re-run the decision on a stored application after the applicant reports changed "
          "facts. Pass the application_id and only the fields that changed. Set record=false for a what-if that must "
          "not be written to the file.",
          {"type": "object",
           "properties": {
               "application_id": {"type": "string"},
               "changes": {"type": "object", "additionalProperties": False,
                           "properties": {"monthly_debts": {"type": "number"}, "gross_monthly_income": {"type": "number"},
                                          "liquid_reserves": {"type": "number"}, "credit_score": {"type": "integer"},
                                          "loan_amount": {"type": "number"}, "employment_months": {"type": "integer"}}},
               "record": {"type": "boolean", "default": True}},
           "required": ["application_id", "changes"]})
    async def reassess_application(args):
        result = await run_in_threadpool(uw.reassess, args["application_id"], args["changes"], args.get("record", True))
        return _as_text(result)

    @tool("add_case_note", "Add a one-sentence note to an application's file. Use it after a re-assessment to record "
          "what changed and the new outcome.", {"application_id": str, "note": str})
    async def add_case_note(args):
        return _as_text({"note_id": await run_in_threadpool(uw.write_case_note, args["application_id"], args["note"])})

    return create_sdk_mcp_server(name="lender", version="1.0.0",
                                 tools=[search_policies, get_case_history, reassess_application, add_case_note])


def _options(**session):
    from claude_agent_sdk import ClaudeAgentOptions

    return ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"lender": _build_tools()},
        allowed_tools=[f"mcp__lender__{name}" for name in LENDER_TOOLS],
        cwd=str(AGENT_DIR),
        setting_sources=[],
        max_turns=12,
        session_store=sessions.store,
        cli_path=settings.claude_cli_path,
        env=agent_env(),
        stderr=cli_stderr,
        **session,
    )


def _unavailable():
    async def events():
        yield {"type": "error", "message": "The Claude Agent SDK is not installed. Install it with "
                                           "`pip install claude-agent-sdk` (it bundles the `claude` CLI)."}
    return sse_response(events())


@router.get("/samples")
def samples() -> dict:
    return {"samples": SAMPLES, "tools": LENDER_TOOLS}


@router.post("/run")
async def run(req: AgentRequest):
    """One turn. With ``session_id`` the agent resumes that session (or forks it when ``fork`` is set)."""
    if not AGENT_AVAILABLE:
        return _unavailable()
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    session = {}
    if req.session_id:
        session = {"resume": req.session_id, "fork_session": req.fork}
    return sse_response(run_agent_events(req.prompt, _options(**session)))


@router.get("/sessions")
async def list_sessions() -> dict:
    return {"sessions": await sessions.list_for(str(AGENT_DIR)), "directory": str(AGENT_DIR)}


@router.get("/sessions/{session_id}")
async def session_messages(session_id: str) -> dict:
    return {"session_id": session_id, "messages": await sessions.messages_for(session_id, str(AGENT_DIR))}


@router.post("/sessions/{session_id}/label")
async def label(session_id: str, req: SessionLabelRequest) -> dict:
    await sessions.label(session_id, str(AGENT_DIR), req.title, req.tag)
    return {"ok": True}


@router.post("/branch")
async def branch(req: BranchRequest) -> dict:
    """A new session that holds the conversation up to one message; continue it with /run."""
    new_id = await sessions.branch(req.session_id, str(AGENT_DIR), req.message_uuid)
    return {"session_id": new_id, "branched_from": req.session_id}


@router.get("/case/{applicant}")
async def case(applicant: str) -> dict:
    return {"files": await run_in_threadpool(uw.case_history, applicant)}
