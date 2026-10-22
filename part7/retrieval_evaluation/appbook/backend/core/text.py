"""Lexical query building, as in the notebook (§3.1 and §4.2): Oracle Text's own stoplist, content words, document
frequencies, and a safe `CONTAINS` query.

Document frequencies come from the corpus itself, read once per dataset and tokenised the notebook's way, so a
"rarest 10 terms" query picks the same words as in the stored run. Only the counts are kept in memory.
"""
from __future__ import annotations

import re
import threading
import time
from collections import Counter

from backend.config import DATASETS
from backend.core import db

TOKEN = re.compile(r"[a-z0-9]+")
RESERVED = {"about", "accum", "and", "bt", "btg", "bti", "btp", "equiv", "fuzzy", "haspath", "inpath", "mdata",
            "minus", "near", "not", "nt", "ntg", "nti", "ntp", "or", "pt", "rt", "sqe", "syn", "tr", "trsyn", "tt",
            "uf", "within"}
MAX_QUERY_CHARS = 3800
_STOPWORDS: set[str] | None = None
_DF: dict[str, Counter] = {}
DF_SECONDS: dict[str, float] = {}
_lock = threading.Lock()


def stopwords() -> set[str]:
    global _STOPWORDS
    if _STOPWORDS is None:
        _STOPWORDS = {r["spw_word"].lower() for r in db.sql(
            "SELECT spw_word FROM ctx_stopwords WHERE spw_owner = 'CTXSYS' AND spw_stoplist = 'DEFAULT_STOPLIST'")}
    return _STOPWORDS


def content_words(text: str, stop: set[str] | None = None) -> list[str]:
    """Lower-cased words of 2+ characters not on Oracle Text's default stoplist, in order, without repeats."""
    stop = stopwords() if stop is None else stop
    return list(dict.fromkeys(t for t in TOKEN.findall(text.lower()) if len(t) > 1 and t not in stop))


def document_frequency(ds: str) -> Counter:
    """Each content word's document frequency in a dataset's corpus (built once, then cached)."""
    if ds not in DATASETS:
        raise KeyError(ds)
    with _lock:
        if ds not in _DF:
            started = time.perf_counter()
            stop = stopwords()
            df: Counter = Counter()
            with db.connection() as conn, conn.cursor() as cur:
                cur.arraysize = 2000
                cur.execute(f"SELECT body FROM beir7_{ds}_docs")
                for (body,) in cur:
                    df.update(set(content_words(body or "", stop)))
            _DF[ds] = df
            DF_SECONDS[ds] = round(time.perf_counter() - started, 1)
    return _DF[ds]


def text_query(ds: str, text: str, op: str = "ACCUM", stem: bool = False, keep: int | None = None) -> str:
    words = content_words(text)
    if keep:
        df = document_frequency(ds)
        words = sorted(words, key=lambda w: (df.get(w, 0), w))[:keep]
    parts = [f"${w}" if stem and w.isalpha() and w not in RESERVED else "{" + w + "}" for w in words]
    query = ""
    for part in parts:
        candidate = f"{query} {op} {part}" if query else part
        if len(candidate) > MAX_QUERY_CHARS:
            break
        query = candidate
    return query


def template(query: str) -> str:
    """Wrap a CONTAINS query in a template that asks Oracle Text for float scores."""
    return f'<query><textquery>{query or "{zzzzzz}"}</textquery><score datatype="FLOAT"/></query>'
