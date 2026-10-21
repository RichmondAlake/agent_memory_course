/* The memory unit behind each Part: its definition, one stored unit as JSON, and when to use it.
   Same text as the notebook's N.1 sections. */
const UNITS = {
  "2": {
    "definition": "An append-only log of the messages in one conversation. Each row is one message with its role, text and time, tied to the application's memory space (`memory_id`), the tenant (`user_id`) and the conversation (`thread_id`).",
    "table": "scratch_conversation",
    "row": "{\n  \"id\": 54,\n  \"memory_id\": \"memo-76dca664\",\n  \"user_id\": \"ada-76dca664\",\n  \"thread_id\": \"migration\",\n  \"role\": \"assistant\",\n  \"content\": \"Your name is Ada, and you're migrating your RAG stack to Oracle AI Database.\",\n  \"summary_id\": null,\n  \"created_at\": \"2026-10-17T21:13:05Z\"\n}",
    "uses": [
      "Follow-up questions in one chat (\"as I said earlier\", \"and the second one?\")",
      "Support tickets, coding sessions and other threads that resume later",
      "An audit trail of exactly what the user and the agent said"
    ],
    "avoid": "Facts that should follow the user into other conversations (entity memory) and reference documents (knowledge base)."
  },
  "3": {
    "definition": "The agent's own identity: name, role, goals and style. It changes rarely and on purpose, so every change is a new version with the reason for it, and earlier versions stay.",
    "table": "scratch_persona",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"agent_name\": \"Memo\",\n  \"version\": 2,\n  \"persona\": {\n    \"name\": \"Memo\",\n    \"role\": \"staff platform engineer\",\n    \"goals\": \"Help platform engineers ship reliable, grounded and cost-aware AI systems.\",\n    \"style\": \"numbered steps, at most 120 words\"\n  },\n  \"change_reason\": \"The platform team adopted cost budgets.\",\n  \"created_at\": \"2026-10-17T21:13:20Z\"\n}",
    "uses": [
      "Branded or role-specific assistants that must keep one voice (support, tutor, reviewer)",
      "Multi-agent systems where each agent plays a distinct role",
      "Tone or policy changes that need an audit trail of who changed what and why"
    ],
    "avoid": "Facts about the user (entity memory) and instructions for a task (skills)."
  },
  "4": {
    "definition": "Lasting facts about a named person, team, service or device, stored one attribute at a time with a confidence and a source. A new value supersedes the old one instead of overwriting it, and the facts follow the user across every thread.",
    "table": "scratch_entity",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"user_id\": \"ada-76dca664\",\n  \"entity\": \"Ada\",\n  \"attribute\": \"owns_service\",\n  \"value\": \"retrieval-api\",\n  \"confidence\": 1.0,\n  \"source\": \"user, thread migration\",\n  \"created_at\": \"2026-10-17T21:13:30Z\",\n  \"superseded_at\": null\n}",
    "uses": [
      "User preferences and profiles in personal assistants (format, language, time zone)",
      "Customer and account facts in support or CRM copilots",
      "Ownership, on-call and status facts about services, products and devices"
    ],
    "avoid": "Long documents (knowledge base) and one-off details that only matter in this turn (working memory)."
  },
  "5": {
    "definition": "Source documents split into chunks, each stored with an embedding and its provenance (source, position). A question is embedded the same way, and the closest chunks are given to the model with citations.",
    "table": "scratch_knowledge",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"namespace\": \"runbook\",\n  \"source\": \"platform-runbook\",\n  \"chunk_index\": 1,\n  \"content\": \"Change control. Every Oracle maintenance change needs a change ticket with the ORAMNT prefix, approved by the on-call lead.\",\n  \"embedding\": \"VECTOR(256, FLOAT32): [0.0132, -0.0871, ...]\",\n  \"importance\": 0.5,\n  \"access_count\": 0,\n  \"last_accessed_at\": null,\n  \"suppressed\": false\n}",
    "uses": [
      "Policies, runbooks, manuals and product documentation (retrieval-augmented generation)",
      "Private or recent information the model was never trained on",
      "Answers that must cite their sources"
    ],
    "avoid": "A single fact that changes (entity memory) and what was said in a conversation (conversation memory)."
  },
  "6": {
    "definition": "A catalogue of capabilities: each tool's name, description, strict JSON schema and an embedding for selection. The executable function stays in trusted application code; the row only describes it.",
    "table": "scratch_toolbox",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"name\": \"index_health\",\n  \"description\": \"Return the health of one Oracle vector index with its full diagnostic report.\",\n  \"parameters\": {\n    \"type\": \"object\",\n    \"additionalProperties\": false,\n    \"required\": [\"index_name\"],\n    \"properties\": {\"index_name\": {\"type\": \"string\"}}\n  },\n  \"embedding\": \"VECTOR(256, FLOAT32): [...]\"\n}",
    "uses": [
      "Agents that need live data or actions: APIs, databases, ticketing systems",
      "Large tool catalogues (dozens of tools, MCP servers) where sending every schema wastes tokens",
      "Choosing the right tool for a request by meaning rather than by hard-coded routing"
    ],
    "avoid": "Storing executable code or credentials as data; a row should never be able to grant new powers."
  },
  "7": {
    "definition": "One row per tool call: the tool, its arguments, what it returned, the status and how long it took. Large results are kept here once and the model gets a short digest and a pointer instead.",
    "table": "scratch_tool_log",
    "row": "{\n  \"thread_id\": \"migration\",\n  \"tool_name\": \"index_health\",\n  \"arguments\": {\"index_name\": \"docs_hnsw\"},\n  \"args_hash\": \"4f1c9a...\",\n  \"result\": \"{\\\"index\\\": \\\"docs_hnsw\\\", \\\"status\\\": \\\"ready\\\", \\\"checks_passed\\\": 30, \\\"diagnostics\\\": [...]}\",\n  \"status\": \"ok\",\n  \"chars\": 974,\n  \"offloaded\": true,\n  \"duration_ms\": 0.1\n}",
    "uses": [
      "Auditing and debugging: what did the agent actually see before it answered?",
      "Large outputs (logs, query results, web pages) that would flood the context window",
      "Reusing a fresh result of an expensive read-only call"
    ],
    "avoid": "Reusing results of tools with side effects or non-deterministic results."
  },
  "8": {
    "definition": "The trajectory of one request: the tool calls in order, with their arguments and the outcome, stored with an embedding of the request. A canonical hash groups runs that took the same path.",
    "table": "scratch_workflow",
    "row": "{\n  \"user_id\": \"ada-76dca664\",\n  \"query\": \"Check docs_hnsw health and tell me who owns retrieval-api.\",\n  \"query_embedding\": \"VECTOR(256, FLOAT32): [...]\",\n  \"steps\": [\n    {\"tool\": \"index_health\", \"arguments\": {\"index_name\": \"docs_hnsw\"}},\n    {\"tool\": \"service_owner\", \"arguments\": {\"service\": \"retrieval-api\"}}\n  ],\n  \"canonical_hash\": \"00c8eaaa7e302f7b\",\n  \"outcome\": \"success\"\n}",
    "uses": [
      "Recurring operational tasks: health checks, triage, reports",
      "Helping the model plan (\"last time a similar request ran these steps\")",
      "Spotting repeated procedures that are worth turning into skills"
    ],
    "avoid": "Replaying old steps blindly: a workflow is evidence of what happened, not an instruction."
  },
  "9": {
    "definition": "Reusable instructions for a kind of request (a playbook), with a lifecycle status: candidate, active or retired. Learned skills start as candidates; only reviewed, active skills reach the prompt.",
    "table": "scratch_skill",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"name\": \"platform/vector-index-rebuild\",\n  \"description\": \"Safely rebuild the production retrieval-api vector index.\",\n  \"content\": \"1. Confirm it is the Tuesday 02:00-04:00 UTC window. 2. Open an ORAMNT change ticket ...\",\n  \"status\": \"active\",\n  \"source\": \"authored by the platform team\",\n  \"uses\": 3,\n  \"embedding\": \"VECTOR(256, FLOAT32): [...]\"\n}",
    "uses": [
      "Standard operating procedures, playbooks and team conventions",
      "Agents that should get better at tasks they repeat",
      "Any instruction that must be reviewed before it can steer the model"
    ],
    "avoid": "One-off facts (entity or knowledge) and raw run history (workflows)."
  },
  "10": {
    "definition": "The request being assembled right now: instructions, retrieved blocks, recent history and request-only context, all within a token budget. It is never stored; it is rebuilt for every call.",
    "table": "(not stored: the request itself)",
    "row": "{\n  \"instructions\": [\"You are Memo, ...\", \"## Persona v2 ...\", \"## Known facts (entity memory) ...\"],\n  \"history\": [{\"role\": \"user\", \"content\": \"...\"}, {\"role\": \"assistant\", \"content\": \"...\"}],\n  \"request_context\": {\"open_page\": \"incident INC-4821: retrieval-api p95 latency above 800 ms\"},\n  \"query\": \"Which incident am I looking at?\",\n  \"budget_tokens\": 500,\n  \"dropped_messages\": 8\n}",
    "uses": [
      "Long conversations close to the model's context limit",
      "UI state that matters for one turn only: the open page, a selection, the current document",
      "Keeping cost and latency flat, or fitting a small-context model"
    ],
    "avoid": "Anything that must be remembered next time: store it in a durable unit instead."
  },
  "11": {
    "definition": "A condensed digest of older messages that replaces them in the prompt while keeping the ID of every source message, so it can always be expanded back to what was actually said.",
    "table": "scratch_summary",
    "row": "{\n  \"id\": 1,\n  \"thread_id\": \"migration\",\n  \"content\": \"Ada is migrating a RAG stack to Oracle AI Database. She owns retrieval-api ...\",\n  \"source_ids\": [53, 54, 55, 56, 59, 60],\n  \"message_count\": 24,\n  \"created_at\": \"2026-10-17T21:15:10Z\"\n}",
    "uses": [
      "Long-running threads: support cases, coding sessions, projects that last days",
      "Keeping prompt size and cost flat as history grows",
      "Hand-offs and recaps (\"what did we decide?\")"
    ],
    "avoid": "Deleting history: a summary changes what the model sees, not what you keep."
  },
  "12": {
    "definition": "Stored answers keyed by the meaning of the question, scoped to a tenant and thread, a domain and a data version, with an expiry. A close enough match answers the request without calling the model.",
    "table": "scratch_cache",
    "row": "{\n  \"thread_id\": \"migration\",\n  \"query\": \"What ticket prefix do Oracle maintenance changes need?\",\n  \"embedding\": \"VECTOR(256, FLOAT32): [...]\",\n  \"answer\": \"Oracle maintenance changes need a change ticket with the ORAMNT prefix ...\",\n  \"domain\": \"runbook\",\n  \"data_version\": \"2026-10-17\",\n  \"hits\": 1,\n  \"created_at\": \"2026-10-17T21:15:30Z\",\n  \"expires_at\": \"2026-10-18T21:15:30Z\"\n}",
    "uses": [
      "FAQ and policy questions that people ask in many different words",
      "High-traffic help desks where the same answer is requested again and again",
      "Read-only answers over data that changes slowly and has a version"
    ],
    "avoid": "Personal or live data, and any turn with side effects or failed tool calls."
  },
  "13": {
    "definition": "A blackboard scoped to one job and one tenant, where agents post typed messages (command, status, report) that name their author and, optionally, their recipient.",
    "table": "scratch_blackboard",
    "row": "{\n  \"session_id\": \"rebuild-review-76dca664\",\n  \"user_id\": \"ada-76dca664\",\n  \"agent\": \"rev\",\n  \"kind\": \"REPORT\",\n  \"target\": \"memo\",\n  \"payload\": {\"findings\": \"Step 3 should state at least 20 percent free space ...\", \"command_id\": 21},\n  \"created_at\": \"2026-10-17T21:15:50Z\"\n}",
    "uses": [
      "Lead and reviewer, or planner and executor, pairs of agents",
      "Research or analysis teams of agents that split one job",
      "Human-in-the-loop review queues and hand-offs between shifts"
    ],
    "avoid": "A global scratchpad every agent can read: scope each session to one job and tenant."
  },
  "14": {
    "definition": "A lifecycle policy rather than a store: rank memories by recency since last use, importance and relevance; suppress low-retention records through a reviewed, reversible plan; delete only through an exact-scope, approved step.",
    "table": "bookkeeping columns on scratch_knowledge",
    "row": "{\n  \"id\": 15,\n  \"content\": \"Support plans. Premium support includes unlimited vector storage ...\",\n  \"importance\": 0.5,\n  \"access_count\": 0,\n  \"last_accessed_at\": null,\n  \"suppressed\": false,\n  \"scores\": {\"recency\": 0.99, \"relevance\": 0.42, \"usage\": 0.0, \"retention\": 0.50}\n}",
    "uses": [
      "Long-lived assistants whose stores keep growing",
      "Stale or superseded documents that crowd out better evidence",
      "Privacy and retention requests that require removing data"
    ],
    "avoid": "Forgetting audit evidence, verified outcomes or records other memories cite as their source."
  },
  "15": {
    "definition": "The decision of which store a new piece of state belongs in, or whether to keep it at all, made by a router and logged with its probabilities.",
    "table": "scratch_routing",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"item\": \"Grace prefers to be paged on Slack rather than by phone.\",\n  \"store\": \"entity\",\n  \"probability\": 0.98,\n  \"probabilities\": {\"entity\": 0.98, \"knowledge\": 0.01, \"do_not_store\": 0.01, \"persona\": 0.0},\n  \"filed_to\": \"entity\"\n}",
    "uses": [
      "Agents that ingest mixed streams: chat, email, notes, tool output",
      "\"Remember this\" features and plugins that capture sessions automatically",
      "Keeping filler and sensitive content out of memory (`do_not_store`)"
    ],
    "avoid": "Routing with free-text answers when you need thresholds: use a decision model's probabilities."
  },
  "16": {
    "definition": "The agent itself: its instruction, which memory layers it uses and their settings. Saved as data, it restores the same agent in another process; the trusted tool bindings stay in code.",
    "table": "scratch_agent",
    "row": "{\n  \"memory_id\": \"memo-76dca664\",\n  \"name\": \"Memo\",\n  \"definition\": {\n    \"instruction\": \"You are Memo, a concise engineering copilot ...\",\n    \"respond\": \"tool_loop\",\n    \"execute\": \"logged_tool_call\",\n    \"layers\": [\n      {\"type\": \"CacheLayer\", \"args\": {\"max_distance\": 0.12, \"ttl_hours\": 24}},\n      {\"type\": \"ConversationLayer\", \"args\": {\"last_n\": 20}},\n      {\"type\": \"KnowledgeLayer\", \"args\": {\"namespace\": \"runbook\", \"k\": 4, \"max_distance\": 0.65}}\n    ]\n  }\n}",
    "uses": [
      "Running the same agent in many processes or services",
      "Versioning and reviewing agent configuration like any other data",
      "Letting a UI, CLI or scheduler load an agent by ID after a restart"
    ],
    "avoid": "Storing credentials or executable code in the definition."
  }
};
