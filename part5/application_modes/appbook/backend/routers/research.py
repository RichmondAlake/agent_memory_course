"""Deep Research mode — long-horizon reasoning, synthesis, multi-source.

The loop: RECALL prior findings (semantic memory) -> SEARCH the web -> SYNTHESISE
a cited answer -> SAVE durable findings as `fact` records -> CONSOLIDATE a digest
(working memory). Memory profile: episodic + semantic + working.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from backend.core.anthropic_client import MAX_TOKENS, MODEL, async_client, structured_json
from backend.core.contextwin import block as ctx_block
from backend.core.contextwin import count_tokens as ctx_count
from backend.core.contextwin import window as ctx_window
from backend.core.memory import store
from backend.core.sse import sse_response
from backend.core.websearch import WEB_AVAILABLE, web_search
from backend.schemas import ResearchRequest

router = APIRouter(prefix="/api/research", tags=["research"])

USER_ID = "research-analyst"
AGENT_ID = "deep-research-agent"
DIGEST_THREAD = "research-digest-main"

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1-3 atomic, one-sentence factual conclusions worth remembering.",
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

SYNTH_BASE = (
    "You are a deep-research analyst. Using your PRIOR FINDINGS (semantic memory) and the "
    "WEB RESULTS below, write a concise, well-structured answer. Cite sources inline as "
    "URLs where you use them. If prior findings already answer part of the question, build "
    "on them instead of repeating the search."
)
SYNTH_SYSTEM = SYNTH_BASE + "\n\nPRIOR FINDINGS:\n{prior}\n\nWEB RESULTS:\n{web}"


@router.post("/run")
async def run(req: ResearchRequest):
    store.ensure_scope(USER_ID, AGENT_ID)
    question = req.question.strip()

    async def events():
        # ① RECALL — semantic memory (prior findings saved as `fact` records)
        prior = store.search(question, user_id=USER_ID, agent_id=AGENT_ID,
                             record_types=["fact"], max_results=5)
        yield {"type": "memory_recall", "scope": "fact", "hits": prior}

        # ② SEARCH — the web (episodic external evidence)
        web_ctx = ""
        if WEB_AVAILABLE:
            yield {"type": "tool_use", "name": "web_search", "input": {"query": question}}
            res = await run_in_threadpool(web_search, question, 4)
            results = res.get("results", [])
            lines = [f"- {r['title']} ({r['url']})\n  {r['content']}" for r in results]
            web_ctx = "\n".join(lines)
            yield {"type": "tool_result",
                   "text": "\n".join(f"{r['title']} — {r['url']}" for r in results) or "(no results)",
                   "sources": [{"title": r["title"], "url": r["url"]} for r in results]}
        else:
            yield {"type": "note", "text": "Tavily key not set — answering from model knowledge + memory only."}

        # ③ SYNTHESISE — stream a cited answer
        prior_text = "\n".join(h["formatted_content"] for h in prior) or "(none yet)"
        system = SYNTH_SYSTEM.format(prior=prior_text, web=web_ctx or "(no web results)")

        # CONTEXT WINDOW — note the true structure: recalled findings and web evidence are
        # concatenated INTO the system prompt (that's how `system` is assembled above), not
        # separate message roles. The only message sent is the question.
        ctx_blocks = [
            ctx_block("system", "System prompt · analyst instructions", SYNTH_BASE),
            ctx_block("system", "System prompt · recalled findings (injected from memory)", prior_text),
            ctx_block("system", "System prompt · web results (injected)", web_ctx or "(no web results)"),
            ctx_block("user", "User message · research question", question),
        ]
        msgs = [{"role": "user", "content": question}]
        measured = await run_in_threadpool(ctx_count, system, msgs)
        yield {"type": "context", "window": ctx_window(ctx_blocks, measured=measured,
               note="Recalled memory + web evidence are assembled into the system prompt — the only message is the question.")}

        parts: list[str] = []
        async with async_client.messages.stream(
            model=MODEL, max_tokens=MAX_TOKENS, system=system, messages=msgs,
        ) as stream:
            async for text in stream.text_stream:
                parts.append(text)
                yield {"type": "delta", "text": text}
        answer = "".join(parts)
        ctx_blocks.append(ctx_block("assistant", "Assistant message · synthesised answer", answer))
        measured2 = await run_in_threadpool(
            ctx_count, system, msgs + [{"role": "assistant", "content": answer}])
        yield {"type": "context", "window": ctx_window(ctx_blocks, measured=measured2)}

        # ④ SAVE — durable findings as semantic memory (`fact` records)
        try:
            extracted = await run_in_threadpool(
                structured_json,
                system="Extract the durable, atomic factual conclusions from this research answer.",
                user=answer, schema=FINDINGS_SCHEMA, max_tokens=400,
            )
            findings = [f for f in (extracted.get("findings") or []) if f.strip()][:3]
        except Exception:  # noqa: BLE001
            findings = []
        if findings:
            store.add_typed(findings, "fact", user_id=USER_ID, agent_id=AGENT_ID,
                            metadata={"kind": "research_finding"})
            for f in findings:
                yield {"type": "memory_write", "record": {"content": f, "record_type": "fact"}}

        # ⑤ CONSOLIDATE — working memory (running digest of the investigation)
        store.thread_add(DIGEST_THREAD, "user", question, user_id=USER_ID, agent_id=AGENT_ID)
        store.thread_add(DIGEST_THREAD, "assistant", answer, user_id=USER_ID, agent_id=AGENT_ID)
        digest = await run_in_threadpool(
            store.thread_summary, DIGEST_THREAD, user_id=USER_ID, agent_id=AGENT_ID)
        if digest:
            yield {"type": "digest", "summary": digest}
        # CONTEXT CARD — OAMP's consolidated working-memory block for the investigation
        card = await run_in_threadpool(
            store.thread_context_card, DIGEST_THREAD, user_id=USER_ID, agent_id=AGENT_ID)
        if card:
            yield {"type": "context_card", "card": card}

        yield {"type": "done", "findings_saved": len(findings),
               "prior_recalled": len(prior)}

    return sse_response(events())


@router.get("/memory")
def memory() -> dict:
    findings = store.search("all saved research findings", user_id=USER_ID, agent_id=AGENT_ID,
                            record_types=["fact"], max_results=20)
    summary = store.thread_summary(DIGEST_THREAD, user_id=USER_ID, agent_id=AGENT_ID)
    return {"findings": findings, "digest": summary, "web_available": WEB_AVAILABLE}
