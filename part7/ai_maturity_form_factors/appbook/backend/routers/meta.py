"""Health, the memory ledger, and the demo reset."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.config import settings
from backend.core import db, reranker, sandbox
from backend.core.agent_runtime import AGENT_AVAILABLE
from backend.core.underwriting import clef_status, current_policy
from backend.core.tracing import tracing_status

router = APIRouter(prefix="/api", tags=["meta"])

# (table, form factor, what it remembers, kind, how it changes) — the notebook's memory ledger.
LEDGER = [
    ("policy_docs", "② RAG", "Acme's lending policy: text, embedding, JSON rules", "semantic", "updated in place, version + 1"),
    ("policy_doc_versions", "② RAG", "every superseded policy version", "semantic history", "one row per policy update"),
    ("loan_applications", "③ workflow", "applications as structured facts", "episodic", "one row per application"),
    ("loan_decisions", "③ workflow, ④ agent", "decisions, probabilities, policy versions used", "episodic", "appended, never overwritten"),
    ("case_notes", "④ agent", "notes the agent or an underwriter wrote", "episodic", "written through a tool"),
    ("agent_session_entries", "④ agent, ⑤ autonomous", "agent session transcripts", "session", "mirrored every turn by a SessionStore"),
]


def _open_models() -> dict:
    from backend.main import OPEN_MODELS

    return {**OPEN_MODELS, "ollama_url": settings.ollama_url}


@router.get("/health")
def health() -> dict:
    return {
        "model": settings.model,
        "provider": settings.provider,
        "open_models": _open_models(),
        "effort": None if settings.open else settings.effort,
        "retrieval": db.status(),
        "decision_model": clef_status(),
        "reranker": reranker.status(),
        "agent_available": AGENT_AVAILABLE,
        "api_key_set": bool(settings.anthropic_api_key),
        "tracing": tracing_status(),
    }


def _ledger() -> list[dict]:
    rows = []
    with db.connection() as conn, conn.cursor() as cur:
        for table, form_factor, what, kind, how in LEDGER:
            if table == "agent_session_entries":
                cur.execute("SELECT COUNT(DISTINCT session_id) FROM agent_session_entries")
            else:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
            rows.append({"table": table, "form_factor": form_factor, "memory": what, "kind": kind,
                         "changes_by": how, "items": int(cur.fetchone()[0])})
    procedural = [f["path"] for f in sandbox.file_list() if f["path"].endswith((".py", "README.md"))]
    rows.append({"table": "ff5 sandbox files", "form_factor": "⑤ autonomous", "memory": "tools and their READMEs",
                 "kind": "procedural", "changes_by": "written by the builder, reused by later sessions",
                 "items": len(procedural)})
    return rows


@router.get("/memory")
async def memory() -> dict:
    """The memory ledger: every store the form factors write, with its current size."""
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    return {"ledger": await run_in_threadpool(_ledger)}


@router.post("/reset")
async def reset() -> dict:
    """Rebuild every appbook table from the seed (policy back to version 1) and reseed the sandbox."""
    if not db.ready():
        raise HTTPException(503, "Oracle AI Database is not ready yet.")
    result = await run_in_threadpool(db.reset_demo)
    await run_in_threadpool(sandbox.reset_sandbox, await run_in_threadpool(current_policy))
    return {"ok": True, **result}
