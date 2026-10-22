"""Minimal repro: grow one MemoRizz entity's attributes until the write fails."""
import os, uuid, traceback
from memorizz import OracleProvider, EntityMemory
os.environ.setdefault("ORACLE_USER", "MEMORIZZ"); os.environ.setdefault("ORACLE_PASSWORD", "MemorizzPwd_2026"); os.environ.setdefault("ORACLE_DSN", "localhost:1521/FREEPDB1")
provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, embedding_provider="openai",
                                   embedding_config={"model": "text-embedding-3-small", "dimensions": 256})
store = EntityMemory(provider)
MID, UID = f"size-{uuid.uuid4().hex[:6]}", "size-user"
chunk = "\n".join(f"{n}. The capital of Country{n} is City{n} and it is a long sentence to pad the value." for n in range(20))
entity_id = None
for i in range(1, 20):
    try:
        entity_id = store.record_attribute(entity_id=entity_id, entity_name="Ordered fact list", attribute_name=f"facts_{i}",
                                           attribute_value=chunk, memory_id=MID, user_id=UID)
        e = store.get_entity(entity_id, memory_id=MID, user_id=UID)
        print(i, "ok", len(e["attributes"]), "attributes,", sum(len(str(a["value"])) for a in e["attributes"]), "chars")
    except Exception as exc:
        print(i, "FAILED:", type(exc).__name__, str(exc)[:200]); traceback.print_exc(limit=6); break
print(provider.delete_scope(memory_id=MID, user_id=UID)["total_deleted"])
