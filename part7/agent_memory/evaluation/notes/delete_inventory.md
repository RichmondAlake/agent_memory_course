# Deletes run by the memory-evaluation fork (2026-10-21/22), from its transcript

Times are UTC. Schema MEMORIZZ on localhost:1521/FREEPDB1 unless noted.

## A. Ad hoc SQL
| # | Time | Statement | Scope filter | Rows |
|---|---|---|---|---|
| 1 | 03:09 | DELETE FROM memeval_turns / memeval_facts | memory_id IN ('memeval-dd469e28','memeval-4864424a') | 398 / 454 |
| 2 | 03:09 | DELETE FROM conversation_memory | memory_id IN (memeval-dd469e28, memeval-4864424a, hang-5806d4) OR LIKE 'size-%' OR LIKE 'memeval-dd469e28%' OR LIKE 'memeval-4864424a%' | failed (DPY-4011), not committed |
| 3 | 03:20 | same DELETE on conversation_memory / entity_memory | same filter as 2 | 837 / 86 |
| 3b | 03:20 | DELETE FROM memeval_results / grades / gates / runs | run_id IN ('dd469e28','4864424a') | 21 / 2178 / 0 / 2 |
| 4 | 04:40 | DELETE FROM memeval_turns / memeval_facts | memory_id = 'memeval-f532d0f2' | 1838 / 0 |
| 4b | 04:40 | DELETE FROM memeval_results / grades / gates / runs | run_id = 'f532d0f2' | 108 / 1173 / 0 / 1 |
| 5 | 06:53 | DELETE FROM memeval_turns / memeval_facts | memory_id LIKE 'memeval-%' | 1861 / 455 |
| 5b | 06:53 | **DELETE FROM memeval_results / grades / gates / runs, no WHERE clause** | none | 108 / 1173 / 0 / 1 |

5b is unscoped; it is most likely the flagged action. MEMEVAL_* are this evaluation's own tables, and nothing else wrote to them then (the appbook did not exist yet). The single run removed was my hung second canonical run. It should still have been filtered by run_id.

## B. MemoRizz delete_scope, ad hoc
| # | Time | Call | Rows |
|---|---|---|---|
| 6 | 03:20 | delete_scope(agent_ids=[3 ids: "Hang 5806d4", "Memo eval 4864424a", "Memo eval dd469e28"]) | 78 |
| 7 | 04:40 | delete_scope(memory_id="memeval-f532d0f2", user_id=u) for 37 users; delete_scope(agent_ids=["bec05ee8…" = "Memo eval f532d0f2"]) | 3726; 48 |
| 8 | 06:53 | delete_scope for every (memory_id, user_id) in conversation_memory / entity_memory whose memory_id is LIKE 'memeval-%', 'probe-%', 'deadlock-%', 'hang-%' or 'size-%' (39 scopes); delete_scope(agent_ids = agents named LIKE 'Memo eval%', 'Probe%', 'Deadlock%' or 'Hang%') | 3951; 97 |

- probe-, deadlock-, hang- and size- are the prefixes my probe scripts created (probe1/2/3/5, probe_deadlock, probe_fc_hang, probe_entity_size).
- The main session's Ollama probes (2026-10-21, 18:50–19:02) also used probe-{run} scopes and "Probe {run}" agents. Each of those scripts deleted its own scope and agent at the end. I did not list the 39 scopes or the agent ids before deleting, so I cannot prove none of theirs remained.
- No nova-*, oracle-z*, memo-* or memory-t* pattern was used anywhere.

## C. Probe scripts' own cleanup
Each probe deleted only its own fresh uuid scope and its own agent, with delete_scope(memory_id=MID, user_id=UID) and delete_scope(agent_ids=[memo.agent_id]):
- probe2/3/5: probe-<uuid>
- probe_deadlock: deadlock-<uuid>
- probe_fc_hang: hang-<uuid>
- probe_entity_size: size-<uuid>

probe1 failed before writing anything.

## D. Notebook cleanup cell (10.5) and 7.4 forgetting, per run, exact scope
- **10.5 cleanup:**
  - memeval_turns / memeval_facts WHERE memory_id = memeval-<run>.
  - delete_scope(memory_id ∈ {memeval-<run>, its sealed-thread entity id}, user_id ∈ the run's users).
  - delete_scope(agent_ids=[the run's two agents]).
- **Evidence:** older runs also deleted their own evidence WHERE run_id = <run>. Since d21f7a08, a run keeps its evidence.
- **Recorded counts:**
  - dev 46f83c20: 12 / 14 / 53 / 37, plus evidence 168 / 1124 / 1.
  - d21f7a08: turns 1905, facts 466, MemoRizz 3967, agent rows 179.
- **7.4 forgetting**, Ada's scope only:
  - DELETE memeval_facts / memeval_turns WHERE memory_id AND user_id AND value/content contains the city.
  - MemoRizz: retire_attributes, and delete_by_id on conversation rows filtered to the same memory_id + user_id + city.

## E. Appbook on 8715, per suite run, exact scope
- **Team.cleanup:**
  - DELETE FROM memapp_turns / memapp_facts WHERE memory_id = memapp-<run>.
  - delete_scope(memory_id ∈ {memapp-<run>, its sealed-thread id}, user_id ∈ the run's users).
  - delete_scope(agent_ids=[its agent]).
- **Run.save_gates:** DELETE FROM memeval_gates WHERE run_id = <its own appbook run id>, before it inserts.
- **Operations forgetting:** as in D, on memapp_* and memapp- scopes.

## F. Files
- `rm -f cmd.json out-* done-*` in my scratch folder `…/jobs/0ca6c044/tmp/mem_eval/dev/` (the dev kernel daemon's files). The daemon also unlinks cmd.json after reading it.
- No other files deleted.
- Process kills (hung kernels, the hung dev task, my uvicorn) are not deletes of data.

## G. After the final run (6a085ba7)
- The run's own 10.5 cleanup, exact scope:
  - memeval_turns 1905
  - memeval_facts 463
  - MemoRizz rows 3967
  - agent rows 179
  - Evidence kept.
- DELETE FROM memeval_results / memeval_grades / memeval_gates / memeval_runs WHERE run_id = 'd21f7a08' (the superseded notebook run): 396 / 1217 / 16 / 1.
- Appbook runs are kept.
