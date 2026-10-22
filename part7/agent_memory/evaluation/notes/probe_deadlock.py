"""Repro of the notebook's FactConsolidation write path in MemoRizz, with the same metered clients; dump stacks on a stall."""
from pathlib import Path
import faulthandler, json, os, re, sys, time, uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
faulthandler.dump_traceback_later(240, repeat=True, file=open(Path(__file__).with_name("deadlock_stacks.txt"), "w"))
import pandas as pd
from memorizz import MemAgentBuilder, OracleProvider, RetrievalPolicy
from memorizz.llms.openai import OpenAI as MemorizzOpenAI
os.environ.setdefault("ORACLE_USER", "MEMORIZZ"); os.environ.setdefault("ORACLE_PASSWORD", "MemorizzPwd_2026"); os.environ.setdefault("ORACLE_DSN", "localhost:1521/FREEPDB1")
cr = pd.read_parquet("hf://datasets/ai-hyz/MemoryAgentBench@7ea066982b140a19337e17e60d45d4076e042faf/data/Conflict_Resolution-00000-of-00001.parquet")
row = cr[cr.metadata.map(lambda m: m["source"]) == "factconsolidation_sh_6k"].iloc[0]
FACTS = [(int(m.group(1)), m.group(2)) for line in row["context"].splitlines() if (m := re.match(r"^(\d+)\.\s+(.*)$", line))]
METER, METER_LOCK = Counter(), Lock()
def metered(model, effort):
    client = MemorizzOpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model, reasoning_effort=effort)
    client.client = client.client.with_options(timeout=180, max_retries=3)
    chat_create, responses_create = client.client.chat.completions.create, client.client.responses.create
    def count(i, c, o):
        with METER_LOCK:
            METER["input_tokens"] += i; METER["cached_tokens"] += c; METER["output_tokens"] += o
    def counted_chat(**kw):
        r = chat_create(**kw)
        if getattr(r, "usage", None) is not None: count(r.usage.prompt_tokens, 0, r.usage.completion_tokens)
        return r
    def counted_responses(**kw):
        r = responses_create(**kw)
        if getattr(r, "usage", None) is not None: count(r.usage.input_tokens, 0, r.usage.output_tokens)
        return r
    client.client.chat.completions.create, client.client.responses.create = counted_chat, counted_responses
    return client
INSTRUCTION = ("You are Memo, a personal assistant with long-term memory of your past conversations with this user. Answer "
               "from what you remember. Dates matter: today's date is given with the question, and when two memories "
               "disagree, the more recent one is the current truth (a fact with a higher number replaces an earlier fact "
               "about the same thing). If your memory does not contain the answer, say you don't know. Keep answers short.")
provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, embedding_provider="openai",
                                   embedding_config={"model": "text-embedding-3-small", "dimensions": 256})
RUN = uuid.uuid4().hex[:6]; MID, UID = f"deadlock-{RUN}", f"fc-deadlock-{RUN}"
memo = (MemAgentBuilder().with_name(f"Deadlock {RUN}").with_instruction(INSTRUCTION).with_model(metered("gpt-6.1-sol", "low"))
        .with_background_model(metered("gpt-6-luna", "none")).with_memory_provider(provider).with_memory_ids(MID)
        .with_entity_memory(True).with_retrieval_policy(RetrievalPolicy(max_items=10, candidate_limit=20))
        .with_automations_enabled(False)).build_and_save()
messages = [("Please remember these facts. They are numbered in the order you learn them; a higher number replaces an earlier "
             "fact about the same thing.\n" + "\n".join(f"{n}. {t}" for n, t in FACTS[i:i + 20])) for i in range(0, len(FACTS), 20)]
def tell():
    for k, m in enumerate(messages):
        t = time.perf_counter()
        memo.run(m, memory_id=MID, user_id=UID, thread_id="facts")
        print(f"turn {k + 1}: {time.perf_counter() - t:.1f}s · tools {len(memo.last_tool_outcomes)} · meter {dict(METER)}", flush=True)
with ThreadPoolExecutor(1) as pool:
    pool.submit(tell).result()
print("ask:", memo.run("Who is the chief executive officer of Microsoft?", memory_id=MID, user_id=UID, thread_id="questions"), flush=True)
memo.close(close_memory_provider=False)
print(provider.delete_scope(memory_id=MID, user_id=UID)["total_deleted"], provider.delete_scope(agent_ids=[memo.agent_id])["total_deleted"])
print("DONE", flush=True)
