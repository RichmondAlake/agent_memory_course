"""The three agents under test (the notebook's Part 3), behind one interface: ingest, observe, answer.

- naive: the whole history pasted into every prompt.
- scratch Memo: MEMAPP_TURNS (rounds, VECTOR(256) + Oracle Text, hybrid RRF retrieval) and MEMAPP_FACTS (entity facts
  extracted on every turn, superseded when they change).
- MemoRizz Memo: a MemAgent on the same Oracle schema, conversation recall across threads, entity memory through the
  model's tools, RetrievalPolicy(max_items=10) to match the scratch Memo's 10 rounds.

Each suite run gets its own memory id (`memapp-…`), so runs never read each other's memory, and `cleanup()` deletes what
the agents wrote while the evidence stays.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from backend.config import settings
from backend.core import db, llm
from backend.core.tracing import io, set_documents, set_output, traced

INSTRUCTION = ("You are Memo, a personal assistant with long-term memory of your past conversations with this user. Answer "
               "from what you remember. Dates matter: today's date is given with the question, and when two memories "
               "disagree, the more recent one is the current truth (a fact with a higher number replaces an earlier fact "
               "about the same thing). If your memory does not contain the answer, say you don't know. Keep answers short.")
FACTS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["facts"], "properties": {"facts": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["entity", "attribute", "value"],
                               "properties": {"entity": {"type": "string"}, "attribute": {"type": "string"},
                                              "value": {"type": "string"}}}}}}
STOPWORDS = set("the a an and or of to in on is are was were do does did i my me for how what when where which who whom why "
                "can could would should will with be it you your this that from at as by if we our much many need there any "
                "have has had am today tell remind again".split())


@dataclass
class Answer:
    system: str
    text: str
    evidence: list = field(default_factory=list)
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    cost_usd: float = 0.0

    def row(self) -> dict:
        return {"input_tokens": self.input_tokens, "cached_tokens": self.cached_tokens, "output_tokens": self.output_tokens,
                "seconds": self.seconds, "cost_usd": self.cost_usd}


def asked(question: str, date: str | None = None) -> str:
    return f"Today is {date}. {question}" if date else question


def text_terms(question: str) -> str | None:
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in STOPWORDS]
    return " ACCUM ".join("{%s}" % w for w in dict.fromkeys(words)) or None


def rounds_of(turns: list[dict]) -> list[dict]:
    rounds = []
    for turn in turns:
        if turn["role"] == "user" or not rounds:
            rounds.append({"user": "", "assistant": "", "has_answer": False})
        rounds[-1]["user" if turn["role"] == "user" else "assistant"] += turn["content"]
        rounds[-1]["has_answer"] |= bool(turn.get("has_answer"))
    return rounds


# ── naive ─────────────────────────────────────────────────────────────────────────────────────────────────────
class NaiveAgent:
    name = "naive"

    def __init__(self):
        self.transcripts = defaultdict(list)
        self.usage = Counter()

    def ingest(self, sessions, scope):
        for session_id, date, turns in sessions:
            body = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
            self.transcripts[(scope["memory_id"], scope["user_id"])].append(f"### Session {session_id} · {date}\n{body}")

    def observe(self, message, scope, sealed=False):
        self.transcripts[(scope["memory_id"], scope["user_id"])].append(f"user: {message}\nassistant: Noted.")

    def answer(self, question, scope, date=None, sealed=False) -> Answer:
        started = time.perf_counter()
        history = "\n\n".join(self.transcripts[(scope["memory_id"], scope["user_id"])])
        response, used = llm.chat(INSTRUCTION, f"Our conversation history:\n\n{history}\n\n---\n{asked(question, date)}")
        return Answer("naive", response.output_text, [], seconds=time.perf_counter() - started, **used)


# ── scratch Memo ──────────────────────────────────────────────────────────────────────────────────────────────
class ScratchMemo:
    name = "scratch"

    def __init__(self, k: int = 10, facts_k: int = 12):
        self.k, self.facts_k, self.usage = k, facts_k, Counter()

    def _insert_rounds(self, scope, thread_id, date, rounds, sealed=False):
        texts = [f"[{date}] user: {r['user']}\nassistant: {r['assistant']}" if date else
                 f"user: {r['user']}\nassistant: {r['assistant']}" for r in rounds]
        vectors = llm.embed(texts, purpose="scratch-write")
        db.executemany("""INSERT INTO memapp_turns (memory_id, user_id, thread_id, sealed, session_date, content, has_answer, embedding)
                          VALUES (:1, :2, :3, :4, :5, :6, :7, :8)""",
                       [(scope["memory_id"], scope["user_id"], thread_id, int(sealed), date, text, int(r["has_answer"]), vector)
                        for r, text, vector in zip(rounds, texts, vectors)])

    def ingest(self, sessions, scope):
        for session_id, date, turns in sessions:
            self._insert_rounds(scope, session_id, date, rounds_of(turns))

    def observe(self, message, scope, sealed=False):
        self._insert_rounds(scope, scope["thread_id"], None, [{"user": message, "assistant": "Noted.", "has_answer": False}], sealed)
        known = {r["attribute"] for r in db.sql("""SELECT DISTINCT attribute FROM memapp_facts
                                                   WHERE memory_id = :memory_id AND user_id = :user_id""", **scope)}
        response, used = llm.chat(("Extract every lasting fact the user states in the message as (entity, attribute, value). Write "
                                   "'I' and 'me' as the entity 'user'. Use snake_case attribute names and reuse these when they fit: "
                                   f"{sorted(known)[:80]}. Facts are listed in order: keep that order. Ignore questions, small talk, "
                                   "hypotheticals, and things someone else asked about or might do."),
                                  message, cheap=True, purpose="scratch-write",
                                  text={"format": {"type": "json_schema", "name": "facts", "schema": FACTS_SCHEMA, "strict": True}})
        for key, value in used.items():
            self.usage[key] += value
        facts = json.loads(response.output_text)["facts"]
        vectors = llm.embed([f"{f['entity']} {f['attribute'].replace('_', ' ')}: {f['value']}" for f in facts],
                            purpose="scratch-write") if facts else []
        for fact, vector in zip(facts, vectors):
            self._upsert(scope, fact, vector, scope["thread_id"] if sealed else None)
        return facts

    def _upsert(self, scope, fact, vector, thread_id):
        current = db.sql("""SELECT id, value FROM memapp_facts WHERE memory_id = :memory_id AND user_id = :user_id
                            AND LOWER(entity) = LOWER(:entity) AND attribute = :attribute AND superseded_at IS NULL
                            AND NVL(thread_id, '-') = NVL(:t, '-')""", entity=fact["entity"], attribute=fact["attribute"],
                         t=thread_id, **scope)
        if current and current[0]["value"].strip().lower() == fact["value"].strip().lower():
            return
        if current:
            db.sql("UPDATE memapp_facts SET superseded_at = SYSTIMESTAMP WHERE id = :id", id=current[0]["id"])
        db.sql("""INSERT INTO memapp_facts (memory_id, user_id, thread_id, entity, attribute, value, source, embedding)
                  VALUES (:memory_id, :user_id, :t, :entity, :attribute, :value, :source, :v)""",
               t=thread_id, entity=fact["entity"][:300], attribute=fact["attribute"][:200], value=fact["value"][:1000],
               source=f"thread {scope['thread_id']}", v=vector, **scope)

    def answer(self, question, scope, date=None, sealed=False) -> Answer:
        started = time.perf_counter()
        q = llm.embed([question], purpose="scratch-read")[0]
        terms = text_terms(question)
        keyword = """txt AS (SELECT id, ROW_NUMBER() OVER (ORDER BY SCORE(1) DESC) AS r FROM memapp_turns
                            WHERE memory_id = :memory_id AND user_id = :user_id AND (sealed = 0 OR thread_id = :thread_id)
                              AND CONTAINS(content, :terms, 1) > 0 ORDER BY SCORE(1) DESC FETCH FIRST 20 ROWS ONLY)""" if terms else \
                  "txt AS (SELECT CAST(NULL AS NUMBER) AS id, CAST(NULL AS NUMBER) AS r FROM dual WHERE 1 = 0)"
        with traced("scratch recall · rounds", "RETRIEVER", **io(question)) as span:   # hybrid: vector + Oracle Text
            rows = db.sql(f"""WITH vec AS (SELECT id, ROW_NUMBER() OVER (ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE)) AS r
                                           FROM memapp_turns
                                           WHERE memory_id = :memory_id AND user_id = :user_id AND (sealed = 0 OR thread_id = :thread_id)
                                           ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE) FETCH FIRST 20 ROWS ONLY),
                                  {keyword},
                                  fused AS (SELECT NVL(v.id, t.id) AS id, NVL(1 / (60 + v.r), 0) + NVL(1 / (60 + t.r), 0) AS score
                                            FROM vec v FULL OUTER JOIN txt t ON t.id = v.id)
                             SELECT m.thread_id, m.session_date, m.content, f.score
                             FROM fused f JOIN memapp_turns m ON m.id = f.id
                             ORDER BY f.score DESC FETCH FIRST :k ROWS ONLY""", q=q, terms=terms, k=self.k, **scope)
            set_documents(span, [(f"{r['thread_id']}", r["content"], r["score"]) for r in rows])
        with traced("scratch recall · facts", "RETRIEVER", **io(question)) as span:    # current facts, by vector
            facts = db.sql("""SELECT entity, attribute, value FROM memapp_facts
                              WHERE memory_id = :memory_id AND user_id = :user_id AND superseded_at IS NULL
                                AND (thread_id IS NULL OR thread_id = :thread_id)
                              ORDER BY VECTOR_DISTANCE(embedding, :q, COSINE) FETCH FIRST :k ROWS ONLY""", q=q, k=self.facts_k, **scope)
            set_documents(span, [(f"{f['entity']}.{f['attribute']}", f["value"], None) for f in facts])
        blocks = []
        if facts:
            blocks.append("Known facts (current values):\n" + "\n".join(f"- {f['entity']}.{f['attribute']} = {f['value']}" for f in facts))
        if rows:
            blocks.append("Memories from past conversations (most relevant first):\n" + "\n\n".join(
                f"[{i + 1}] session {r['thread_id']}{' · ' + r['session_date'] if r['session_date'] else ''}\n{r['content'][:3000]}"
                for i, r in enumerate(rows)))
        response, used = llm.chat(INSTRUCTION, "\n\n".join(blocks + [asked(question, date)]))
        return Answer("scratch", response.output_text, [r["thread_id"] for r in rows], seconds=time.perf_counter() - started, **used)


# ── MemoRizz Memo ─────────────────────────────────────────────────────────────────────────────────────────────
_provider = None
_provider_lock = threading.Lock()
METER, METER_LOCK = Counter(), threading.Lock()


def provider():
    """MemoRizz's Oracle provider, created once (on open models it embeds with this app's embed())."""
    global _provider
    with _provider_lock:
        if _provider is None:
            from memorizz import OracleProvider
            from memorizz.embeddings import BaseEmbeddingProvider, EmbeddingManager

            if settings.open:
                class OpenEmbeddings(EmbeddingManager):
                    class Nomic(BaseEmbeddingProvider):
                        def get_embedding(self, text, **kwargs):
                            return list(llm.embed([text], purpose="memorizz")[0])

                        def get_embeddings(self, texts, **kwargs):
                            return [list(v) for v in llm.embed(texts, purpose="memorizz")]

                        def get_dimensions(self):
                            return settings.dimensions

                        def get_default_model(self):
                            return settings.embed_model

                    def _create_provider(self):
                        return self.Nomic(self.config)

                embeddings = {"embedding_provider": OpenEmbeddings("ollama", {"model": settings.embed_model})}
            else:
                embeddings = {"embedding_provider": "openai",
                              "embedding_config": {"model": settings.embed_model, "dimensions": settings.dimensions}}
            _provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, **embeddings)
    return _provider


def metered(cheap: bool = False):
    """A MemoRizz model client whose calls are counted, with a timeout (and the open-model nudge)."""
    from memorizz.llms.openai import OpenAI as MemorizzOpenAI

    model, effort = (settings.cheap_model, settings.cheap_effort) if cheap else (settings.model, settings.model_effort)
    client = MemorizzOpenAI(api_key=settings.openai_api_key, model=model, reasoning_effort=effort)
    client.client = client.client.with_options(timeout=settings.request_timeout, max_retries=3)
    chat_create, responses_create = client.client.chat.completions.create, client.client.responses.create

    def count(input_tokens, cached, output_tokens):
        dollars = llm.cost(model, input_tokens, cached, output_tokens)
        with METER_LOCK:
            METER["input_tokens"] += input_tokens
            METER["cached_tokens"] += cached
            METER["output_tokens"] += output_tokens
            METER["cost_usd"] += dollars
        llm.spend("memorizz", cost_usd=dollars, input_tokens=input_tokens)

    def counted_chat(**kwargs):
        response = chat_create(**kwargs)
        if settings.open and not kwargs.get("stream"):
            message = response.choices[0].message
            if not message.tool_calls and not (message.content or "").strip():
                response = chat_create(**{**kwargs, "messages": [*kwargs["messages"], {"role": "user", "content": "Answer now."}]})
        if getattr(response, "usage", None) is not None:
            details = getattr(response.usage, "prompt_tokens_details", None)
            count(response.usage.prompt_tokens, (getattr(details, "cached_tokens", 0) or 0) if details else 0,
                  response.usage.completion_tokens)
        return response

    def counted_responses(**kwargs):
        response = responses_create(**kwargs)
        if getattr(response, "usage", None) is not None:
            details = getattr(response.usage, "input_tokens_details", None)
            count(response.usage.input_tokens, (getattr(details, "cached_tokens", 0) or 0) if details else 0,
                  response.usage.output_tokens)
        return response

    client.client.chat.completions.create, client.client.responses.create = counted_chat, counted_responses
    return client


def build_memo(name: str, memory_id: str, entity_memory: bool = True):
    from memorizz import MemAgentBuilder, RetrievalPolicy

    return (MemAgentBuilder().with_name(name).with_instruction(INSTRUCTION).with_model(metered())
            .with_background_model(metered(cheap=True)).with_memory_provider(provider()).with_memory_ids(memory_id)
            .with_entity_memory(entity_memory).with_retrieval_policy(RetrievalPolicy(max_items=10, candidate_limit=20))
            .with_automations_enabled(False)).build_and_save()


def fingerprint(record_id) -> str:
    """MemoRizz's evidence fingerprint of a record id (SHA-256 of its JSON form)."""
    return hashlib.sha256(json.dumps(str(record_id), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MemorizzMemo:
    name = "memorizz"

    def __init__(self, agent):
        from memorizz.memagent.managers.memory_manager import MemoryManager

        self.agent, self.manager, self.session_of = agent, MemoryManager(provider()), {}
        self.usage, self.supplied = Counter(), []
        self.lock = threading.Lock()   # one MemAgent, one call at a time

    def ingest(self, sessions, scope):
        from memorizz.enums import Role

        for session_id, date, turns in sessions:
            texts = [f"[{date}] {turn['content']}"[:20000] for turn in turns]
            for turn, text, vector in zip(turns, texts, llm.embed(texts, purpose="memorizz-write")):
                unit = self.manager.create_conversation_memory_unit(
                    role=Role(turn["role"]), content=text, thread_id=session_id, memory_id=scope["memory_id"],
                    agent_id=self.agent.agent_id, user_id=scope["user_id"])
                unit.embedding = list(vector)
                record_id = self.manager.save_memory_unit(unit, scope["memory_id"])
                self.session_of[fingerprint(record_id)] = session_id

    def _run(self, text, scope, sealed=False):
        from memorizz import RetrievalPolicy

        with self.lock:
            before = dict(METER)
            policy = {"retrieval_policy": RetrievalPolicy.sealed(max_items=10, candidate_limit=20)} if sealed else {}
            started = time.perf_counter()
            with traced("memorizz run", "CHAIN", **io(text)) as span:   # MemoRizz keeps its own trace in Oracle
                reply = self.agent.run(text, **scope, **policy)
                set_output(span, reply)
            spent = {k: METER[k] - before.get(k, 0) for k in ("input_tokens", "cached_tokens", "output_tokens", "cost_usd")}
            evidence = self.agent.last_memory_context_evidence()
            return reply, spent, time.perf_counter() - started, evidence

    def observe(self, message, scope, sealed=False):
        reply, spent, _, _ = self._run(message, scope, sealed)
        for key, value in spent.items():
            self.usage[key] += value
        return reply

    def answer(self, question, scope, date=None, sealed=False) -> Answer:
        reply, spent, seconds, evidence = self._run(asked(question, date), scope, sealed)
        self.supplied.append((evidence.get("supplied_count", 0), evidence.get("injected_char_count", 0)))
        refs = [r["ref"] for r in evidence.get("semantic_refs", [])]
        return Answer("memorizz", reply, [self.session_of[r] for r in refs if r in self.session_of], seconds=seconds, **spent)


class Team:
    """The three agents for one suite run, under one memory id; cleanup() deletes what they wrote."""

    def __init__(self, run_id: str, memorizz_entity_memory: bool = True):
        self.memory_id = f"memapp-{run_id[-15:]}"
        self.users: set[str] = set()
        self.naive, self.scratch = NaiveAgent(), ScratchMemo()
        self.memo_name = f"Memo appbook {run_id[-15:]}"
        self.memo = build_memo(self.memo_name, self.memory_id, memorizz_entity_memory)
        self.memorizz = MemorizzMemo(self.memo)
        self.agents = {"naive": self.naive, "scratch": self.scratch, "memorizz": self.memorizz}

    def scope(self, user: str, thread: str = "main") -> dict:
        self.users.add(user)
        return {"memory_id": self.memory_id, "user_id": user, "thread_id": thread}

    def close(self) -> dict:
        """End the run and keep what it wrote: the MemoRizz agent, memories and trace bundles, and the MEMAPP_ rows."""
        try:
            self.memo.close(close_memory_provider=False)
        except Exception:  # noqa: BLE001
            pass
        return {"memory_id": self.memory_id, "agent_id": self.memo.agent_id, "agent": self.memo_name, "users": sorted(self.users)}

    def cleanup(self) -> dict:
        """Delete what the run wrote (only with MEMO_CLEANUP=1): exact-scope deletes on its memory id, users and agent."""
        from memorizz.retrieval import thread_entity_memory_id

        deleted = {t: db.sql(f"DELETE FROM {t} WHERE memory_id = :m", m=self.memory_id) for t in ("memapp_turns", "memapp_facts")}
        self.close()
        scopes = [(m, u) for u in sorted(self.users) for m in (self.memory_id, thread_entity_memory_id(self.memory_id, "incident"))]
        deleted["memorizz rows"] = sum(provider().delete_scope(memory_id=m, user_id=u)["total_deleted"] for m, u in scopes)
        deleted["memorizz agent rows"] = provider().delete_scope(agent_ids=[self.memo.agent_id])["total_deleted"]
        return deleted
