"""The shared corpus: a small, synthetic set of agent-memory research notes.

Both substrates store these identical notes; the app then writes/searches/benchmarks
over them. The text is original and synthetic (no external dataset) and deliberately
written so that some questions use *different words* than the notes — that gap is what
separates literal keyword search (filesystem) from semantic vector search (database).

Each note: doc_id, title, category, content.
"""
from __future__ import annotations

DOCS: list[dict] = [
    {
        "doc_id": "note-context-paging",
        "title": "Context Window Paging",
        "category": "context",
        "content": (
            "An agent has a finite prompt budget. When a conversation grows past that budget, "
            "the agent must decide what to keep in front of the model and what to move aside. "
            "A paging strategy keeps a small working set of recent, relevant material resident and "
            "swaps the rest to external storage, fetching it back on demand. This is the same idea as "
            "virtual memory in an operating system: the illusion of unlimited space built on top of a "
            "small fast tier and a large slow tier."
        ),
    },
    {
        "doc_id": "note-episodic-memory",
        "title": "Episodic Memory and Transcripts",
        "category": "memory-architecture",
        "content": (
            "Episodic memory is the agent's diary: an append-only record of what happened during a "
            "session — the turns exchanged, the tools invoked, the decisions taken. It is keyed by a "
            "session or thread identifier so separate runs never bleed into one another. Episodic "
            "records are rarely re-read in full; instead they are summarised, and the summary becomes "
            "the durable artifact that carries continuity into the next session."
        ),
    },
    {
        "doc_id": "note-semantic-memory",
        "title": "Semantic Memory and the Knowledge Base",
        "category": "memory-architecture",
        "content": (
            "Semantic memory holds durable facts and reference material the agent can draw on regardless "
            "of which conversation surfaced them: ingested documents, extracted facts, domain knowledge. "
            "Unlike a transcript, semantic memory is organised for lookup by meaning rather than by time. "
            "It is the long-term store that lets an agent answer a question it was never explicitly told, "
            "by recalling related material it absorbed earlier."
        ),
    },
    {
        "doc_id": "note-vector-retrieval",
        "title": "Retrieval by Meaning",
        "category": "retrieval",
        "content": (
            "Embedding a passage turns its meaning into a point in a high-dimensional space, so two texts "
            "that say the same thing in different words land close together. A query is embedded the same "
            "way, and the nearest stored points are returned. Because the match is on meaning and not on "
            "shared letters, a question phrased with synonyms still finds the right passage — something "
            "exact string matching cannot do."
        ),
    },
    {
        "doc_id": "note-keyword-grep",
        "title": "Literal Search Over Files",
        "category": "retrieval",
        "content": (
            "The simplest way to find something on disk is to scan every file for a pattern, the way grep "
            "does. It is transparent, needs no index, and is perfect when you know the exact term. Its "
            "weakness is brittleness: a document that discusses the same concept with different vocabulary "
            "is invisible to it, and a search for a common word drowns in matches. Literal search rewards "
            "precise wording and punishes paraphrase."
        ),
    },
    {
        "doc_id": "note-hybrid-rrf",
        "title": "Fusing Two Rankings",
        "category": "retrieval",
        "content": (
            "Keyword ranking and vector ranking each see things the other misses, so production systems "
            "often blend them. Reciprocal rank fusion is a simple, robust recipe: take each result's "
            "position in each list, add the reciprocals, and sort by the combined score. The fused list "
            "keeps documents that either method ranked highly and is far less sensitive to the quirks of a "
            "single scorer."
        ),
    },
    {
        "doc_id": "note-acid-writes",
        "title": "All-or-Nothing Writes",
        "category": "reliability",
        "content": (
            "When many workers update the same memory at once, naive file edits collide: two readers load "
            "the same version, both append, and the second save erases the first. A transactional store "
            "avoids this by treating each change as an indivisible unit that either lands completely or not "
            "at all, isolating concurrent changes so they do not overwrite each other. The guarantee is "
            "built in rather than something every caller must remember to implement."
        ),
    },
    {
        "doc_id": "note-locking",
        "title": "Coordinating Concurrent Writers",
        "category": "reliability",
        "content": (
            "A plain file can be made safe under concurrency, but only with explicit discipline. An "
            "exclusive lock forces writers to take turns, and opening in append mode avoids the read-then-"
            "overwrite trap. The cost is contention and code you must get right everywhere a write happens; "
            "the benefit is that you keep human-readable files while still avoiding lost updates."
        ),
    },
    {
        "doc_id": "note-summarisation",
        "title": "Compacting History",
        "category": "context",
        "content": (
            "Rather than truncating old turns and losing information, an agent can compress them: an LLM "
            "rewrites a long exchange into a short brief that preserves decisions, constraints, and open "
            "questions. The compact brief replaces the raw history in the working set, freeing budget while "
            "keeping the thread coherent. Triggering this at a utilisation threshold keeps the agent from "
            "ever slamming into its limit."
        ),
    },
    {
        "doc_id": "note-progressive-disclosure",
        "title": "Reading Only What You Need",
        "category": "retrieval",
        "content": (
            "Loading an entire document to answer one question wastes budget. Progressive disclosure reads "
            "in widening steps: peek at the tail, locate the relevant region by pattern, pull just those "
            "lines, and open the whole file only as a last resort. The habit keeps the working set small and "
            "the agent fast, especially over large local corpora."
        ),
    },
    {
        "doc_id": "note-thread-isolation",
        "title": "Keeping Sessions Apart",
        "category": "storage",
        "content": (
            "Multi-user and multi-session agents must never let one conversation read another's history. "
            "Tagging every stored record with a thread identifier and filtering on it at read time gives "
            "each session its own private view of memory over shared infrastructure. Structured stores make "
            "this filtering cheap and indexable; ad-hoc file layouts make it error-prone."
        ),
    },
    {
        "doc_id": "note-ingestion-chunking",
        "title": "Ingesting Long Documents",
        "category": "storage",
        "content": (
            "A long source document is split into overlapping passages before storage, because embedding "
            "models have an input limit and smaller passages retrieve more precisely. Each chunk carries "
            "metadata — its source, title, and position — so a retrieved fragment can be traced back to the "
            "document it came from. Writing the chunks directly to the store avoids ever routing the full "
            "text through the model's context."
        ),
    },
]

# Suggested queries for the retrieval lesson, ordered strongest-contrast first.
# The leading two are cases where literal keyword search MIS-RANKS (it latches onto a
# shared word like "long") while semantic search picks the note that actually matches
# the meaning — the clearest demonstration of the substrate gap.
SUGGESTED_QUERIES = [
    "Shrinking a long conversation without losing the important parts",   # keyword → "Ingesting Long Documents"; semantic → "Compacting History"
    "Why does searching for an exact keyword sometimes miss the answer?",  # keyword → "Fusing Two Rankings"; semantic → "Retrieval by Meaning"
    "How does an agent cope when it runs out of room in the prompt?",
    "Keeping one user's chat private from other sessions",
    "Blending two different result rankings into a single list",
]

BY_ID = {d["doc_id"]: d for d in DOCS}
CATEGORIES = sorted({d["category"] for d in DOCS})
