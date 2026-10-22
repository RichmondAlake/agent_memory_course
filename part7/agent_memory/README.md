# Agent memory

Two notebook and appbook pairs on Oracle AI Database's `MEMORIZZ` schema and MemoRizz 0.17: one builds agent memory, the other evaluates it.

| Pair | What it teaches | Start with | Then |
|---|---|---|---|
| [`zero_to_hero/`](zero_to_hero/) | Every memory unit built twice: from scratch with SQL tables on Oracle, then with MemoRizz. One agent, Memo, grows by one unit per Part, ending with memory routing by the Jev decision model. | [`notebook/agent_memory_zero_to_hero.ipynb`](zero_to_hero/notebook/agent_memory_zero_to_hero.ipynb) | [`appbook/`](zero_to_hero/appbook/) on port 8710 |
| [`evaluation/`](evaluation/) | How well does each memory work? A naive agent, the scratch Memo and the MemoRizz Memo on LongMemEval and MemoryAgentBench, then memory operations (writes, updates, isolation, forgetting), the semantic cache threshold and memory routing, graded by code, an LLM judge and the Clef and Jev decision models, each validated first. | [`notebook/agent_memory_evaluation.ipynb`](evaluation/notebook/agent_memory_evaluation.ipynb) | [`appbook/`](evaluation/appbook/) on port 8715 |

Both need the shared database (`../oracle.sh start`) and an `OPENAI_API_KEY` (or Ollama for open models). The
zero-to-hero routing Part uses a `TYPESAFE_API_KEY`; the evaluation uses it for Jev when present and an
`ANTHROPIC_API_KEY` for its cross-family judge when present. See [`../README.md`](../README.md) for setup, running and
tests.
