"""The scripted conversation for the live head-to-head benchmark.

Design rationale (this matters educationally):

A *live* benchmark has to finish in a couple of minutes, so it must be SHORT. But a
short prefix of a long script is all "load facts" with no recall probes — which makes
the LLM-as-judge meaningless (it just compares two acknowledgements). So we ship a
compact, **recall-dense** script: ~7 dense declarative turns that load concrete,
checkable facts, then ~5 recall / synthesis probes that force retrieval. Even a
2-minute run then actually exercises memory.

The honest result this produces is the teaching point. Within a single short session
the naive agent holds the entire verbatim transcript, so it is hard to beat on recall —
with capable extraction, OAMP *matches* it (close scores / ties) while sending a
fraction of the tokens, and adds durability across sessions. "Same answer quality, far
fewer tokens, and it persists" is the win — not a manufactured OAMP knockout. The full
80-turn run, where OAMP's quality edge pulls clearly ahead because the naive prompt
balloons and buries facts, lives in the companion notebook.

Set BENCH_USE_NOTEBOOK_SCRIPT=1 to swap in that full 80-turn conversation instead
(long-form; its first recall probe is turn 23, so pair it with a high turn count).
"""
from __future__ import annotations

import ast
import json
import os

from backend.config import APP_DIR

# Compact, recall-dense live script — same ChromAtlas-ND world as the notebook so the
# journey stays coherent, condensed to load checkable facts fast and then probe them.
LIVE_SCRIPT: list[str] = [
    # ---------- load facts (dense, concrete, verifiable) ----------
    "Hi! I'm Dr. Richmond Alake at the Oracle Life Sciences Institute. My project, "
    "ChromAtlas-ND, is a whole-genome variant-annotation pipeline over 3,412 rare-disease "
    "trios, sequenced on two platforms: Oxford Nanopore PromethION for long reads and "
    "Illumina NovaSeq X for short reads.",

    "I work with three collaborators. Dr. Sarah Chen at Baylor College of Medicine leads the "
    "wet-lab chromatin arm. Dr. Javier Morales at the Broad Institute leads model "
    "interpretability. Dr. Aisha Patel at Genomics England leads polygenic-risk-score validation.",

    "We compare three variant-prioritization strategies on a ClinVar holdout: pure Enformer "
    "embeddings at AUROC 0.84, a hybrid XGBoost that fuses Enformer features with Hi-C, PhyloP, "
    "and eQTL priors at AUROC 0.91, and a knowledge-graph approach at AUROC 0.78. I prefer the "
    "hybrid because the SHAP interpretability is something our clinical geneticists trust.",

    "Our production agent is GenomeBot. It runs on Oracle Autonomous Database, handles "
    "variant-lookup tickets from the clinical team, runs VEP and SpliceAI on demand, and posts "
    "prioritized candidates into our Epic EHR. It currently serves about 200 clinicians at "
    "Texas Children's Hospital.",

    "Sarah just added a new modality: CUT&Tag for H3K27ac and H3K4me1 on the same 60 organoid "
    "lines, generated on an Illumina NextSeq 2000 at 30 million reads per sample. It forces us "
    "to switch to a leave-one-donor-out cross-validation scheme to avoid donor leakage.",

    "For the record: compute is 128 NVIDIA A100 GPUs on Oracle Cloud Infrastructure, orchestrated "
    "with Nextflow on Slurm. Funding is a 5-year NIH R01 at $2.4M per year plus $500K per year in "
    "Oracle for Research credits. Our Nature Genetics submission is due July 2026.",

    "One hard constraint to remember: all raw sequencing data for the clinical cohort must stay "
    "inside the HIPAA-audited Oracle Cloud Ashburn enclave. Only derived features and "
    "de-identified predictions may leave that enclave.",

    # ---------- recall probes (force retrieval of the above) ----------
    "Recall check — what is the cohort size for ChromAtlas-ND, and which two sequencing platforms "
    "do we use for the primary variant calls?",

    "Recall check — list my three collaborators, their institutions, and the arm of the project "
    "each one leads.",

    "Recall check — what are the three variant-prioritization strategies and their ClinVar AUROCs, "
    "and which one do I prefer and why?",

    "Recall check — describe GenomeBot: what it does, where it runs, which EHR it integrates with, "
    "and roughly how many clinicians use it.",

    "Final summary — give me a complete briefing covering: the cohort and both sequencing platforms, "
    "the three strategies and their AUROCs, all three collaborators and their roles, GenomeBot, the "
    "CUT&Tag addition (platform, read depth, and the cross-validation change), the compute and "
    "funding, the July 2026 deadline, and the HIPAA data-residency constraint.",
]


def _load_from_notebook() -> list[str] | None:
    """Opt-in (BENCH_USE_NOTEBOOK_SCRIPT=1): extract the notebook's full 80-turn
    ``conversation_turns`` list literal for a long-form run."""
    path = APP_DIR.parent / "notebook" / "oracle_agent_memory_benchmarks.ipynb"
    try:
        nb = json.loads(path.read_text())
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            src = cell["source"]
            src = "".join(src) if isinstance(src, list) else src
            if "conversation_turns = [" not in src:
                continue
            head = src.split("\nDEFAULT_RUN_TURNS")[0]  # drop the RUN_TURNS / print tail
            for node in ast.parse(head).body:
                if isinstance(node, ast.Assign) and any(
                    getattr(t, "id", None) == "conversation_turns" for t in node.targets
                ):
                    turns = ast.literal_eval(node.value)  # a list of strings — safe to eval
                    turns = [t for t in turns if isinstance(t, str) and t.strip()]
                    if turns:
                        return turns
    except Exception:  # noqa: BLE001 — fall back to the live script
        pass
    return None


# Default: the compact recall-dense live script. Opt in to the full 80-turn notebook
# conversation with BENCH_USE_NOTEBOOK_SCRIPT=1 (then raise the turn count to reach its
# recall probes, the first of which is turn 23).
_USE_NOTEBOOK = os.environ.get("BENCH_USE_NOTEBOOK_SCRIPT") == "1"
SCRIPT: list[str] = (_load_from_notebook() if _USE_NOTEBOOK else None) or LIVE_SCRIPT
MAX_TURNS = len(SCRIPT)
