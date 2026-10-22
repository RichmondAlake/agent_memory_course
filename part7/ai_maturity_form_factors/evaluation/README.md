# Evaluating the AI Maturity Ladder

The maturity module builds one mortgage application, **Acme Home Loans**, as five form factors: a chatbot, RAG, an LLM workflow with the Clef decision model, a tool-using agent and an autonomous agent. This module asks the question that comes before a release: **how well does each rung work, and how do you know?**

Each form factor is evaluated step by step, the way its own failures demand:

| Rung | What can go wrong | What is measured | Graded by |
|---|---|---|---|
| ① chatbot | states numbers that are not Acme's; forgets once the buffer is gone | correct / abstained / **confident error** on 36 golden questions; recall of facts and corrections from earlier turns | decision model, LLM judge |
| ② RAG | wrong section retrieved; claims beyond the passages; a superseded rule | recall@3, MRR, nDCG@5 for keyword, vector, hybrid and graph retrieval, with and without the reranker; **faithfulness** claim by claim; citation coverage and precision; freshness; abstention | code, decision model, LLM judge |
| ③ workflow | one misread figure flows into every later step | each step on **gold inputs** (extraction field accuracy, a unit test for the ratios, decision accuracy and **calibration**, the gate), then end to end with **unsafe errors** and the first wrong step | code, decision model |
| ④ agent | wrong tools, writes it should not make, claims it never acted on, a success that does not repeat | task success judged by the **end state in Oracle**, **pass^k** over repeated runs, forbidden actions, a prompt-injection task, session resume and fork | code, decision model |
| ⑤ autonomous agent | a tool that passes its own checks but not yours; reaching outside the sandbox | **hidden tests** (a new batch, a changed policy, bad inputs), an audit of every tool call, turns and cost, reuse by a new session | code |

## Three graders, validated before use

Every answer is graded by the cheapest grader that can be trusted:

1. **Code**: ranks, values, rows, exit codes.
2. **Decision models**: **Clef-Flash** (open weights, local, Apache-2.0) and **Jev** (hosted, optional `TYPESAFE_API_KEY`) answer atomic yes/no checks, such as *"Does the answer state that the maximum DTI is 43%?"*, with a calibrated probability.
3. **An LLM judge** from a different model family than the application: `gpt-6.1-sol` when `OPENAI_API_KEY` is set, otherwise `claude-sonnet-5-5`.

Part 2 builds about 370 labelled checks **by construction** (a correct reply, then the same reply with a wrong value, an abstention, another fact, a hedge), runs all three graders, and reports accuracy, Cohen's κ, ECE (calibration), latency and cost per check kind. Then it picks, per kind, the cheapest grader within 0.05 κ of the best, and escalates decision-model answers between 0.2 and 0.8 to the judge ("trust or escalate"). The validation is not a formality. In the saved run Clef-Flash is close to chance on the abstention check (κ 0.05) while Jev and the judge are perfect, so Clef never grades abstention; on fact checks Jev matches the judge (κ 0.97) and beats Clef (0.87); on claim support all three reach 0.90, so the free local Clef grades it and its uncertain answers go to the judge. The escalation band stretches to just above a chosen threshold, so a decision model that needs 0.9 to say yes sends its 0.85s to the judge.

## Layout

```
evaluation/
├── notebook/ai_maturity_evaluation.ipynb   the evaluation, Parts 0 to 8, saved with a live run's outputs
├── notebook/img/                            diagrams (PNG, Mermaid source in each cell)
└── appbook/                                 the evaluation studio (port 8705)
```

The notebook is standalone: it rebuilds compact versions of the five form factors (same policy, prompts, models and tools as the maturity notebook) under `FFEVAL_` table names, so it never touches the maturity notebook's or appbook's tables.

## Run the notebook

1. Start the database from `part7/`: `./oracle.sh start`.
2. Keys: `ANTHROPIC_API_KEY` for the application under test, `OPENAI_API_KEY` for the cross-family judge (optional), `TYPESAFE_API_KEY` for Jev (optional). Missing keys are asked for with `getpass`. **No keys at all?** Press Enter at the Anthropic prompt (or set `AIML_PROVIDER=ollama`): the application, its agents and the judge run on Gemma 4 through Ollama. Clef-Flash needs no key on either path (it is an open-weight model; see step 3 for where it runs), and Jev is skipped without `TYPESAFE_API_KEY`.
3. Clef-Flash runs in the notebook's process (MLX on Apple silicon, PyTorch on an NVIDIA GPU), or at `CLEF_URL` if you serve it elsewhere.
4. Run top to bottom (30 to 55 minutes on the API path), or unattended from `part7/`:

```bash
.venv/bin/python tests/run_notebooks.py --env-file path/to/keys.env maturity_eval
```

| Setting | Default | Purpose |
|---|---|---|
| `AIML_MODEL`, `AIML_EFFORT` | `claude-haiku-5-5`, `low` | the application under test |
| `EVAL_JUDGE_MODEL` | `gpt-6.1-sol` or `claude-sonnet-5-5` | the LLM judge |
| `FFEVAL_AGENT_RUNS` | 3 (1 on open models) | attempts per agent task, for pass^k |
| `FFEVAL_DROP_RUN` | unset | `1` deletes this run's evidence rows at the end |

## Evidence in Oracle

Every run writes its evidence to the `VECTOR` schema, labelled by run id:

| Table | One row per |
|---|---|
| `FFEVAL_RUNS` | run: provider, model, judge, graders |
| `FFEVAL_RESULTS` | case × metric, with details as `JSON` |
| `FFEVAL_GRADER_CHECKS` | one grader's answer to one labelled check |
| `FFEVAL_TOOL_EVENTS` | one tool call by an agent, with the guard's decision |
| `FFEVAL_GATES` | one release gate: metric, threshold, value, pass |

## Saved live run

Claude Haiku 5.5 under test, `gpt-6.1-sol` as judge, Clef-Flash and Jev as decision models; 106 code cells, 54 minutes,
1,833 model calls and $0.51 in API cost (most of it the judge in Part 2). Run id `ffeval-20261022-120842-862ff5`.

| Rung | Headline | Also |
|---|---|---|
| ① chatbot (closed book) | 7 of 30 answerable questions correct | 15 confident errors, 8 abstentions; 6 of 6 unanswerable handled; the buffer carried facts and corrections in 5 of 5 conversations |
| ② RAG | 30 of 30 answerable correct, 6 of 6 unanswerable declined | recall@3 1.0, MRR and MAP@5 0.98 (vector → rerank; keyword alone 0.67 recall@3); context precision 0.98, context recall 1.0; faithfulness 96%, groundedness 79%, answer relevance 100% (control 3%), chunk utilisation 0.33 against a relevant share of 0.28; citation coverage 81%; the superseded 41% never appears |
| ③ workflow | 24 of 24 outcomes right end to end, no unsafe errors | every field extracted right; Clef agrees with the policy on 24 of 24 gold inputs (Brier 0.01, ECE 0.09) |
| ④ agent | every attempt passed, pass^3 on all 7 tasks | no forbidden actions; resume and fork behave |
| ⑤ autonomous agent | every hidden test passed | no sandbox events; a new session reused the tool |

Release gates: ③, ④, ⑤ and the graders are READY. The closed-book chatbot is BLOCKED on confident errors, as designed.
RAG is BLOCKED on **citation coverage** (81% against a 90% gate): 27 of 139 claims carry no citation. Groundedness
(79%) shows the gap is almost all missing citations, not wrong ones; faithfulness (96%) passes. The previous run
(`ffeval-20261022-072806-3e8e97`) reached 94% coverage with the same prompt, so this gate sits close to the model's
run-to-run variation.

Graders (test half): on the abstention check Clef-Flash scores κ 0.07 while Jev and the judge score 1.0, so Jev grades
it; on fact checks Jev and the judge reach 0.97 and Clef 0.82, and Clef is chosen within 0.05 dev κ at a 0.85 threshold,
with answers between 0.20 and 0.90 escalated to the judge (15%; cascade κ 0.87); on claim support Clef and Jev reach
0.86 and the judge 0.90, so the free local Clef grades it (4% escalated).

