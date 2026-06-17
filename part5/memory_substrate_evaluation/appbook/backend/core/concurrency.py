"""The ACID / concurrency benchmark — the notebook's Part 4, made live.

Three writers race to record entries concurrently:

  1. Filesystem, no lock  — naive read-modify-write; updates clobber each other.
  2. Filesystem, flock    — exclusive lock + append; safe, but you must implement it.
  3. Database (ACID)      — atomic, isolated commits; safe by default.

The database leg uses Oracle when it is reachable (same engine as the notebook),
otherwise SQLite — a real ACID database that is always available — so the lesson
("a transactional store doesn't lose writes; a naive file does") always lands.
The active engine is reported back to the UI.
"""
from __future__ import annotations

import fcntl
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.core.db_substrate import db_substrate

WORK = settings.workspace_dir / "concurrency"
CONC_TABLE = "SUBSTRATE_CONC_TEST"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")


def _result(approach: str, engine: str, expected: int, actual: int, elapsed_ms: float, note: str) -> dict:
    lost = expected - actual
    return {
        "approach": approach,
        "engine": engine,
        "safe": lost <= 0,
        "expected": expected,
        "actual": actual,
        "lost": lost,
        "loss_rate": round(lost / expected * 100, 1) if expected else 0.0,
        "elapsed_ms": round(elapsed_ms, 1),
        "note": note,
    }


# ── 1) filesystem, no locking (the anti-pattern) ──────────────────────────────
def run_naive_fs(writers: int, per_writer: int) -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "naive.log"
    path.write_text("")
    expected = writers * per_writer

    def writer(wid: int) -> None:
        for i in range(per_writer):
            entry = f"[W{wid}] entry {i + 1} @ {_ts()}\n"
            try:
                existing = path.read_text() if path.exists() else ""   # read …
                path.write_text(existing + entry)                       # … modify … write (race!)
            except Exception:
                pass

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=writers) as ex:
        for f in as_completed([ex.submit(writer, w) for w in range(writers)]):
            f.result()
    elapsed = (time.perf_counter() - t0) * 1000
    actual = path.read_text().count("[W")
    return _result("Filesystem (no lock)", "ext4/apfs file", expected, actual, elapsed,
                   "Read-modify-write with no coordination: concurrent saves overwrite each other.")


# ── 2) filesystem, with flock (safe, but manual) ──────────────────────────────
def run_locked_fs(writers: int, per_writer: int) -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / "locked.log"
    path.write_text("")
    expected = writers * per_writer

    def writer(wid: int) -> None:
        for i in range(per_writer):
            entry = f"[W{wid}] entry {i + 1} @ {_ts()}\n"
            with open(path, "a") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)   # take turns
                fh.write(entry)
                fh.flush()
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=writers) as ex:
        for f in as_completed([ex.submit(writer, w) for w in range(writers)]):
            f.result()
    elapsed = (time.perf_counter() - t0) * 1000
    actual = path.read_text().count("[W")
    return _result("Filesystem (flock)", "ext4/apfs + flock", expected, actual, elapsed,
                   "Exclusive lock + append: safe, but every writer must opt in correctly.")


# ── 3) database, ACID (Oracle when up, else SQLite) ───────────────────────────
def run_database(writers: int, per_writer: int) -> dict:
    db_substrate.initialize()
    expected = writers * per_writer
    use_oracle = db_substrate.backend == "oracle"
    if use_oracle:
        return _run_oracle(writers, per_writer, expected)
    return _run_sqlite(writers, per_writer, expected)


def _run_oracle(writers: int, per_writer: int, expected: int) -> dict:
    import oracledb

    def connect():
        return oracledb.connect(user=settings.oracle_user, password=settings.oracle_password,
                                dsn=settings.oracle_dsn, tcp_connect_timeout=8)

    admin = connect()
    with admin.cursor() as cur:
        for stmt in (
            f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {CONC_TABLE} PURGE'; "
            f"EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;",
            f"CREATE TABLE {CONC_TABLE} (id VARCHAR2(32) DEFAULT RAWTOHEX(SYS_GUID()) PRIMARY KEY, "
            f"writer_id NUMBER, entry_num NUMBER, content VARCHAR2(200))",
        ):
            cur.execute(stmt)
    admin.commit()

    def writer(wid: int) -> None:
        conn = connect()  # each thread its OWN connection (python-oracledb is not thread-shareable)
        try:
            for i in range(per_writer):
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {CONC_TABLE} (writer_id, entry_num, content) VALUES (:1, :2, :3)",
                        (wid, i + 1, f"[W{wid}] entry {i + 1}"),
                    )
                conn.commit()
        finally:
            conn.close()

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=writers) as ex:
        for f in as_completed([ex.submit(writer, w) for w in range(writers)]):
            f.result()
    elapsed = (time.perf_counter() - t0) * 1000

    with admin.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {CONC_TABLE}")
        actual = int(cur.fetchone()[0])
    admin.close()
    return _result("Database (ACID)", "Oracle AI Database", expected, actual, elapsed,
                   "Atomic, isolated INSERTs with per-thread connections — safety is built in.")


def _run_sqlite(writers: int, per_writer: int, expected: int) -> dict:
    WORK.mkdir(parents=True, exist_ok=True)
    db_path = WORK / "acid.sqlite"
    if db_path.exists():
        db_path.unlink()
    init = sqlite3.connect(db_path)
    init.execute("PRAGMA journal_mode=WAL")
    init.execute("CREATE TABLE conc (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_id INT, entry_num INT, content TEXT)")
    init.commit()
    init.close()

    def writer(wid: int) -> None:
        conn = sqlite3.connect(db_path, timeout=30)  # busy-wait instead of failing
        try:
            for i in range(per_writer):
                conn.execute("INSERT INTO conc (writer_id, entry_num, content) VALUES (?, ?, ?)",
                             (wid, i + 1, f"[W{wid}] entry {i + 1}"))
                conn.commit()
        finally:
            conn.close()

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=writers) as ex:
        for f in as_completed([ex.submit(writer, w) for w in range(writers)]):
            f.result()
    elapsed = (time.perf_counter() - t0) * 1000

    check = sqlite3.connect(db_path)
    actual = check.execute("SELECT COUNT(*) FROM conc").fetchone()[0]
    check.close()
    return _result("Database (ACID)", "SQLite (Oracle offline)", expected, actual, elapsed,
                   "Oracle is offline, so this uses SQLite — also ACID, also zero loss. Same lesson.")
