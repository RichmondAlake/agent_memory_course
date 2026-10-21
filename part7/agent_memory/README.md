# Agent memory

One notebook and appbook pair on Oracle AI Database's `MEMORIZZ` schema and MemoRizz 0.17.

| Pair | What it teaches | Start with | Then |
|---|---|---|---|
| [`zero_to_hero/`](zero_to_hero/) | Every memory unit built twice: from scratch with SQL tables on Oracle, then with MemoRizz. One agent, Memo, grows by one unit per Part, ending with memory routing by the Jev decision model. | [`notebook/agent_memory_zero_to_hero.ipynb`](zero_to_hero/notebook/agent_memory_zero_to_hero.ipynb) | [`appbook/`](zero_to_hero/appbook/) on port 8710 |

It needs the shared database (`../oracle.sh start`) and an `OPENAI_API_KEY`; the routing Part also needs a
`TYPESAFE_API_KEY`. See [`../README.md`](../README.md) for setup, running and tests.
