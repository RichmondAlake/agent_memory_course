"""One lab session: both versions of Memo, grown Part by Part as in the notebook.

A session owns a run id and its exact scope (``memo-app-<run>`` memory space,
``ada-app-<run>`` tenant). Every page works with both agents built to its Part:
the scratch agent gets the notebook's layers up to that Part, and the MemoRizz
agent is rebuilt from a builder with the notebook's ``with_...`` calls up to
that Part. Setup a Part needs (persona v1, the runbook, the tools, the authored
skill) runs once, in order, the first time any later page needs it. Reset and
shutdown delete the session's rows with exact-scope deletes only.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from backend.config import settings
from backend.core import context_view, judge, rows, scratch, tokenomics
from backend.core.memorizz_memo import MemorizzMemo, governed_tools, memorizz_model, runtime

THREADS = ["migration", "on-call", "incident-review", "incident-review-2", "review", "rebuild-night", "tokenomics"]
PAGE_TABLES: dict[int, tuple[list[str], list[str]]] = {
    1: ([], []),
    2: (["scratch_conversation"], ["conversation_memory", "agents"]),
    3: (["scratch_persona"], ["personas"]),
    4: (["scratch_entity"], ["entity_memory"]),
    5: (["scratch_knowledge"], ["knowledge_base"]),
    6: (["scratch_toolbox"], ["toolbox"]),
    7: (["scratch_tool_log"], ["tool_log"]),
    8: (["scratch_workflow"], ["workflow_memory"]),
    9: (["scratch_skill"], ["skillbox"]),
    10: (["scratch_conversation"], ["short_term_memory"]),
    11: (["scratch_summary", "scratch_conversation"], ["summaries", "summary_message_links"]),
    12: (["scratch_cache"], ["semantic_cache"]),
    13: (["scratch_blackboard"], ["shared_memory"]),
    14: (["scratch_knowledge"], ["conversation_memory"]),
    15: (["scratch_routing"], ["knowledge_base", "short_term_memory"]),
    16: (["scratch_agent"], ["agents"]),
}
SETUP_PARTS = (2, 3, 5, 6, 7, 9)
HIDDEN = frozenset({"memory_id", "user_id"})   # the session scope, shown in the page header
BRIEF = "You are a helpful assistant. Answer in at most two sentences."


def _tool_names(outcomes: list[dict]) -> list[str]:
    return [str(item.get("tool_name")) for item in outcomes or [] if item.get("tool_name")]


def _measure_scratch(agent: Any, message: str, run_kwargs: dict) -> tuple[str, Any, float]:
    """Run the scratch agent under the Tokenomics meter: (answer, meter, total ms)."""
    with tokenomics.metering() as meter:
        started = time.perf_counter()
        answer = agent.run(message, **run_kwargs)
        return answer, meter, (time.perf_counter() - started) * 1000


def _measure_memorizz(memo: Any, message: str, run_kwargs: dict) -> tuple[str, tokenomics.TraceCollector, float]:
    """Run the MemoRizz agent while collecting its trace events: (answer, collector, total ms)."""
    memo.set_stream_event_callback(collector := tokenomics.TraceCollector())
    started = collector.window[0]
    try:
        answer = memo.run(message, **run_kwargs)
    finally:
        collector.stop()
        memo.set_stream_event_callback(None)
    return answer, collector, (time.perf_counter() - started) * 1000


class LabSession:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.run_id = uuid.uuid4().hex[:8]
        self.memory_id = f"memo-app-{self.run_id}"
        self.user_id = f"ada-app-{self.run_id}"
        self.review_session = f"rebuild-review-{self.run_id}"
        self.memorizz = MemorizzMemo(self.run_id, self.memory_id, self.user_id)
        self.naive = scratch.NaiveMemo()     # Tokenomics baseline: the whole thread appended, nothing else
        self.setup_done: set[int] = set()
        self.last: dict[int, dict] = {}
        self.actions: dict[int, dict] = {}
        self.restored: dict[str, Any] = {}
        self.shared_session_id: str | None = None
        self.tables_ready = False
        self.metrics: list[dict] = []        # Tokenomics: one record per agent per measured turn
        self.contexts: dict[int, dict] = {}  # Context window: every model call of each measured turn, both agents
        self.turn_no = 0
        self.workload_stacks: dict | None = None
        self.workload_running = False
        self.stop_requested = threading.Event()   # set by Stop run; the workload checks it before each turn
        self.workload_state: dict = {"state": "idle"}   # what every page's run notification shows

    # ── scope ──
    def scope(self, thread: str = "migration") -> dict:
        return {"memory_id": self.memory_id, "user_id": self.user_id, "thread_id": thread}

    def row_scope(self) -> dict:
        return {"memory_id": self.memory_id, "user_id": self.user_id, "session_id": self.review_session,
                "knowledge_ids": list(self.memorizz.knowledge_ids),
                "shared_ids": [self.shared_session_id] if self.shared_session_id else [],
                "agent_ids": sorted(self.memorizz.agent_ids)}

    def snapshot(self) -> dict:
        return {"run_id": self.run_id, "scope": self.scope(), "session_id": self.review_session,
                "setup_done": sorted(self.setup_done), "level": self.memorizz.level,
                "visited": sorted(self.last), "jev": bool(settings.typesafe_api_key),
                "agent_id": self.memorizz.agent.agent_id if self.memorizz.agent is not None else None}

    # ── setup the notebook performs up to a Part ──
    def ensure(self, part: int, emit: Callable[[dict], None] | None = None) -> None:
        runtime.require()
        if not self.tables_ready:                # CREATE TABLE IF NOT EXISTS: cheap, and safe if a table was dropped
            scratch.create_tables()
            self.tables_ready = True
        for number in SETUP_PARTS:
            if number > part or number in self.setup_done:
                continue
            started = time.perf_counter()
            if emit:
                emit({"type": "setup", "part": number, "status": "running"})
            if number == 3 and not scratch.PersonaLayer("Memo").current(self.memory_id):
                scratch.PersonaLayer("Memo").evolve(self.memory_id, dict(scratch.INITIAL_PERSONA), reason="initial persona")
            if number == 5:
                scratch.ingest(self.memory_id, scratch.RUNBOOK, namespace="runbook", source="platform-runbook")
            if number == 6:
                scratch.register_tools(self.memory_id, scratch.PLATFORM_TOOLS)
            if number == 7:
                scratch.register_tools(self.memory_id, [scratch.expand_tool_result])
            if number == 9:
                scratch.add_skill(self.memory_id, "platform/vector-index-rebuild",
                                  "Safely rebuild the production retrieval-api vector index.",
                                  scratch.REBUILD_PLAYBOOK, status="active", source="authored by the platform team")
            self.memorizz.setup(number)
            self.setup_done.add(number)
            if emit:
                emit({"type": "setup", "part": number, "status": "done",
                      "seconds": round(time.perf_counter() - started, 2)})

    # ── one message to both agents at a Part's level ──
    def chat(self, part: int, message: str, thread: str, context: dict, budget: int,
             emit: Callable[[dict], None], *, reference: str | None = None, test: str | None = None) -> dict:
        with self.lock:
            self.ensure(part, emit)
            scope = self.scope(thread)
            scratch_context = {k: v for k, v in context.items() if k != "cache_domains"}
            memorizz_context = dict(context)
            if "cache_domain" in context:
                memorizz_context = {k: v for k, v in context.items() if k != "cache_domain"}
                memorizz_context["cache_domains"] = [context["cache_domain"]]
            extra = {"session_id": self.review_session} if part >= 13 else {}

            emit({"type": "start", "side": "scratch"})
            agent = scratch.build_agent(part, budget=budget)
            self.turn_no += 1
            measure = {"turn": self.turn_no, "part": part, "thread": thread, "question": message,
                       "model": settings.model, "test": test}
            answer, meter, total_ms = _measure_scratch(
                agent, message, {**scope, **extra, **({"context": scratch_context} if scratch_context else {})})
            turn = agent.last_turn
            self.metrics.append(tokenomics.scratch_record(meter, total_ms=total_ms, cache_hit=turn.cache_hit is not None,
                                                          tool_calls=[c["tool"] for c in turn.calls], **measure))
            scratch_calls = context_view.scratch_calls(meter.requests)
            left = {"side": "scratch", "turn": self.turn_no, "text": answer, "seconds": round(total_ms / 1000, 2),
                    "input_tokens": turn.usage.get("input_tokens", 0), "tool_calls": [c["tool"] for c in turn.calls],
                    "context": scratch.show_context(agent), "layers": scratch.stack(agent),
                    "dropped": turn.dropped, "cache_hit": turn.cache_hit, "routed": turn.routed}
            emit({"type": "answer", **left})

            emit({"type": "start", "side": "memorizz"})
            started = time.perf_counter()
            if part == 1:
                with tokenomics.metering() as raw:
                    response = scratch.chat(BRIEF, message)
                self.metrics.append(tokenomics.raw_record(response, (time.perf_counter() - started) * 1000, **measure))
                memorizz_calls = context_view.scratch_calls(raw.requests)
                right = {"side": "memorizz", "turn": self.turn_no, "text": response.output_text, "raw": True,
                         "seconds": round(time.perf_counter() - started, 2),
                         "input_tokens": response.usage.input_tokens, "tool_calls": [],
                         "note": "Part 1 is a raw model call; MemoRizz enters in Part 2."}
            else:
                memo = self.memorizz.agent_at(part)
                answer, collector, total_ms = _measure_memorizz(
                    memo, message, {**scope, **({"context": memorizz_context} if memorizz_context else {})})
                usage = memo.get_last_run_usage() or {}
                evidence = memo.last_memory_context_evidence() or {}
                self.metrics.append(tokenomics.memorizz_record(
                    collector, usage, total_ms=total_ms, tool_calls=_tool_names(memo.last_tool_outcomes),
                    cache_hit=not usage.get("calls"), **measure))
                memorizz_calls = context_view.memorizz_calls(self.memorizz.context_snapshots(collector.calls))
                right = {"side": "memorizz", "turn": self.turn_no, "text": answer, "seconds": round(total_ms / 1000, 2),
                         "input_tokens": usage.get("input_tokens", 0), "cached_tokens": usage.get("cached_tokens", 0),
                         "calls": usage.get("calls", 0), "tool_calls": _tool_names(memo.last_tool_outcomes),
                         "memory_types": [t.value for t in memo.active_memory_types],
                         "source_counts": evidence.get("source_counts") or {},
                         "context_window": rows.json_value(memo.get_context_window_stats() or {})}
                if part >= 12:
                    stats = memo.semantic_cache_stats()
                    right["semantic_cache"] = {k: stats.get(k) for k in ("hits", "misses", "bypasses", "writes")}
                    right["semantic_cache"]["bypass_reasons"] = stats.get("bypass_reasons")
            self.contexts[self.turn_no] = context_view.turn(
                turn=self.turn_no, part=part, thread=thread, question=message, test=test, scratch=scratch_calls,
                memorizz=memorizz_calls, memorizz_title="Raw model call" if part == 1 else "MemoRizz")
            emit({"type": "answer", **right})
            reference = reference or tokenomics.reference_for(message)
            if reference:                                    # a golden question: the LLM judge grades both answers
                emit({"type": "judging"})
                judge.grade_pair(message, self.metrics[-2:], {"scratch": left["text"], "memorizz": right["text"]},
                                 reference)
                left["accuracy"], right["accuracy"] = (record["accuracy"] for record in self.metrics[-2:])
                emit({"type": "judged", "scratch": left["accuracy"], "memorizz": right["accuracy"]})
            result = {"part": part, "message": message, "thread": thread, "scratch": left, "memorizz": right}
            self.last[part] = result
            return result

    def naive_chat(self, part: int, message: str, thread: str, *, reference: str | None = None,
                   test: str | None = None) -> dict:
        """The naive baseline on the turn just measured: the thread's whole transcript, nothing else."""
        with self.lock:
            answer, meter, total_ms = _measure_scratch(self.naive, message, self.scope(thread))
            record = tokenomics.scratch_record(meter, agent="naive", turn=self.turn_no, part=part, thread=thread,
                                               question=message, model=settings.model, total_ms=total_ms,
                                               tool_calls=[], cache_hit=False, test=test)
            self.metrics.append(record)
            if reference:
                judge.grade_pair(message, [record], {"naive": answer}, reference)
            return record

    # ── per-Part state: tables, rows and stats ──
    def page(self, part: int) -> dict:
        scratch_tables, memorizz_tables = PAGE_TABLES[part]
        out: dict[str, Any] = {"part": part, "session": self.snapshot(), "scratch": [], "memorizz": [],
                               "last": self.last.get(part), "action": self.actions.get(part), "extra": {}}
        if not runtime.ready:
            return out
        scope = self.row_scope()
        for table in scratch_tables:
            data = rows.read_rows(table, scope, hide=HIDDEN)
            data["ddl"] = scratch.DDL[table]
            out["scratch"].append(data)
        for table in memorizz_tables:
            data = rows.read_rows(table, scope, hide=HIDDEN | {"id", "agent_id", "retention_meta"})
            data["all_columns"] = [c["column_name"].lower() for c in scratch.columns(table)]
            out["memorizz"].append(data)
        memo = self.memorizz.agent
        if memo is not None and self.memorizz.level >= 7 and part == 7:
            stats = memo.tool_cache_stats()
            out["extra"]["tool_cache"] = {k: stats.get(k) for k in ("hits", "misses", "stored", "hit_rate")}
        if memo is not None and part == 12 and self.memorizz.level >= 12:
            stats = memo.semantic_cache_stats()
            out["extra"]["semantic_cache"] = {k: stats.get(k) for k in ("hits", "misses", "bypasses", "writes")}
        return out

    # ── Part actions ──
    def action(self, part: int, name: str, params: dict) -> dict:
        handler = getattr(self, f"_p{part}_{name}", None)
        if handler is None:
            raise KeyError(f"Part {part} has no action {name!r}")
        with self.lock:
            self.ensure(part)
            started = time.perf_counter()
            result = handler(params)
            result["seconds"] = round(time.perf_counter() - started, 2)
            self.actions[part] = {"name": name, "result": result}
            return result

    def _p1_baseline(self, params: dict) -> dict:
        first = scratch.chat(BRIEF, "I'm Ada. I'm migrating our RAG stack to Oracle AI Database.").output_text
        second = scratch.chat(BRIEF, "What am I working on, and what's my name?").output_text
        return {"first": first, "second": second}

    def _p2_restore(self, params: dict) -> dict:
        from memorizz import MemAgent

        question = "Remind me: what project are we on?"
        fresh = scratch.ScratchMemo(scratch.INSTRUCTION).add(scratch.ConversationLayer())
        left = fresh.run(question, **self.scope())
        restored = MemAgent.load(self.memorizz.agent_at(2).agent_id, memory_provider=runtime.require(),
                                 model=memorizz_model())
        try:
            right = restored.run(question, **self.scope())
        finally:
            restored.close(close_memory_provider=False)
        return {"scratch": left, "memorizz": right, "agent_id": restored.agent_id}

    def _p3_evolve(self, params: dict) -> dict:
        field = params.get("field") if params.get("field") in {"goals", "style"} else "goals"
        value, reason = str(params.get("value") or "").strip(), str(params.get("reason") or "").strip()
        if not value or not reason:
            raise ValueError("A persona change needs a new value and a reason.")
        version_no = scratch.PersonaLayer("Memo").evolve(self.memory_id, {field: value}, reason=reason)
        persona = self.memorizz.persona
        persona.update(updates={"goals" if field == "goals" else "background": value},
                       change_trigger={"reason": reason, "source_type": "user_feedback",
                                       "source_id": f"appbook-{self.run_id}",
                                       "agent_id": self.memorizz.agent_at(3).agent_id},
                       provider=runtime.require())
        self.memorizz.agent_at(3, force=True)
        history = [{"version": e.get("version"), "reason": (e.get("change_trigger") or {}).get("reason")}
                   for e in persona.evolution_history]
        return {"scratch_version": version_no, "memorizz_version": persona.version, "memorizz_history": history}

    def _p5_search(self, params: dict) -> dict:
        from memorizz import MemoryType

        query = str(params.get("query") or scratch.QUESTION)
        left = [{"chunk_index": r["chunk_index"], "distance": float(r["distance"]), "content": r["content"]}
                for r in scratch.search_knowledge(self.memory_id, query, "runbook", k=7)]
        hits = runtime.require().retrieve_by_query(query, memory_store_type=MemoryType.KNOWLEDGE_BASE,
                                                   namespace=self.memorizz.namespace, user_id=self.user_id, limit=7)
        right = [{"score": round(float(h.get("score", 0) or 0), 3), "content": str(h.get("content"))} for h in hits]
        return {"query": query, "scratch": left, "memorizz": right}

    def _p6_preview(self, params: dict) -> dict:
        query = str(params.get("query") or "Check the health of the docs_hnsw index.")
        left = [{"name": r["name"], "distance": float(r["distance"])}
                for r in scratch.select_tools(self.memory_id, query, k=7)]
        memo = self.memorizz.agent_at(6)
        right = list(memo.semantic_tool_router.preview(query, user_id=self.user_id))
        return {"query": query, "scratch": left, "memorizz": right}

    def _p9_propose(self, params: dict) -> dict:
        return {"proposed": scratch.propose_skills(self.memory_id)}

    def _p9_approve(self, params: dict) -> dict:
        approved = scratch.approve_candidates(self.memory_id)
        memo = self.memorizz.agent_at(9)
        query = str(params.get("query") or "Plan the retrieval-api index rebuild for me.")
        hits = memo.skillbox.retrieve_skills_by_query(query, limit=2, min_similarity=0.0, user_id=self.user_id)
        report = memo.learning_report(memory_id=self.memory_id, user_id=self.user_id)
        return {"approved": approved,
                "memorizz_skills": [{"name": h.skill.name, "similarity": round(h.similarity, 3)} for h in hits],
                "learning_events": (report.get("records") or {}).get("event_types", {})}

    def _p11_compact(self, params: dict) -> dict:
        scope = self.scope("migration")
        summary_id = scratch.compact(scope, keep_recent=4)
        memo = self.memorizz.agent_at(11)
        ids = memo.generate_summaries(memory_id=self.memory_id, user_id=self.user_id, thread_id="migration",
                                      days_back=1, keep_recent=4)
        summary = memo.fetch_context_summary(ids[0], memory_id=self.memory_id, user_id=self.user_id,
                                             thread_id="migration") if ids else None
        return {"scratch_summary_id": summary_id,
                "scratch_sources": scratch.summary_sources(scope, summary_id) if summary_id else [],
                "memorizz_summary_ids": ids,
                "memorizz_summary": {"content": summary.get("content"),
                                     "memory_units_count": summary.get("memory_units_count"),
                                     "source_message_ids": len(summary.get("source_message_ids") or [])}
                if summary else None}

    def _p12_invalidate(self, params: dict) -> dict:
        domain = str(params.get("domain") or "runbook")
        removed = scratch.invalidate_cache(self.memory_id, domain)
        memo = self.memorizz.agent_at(12)
        return {"domain": domain, "scratch_removed": removed,
                "memorizz_removed": memo.invalidate_semantic_cache(domains=[domain])}

    def _p13_review(self, params: dict) -> dict:
        from memorizz import SharedMemory

        ask = str(params.get("plan_request") or
                  "Draft a five-step plan for tonight's retrieval-api index rebuild. Tonight is Wednesday.")
        main, review = self.scope("migration"), self.scope("review")
        memo_s = scratch.build_agent(13)
        plan_s = memo_s.run(ask, **main, session_id=self.review_session)
        scratch.post(self.user_id, self.review_session, "memo", "COMMAND",
                     {"instructions": "Review this plan against the runbook.", "plan": plan_s}, target="rev")
        rev = scratch.ScratchMemo(scratch.REVIEWER_INSTRUCTION).add(scratch.KnowledgeLayer("runbook"))
        command = scratch.inbox(self.user_id, self.review_session, "rev", "COMMAND")[-1]
        findings_s = rev.run(f"{command['payload']['instructions']}\n\n{command['payload']['plan']}", **review)
        scratch.post(self.user_id, self.review_session, "rev", "REPORT",
                     {"findings": findings_s, "command_id": command["id"]}, target="memo")
        revised_s = memo_s.run("Revise the plan using the reviewer's findings.", **main, session_id=self.review_session)

        memo, rev_agent = self.memorizz.agent_at(13), self.memorizz.rev_agent()
        shared = SharedMemory(runtime.require())
        if self.shared_session_id is None:
            self.shared_session_id = shared.create_shared_session(
                root_agent_id=memo.agent_id, delegate_agent_ids=[rev_agent.agent_id], workflow_id=self.review_session,
                user_id=self.user_id, trace_id=f"trace-{self.run_id}")
            self.memorizz.shared_ids.append(self.shared_session_id)
        plan_m = memo.run(ask, **main)
        command_id = f"review-{len(shared.get_blackboard_entries(self.shared_session_id)) + 1}"
        shared.post_command(self.shared_session_id, agent_id=memo.agent_id, command_id=command_id,
                            target_agent_id=rev_agent.agent_id, instructions=f"Review this plan against the runbook:\n{plan_m}")
        findings_m = rev_agent.run(f"Review this plan against the runbook:\n{plan_m}", **review)
        shared.post_report(self.shared_session_id, agent_id=rev_agent.agent_id, command_id=command_id,
                           findings=findings_m, citations=[])
        revised_m = memo.run("Revise the plan using the reviewer's findings.", **main,
                             context={"reviewer_findings": findings_m})
        names = {memo.agent_id: "memo", rev_agent.agent_id: "rev"}
        entries = [{"type": e.get("entry_type"), "agent": names.get(e.get("agent_id"), e.get("agent_id"))}
                   for e in shared.get_blackboard_entries(self.shared_session_id)]
        return {"scratch": {"plan": plan_s, "findings": findings_s, "revised": revised_s},
                "memorizz": {"plan": plan_m, "findings": findings_m, "revised": revised_m, "blackboard": entries}}

    def _p14_scores(self, params: dict) -> dict:
        query = str(params.get("query") or "Who do I page when the rebuild fails?")
        memo = self.memorizz.agent_at(14)
        return {"query": query, "scratch": rows.json_value(scratch.memory_scores(self.memory_id, query)),
                "memorizz_scoring": str(memo.retrieval_scoring), "memorizz_retention": str(memo.retention_config)}

    def _p14_suppress(self, params: dict) -> dict:
        candidates = scratch.suppress_low_retention(self.memory_id)
        remaining = [r["chunk_index"] for r in scratch.search_knowledge(self.memory_id, "support plan response time",
                                                                        "runbook", k=7)]
        self.memorizz.retention = {"enabled": True, "grace_days": 0, "min_retention": scratch.MIN_RETENTION,
                                   "memory_types": ["conversation_memory"]}
        memo = self.memorizz.agent_at(14, force=True)
        plan = memo.plan_memory_retention(memory_id=self.memory_id, user_id=self.user_id)
        view = plan if isinstance(plan, dict) else plan.to_dict()
        if view.get("candidate_count"):
            memo.apply_memory_retention(plan, approved_by="platform-lead", reason="appbook demo of governed forgetting")
        suppressed = memo.suppressed_memories(memory_id=self.memory_id, user_id=self.user_id)
        return {"scratch_suppressed_ids": candidates, "scratch_search_after": remaining,
                "memorizz_plan": {k: view.get(k) for k in ("plan_id", "dry_run", "candidate_count", "retained")},
                "memorizz_suppressed": len(suppressed),
                "memorizz_first": {k: suppressed[0].get(k) for k in ("memory_type", "approver", "reason")}
                if suppressed else None}

    def _p14_restore(self, params: dict) -> dict:
        restored = scratch.restore_suppressed(self.memory_id)
        after = [r["chunk_index"] for r in scratch.search_knowledge(self.memory_id, "support plan response time",
                                                                    "runbook", k=7)]
        memo = self.memorizz.agent_at(14)
        rows_ = memo.suppressed_memories(memory_id=self.memory_id, user_id=self.user_id)
        back = sum(bool(memo.unsuppress_memory(r["record_id"], r["memory_type"], approved_by="platform-lead"))
                   for r in rows_)
        left = len(memo.suppressed_memories(memory_id=self.memory_id, user_id=self.user_id))
        return {"scratch_restored": restored, "scratch_search_after": after,
                "memorizz_restored": back, "memorizz_still_suppressed": left}

    def _p15_route(self, params: dict) -> dict:
        from memorizz.finetune import routing
        from memorizz.finetune.synthetic import JevVerifier
        from memorizz.finetune.tasks import memory_routing_spec

        items = params.get("items") or list(scratch.ITEMS)
        items = [str(item)[:400] for item in items][:12]
        started = time.perf_counter()
        llm = [scratch.llm_route(item) for item in items]
        llm_seconds = round(time.perf_counter() - started, 2)
        started = time.perf_counter()
        jev = scratch.jev_route(items)
        jev_seconds = round(time.perf_counter() - started, 2)
        question = memory_routing_spec()["questions"]["memory_type"]
        verifier = JevVerifier(model="jev-latest", api_key=settings.typesafe_api_key)
        verdicts = verifier.decide_many(question, items)
        table = []
        for item, choice, probabilities, verdict in zip(items, llm, jev, verdicts):
            best = max(probabilities, key=probabilities.get)
            answer = verdict.get("answer")
            confidence = (verdict.get("probabilities") or {}).get(answer, 0.0) if answer else 0.0
            placed = routing.place({"memory_type": answer, "confidence": confidence} if answer else None,
                                   {"knowledge_base", "short_term_memory"}, default="knowledge_base")
            table.append({"item": item, "expected": scratch.ITEMS.get(item), "llm": choice["store"],
                          "llm_confidence": choice["confidence"], "jev": best, "jev_p": round(probabilities[best], 3),
                          "jev_probabilities": {k: round(v, 3) for k, v in sorted(probabilities.items(), key=lambda kv: -kv[1])[:4]},
                          "memorizz_jev": answer, "memorizz_p": round(confidence, 3),
                          "filed_to": placed.get("memory_type"), "applied": placed.get("applied"),
                          "next_step": placed.get("next_step")})
        labelled = [row for row in table if row["expected"]]
        accuracy = {"llm": sum(r["llm"] == r["expected"] for r in labelled) / len(labelled) if labelled else None,
                    "jev": sum(r["jev"] == r["expected"] for r in labelled) / len(labelled) if labelled else None}
        return {"rows": table, "llm_seconds": llm_seconds, "jev_seconds": jev_seconds, "accuracy": accuracy,
                "memorizz_options": list(question["criteria"]), "jev_usage": verifier.usage(),
                "active_fine_tuned_router": routing.route(runtime.require(), items[0], memory_id=self.memory_id)}

    def _p15_file(self, params: dict) -> dict:
        from memorizz import MemoryType
        from memorizz.finetune.synthetic import JevVerifier
        from memorizz.finetune.tasks import memory_routing_spec

        item = str(params.get("item") or "").strip()[:400]
        if not item:
            raise ValueError("Give the item to file.")
        probabilities = scratch.jev_route([item])[0]
        filed = scratch.file_memory(self.scope("migration"), self.review_session, item, probabilities)
        verdict = JevVerifier(model="jev-latest", api_key=settings.typesafe_api_key).decide_many(
            memory_routing_spec()["questions"]["memory_type"], [item])[0]
        target, memorizz_filed = verdict.get("answer"), None
        if target == "knowledge_base":
            self.memorizz.knowledge_ids.append(self.memorizz.knowledge.ingest_knowledge(
                item, namespace=self.memorizz.namespace, chunking_strategy="none", user_id=self.user_id))
            self.memorizz.agent_at(self.memorizz.level, force=True)
            memorizz_filed = "knowledge_base (new knowledge base, attached)"
        elif target == "short_term_memory":
            runtime.require().store({"content": item, "memory_id": self.memory_id, "user_id": self.user_id},
                                    memory_store_type=MemoryType.SHORT_TERM_MEMORY)
            memorizz_filed = "short_term_memory"
        elif target == "entity_memory":
            self.memorizz.agent_at(15).run(f"Please remember this: {item}", **self.scope("migration"))
            memorizz_filed = "entity_memory (through Memo's entity tools)"
        return {"item": item, "scratch_store": max(probabilities, key=probabilities.get), "scratch_filed": filed,
                "scratch_probabilities": {k: round(v, 3) for k, v in sorted(probabilities.items(), key=lambda kv: -kv[1])},
                "memorizz_answer": target, "memorizz_filed": memorizz_filed or "not filed here (see next step)"}

    def _p16_save_restore(self, params: dict) -> dict:
        from memorizz import MemAgent

        definition = scratch.save_agent(self.memory_id, scratch.build_agent(16), "Memo")
        scratch_restored = scratch.load_agent(self.memory_id, "Memo")
        memo = self.memorizz.agent_at(16)
        # Tool code is never stored: the trusted bindings are passed in, and keep their governed policies.
        restored = MemAgent.load(memo.agent_id, memory_provider=runtime.require(), model=memorizz_model(),
                                 toolbox=self.memorizz.toolbox, tools=governed_tools())
        restored.capture_context_snapshots = True
        old = self.restored.get("memorizz")
        if old is not None:
            try:
                old.close(close_memory_provider=False)
            except Exception:
                pass
        self.restored = {"scratch": scratch_restored, "memorizz": restored}
        return {"scratch_layers": [{"order": layer.order, "layer": layer.name, "class": type(layer).__name__}
                                   for layer in scratch_restored.layers],
                "scratch_definition": rows.json_value(definition),
                "memorizz": {"agent_id": restored.agent_id, "name": restored.name,
                             "active_memory_types": [t.value for t in restored.active_memory_types],
                             "knowledge_bases": len(restored.knowledge_base_ids or []),
                             "skill_retrieval": restored.skill_retrieval,
                             "semantic_cache": restored.semantic_cache_stats().get("enabled")}}

    def _p16_compare(self, params: dict) -> dict:
        if not self.restored:
            self._p16_save_restore({})
        request = str(params.get("request") or (
            "It's Tuesday 02:20 UTC. I'm about to rebuild the retrieval-api vector index. Check docs_hnsw and the "
            "vector pool, then give me a go or no-go and the exact steps."))
        final = self.scope("rebuild-night")
        agent_s, agent_m = self.restored["scratch"], self.restored["memorizz"]
        self.turn_no += 1
        measure = {"turn": self.turn_no, "part": 16, "thread": "rebuild-night", "question": request,
                   "model": settings.model}
        answer_s, meter, total_ms = _measure_scratch(agent_s, request, {**final, "session_id": self.review_session})
        seconds_s = round(total_ms / 1000, 2)
        self.metrics.append(tokenomics.scratch_record(
            meter, total_ms=total_ms, cache_hit=agent_s.last_turn.cache_hit is not None,
            tool_calls=[c["tool"] for c in agent_s.last_turn.calls], **measure))
        answer_m, collector, total_ms = _measure_memorizz(agent_m, request, final)
        seconds_m = round(total_ms / 1000, 2)
        usage = agent_m.get_last_run_usage() or {}
        self.metrics.append(tokenomics.memorizz_record(
            collector, usage, total_ms=total_ms, tool_calls=_tool_names(agent_m.last_tool_outcomes),
            cache_hit=not usage.get("calls"), **measure))
        self.contexts[self.turn_no] = context_view.turn(
            turn=self.turn_no, part=16, thread="rebuild-night", question=request, test=None,
            scratch=context_view.scratch_calls(meter.requests),
            memorizz=context_view.memorizz_calls(self.memorizz.context_snapshots(collector.calls)))
        return {"request": request,
                "scratch": {"text": answer_s, "seconds": seconds_s, "turn": self.turn_no,
                            "input_tokens": agent_s.last_turn.usage.get("input_tokens"),
                            "tool_calls": [c["tool"] for c in agent_s.last_turn.calls],
                            "context": scratch.show_context(agent_s)},
                "memorizz": {"text": answer_m, "seconds": seconds_m, "turn": self.turn_no,
                             "input_tokens": usage.get("input_tokens"),
                             "cached_tokens": usage.get("cached_tokens"),
                             "tool_calls": _tool_names(agent_m.last_tool_outcomes)}}

    def _p16_observability(self, params: dict) -> dict:
        counts = {}
        for table in scratch.SCRATCH_TABLES:
            column, value = ("user_id", self.user_id) if table == "scratch_blackboard" else ("memory_id", self.memory_id)
            counts[table] = scratch.sql(f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = :v", v=value)[0]["n"]
        memo = self.memorizz.agent_at(16)
        summary = memo.observability_summary(self.memory_id, self.user_id, thread_id="migration")
        return {"scratch_counts": counts,
                "memorizz": rows.json_value({key: summary.get(key) for key in
                                             ("conversation", "tool_logs", "workflows", "summaries")})}

    # ── Tokenomics ──
    def tokenomics(self) -> dict:
        return {"turns": list(self.metrics), "summary": tokenomics.summary(self.metrics),
                "model": settings.model, "judge_model": settings.judge_model,
                "workload": [{k: item[k] for k in ("question", "test", "reference", "thread")}
                             for item in tokenomics.WORKLOAD],
                "tests": tokenomics.TESTS, "compact_after": tokenomics.COMPACT_AFTER,
                "stacks": self.workload_stacks, "running": self.workload_running}

    def workload_level(self) -> int:
        return 16 if settings.typesafe_api_key else 14     # Part 15 onwards routes every turn with Jev

    def compact(self, thread: str) -> dict:
        """Summarise a thread on both sides, keeping its four newest messages word for word."""
        with self.lock:
            scratch_id = scratch.compact(self.scope(thread), keep_recent=4)
            memo = self.memorizz.agent_at(self.memorizz.level)
            ids = memo.generate_summaries(memory_id=self.memory_id, user_id=self.user_id, thread_id=thread,
                                          days_back=1, keep_recent=4)
            return {"scratch_summary_id": scratch_id, "memorizz_summary_ids": ids}

    def workload(self, emit: Callable[[dict], None]) -> dict:
        """Run the memory workload at the full stack in a fresh scope; every turn of every agent is measured.

        A separate lab session holds the workload, so it starts with empty memory and the same setup
        (persona, runbook, tools, skill) whatever was sent on the Part pages; its rows are deleted at the end.
        The naive baseline answers each turn after both Memos, from its own transcript; it never compacts.
        Stop run ends it before the next turn: the turns measured so far stay, and its rows are still deleted.
        """
        level, total = self.workload_level(), len(tokenomics.WORKLOAD)
        bench = LabSession()
        stream = emit

        def emit(event: dict) -> None:
            """Send an event to the page that started the run, and keep the state other pages poll."""
            self._track_workload(event)
            stream(event)

        setup_only = lambda event: emit(event) if event.get("type") == "setup" else None  # noqa: E731
        self.stop_requested.clear()
        self.workload_running = True
        self.workload_state = {"state": "running", "index": 0, "total": total, "completed": 0,
                               "note": "Starting", "started_at": time.time()}
        try:
            for index, item in enumerate(tokenomics.WORKLOAD, 1):
                if self.stop_requested.is_set():
                    emit({"type": "stopped", "after": index - 1, "total": total})
                    break
                emit({"type": "progress", "index": index, "total": total, "question": item["question"],
                      "part": level, "test": item["test"], "thread": item["thread"]})
                bench.chat(level, item["question"], item["thread"], dict(item["context"] or {}), 8000, setup_only,
                           reference=item["reference"], test=item["test"])
                bench.naive_chat(level, item["question"], item["thread"], reference=item["reference"],
                                 test=item["test"])
                with self.lock:
                    self.turn_no += 1
                    records = bench.metrics[-3:]
                    for record in records:
                        record.update(turn=self.turn_no, run_id=f"t{self.turn_no}")
                    self.metrics.extend(records)
                    self.contexts[self.turn_no] = {**bench.contexts[bench.turn_no], "turn": self.turn_no}
                emit({"type": "turn", "records": records})
                if index == tokenomics.COMPACT_AFTER and not self.stop_requested.is_set():
                    emit({"type": "progress", "index": index, "total": total, "part": level,
                          "note": f"Compacting thread \"{tokenomics.MAIN_THREAD}\" on both sides (summaries)"})
                    bench.compact(tokenomics.MAIN_THREAD)
            self.workload_stacks = {"scratch": scratch.stack(scratch.build_agent(level)).split(" → "),
                                    "memorizz": bench.memorizz.memory_stack(), "part": level,
                                    "naive": ["the whole thread, appended"]}
        except Exception as exc:
            self.workload_state.update(state="failed", note=f"{type(exc).__name__}: {exc}"[:300])
            raise
        finally:
            self.workload_running = False
            if self.workload_state["state"] == "running":
                self.workload_state["state"] = "complete"
            self.workload_state["finished_at"] = time.time()
            try:
                bench.cleanup()
            except Exception:
                pass
        return self.tokenomics()

    def _track_workload(self, event: dict) -> None:
        state, kind = self.workload_state, event.get("type")
        if kind == "progress":
            state.update(index=event["index"], note=event.get("note"))
            state.update({key: event[key] for key in ("question", "test", "thread") if event.get(key)})
        elif kind == "setup" and event.get("status") == "running":
            state["note"] = f"Setting up Part {event['part']}"
        elif kind == "turn":
            state.update(completed=state["completed"] + 1, note=None)
        elif kind == "stopped":
            state.update(state="stopped", completed=event["after"], note=None)

    def workload_status(self) -> dict:
        """The memory workload for every page's notification: idle, running, stopping, or how it ended."""
        state = dict(self.workload_state)
        if self.workload_running and self.stop_requested.is_set():
            state["state"] = "stopping"
        return {**state, "running": self.workload_running}

    def stop_workload(self) -> dict:
        """Ask a running workload to stop before its next turn; the turns already measured are kept."""
        self.stop_requested.set()
        return {"stopping": self.workload_running}

    def clear_metrics(self) -> dict:
        with self.lock:
            self.metrics.clear()
            self.contexts.clear()
            self.turn_no = 0
            return self.tokenomics()

    def context_turns(self) -> list[dict]:
        """Every turn with a recorded context window, without its sections (read without the lock: a turn
        in progress holds it)."""
        return [context_view.summary(record) for record in list(self.contexts.values())]

    def context(self, turn: int) -> dict | None:
        return self.contexts.get(turn)

    # ── lifecycle ──
    def cleanup(self) -> dict:
        with self.lock:
            for agent in self.restored.values():
                close = getattr(agent, "close", None)
                if close:
                    try:
                        close(close_memory_provider=False)
                    except Exception:
                        pass
            self.restored = {}
            report = {"scratch": scratch.delete_session_rows(self.memory_id, self.user_id)}
            report.update(self.memorizz.cleanup())
            return report


class SessionHolder:
    """The current lab session; reset replaces it after deleting its rows."""

    def __init__(self) -> None:
        self.current = LabSession()

    def reset(self) -> dict:
        old = self.current
        report: dict = {"cleaned": False}
        if runtime.ready and settings.cleanup_on_reset:
            report = {"cleaned": True, **old.cleanup()}
        else:
            old.memorizz.close()
        self.current = LabSession()
        return report

    def shutdown(self) -> None:
        if runtime.ready and settings.cleanup_on_reset:
            try:
                self.current.cleanup()
            except Exception:
                pass
        else:
            self.current.memorizz.close()


sessions = SessionHolder()
