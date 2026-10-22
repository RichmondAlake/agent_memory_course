"""Are a run's MemoRizz traces in SHARED_MEMORY, and does the MemoRizz UI (read-only, port 8765) show them?

    python trace_check.py RUN_ID [AGENT_ID ...]
"""
import json
import sys
import urllib.parse
import urllib.request

import oracledb

run_id, agent_ids = sys.argv[1], sys.argv[2:]
memory_id = f"memeval-{run_id}" if not run_id.startswith(("memeval-", "memapp-")) else run_id
oracledb.defaults.fetch_lobs = False
cur = oracledb.connect(user="MEMORIZZ", password="MemorizzPwd_2026", dsn="localhost:1521/FREEPDB1").cursor()
if not agent_ids:
    cur.execute("SELECT agent_id, name FROM agents WHERE name LIKE :n", n=f"%{run_id[-15:]}%")
    agents = cur.fetchall()
    agent_ids = [a for a, _ in agents]
    print("agents:", agents)
binds = {f"a{i}": a for i, a in enumerate(agent_ids)}
owner_list = ", ".join(f":a{i}" for i in range(len(agent_ids))) or "NULL"
cur.execute(f"""SELECT owner_agent_id, COUNT(*) FROM shared_memory
                WHERE owner_agent_id IN ({owner_list}) AND DBMS_LOB.INSTR(content, 'observability_trace_bundle') > 0
                GROUP BY owner_agent_id""", binds)
by_agent = dict(cur.fetchall())
cur.execute("""SELECT COUNT(*) FROM shared_memory WHERE DBMS_LOB.INSTR(content, 'observability_trace_bundle') > 0
               AND DBMS_LOB.INSTR(content, :m) > 0""", m=f'"memory_id": "{memory_id}"')
by_memory = cur.fetchone()[0]
print(json.dumps({"memory_id": memory_id, "trace bundles by owner agent": by_agent, "trace bundles naming the memory id": by_memory}))

# the UI, read-only: page through trace events (newest first) back to the run's start, and count this run's
cur.execute("SELECT TO_CHAR(SYS_EXTRACT_UTC(started_at), 'YYYY-MM-DD\"T\"HH24:MI:SS') FROM memeval_runs WHERE run_id = :r", r=run_id)
row = cur.fetchone()
since = row[0] if row else "0000"
seen, cursor, pages, per_agent = 0, None, 0, {}
while pages < 400:
    url = "http://localhost:8765/traces/events.json?store=trace&limit=50" + (f"&cursor={cursor}" if cursor else "")
    with urllib.request.urlopen(url.replace(f"&cursor={cursor}", "&cursor=" + urllib.parse.quote(str(cursor))) if cursor else url, timeout=30) as response:
        body = json.load(response)
    pages += 1
    events = body.get("items") or []
    for e in events:
        if e.get("memory_id") == memory_id or e.get("agent_id") in agent_ids:
            seen += 1
            per_agent[e.get("agent_id")] = per_agent.get(e.get("agent_id"), 0) + 1
    cursor = body.get("next_cursor")
    if not cursor or not events or all(str(e.get("timestamp", "")) < since for e in events):
        break
print(json.dumps({"UI pages read": pages, "UI events for this run": seen, "by agent": per_agent, "read back to": since}))
