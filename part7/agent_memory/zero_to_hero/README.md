# Agent memory from scratch, then with MemoRizz

Memo is an engineering copilot that helps Ada migrate her team's RAG stack to
Oracle AI Database. Memo is built twice and grows by one memory unit per Part:

- **From scratch:** the unit is an Oracle table you create, with a write path and a
  read path in a few lines of Python and SQL (`python-oracledb`, `VECTOR`,
  `VECTOR_DISTANCE`, `JSON`).
- **With MemoRizz 0.17:** the same unit through MemoRizz's `OracleProvider` and
  `MemAgentBuilder`, on the same database, so your table sits next to the one
  MemoRizz manages.

| Part | Memory unit | From scratch | With MemoRizz |
|---|---|---|---|
| 1 | Stateless baseline | the `ScratchMemo` skeleton: layers with `read` and `write` | |
| 2 | Conversation (episodic) | `SCRATCH_CONVERSATION` | `MemAgent.run(...)` with scope, `MemAgent.load` |
| 3 | Persona | versioned `SCRATCH_PERSONA` rows | `Persona`, `update(change_trigger=...)` |
| 4 | Entity memory | `SCRATCH_ENTITY` with supersession | `with_entity_memory(True)` |
| 5 | Knowledge base | chunks + `VECTOR(256)` search | `KnowledgeBase`, `knowledge_base_lookup` |
| 6 | Toolbox | tool selection by vector search, tool loop | `@governed_tool`, `Toolbox`, progressive disclosure |
| 7 | Tool log | log, offload large results, reuse fresh results | `ToolResultPolicy`, tool cache |
| 8 | Workflow memory | trajectories with a canonical hash | continual learning workflow capture |
| 9 | Skillbox | candidate → reviewed → active skills | `with_skills`, skill retrieval |
| 10 | Working memory | token budget, request-only context | context stats, usage, evidence |
| 11 | Summaries | compaction with source links in one transaction | `generate_summaries()` |
| 12 | Semantic cache | scoped, versioned, expiring cache | `with_semantic_cache()` |
| 13 | Shared memory | a typed blackboard and a reviewer agent | `SharedMemory` |
| 14 | Forgetting | recency/importance/relevance, reversible suppression | retention plans |
| 15 | Memory routing | LLM router vs the Jev decision model over HTTP | `memory_routing_spec`, `JevVerifier`, `place()` |
| 16 | The complete agent | save/restore the definition, one request to both, answer accuracy graded by an LLM judge | `MemAgent.load`, observability |

| Start here | Then |
|---|---|
| [`notebook/agent_memory_zero_to_hero.ipynb`](notebook/agent_memory_zero_to_hero.ipynb): every unit cell by cell, with diagrams and saved outputs | [`appbook/`](appbook/): the same Parts as a web app, scratch and MemoRizz side by side, plus a Tokenomics page that runs a 30-turn memory workload (recall, updates, back-references, tool recall, abstention, a new thread) and charts answer accuracy (LLM judge), latency, cost and tokens for both |

Every memory unit opens with its definition, one stored unit as JSON, when to
use it and what it is not for, in both the notebook and the appbook.

## Run the notebook

```bash
../../oracle.sh start                 # from this folder
jupyter lab notebook/agent_memory_zero_to_hero.ipynb
```

It reads `OPENAI_API_KEY` and `TYPESAFE_API_KEY` from the environment or from
`appbook/.env`, and asks for them otherwise. A run takes about five minutes and
deletes its own rows at the end; set `MEMO_KEEP_DATA=1` to keep them, and
`MEMO_MODEL` to change the agents' model (default `gpt-6.1-sol`, the latest) and
`MEMO_CHEAP_MODEL` the model for background calls (default `gpt-6-luna`, the cheapest).

To re-run it and save the outputs in place, from `part7/`:

```bash
.venv/bin/python tests/run_notebooks.py --env-file agent_memory/zero_to_hero/appbook/.env zero_to_hero
```

## Run the appbook

```bash
cd appbook
cp .env.example .env                  # add the keys
./run.sh                              # http://127.0.0.1:8710
```

See [`appbook/README.md`](appbook/README.md) for its pages and tests.
