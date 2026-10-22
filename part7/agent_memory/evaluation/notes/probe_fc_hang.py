"""Repro: FactConsolidation facts as 23 MemoRizz turns with entity memory on; dump all thread stacks if it stalls."""
from pathlib import Path
import faulthandler, json, os, re, sys, time, uuid
faulthandler.dump_traceback_later(240, repeat=True, file=open(Path(__file__).with_name("fc_hang_stacks.txt"), "w"))
import pandas as pd
from memorizz import MemAgentBuilder, OracleProvider, RetrievalPolicy, EntityMemory
from memorizz.llms.openai import OpenAI as MemorizzOpenAI
os.environ.setdefault("ORACLE_USER", "MEMORIZZ"); os.environ.setdefault("ORACLE_PASSWORD", "MemorizzPwd_2026"); os.environ.setdefault("ORACLE_DSN", "localhost:1521/FREEPDB1")
cr = pd.read_parquet("hf://datasets/ai-hyz/MemoryAgentBench@7ea066982b140a19337e17e60d45d4076e042faf/data/Conflict_Resolution-00000-of-00001.parquet")
row = cr[cr.metadata.map(lambda m: m["source"]) == "factconsolidation_sh_6k"].iloc[0]
FACTS = [(int(m.group(1)), m.group(2)) for line in row["context"].splitlines() if (m := re.match(r"^(\d+)\.\s+(.*)$", line))]
provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, embedding_provider="openai",
                                   embedding_config={"model": "text-embedding-3-small", "dimensions": 256})
RUN = uuid.uuid4().hex[:6]; MID, UID = f"hang-{RUN}", f"fc-hang-{RUN}"
memo = (MemAgentBuilder().with_name(f"Hang {RUN}").with_instruction("You are Memo, a personal assistant with long-term memory.")
        .with_model(MemorizzOpenAI(model="gpt-6.1-sol", reasoning_effort="low"))
        .with_background_model(MemorizzOpenAI(model="gpt-6-luna", reasoning_effort="none"))
        .with_memory_provider(provider).with_memory_ids(MID).with_entity_memory(True)
        .with_retrieval_policy(RetrievalPolicy(max_items=10, candidate_limit=20)).with_automations_enabled(False)).build_and_save()
for i in range(0, len(FACTS), 20):
    t = time.perf_counter()
    msg = ("Please remember these facts. They are numbered in the order you learn them; a higher number replaces an earlier "
           "fact about the same thing.\n" + "\n".join(f"{n}. {x}" for n, x in FACTS[i:i + 20]))
    reply = memo.run(msg, memory_id=MID, user_id=UID, thread_id="facts")
    print(f"turn {i // 20 + 1}: {time.perf_counter() - t:.1f}s · tools {len(memo.last_tool_outcomes)} · {reply[:80]!r}", flush=True)
memo.close(close_memory_provider=False)
print(provider.delete_scope(memory_id=MID, user_id=UID)["total_deleted"], provider.delete_scope(agent_ids=[memo.agent_id])["total_deleted"])
print("DONE")
