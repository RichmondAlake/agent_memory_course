# Memo, from Scratch to MemoRizz — App

The interactive companion to
[`../notebook/agent_memory_zero_to_hero.ipynb`](../notebook/agent_memory_zero_to_hero.ipynb).
Start with the notebook: it builds every memory unit twice, first as Oracle
tables and SQL you write yourself, then with MemoRizz. This app puts the two
builds side by side so you can poke at them.

Every page is one Part of the notebook. You send **one message to both
agents**, each built up to that Part: Memo from scratch (the notebook's layers,
your `SCRATCH_*` tables) and Memo with MemoRizz 0.17.4 (the same
`MemAgentBuilder` calls). Both run on gpt-5.5 and the `MEMORIZZ` schema of
Oracle AI Database. Each page shows both answers with time, tokens and tool
calls, your table (with its DDL) next to MemoRizz's table (with its columns),
this session's rows, and the Part's own actions. The right-hand **Model
context** rail shows the token breakdown of the scratch request and MemoRizz's
usage and memory evidence, with a link to the full context window of the turn.

| Part | Page | Unit | Actions on the page |
|---|---|---|---|
| 1 | Stateless baseline | no memory | two raw model calls; the right column is a raw call |
| 2 | Conversation | `CONVERSATION_MEMORY` | thread selector; restore both agents in fresh objects |
| 3 | Persona | `PERSONAS` | evolve the persona with a reason (both sides) |
| 4 | Entities | `ENTITY_MEMORY` | thread selector; a correction supersedes a fact |
| 5 | Knowledge | `KNOWLEDGE_BASE` | search: `VECTOR_DISTANCE` vs `retrieve_by_query` |
| 6 | Toolbox | `TOOLBOX` | tool-selection preview vs the MemoRizz router |
| 7 | Tool log | `TOOL_LOG` | offloaded and reused calls; tool-cache stats |
| 8 | Workflows | `WORKFLOW_MEMORY` | runs grouped by canonical hash |
| 9 | Skills | `SKILLBOX` | propose skills from workflows; approve candidates |
| 10 | Working memory | `SHORT_TERM_MEMORY` | token budget slider; request-only context |
| 11 | Summaries | `SUMMARIES` | compact with source links (both sides) |
| 12 | Semantic cache | `SEMANTIC_CACHE` | domain and data version; invalidate |
| 13 | Shared memory | `SHARED_MEMORY` | draft → Rev reviews → revise (both sides) |
| 14 | Forgetting | retention | scores; plan and suppress; restore |
| 15 | Routing (Jev) | memory routing | chat model vs Jev on eight items; route and file one item |
| 16 | Complete Memo | `MEMAGENT` | save and restore; one request to both; operational evidence |
| — | Tokenomics | all of them | answer accuracy (LLM judge), latency, cost and token charts for every measured turn; a 30-turn memory workload |
| — | Context window | all of them | every model call of every measured turn, both agents, section by section, with the prompt-cached prefix |

Each Part page from 2 to 16 opens with **the memory unit**: its definition, one
stored unit as JSON (a row of your table), when to use it and what it is not
for. The text is the same as the notebook's N.1 sections (`frontend/units.js`).

### Tokenomics

**Tokenomics** (`#/tokenomics`) charts every turn either agent has answered in
this session: each message sent to both agents on a Part page, the Part 16
comparison, and the 30-turn **memory workload** the page can run at the full
stack (Part 16, or Part 14 without a Jev key). Both agents are measured the
same way:

| Chart | What each turn shows |
|---|---|
| Answer accuracy | running % correct per agent over the graded turns, by an LLM judge; below it, accuracy by memory test |
| Latency per turn | stacked by phase: model calls, memory work outside model calls (SQL, embeddings, the Jev router), tool executions, and the rest |
| Inference cost per turn | every model call of the turn at OpenAI list prices, from MemoRizz's rate card (`DEFAULT_PRICING`), for both agents |
| Token consumption per turn | input tokens not cached, input served from OpenAI's prompt cache, and output tokens, over every model call of the turn |

**The memory workload** runs in a fresh memory scope of its own (a separate
lab session with the same setup), so what was sent on the Part pages cannot
leak into it, and its rows are deleted when it ends. Ada tells Memo facts,
changes some of them, and asks questions that refer back. Each of the 25
graded turns tests one way memory can fail:

| Test | What it asks |
|---|---|
| grounding | facts from the persona, runbook, tools or rebuild skill |
| recall | a fact Ada told Memo earlier in the conversation |
| update | a fact that changed later: only the new value is correct |
| back-reference | an earlier question or answer ("in that plan…", "the first thing I asked") |
| tool recall | a result from an earlier tool call |
| cache | a paraphrase of an earlier cacheable question |
| abstention | something never said, or a false premise: inventing an answer is wrong |
| preference | a standing instruction Ada gave earlier (end every answer with a TL;DR) |
| cross-thread | asked in a new thread, so only long-term memory carries it over |

After turn 20 both agents compact the main thread into a summary, keeping its
four newest messages, so the later probes also test summaries. The page lists
every turn with its reference, and the memory each agent ran with.

**Accuracy** is graded by a separate LLM judge (`MEMO_JUDGE_MODEL`, default
`gpt-5.5` at low reasoning effort) against each turn's reference: a typed
verdict, the missing facts and a reason. On a Part page, the golden questions
(references built only from the setup, so chat history cannot change them)
are graded the same way, with the verdict under each answer. The judge's
tokens and cost are reported on their own and never added to an agent's cost.

The scratch agent is metered by hooks in its model call, tool loop and layers;
MemoRizz reports the same phases through its trace events. Concurrent and
nested reads are counted once (wall-clock intervals, model first, then tools,
then memory), so every bar adds up to the turn's real duration. The charts
follow the hedge-fund analyst appbook in the Oracle AI Developer Hub: inline
SVG, one shared tooltip, a legend on every card, a click to enlarge with a
table of the plotted values, a session summary and a turn-by-turn table.
Embedding tokens are excluded on both sides, and list prices are not an invoice.

### Context window

**Context window** (`#/context`) shows what each agent sent to the model on
every call of every measured turn: the Part-page messages and every turn of
the memory workload. Pick a turn (or follow the link under an answer, in the
Model context rail or in the Tokenomics turn table) and each agent's calls
are listed: the steps of its tool loop, and calls a scratch memory layer
makes itself (entity extraction). Each call is split into sections in the
order the model reads them: instructions, tool schemas, then the messages
(history, memory blocks, the user's message, tool calls and results).

- **Scratch** records the request its `chat()` sent: the instruction, one
  block per memory layer, the selected tools and the input.
- **MemoRizz** stores a context snapshot of every model call
  (`capture_context_snapshots`, in `SHARED_MEMORY`): the messages after prompt
  fitting and the tool schemas. Its per-turn `<memorizz:context>` block is
  split at MemoRizz's own headers: evidence-pack items, entity facts,
  summaries, recent tool outputs, request context.

Each call keeps OpenAI's input, prompt-cached and output counts; the bar
scales the sections to the input count and hatches the prefix OpenAI served
from its prompt cache, so you can see which sections were billed in full.
Section token counts are tiktoken estimates. Writing a snapshot takes about
15 ms inside MemoRizz's model span (well under 1% of a call).

Pages build on each other as the notebook does: the first time a page needs
an earlier Part's setup (persona v1, the runbook, the tools, the authored
skill), it runs it once. One **lab session** holds everything, scoped to
`memo-app-<run>` / `ada-app-<run>`. **Reset session** on the overview deletes
the session's rows with exact-scope deletes (your tables and MemoRizz's); the
server does the same on shutdown unless `MEMO_CLEANUP_ON_RESET=0`.

The **Data Explorer** at the bottom of every page lists your `SCRATCH_*`
tables next to MemoRizz's tables, limited to this session or across the
schema, with live read/write activity. It is read-only, allowlisted, and
accepts no SQL.

## Run

```bash
../../../oracle.sh start          # from this folder: the shared Oracle container on 1521
cp .env.example .env              # add OPENAI_API_KEY (and TYPESAFE_API_KEY for Part 15)
./run.sh                          # → http://127.0.0.1:8710
```

`run.sh` uses `$PYTHON` if set, otherwise `part7/.venv/bin/python` when it
exists, otherwise `python3`, and installs `requirements.txt` when MemoRizz
is older than 0.17.4, or FastAPI, the SSE package, `oracledb`, `tiktoken` or
`requests` is missing. `HOST` and `PORT` override the address.

## Requirements and failure behaviour

- **`OPENAI_API_KEY`** — required: gpt-5.5 (Responses API, reasoning effort
  `none`) and `text-embedding-3-small` at 256 dimensions, as in the notebook.
- **Oracle AI Database** — required: the `MEMORIZZ` schema from
  `part7/oracle.sh`. There is no fallback store; without it `/api/health`
  and every page report a clear error.
- **`TYPESAFE_API_KEY`** — optional: Jev, the decision model of Part 15.
  Without it the routing page says so and the scratch agent skips its routing
  layer.

Keys are read from the environment or the ignored `.env`; they are never sent
to the browser.

## Tests

From this folder, with the part7 environment:

```bash
../../../.venv/bin/python -m pytest tests/test_contracts.py -q   # offline: routes, schemas, allowlist, every scratch
                                                                 # SQL statement scoped, context-window splitting
../../../.venv/bin/python tests/check_live.py                    # against a running server: every Part's effect, the
                                                                 # context windows, Tokenomics and the memory workload
../../../.venv/bin/python tests/check_browser.py                 # Playwright: every page and unit card, main actions,
                                                                 # Tokenomics charts, the Context window page, phone width
```

The live and browser checks reset the lab session first and use real models,
Oracle and Jev (a full live run, with the 30-turn workload, makes about 300 model calls and takes about 10 minutes). Run them
one at a time: they share the server's single session. Screenshots land in
`tests/artifacts/` (ignored by git).

## Architecture

```
appbook/
├── backend/
│   ├── main.py               FastAPI app; warms the Oracle runtime; activity middleware; serves the SPA
│   ├── config.py             keys, model, Oracle settings (env / .env)
│   ├── schemas.py            bounded request bodies
│   ├── core/
│   │   ├── scratch.py        the notebook's scratch code: SCRATCH_* DDL, layers, tool loop, routing…
│   │   ├── memorizz_memo.py  OracleProvider runtime + Memo rebuilt Part by Part with MemAgentBuilder
│   │   ├── session.py        the lab session: setup per Part, chat to both agents, every Part action
│   │   ├── tokenomics.py     metering, prices, the memory workload; judge.py grades answers
│   │   ├── context_view.py   each model call's request split into sections, for the Context window page
│   │   ├── rows.py           allowlist, session row filter, JSON-safe values
│   │   ├── activity.py       read/write activity feed for the Data Explorer
│   │   └── sse.py            Server-Sent Events helper
│   └── routers/              meta (health, session) · parts (pages, chat, actions) · data_explorer · tokenomics · context
├── frontend/                 index.html · styles.css · app.js · units.js · tokenomics.js · context.js (no build step)
└── tests/                    test_contracts.py · check_live.py · check_browser.py
```

`scratch.py` keeps the notebook's tables, SQL and layer classes; the only
change is that functions take the session scope instead of reading notebook
globals. Two MemoRizz details the app handles the way the notebook does: each
rebuild names its knowledge bases with `with_knowledge_base(...)` (none before
Part 5), since a rebuild otherwise keeps the stored agent's; and a restored
agent gets its trusted tool bindings from code with `MemAgent.load(agent_id,
tools=[...])`, because the stored definition holds tool schemas, never code.
