"""Memo with MemoRizz: the notebook's ``N.3 · With MemoRizz`` sections as a module.

One ``OracleProvider`` (256-dimensional embeddings, lazy HNSW indexes) is
shared by the server. On open models it embeds through the scratch side's
``embed()`` (nomic-embed-text through Ollama): MemoRizz's OpenAI embedding
provider accepts only OpenAI's model names, and its Ollama one returns 768
dimensions. A lab session holds one ``MemorizzMemo``:
it rebuilds the agent from a fresh ``MemAgentBuilder`` with every ``with_...``
call the notebook has made up to the Part being used. The name is fixed per
session, so every rebuild updates the same saved agent (same ``agent_id``).
"""
from __future__ import annotations

import threading
from importlib.metadata import version
from typing import Any

from backend.config import settings
from backend.core import scratch

_lock = threading.Lock()


class Runtime:
    """Lazily-initialised Oracle provider with preflight; fails closed."""

    def __init__(self) -> None:
        self.provider: Any = None
        self.preflight: dict | None = None
        self.ready = False
        self.error: str | None = None

    def initialize(self) -> Any:
        with _lock:
            if self.ready:
                return self.provider
            if not settings.openai_api_key:
                self.error = ("OPENAI_API_KEY is not set. Copy .env.example to .env and add the key, or set "
                              "MEMO_PROVIDER=ollama to run open models on this machine, then restart.")
                return None
            if settings.open:
                try:
                    prepare_open_models()
                except Exception as exc:  # noqa: BLE001 - reported on the status card
                    self.error = (f"Ollama is not ready at {settings.ollama_url} ({type(exc).__name__}: "
                                  f"{str(exc)[:160]}). Install Ollama from ollama.com and start it.")
                    return None
            try:
                import os

                if settings.open:          # any OpenAI client built inside MemoRizz reaches Ollama too
                    os.environ.update(OPENAI_API_KEY="ollama", OPENAI_BASE_URL=settings.openai_base_url)
                os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
                os.environ.setdefault("ORACLE_USER", settings.oracle_user)
                os.environ.setdefault("ORACLE_PASSWORD", settings.oracle_password)
                os.environ.setdefault("ORACLE_DSN", settings.oracle_dsn)
                from memorizz import OracleProvider

                embeddings = ({"embedding_provider": open_embeddings()} if settings.open else
                              {"embedding_provider": "openai",
                               "embedding_config": {"model": settings.embed_model,
                                                    "dimensions": settings.embed_dimensions}})
                provider = OracleProvider.from_env(index_policy="lazy", in_database_embedding=False, **embeddings)
                preflight = provider.preflight()
                if not preflight.get("ok"):
                    raise RuntimeError(f"preflight failed: {preflight.get('diagnostics')}")
                scratch.create_tables()
            except Exception as exc:  # noqa: BLE001 - every startup failure is reported plainly
                self.error = (f"Oracle AI Database is unavailable ({type(exc).__name__}: {str(exc)[:180]}). "
                              "Start it with part7/oracle.sh start; this appbook has no fallback store.")
                return None
            self.provider, self.preflight = provider, preflight
            self.ready, self.error = True, None
            return provider

    def require(self) -> Any:
        provider = self.provider if self.ready else self.initialize()
        if provider is None:
            raise RuntimeError(self.error or "The MemoRizz runtime is not ready.")
        return provider

    def status(self) -> dict:
        preflight = self.preflight or {}
        return {
            "ready": self.ready,
            "backend": "oracle" if self.ready else "unavailable",
            "schema": settings.oracle_user.upper(),
            "dsn": settings.oracle_dsn,
            "error": self.error,
            "memorizz_version": version("memorizz"),
            "database": preflight.get("version_full"),
            "index_policy": preflight.get("index_policy"),
            "embedding": {"model": settings.embed_model, "dimensions": settings.embed_dimensions},
            "provider": settings.provider,
        }

    def close(self) -> None:
        with _lock:
            if self.provider is not None:
                try:
                    self.provider.close()
                except Exception:
                    pass
            self.provider, self.ready = None, False


runtime = Runtime()


def prepare_open_models() -> None:
    """Open models: pull what Ollama is missing, then make the 32k-context variant the agents use.

    Ollama's default context window is 4,096 tokens; a longer request (MemoRizz's carry every tool schema and
    a memory block) would be cut without an error.
    """
    import requests

    def call(path: str, **body: Any) -> dict:
        response = requests.post(f"{settings.ollama_url}{path}", json={**body, "stream": False}, timeout=3600)
        response.raise_for_status()
        return response.json()

    tags = requests.get(f"{settings.ollama_url}/api/tags", timeout=10)
    tags.raise_for_status()
    installed = {model["name"] for model in tags.json().get("models", [])}
    for name in (settings.open_model, settings.embed_model):
        if name not in installed and f"{name}:latest" not in installed:
            call("/api/pull", model=name)
    call("/api/create", model=settings.model, parameters={"num_ctx": settings.open_context},
         **{"from": settings.open_model})


def open_embeddings():
    """MemoRizz's embeddings on open models: the scratch side's embed() (nomic-embed-text at 256 dimensions)."""
    from memorizz.embeddings import BaseEmbeddingProvider, EmbeddingManager

    class Nomic(BaseEmbeddingProvider):
        def get_embedding(self, text: str, **kwargs: Any) -> list[float]:
            return list(scratch.embed([text])[0])

        def get_embeddings(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
            return [list(vector) for vector in scratch.embed(texts)]

        def get_dimensions(self) -> int:
            return settings.embed_dimensions

        def get_default_model(self) -> str:
            return settings.embed_model

    class OpenEmbeddings(EmbeddingManager):
        def _create_provider(self):
            return Nomic(self.config)

    return OpenEmbeddings("ollama", {"model": settings.embed_model})


def memorizz_model():
    from memorizz.llms.openai import OpenAI as MemorizzOpenAI

    model = MemorizzOpenAI(api_key=settings.openai_api_key, model=settings.model, reasoning_effort="none",
                           base_url=settings.openai_base_url)
    if settings.open:   # MemoRizz stops on an empty reply; an open model's empty turn is nudged once
        create = model.client.chat.completions.create

        def create_again_if_empty(**kwargs: Any):
            response = create(**kwargs)
            if not kwargs.get("stream"):
                message = response.choices[0].message
                if not message.tool_calls and not (message.content or "").strip():
                    nudge = {"role": "user", "content": "Answer my last request now, using the results above."}
                    response = create(**{**kwargs, "messages": [*kwargs["messages"], nudge]})
            return response

        model.client.chat.completions.create = create_again_if_empty
    return model


_governed: list | None = None


def governed_tools() -> list:
    """The platform tools with their MemoRizz policy (notebook 6.3)."""
    global _governed
    if _governed is None:
        from memorizz import governed_tool

        _governed = [governed_tool(deterministic=True, side_effects=False, domains=("platform",),
                                   cacheable=True, cache_ttl_seconds=300)(fn) for fn in scratch.PLATFORM_TOOLS]
    return _governed


class MemorizzMemo:
    """MemoRizz Memo for one lab session, rebuilt Part by Part like the notebook."""

    def __init__(self, run_id: str, memory_id: str, user_id: str) -> None:
        self.run_id, self.memory_id, self.user_id = run_id, memory_id, user_id
        self.name = f"Memo {run_id}"
        self.namespace = f"runbook-{run_id}"
        self.agent: Any = None
        self.level = 0
        self.persona: Any = None
        self.knowledge: Any = None
        self.knowledge_ids: list[str] = []
        self.toolbox: Any = None
        self.skill: dict | None = None
        self.retention: dict | None = None
        self.rev: Any = None
        self.shared_ids: list[str] = []
        self.agent_ids: set[str] = set()

    # ── setup the notebook performs in each Part ──
    def setup(self, part: int) -> None:
        from memorizz import KnowledgeBase, Persona, RoleType, Toolbox

        provider = runtime.require()
        if part == 2 and self.agent is None:
            self.agent_at(2)
        elif part == 3 and self.persona is None:
            self.persona = Persona(name="Memo", role=RoleType.TECHNICAL_EXPERT,
                                   goals="Help platform engineers ship reliable, memory-first AI systems.",
                                   background="A staff platform engineer who answers in numbered steps, at most 120 words.")
        elif part == 5 and not self.knowledge_ids:
            self.knowledge = KnowledgeBase(provider)
            self.knowledge_ids.append(self.knowledge.ingest_knowledge(
                scratch.RUNBOOK, namespace=self.namespace, chunking_strategy="paragraph", user_id=self.user_id))
        elif part == 6 and self.toolbox is None:
            agent_id = self.agent_at(max(self.level, 2)).agent_id
            self.toolbox = Toolbox.from_functions(governed_tools(), memory_provider=provider, agent_id=agent_id,
                                                  user_id=self.user_id, augment=False)
        elif part == 9 and self.skill is None:
            self.skill = {"name": f"platform/vector-index-rebuild-{self.run_id}",
                          "description": "Safely rebuild the production retrieval-api vector index.",
                          "content": scratch.REBUILD_PLAYBOOK, "preconditions": ["rollback path tested"],
                          "tools_used": ["index_health", "vector_pool_usage", "golden_set_recall"],
                          "queries": ["rebuild vector index", "reindex retrieval-api"],
                          "user_id": self.user_id, "status": "active"}

    def builder(self, level: int):
        from memorizz import ContextPolicy, MemAgentBuilder, RetrievalPolicy, ToolResultPolicy

        builder = (MemAgentBuilder().with_name(self.name).with_instruction(scratch.INSTRUCTION)
                   .with_model(memorizz_model()).with_memory_provider(runtime.require())
                   .with_memory_ids(self.memory_id).with_automations_enabled(False))
        if level >= 3 and self.persona is not None:
            builder.with_persona(self.persona)
        # MemoRizz's default mode has entity memory on; as in the notebook, it arrives with Part 4.
        builder.with_entity_memory(level >= 4)
        # A rebuild keeps the stored agent's knowledge bases unless told; before Part 5 Memo has none.
        builder.with_knowledge_base(self.knowledge_ids if level >= 5 else [])
        if level >= 6 and self.toolbox is not None:
            builder.with_tools(governed_tools()).with_toolbox(self.toolbox).with_context_policy(
                ContextPolicy(progressive_tool_disclosure=True, tool_top_k=3))
        if level >= 7:
            builder.with_tool_result_policy(ToolResultPolicy(offload_above_chars=scratch.OFFLOAD_CHARS,
                                                             persist_all_results=True))
            builder.with_tool_cache(True, ttl_seconds=scratch.CACHE_SECONDS)
        if level >= 8:
            builder.with_continual_learning(enabled=True)
        if level >= 9 and self.skill is not None:
            builder.with_skills([self.skill]).with_skill_retrieval(enabled=True, top_k=2, min_similarity=0.3)
        if level >= 12:
            builder.with_semantic_cache(enabled=True, threshold=0.92, scope="session")
        if level >= 14 and self.retention:
            builder.with_retrieval_policy(RetrievalPolicy(retention=self.retention))
        return builder

    def agent_at(self, level: int, *, force: bool = False):
        """Memo built with everything the notebook added up to Part ``level``."""
        level = max(2, level)
        if self.agent is not None and self.level == level and not force:
            return self.agent
        if self.agent is not None:
            try:
                self.agent.close(close_memory_provider=False)
            except Exception:
                pass
        self.agent = self.builder(level).build_and_save()
        # MemoRizz stores what each model call was sent (messages after prompt fitting, tool schemas) as a
        # context snapshot; the Context window page reads them back.
        self.agent.capture_context_snapshots = True
        self.level = level
        self.agent_ids.add(self.agent.agent_id)
        return self.agent

    def context_snapshots(self, calls: dict[str, dict]) -> list[tuple[dict, dict]]:
        """Each model call of the last run: its stored context snapshot and the tokens its trace reported."""
        from memorizz.observability.context_snapshots import ContextSnapshots

        snapshots = ContextSnapshots(runtime.require())
        return [(snapshots.get(call["snapshot_id"], agent_id=self.agent.agent_id) or {} if call.get("snapshot_id")
                 else {}, call) for call in calls.values()]

    def memory_stack(self) -> list[str]:
        """What the current agent remembers with: its active memory types, then the features layered on them."""
        agent = self.agent
        if agent is None:
            return []
        stack = [t.value for t in agent.active_memory_types]
        features = [("toolbox", self.level >= 6 and self.toolbox is not None),
                    ("tool_log (offload + tool cache)", self.level >= 7),
                    ("evidence pack (continual learning)", agent.learning_control_plane is not None),
                    ("semantic_cache", self.level >= 12),
                    ("retention policy", self.level >= 14 and bool(self.retention))]
        return stack + [name for name, on in features if on]

    def rev_agent(self):
        from memorizz import MemAgentBuilder

        if self.rev is None:
            self.rev = (MemAgentBuilder().with_name(f"Rev {self.run_id}").with_instruction(scratch.REVIEWER_INSTRUCTION)
                        .with_model(memorizz_model()).with_memory_provider(runtime.require())
                        .with_memory_ids(self.memory_id).with_knowledge_base(self.knowledge_ids)
                        .with_automations_enabled(False).build_and_save())
            self.agent_ids.add(self.rev.agent_id)
        return self.rev

    def close(self) -> None:
        for agent in (self.agent, self.rev):
            if agent is not None:
                try:
                    agent.close(close_memory_provider=False)
                except Exception:
                    pass
        self.agent = self.rev = None

    def cleanup(self) -> dict:
        """Exact-scope deletes, as the notebook's cleanup cell does."""
        from memorizz import KnowledgeBase, MemoryType

        provider = runtime.require()
        self.close()
        knowledge = self.knowledge or KnowledgeBase(provider)
        for kb_id in self.knowledge_ids:
            for chunk in knowledge.retrieve_knowledge(kb_id):
                provider.delete_by_id(str(chunk.get("_id") or chunk.get("id")), MemoryType.KNOWLEDGE_BASE)
        for shared_id in self.shared_ids:
            try:
                provider.delete_by_id(shared_id, MemoryType.SHARED_MEMORY)
            except Exception:
                pass
        persona_id = getattr(self.persona, "persona_id", None)
        if persona_id:                                 # stored without a memory_id, so delete it by id
            try:
                provider.delete_by_id(persona_id, MemoryType.PERSONAS)
            except Exception:
                pass
        content = provider.delete_scope(memory_id=self.memory_id, user_id=self.user_id)
        agents = provider.delete_scope(agent_ids=sorted(self.agent_ids)) if self.agent_ids else {"total_deleted": 0}
        return {"memorizz_rows": content.get("total_deleted", 0), "agent_rows": agents.get("total_deleted", 0)}
