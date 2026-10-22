# MemoRizz 0.17.4 findings from the agent-memory evaluation (2026-10-22)

## 1. Entity writes fail with ORA-03146 once an entity's JSON passes ~8 KB

`OracleProvider._store_entity_memory` (memorizz/memory_provider/oracle/provider.py ~L4183-4240) binds `attributes`,
`relations` and `metadata` as Python `str` in the MERGE, without `cursor.setinputsizes(... = oracledb.DB_TYPE_CLOB)`.
With python-oracledb thin 26.0.1 against Oracle AI Database Free 23.26, the MERGE fails once the attributes JSON is
about 8 KB (6.5 KB succeeds, 8.1 KB fails):

    oracledb.exceptions.DatabaseError: ORA-03146: invalid buffer length for TTC field
      provider.py:4256 _store_entity_memory -> _execute_merge -> cursor.execute(merge_sql, params)

How it happens in an agent: with entity memory on and a user who sends lists of facts, gpt-6.1-sol files each batch
as one more attribute of a single entity ("User-provided ordered fact list".facts_40_through_59), so the entity grows by
~1.5 KB per turn and fails from about the 6th batch. Minimal repro (no model needed):

```python
"""Minimal repro: grow one MemoRizz entity's attributes until the write fails."""
import os, uuid, traceback
from memorizz import OracleProvider, EntityMemory
os.environ.setdefault("ORACLE_USER", "MEMORIZZ"); os.environ.setdefault("ORACLE_PASSWORD", "MemorizzPwd_2026"); os.environ.setdefault("ORACLE_DSN", "localhost:1521/FREEPDB1")
provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, embedding_provider="openai",
                                   embedding_config={"model": "text-embedding-3-small", "dimensions": 256})
store = EntityMemory(provider)
MID, UID = f"size-{uuid.uuid4().hex[:6]}", "size-user"
chunk = "\n".join(f"{n}. The capital of Country{n} is City{n} and it is a long sentence to pad the value." for n in range(20))
entity_id = None
for i in range(1, 20):
    try:
        entity_id = store.record_attribute(entity_id=entity_id, entity_name="Ordered fact list", attribute_name=f"facts_{i}",
                                           attribute_value=chunk, memory_id=MID, user_id=UID)
        e = store.get_entity(entity_id, memory_id=MID, user_id=UID)
        print(i, "ok", len(e["attributes"]), "attributes,", sum(len(str(a["value"])) for a in e["attributes"]), "chars")
    except Exception as exc:
        print(i, "FAILED:", type(exc).__name__, str(exc)[:200]); traceback.print_exc(limit=6); break
print(provider.delete_scope(memory_id=MID, user_id=UID)["total_deleted"])
```

Output: `1 ok … 4 ok 4 attributes, 6516 chars` then `5 FAILED: DatabaseError ORA-03146`.
Suggested fix: `cursor.setinputsizes(attributes=oracledb.DB_TYPE_CLOB, relations=oracledb.DB_TYPE_CLOB,
metadata=oracledb.DB_TYPE_CLOB)` before the MERGE (and the same for other CLOB binds, e.g. RETENTION_META).

## 2. After that error the agent hangs forever in pool.acquire()

After ORA-03146 the pooled connection is broken; the next operations that get it fail with
`DPY-4011: the database or network closed the connection` ("Tool execution failed" in the run log), and after a few
turns `memo.run()` never returns: the database shows no MEMORIZZ session at all, and the Python thread waits in
`oracledb pool.acquire()` (default getmode WAIT, no wait_timeout). Stack of the hung thread (faulthandler):

```
Thread 0x000000016fb2f000 (most recent call first):
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/threading.py", line 355 in wait
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/threading.py", line 390 in wait_for
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/oracledb/connection.py", line 1370 in __init__
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/oracledb/connection.py", line 2133 in connect
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/oracledb/pool.py", line 430 in acquire
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memory_provider/oracle/provider.py", line 1460 in _get_connection
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memory_provider/oracle/provider.py", line 3495 in _store_conversation_memory_impl
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memory_provider/oracle/provider.py", line 3577 in _store_conversation_memory
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memory_provider/oracle/provider.py", line 2940 in store
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memagent/managers/memory_manager.py", line 306 in save_memory_unit
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memagent/core.py", line 11649 in _record_interaction
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memagent/core.py", line 6342 in _finish_turn
  File "~/Desktop/agent_memory_course/part7/.venv/lib/python3.12/site-packages/memorizz/memagent/core.py", line 6551 in run
  File "notes/probe_deadlock.py", line 48 in tell
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/concurrent/futures/thread.py", line 59 in run
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/concurrent/futures/thread.py", line 93 in _worker
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/threading.py", line 1012 in run
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/threading.py", line 1075 in _bootstrap_inner
  File "~/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/threading.py", line 1032 in _bootstrap
```

Repro: `probe_deadlock.py` (23 turns of 20 FactConsolidation facts through `memo.run()` with entity memory on; hangs
around turn 17-23). Suggested fixes: drop broken connections from the pool (`pool.drop(conn)` on DPY-4011/ORA-03146),
and create the pool with `getmode=oracledb.POOL_GETMODE_TIMEDWAIT, wait_timeout=...` (plus `ping_interval`), so a
leak becomes an error instead of a hang.

## 3. Smaller observations
- Recalled conversation items are cut to 600 characters (`dedupe_and_select(max_chars_per_item=600)` in
  memagent/utils/context_dedup.py); `RetrievalPolicy` cannot change it. Long assistant messages lose their details
  (LongMemEval single-session-assistant questions).
- `ContextPolicy.max_tool_invocations_per_turn=20`: a message with 25 facts left 5 unsaved; the model said so in
  prose, nothing in the API reports it.
- `last_memory_context_evidence()["semantic_refs"]` are SHA-256 fingerprints of record ids: mappable, but a public
  list of the retrieved record ids (and their thread ids) would make retrieval evaluation simpler.
- Entity memory on adds an `entity_memory_lookup` tool call to most questions: about 9k input tokens and ~10 s per
  answer vs ~4.6k for one call, even when no entity exists for the user.

## Fixed in 0.17.8 (verified 2026-10-22)

MemoRizz 0.17.8 (commit e18c946) fixes both bugs:
- Entity and vector-document writes use UPDATE or INSERT instead of MERGE, so values above 8 KB save.
- Pooled connections that hit a session error are pinged and closed, or dropped.
- `OracleConfig.pool_wait_timeout=60` s raises DPY-4005 instead of waiting forever.

Verified in `part7/.venv` with `memorizz[oracle]==0.17.8`, against the same Oracle AI Database Free container.

### Bug 1: entity size (`probe_entity_size.py`, unchanged)
- **Result:** 19 of 19 `EntityMemory.record_attribute()` writes succeed. The entity reaches 19 attributes and 30,951 characters of values, where 0.17.4 failed at about 8 KB.
- **Embedding limit:** at the 19th write the entity text passed the embedding model's 8,192-token input limit. MemoRizz logged `Storing entity … without an embedding (BadRequestError)` and saved it anyway. The write succeeds, but an entity that large has no vector, so vector search cannot find it.
  - Suggestion: embed a summary or the most recent attributes when the full text is too long, and report it through the API rather than only a log line.

### Bug 2: the hang (`probe_deadlock.py`, run again on 0.17.8: output in `probe_deadlock_0178.log`, stacks in `deadlock_stacks_0178.txt`)
- **Setup:** 23 turns of 20 FactConsolidation facts through `memo.run()`, entity memory on, `gpt-6.1-sol` with `gpt-6-luna` in the background, `RetrievalPolicy(max_items=10, candidate_limit=20)`.
- **Result:** all 23 turns finished. No ORA-03146, no DPY error, and no `pool.acquire()` in any stack dump. On 0.17.4 the same script hung for good between turns 17 and 23.
- **Turn times:** about 31 s per turn while entities were being written (turns 1–6, 18–20 tool calls each), and 9–16 s afterwards.
  - Turn 18 took 193 s. The stack dump taken during it shows the agent thread in an OpenAI Responses API read (`memagent/core.py` `_execute_llm_interaction` → `llms/openai.py` `_generate_responses`), not in Oracle. That was a slow model call inside the client's 180 s timeout and retry.
- **Total:** 466,732 input and 10,051 output tokens. The final question ("Who is the chief executive officer of Microsoft?") was answered, "Satya Nadella.", and cleanup deleted 158 memory rows and 35 agent rows.
- **Tool calls:** after turn 6 the model made one tool call per turn instead of one per fact.

### Still open in 0.17.8
- Recalled conversation items are still cut to 600 characters (`context_dedup` `max_chars_per_item=600`). `RetrievalPolicy` exposes only `max_items`. The evaluation keeps eight facts per message for that reason.
- The other observations in section 3 are unchanged: the 20-tool-call cap per turn, fingerprinted evidence refs, and the extra `entity_memory_lookup` call per answer.
- The canonical notebook run on 0.17.8, with entity memory on in Part 6, is reported in the evaluation README.
- Entity writes depend on the model choosing to call `entity_memory_upsert`. With entity memory on and the
  evaluation's Memo instruction, four turns of eight numbered facts made no tool call at all when the user turn began
  "Numbered facts (a higher number wins):", so entity memory stayed empty. The same turns made 8 upserts each (one per
  fact) when they began "Please remember these facts (a higher number wins):" (`probe_fc_entities.py`).
  - Suggestion: an option to extract entities in the background, as the scratch Memo does, so that memory does not
    depend on how the user phrases a message.
