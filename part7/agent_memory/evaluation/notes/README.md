# Notes from building the agent memory evaluation

Kept for the record; the notebook and the appbook do not import anything here.

| File | What it is |
|---|---|
| `memorizz_findings.md` | The two MemoRizz 0.17.4 bugs this evaluation found: entity writes over about 8 KB failed with `ORA-03146`, then the pool hung. Their repros and stack dumps, the fix in 0.17.8 and its verification, and what is still open. |
| `probe_entity_size.py` | Repro of bug 1: grows one entity until a write fails (19 of 19 writes succeed on 0.17.8). |
| `probe_deadlock.py` | Repro of bug 2: 23 turns of 20 FactConsolidation facts through `memo.run()` with entity memory on. Dumps every thread's stack every 4 minutes. |
| `probe_fc_hang.py` | The first, smaller hang repro, kept for its stack dump. |
| `deadlock_stacks_run1.txt`, `fc_hang_stacks.txt` | The stacks of the hang on 0.17.4: the agent waiting in `pool.acquire()`. |
| `probe_deadlock_0178.log`, `deadlock_stacks_0178.txt` | The same repro on 0.17.8: all 23 turns finish, and no thread waits on Oracle. |
| `probe_fc_entities.py` | Whether the notebook's fact messages make MemoRizz write entity memory. They do when a message asks it to remember. |
| `trace_check.py` | Counts a run's MemoRizz trace bundles in `SHARED_MEMORY`, and the events the MemoRizz UI (port 8765, read-only) shows for them. |
| `delete_inventory.md` | Every delete run while building the evaluation, with its scope, for review. |

The probes read `OPENAI_API_KEY` from the environment, and connect to `MEMORIZZ` on `localhost:1521/FREEPDB1`. Each one
deletes only the scope it created.
