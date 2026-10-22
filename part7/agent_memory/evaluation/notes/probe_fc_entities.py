"""Do the notebook's FactConsolidation messages make MemoRizz (entity memory on) file entities? Three turns, then inspect."""
import sys, uuid
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "appbook"))
from backend.core import agents, datasets
from memorizz import EntityMemory
facts, _ = datasets.fc_sample(5)
messages = [m.replace("Numbered facts (a higher number wins):", "Please remember these facts (a higher number wins):") for m in datasets.fc_messages(facts)[:4]]; print(max(len(x) for x in messages), "chars")
run = uuid.uuid4().hex[:6]
memory_id, user = f"memeval-probe-{run}", f"fc-probe-{run}"
memo = agents.build_memo(f"Memo eval probe {run}", memory_id, True)
m = agents.MemorizzMemo(memo)
scope = {"memory_id": memory_id, "user_id": user, "thread_id": "facts"}
try:
    for i, message in enumerate(messages, 1):
        m.observe(message, scope)
        outcomes = getattr(memo, "last_tool_outcomes", None) or []
        names = [getattr(o, "tool_name", None) or (o.get("tool_name") if isinstance(o, dict) else str(o)[:40]) for o in outcomes]
        print(f"turn {i}: {len(outcomes)} tool calls {names[:6]}", flush=True)
    entities = EntityMemory(agents.provider()).list_entities(memory_id=memory_id, user_id=user)
    print("entities:", len(entities), "attributes:", sum(len(e.get("attributes") or []) for e in entities))
    print("reply to the last message:", (m.answer("Who is the chief executive officer of Microsoft?", {**scope, "thread_id": "q"}).text)[:200])
finally:
    memo.close(close_memory_provider=False)
    p = agents.provider()
    print("cleanup", p.delete_scope(memory_id=memory_id, user_id=user)["total_deleted"], p.delete_scope(agent_ids=[memo.agent_id])["total_deleted"])
