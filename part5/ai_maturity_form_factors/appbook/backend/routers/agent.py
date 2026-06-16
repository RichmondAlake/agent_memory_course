"""Form Factor 4 — The Agent.

An LLM in a loop with tools. We provide two (search the docs, open a ticket) via
an in-process MCP server and hand the model a goal; *it* decides which tools to
call and when. Built on the same `claude-agent-sdk` runtime that powers Claude Code.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.agent_runtime import AGENT_AVAILABLE, agent_env, run_agent_events
from backend.core.anthropic_client import MODEL
from backend.core.retrieval import store
from backend.core.sse import sse_response
from backend.schemas import AgentRequest

router = APIRouter(prefix="/api/agent", tags=["agent"])

SYSTEM_PROMPT = (
    "You are the Acme Cloud support agent. You have exactly two tools: search_docs and "
    "create_support_ticket. Use search_docs to ground every factual claim. Only open a "
    "ticket if the user clearly needs escalation. Cite docs with [n]."
)


def _build_tools():
    """Defined lazily so importing this module never requires the agent SDK."""
    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool(
        "search_docs",
        "Search the Acme Cloud documentation. Use this whenever the user asks about Acme "
        "Cloud's plans, pricing, limits, or features.",
        {"query": str},
    )
    async def search_docs(args):
        hits = store.retrieve(args["query"], k=3)
        text = "\n".join(f"[{i + 1}] {doc}" for i, (doc, _) in enumerate(hits))
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "create_support_ticket",
        "Open a support ticket. Use this only when the user asks to escalate, or reports an "
        "urgent, unresolved problem.",
        {"summary": str, "priority": str},
    )
    async def create_support_ticket(args):
        ticket_id = f"ACME-{abs(hash(args['summary'])) % 10000:04d}"
        msg = f"Created ticket {ticket_id} (priority={args['priority']}): {args['summary']}"
        return {"content": [{"type": "text", "text": msg}]}

    return create_sdk_mcp_server(
        name="acme", version="1.0.0", tools=[search_docs, create_support_ticket]
    )


@router.post("/run")
async def run(req: AgentRequest):
    if not AGENT_AVAILABLE:
        async def unavailable():
            yield {"type": "error",
                   "message": "The Claude Agent SDK CLI was not found. Install it with "
                              "`npm i -g @anthropic-ai/claude-code` to enable Form Factors 4 & 5."}
        return sse_response(unavailable())

    store.initialize()  # ensure the retriever is warm before the agent calls search_docs

    from claude_agent_sdk import ClaudeAgentOptions

    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"acme": _build_tools()},
        allowed_tools=["mcp__acme__search_docs", "mcp__acme__create_support_ticket"],
        setting_sources=[],
        cli_path=settings.claude_cli_path,
        env=agent_env(),
    )
    return sse_response(run_agent_events(req.prompt, options))
