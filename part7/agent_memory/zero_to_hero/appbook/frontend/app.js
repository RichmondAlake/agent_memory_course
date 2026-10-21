/* ======================================================================
   Memo, from Scratch to MemoRizz — single-page app
   Vanilla JS. Hash router, theme toggle, SSE-over-fetch streaming client.
   One page per notebook Part: the same message goes to Memo built from
   scratch (your SCRATCH_* tables) and to Memo built with MemoRizz 0.17.4,
   both on Oracle AI Database.
   ====================================================================== */

// ── icons ──────────────────────────────────────────────────────────────
const I = {
  stack: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5M3 16.5l9 5 9-5"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 16-8-6 16-3-7-7-1Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5" fill="currentColor"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  window: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 9v11"/><path d="M5.5 6.5h.01M8 6.5h.01"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 6-6 6 6 6"/></svg>',
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>',
};

// ── the notebook's Parts (one page each) ─────────────────────────────
const GROUPS = {
  episodic: { name: "Episodic", accent: "var(--r1)" },
  semantic: { name: "Semantic", accent: "var(--r2)" },
  procedural: { name: "Procedural", accent: "var(--r4)" },
  working: { name: "Working", accent: "var(--r3)" },
  social: { name: "Social", accent: "var(--r5)" },
  lifecycle: { name: "Lifecycle", accent: "var(--r6)" },
  complete: { name: "Complete", accent: "var(--r6)" },
};
const ROUTING_ITEMS = [
  "Grace prefers to be paged on Slack rather than by phone.",
  "Policy: vector indexes for embedding-worker may only be rebuilt on Thursdays.",
  "thanks, that's all for now!",
  "From now on, Memo, always answer with numbered steps and keep it under 120 words.",
  "Reviewer agent: please double-check the rollback plan before 03:00 and post your findings.",
  "Intermediate result: 14 of 30 golden queries checked so far, continuing.",
  "To rotate an ORAMNT approver: open the ticket, reassign the approver, notify #platform-oncall, log the change.",
  "We agreed in this thread to postpone the cutover until the recall check passes.",
];
const PARTS = [
  { n: 1, group: "episodic", unit: "No memory", nav: "Stateless baseline",
    title: "A model call has no past",
    idea: "The model only sees what is in the request. Two calls with no shared messages are two strangers, even a second apart. Memo starts here with no layers; the right column is a raw model call (MemoRizz enters in Part 2).",
    watch: "The second question cannot be answered: neither request carries the first.",
    suggest: ["I'm Ada. I'm migrating our RAG stack to Oracle AI Database.", "What am I working on, and what's my name?"] },
  { n: 2, group: "episodic", unit: "CONVERSATION_MEMORY", nav: "Conversation",
    title: "What happened in this conversation?",
    idea: "One row per message, scoped by memory, tenant and thread. Before each call Memo reads the latest messages of the thread; after it, Memo writes both turns. MemoRizz's <code>run()</code> does the same, and also recalls earlier messages of the memory space by meaning.",
    watch: "After the first message both agents name Ada and her project. In the on-call thread the scratch agent does not know (thread isolation); MemoRizz may recall it by meaning across threads.",
    threads: ["migration", "on-call"],
    suggest: ["I'm Ada. I'm migrating our RAG stack to Oracle AI Database.", "What am I working on, and what's my name?", "What am I working on?"] },
  { n: 3, group: "semantic", unit: "PERSONAS", nav: "Persona",
    title: "Who is the agent?",
    idea: "A persona is name, role, goals and style. A change writes a new version with a reason; the old version stays for audit. MemoRizz's <code>Persona.update()</code> records a change trigger for each version.",
    watch: "Answers follow the persona's style. Evolving it adds a version on both sides, with your reason.",
    suggest: ["Who are you, and how do you answer?"] },
  { n: 4, group: "semantic", unit: "ENTITY_MEMORY", nav: "Entities",
    title: "Lasting facts about people and services",
    idea: "Facts such as <code>Ada.owns_service = retrieval-api</code>, each with a confidence and a source. A new value supersedes the old one instead of overwriting it. Entity memory is scoped to the user, so it crosses threads on purpose.",
    watch: "After the first message the facts appear in both tables. In the on-call thread both agents know which service Ada owns. A correction supersedes the SQL preference.",
    threads: ["migration", "on-call"],
    suggest: ["For the record: I own the retrieval-api service, and I prefer answers with SQL examples.", "Which service do I own?", "Correction: from now on I'd rather have Python examples than SQL."] },
  { n: 5, group: "semantic", unit: "KNOWLEDGE_BASE", nav: "Knowledge",
    title: "Documents, vectors and cited answers",
    idea: "The runbook is split into paragraph chunks, each with a 256-d <code>VECTOR</code>. The scratch layer searches with <code>VECTOR_DISTANCE</code> before every call. MemoRizz recalls the closest chunks of the knowledge bases attached to Memo before the call too, and also gives the model a <code>knowledge_base_lookup</code> tool for further searches.",
    watch: "Both answers give the Tuesday 02:00–04:00 UTC window and the ORAMNT ticket. The search shows which chunks are closest.",
    suggest: ["When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?"] },
  { n: 6, group: "procedural", unit: "TOOLBOX", nav: "Toolbox",
    title: "What Memo can do",
    idea: "A tool is a description, a strict schema and a trusted Python binding. Memo retrieves only the tools that fit the request (progressive disclosure); the binding never lives in the database.",
    watch: "Both agents call index_health; the preview shows the few tools each would disclose. While all its schemas fit in stable_tool_list_tokens (6,000 by default), MemoRizz still sends the whole list each turn so the prompt-cache prefix stays the same; selection takes over for larger catalogues.",
    suggest: ["Check the health of the docs_hnsw index.", "Check docs_hnsw and the vector pool."] },
  { n: 7, group: "procedural", unit: "TOOL_LOG", nav: "Tool log",
    title: "What tools returned",
    idea: "Every call is logged. A large result is stored once and the model gets a digest plus a pointer; a fresh identical read-only call is served from the log. MemoRizz does this with <code>ToolResultPolicy</code> and its tool cache.",
    watch: "The first check is logged as offloaded; the repeat within five minutes is reused (scratch) and a tool-cache hit (MemoRizz).",
    suggest: ["Check docs_hnsw health and tell me how many checks passed.", "Run the docs_hnsw health check once more."] },
  { n: 8, group: "procedural", unit: "WORKFLOW_MEMORY", nav: "Workflows",
    title: "What actually ran",
    idea: "A workflow is the trajectory of one request: the tool calls and the outcome, with a canonical hash that groups runs that took the same path. MemoRizz records them once continual learning is on.",
    watch: "Both requests take the same path, so they share a canonical hash; the second request's context carries the first run's steps.",
    suggest: ["Check docs_hnsw health and tell me who owns retrieval-api.", "Check docs_ivf health and tell me who owns embedding-worker."] },
  { n: 9, group: "procedural", unit: "SKILLBOX", nav: "Skills",
    title: "Reviewed, reusable instructions",
    idea: "A skill is a playbook for a kind of request. Learned skills start as candidates; only a reviewed, active skill reaches the prompt. The platform team's rebuild playbook is authored, so it starts active.",
    watch: "Propose turns the repeated workflow into a candidate; Approve makes it active. The rebuild plan follows the playbook on both sides.",
    suggest: ["Plan the retrieval-api index rebuild for me."] },
  { n: 10, group: "working", unit: "SHORT_TERM_MEMORY", nav: "Working memory",
    title: "What is in the window right now",
    idea: "Every layer competes for the context window. The scratch working-memory layer runs last, adds request-only context and drops the oldest history to fit a budget. MemoRizz accepts the same <code>context=</code> and reports the window it used.",
    watch: "A small budget drops old messages. The open page is known in this thread and unknown in a fresh one: request context is never stored.",
    threads: ["incident-review", "incident-review-2", "migration"], budget: true, page: true,
    suggest: ["Which incident am I looking at?", "Summarise where my migration stands in three bullets."] },
  { n: 11, group: "working", unit: "SUMMARIES", nav: "Summaries",
    title: "Compaction that keeps its sources",
    idea: "A summary replaces older messages in the prompt but keeps their IDs; the summary and the source marks are written in one transaction, so it can always be expanded back.",
    watch: "Compact writes a summary on both sides; the scratch context then shows one summary block plus the newest messages.",
    suggest: ["What have we covered so far?"] },
  { n: 12, group: "working", unit: "SEMANTIC_CACHE", nav: "Semantic cache",
    title: "Reuse an answer without the model",
    idea: "A stored answer is served when a question means the same, in the same tenant and thread, for the same domain and data version, before it expires. Only answers from safe turns are admitted.",
    watch: "The paraphrase is a hit on both sides; a new data version is a miss; Invalidate removes the domain's entries.",
    cache: true,
    suggest: ["What ticket prefix do Oracle maintenance changes need?", "Which ticket prefix is required for Oracle maintenance changes?"] },
  { n: 13, group: "social", unit: "SHARED_MEMORY", nav: "Shared memory",
    title: "Agents working on one job",
    idea: "A blackboard scoped to one job and one tenant, with typed commands, statuses and reports that name their author. Rev, a reviewer with only the runbook, checks Memo's plan.",
    watch: "Rev flags the Tuesday-only window for a Wednesday plan; Memo's revision follows the report.",
    suggest: ["Revise the plan using the reviewer's findings."] },
  { n: 14, group: "lifecycle", unit: "Forgetting", nav: "Forgetting",
    title: "Rank, suppress, restore",
    idea: "Retrieval ranks by recency since last use, importance and relevance. A reviewed plan suppresses records whose retention stayed low; suppression is reversible and deletion is a separate, exact-scope step.",
    watch: "Chunks Memo never retrieved are the candidates; after suppression search skips them, and Restore brings them back.",
    suggest: [] },
  { n: 15, group: "lifecycle", unit: "Memory routing", nav: "Routing (Jev)",
    title: "Who decides where a memory goes?",
    idea: "A decision model answers a typed question (which store?) with a probability per option. Jev routes all eight items in one short request; the chat model needs one call each. MemoRizz's <code>memory_routing_spec()</code> and <code>place()</code> apply the same rules.",
    watch: "Both routers agree with the expected stores on most items; Jev is far faster. A style instruction sent in chat becomes a new persona version.",
    suggest: ["Going forward, Memo, put the go or no-go decision in the first line of every plan."] },
  { n: 16, group: "complete", unit: "MEMAGENT", nav: "Complete Memo",
    title: "Save, restore and run the whole agent",
    idea: "The agent definition is memory too. Both agents are saved, restored in fresh objects (tool code is never stored, so the trusted bindings are passed in by code), and given one real request in a new thread.",
    watch: "Both restored agents check the index and the pool, use the playbook and the runbook, and answer go or no-go.",
    suggest: [] },
];
const PART_BY_N = Object.fromEntries(PARTS.map((p) => [String(p.n), p]));
const accentOf = (p) => GROUPS[p.group].accent;

// ── tiny utils ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function renderRich(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+?)`/g, "<code>$1</code>");
  return h.split(/\n{2,}/).map((p) => "<p>" + p.replace(/\n/g, "<br>") + "</p>").join("");
}

// SSE-over-fetch: POST, then parse the text/event-stream body.
async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}), signal });
  if (!res.ok || !res.body) {
    let detail = ""; try { const data = await res.json(); detail = JSON.stringify(data.detail || data); } catch (_) {}
    throw new Error(`HTTP ${res.status} ${detail}`.trim());
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const SEP = /\r?\n\r?\n/;
    let m;
    while ((m = SEP.exec(buf))) {
      const block = buf.slice(0, m.index);
      buf = buf.slice(m.index + m[0].length);
      let event = "message", data = "";
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith(":")) continue;
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).replace(/^\s/, "");
      }
      if (event === "end") return;
      if (data) { try { onEvent(JSON.parse(data)); } catch (_) {} }
    }
  }
}
async function getJSON(url) {
  const r = await fetch(url);
  let data = {}; try { data = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`);
  return data;
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  let data = {}; try { data = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`);
  return data;
}

// ── app state ──────────────────────────────────────────────────────────
const state = { health: null, session: null, abort: null, route: "", busy: false, page: null };
const explorerState = {
  tables: [], selected: null, result: null, offset: 0, limit: 40, scope: "run",
  events: [], active: new Map(), recent: new Map(), source: null,
  refreshTimer: null, preferredTable: "scratch_conversation",
};
const SIDEBAR_STORAGE_KEY = "zth-sidebar";
const CTXRAIL_STORAGE_KEY = "zth-ctxrail";
function cancelStream() { if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; } }
async function refreshSession() { try { state.session = await getJSON("/api/session"); } catch (_) {} }

// ── sidebar ──────────────────────────────────────────────────────────
function renderSidebar(activeId) {
  let lastGroup = "";
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" aria-label="Overview" title="Overview" style="--c:var(--text-2)">
       <span class="nav-node">${I.home}</span><span class="nav-label">Overview</span></a>`,
  ];
  const visited = new Set((state.session?.visited || []).map(String));
  PARTS.forEach((p, i) => {
    if (p.group !== lastGroup) { lastGroup = p.group; items.push(`<div class="nav-part">${esc(GROUPS[p.group].name)}</div>`); }
    const mark = visited.has(String(p.n)) ? '<i class="nav-done ok" title="Used in this session"></i>' : "";
    items.push(`
      <a class="nav-item ${activeId === String(p.n) ? "active" : ""}" href="#/${p.n}" aria-label="${esc(`Part ${p.n} ${p.nav}`)}" title="${esc(`Part ${p.n} · ${p.nav}`)}" style="--c:${accentOf(p)};animation-delay:${(i + 1) * 30}ms">
        <span class="nav-node nav-number">${p.n}</span><span class="nav-label">${esc(p.nav)}</span>${mark}
      </a>`);
  });
  items.push(`<div class="nav-part">Measure</div>`,
    `<a class="nav-item ${activeId === "tokenomics" ? "active" : ""}" href="#/tokenomics" aria-label="Tokenomics" title="Tokenomics: latency, cost and tokens" style="--c:var(--r6)">
       <span class="nav-node">${I.chart}</span><span class="nav-label">Tokenomics</span></a>`,
    `<a class="nav-item ${activeId === "context" ? "active" : ""}" href="#/context" aria-label="Context window" title="Context window: what each agent sent to the model" style="--c:var(--r1)">
       <span class="nav-node">${I.window}</span><span class="nav-label">Context window</span></a>`);
  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.stack}</span>
      <span class="brand-text"><b>Memo</b><span>from scratch, then with MemoRizz</span></span>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button" aria-controls="sidebar-nav"></button>
    </div>
    <nav class="ladder-rail" id="sidebar-nav" aria-label="Notebook parts">${items.join("")}</nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Toggle color theme" title="Toggle color theme">
        <span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span id="theme-label">${themeLabel()}</span></span>
        <span class="toggle-track"></span>
      </button>
    </div>`;
  syncSidebarToggle();
  $("#sidebar-toggle").addEventListener("click", toggleSidebar);
  $("#theme-toggle").addEventListener("click", toggleTheme);
  requestAnimationFrame(() => setTimeout(() => document.documentElement.setAttribute("data-nav-ready", "1"), 900));
}
function sidebarCollapsed() { return document.documentElement.getAttribute("data-sidebar") === "collapsed"; }
function syncSidebarToggle() {
  const toggle = $("#sidebar-toggle");
  if (!toggle) return;
  const collapsed = sidebarCollapsed();
  const label = collapsed ? "Expand side navigation" : "Collapse side navigation";
  toggle.innerHTML = collapsed ? I.expand : I.collapse;
  toggle.setAttribute("aria-label", label);
  toggle.setAttribute("title", label);
  toggle.setAttribute("aria-expanded", String(!collapsed));
}
function toggleSidebar() {
  const next = sidebarCollapsed() ? "expanded" : "collapsed";
  document.documentElement.setAttribute("data-sidebar", next);
  try { localStorage.setItem(SIDEBAR_STORAGE_KEY, next); } catch (_) {}
  syncSidebarToggle();
}
// The Model context rail collapses to a strip on the right, like the navigation on the left.
function ctxRailCollapsed() { return document.documentElement.getAttribute("data-ctxrail") === "collapsed"; }
function syncCtxRailToggle() {
  const toggle = $("#ctxrail-toggle");
  if (!toggle) return;
  const collapsed = ctxRailCollapsed();
  const label = collapsed ? "Expand the model context panel" : "Collapse the model context panel";
  toggle.innerHTML = collapsed ? I.collapse : I.expand;      // the rail opens leftwards, so the arrows mirror the sidebar's
  toggle.setAttribute("aria-label", label);
  toggle.setAttribute("title", label);
  toggle.setAttribute("aria-expanded", String(!collapsed));
}
function toggleCtxRail() {
  const next = ctxRailCollapsed() ? "expanded" : "collapsed";
  document.documentElement.setAttribute("data-ctxrail", next);
  try { localStorage.setItem(CTXRAIL_STORAGE_KEY, next); } catch (_) {}
  syncCtxRailToggle();
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const mem = h.memory || {};
  const mdot = mem.ready ? "ok" : mem.error ? "off" : "warn pulse";
  const label = mem.ready ? `Oracle · ${esc(mem.schema)}` : mem.error ? "unavailable" : "warming…";
  return `
    <div class="status-row"><span class="k">Model</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Memory</span><span class="dot ${mdot}"></span><span>${label}</span></div>
    <div class="status-row"><span class="k">MemoRizz</span><span class="mono">${esc(mem.memorizz_version || "")}</span></div>
    <div class="status-row"><span class="k">OpenAI key</span><span class="dot ${h.api_key_set ? "ok" : "off"}"></span><span>${h.api_key_set ? "set" : "missing"}</span></div>
    <div class="status-row"><span class="k">Jev key</span><span class="dot ${h.jev_key_set ? "ok" : "warn"}"></span><span>${h.jev_key_set ? "set" : "missing"}</span></div>`;
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("zth-theme", next); } catch (_) {}
  const label = $("#theme-label"); if (label) label.textContent = themeLabel();
  const toggle = $("#theme-toggle"); if (toggle) toggle.querySelector("svg").outerHTML = themeIcon();
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "var(--r6)");
  stage.innerHTML = `<div class="view view-enter">${html}</div>`;
  stage.scrollTop = 0;
}
function healthBanner(extra) {
  const h = state.health;
  const reason = extra || (!h ? "" : !h.api_key_set ? "OPENAI_API_KEY is not set. Copy .env.example to .env, add the key and restart." : h.memory?.error || "");
  return reason ? `<div class="banner warn" id="health-banner">${I.alert}<span>${esc(reason)}</span></div>` : "";
}
function warn(host, message) {
  if (host) host.insertAdjacentHTML("afterbegin", `<div class="banner warn">${I.alert}<span>${esc(message)}</span></div>`);
}

// ── view: overview ───────────────────────────────────────────────────
function viewHome() {
  const s = state.session || {};
  const scope = s.scope || {};
  const rungs = PARTS.map((p, i) => `
    <a class="rung" href="#/${p.n}" style="--c:${accentOf(p)};animation-delay:${i * 35 + 60}ms">
      <div class="rung-num">${p.n}</div>
      <div class="rung-main"><h3><code>${esc(p.unit)}</code></h3><p>${esc(p.title)}</p></div>
      <div class="rung-meta"><div class="meta-line"><span class="mk">Group</span><span class="mv">${esc(GROUPS[p.group].name)}</span></div>
        <div class="meta-line"><span class="mk">Status</span><span class="mv">${(s.visited || []).includes(p.n) ? '<span class="tag ok">used</span>' : '<span class="tag">not yet</span>'}</span></div></div>
      <div class="rung-go">${I.arrow}</div>
    </a>`).join("");
  setStage(`
    <section class="hero">
      <div class="hero-kicker"><span class="pip"></span> MemoRizz 0.17.4 · Oracle AI Database · GPT-5.5 · Jev</div>
      <h1>Every memory unit, built twice — <em>from scratch, then with MemoRizz</em>.</h1>
      <p>Memo is an engineering copilot helping Ada migrate her team's RAG stack to Oracle AI Database. Each page is one Part of the notebook: the same message goes to Memo built from your own <code>SCRATCH_*</code> tables and to Memo built with MemoRizz, both on the same Oracle schema, so you can compare the answers, the context and the rows.</p>
    </section>
    ${healthBanner()}
    <section class="home-explorer lab-card" aria-labelledby="lab-title">
      <div class="home-explorer-mark">${I.stack}</div>
      <div class="home-explorer-copy">
        <div class="home-explorer-kicker">This lab session · ${(s.visited || []).length} of ${PARTS.length} Parts used</div>
        <h2 id="lab-title">Session scope</h2>
        <div class="scope-grid">
          <span class="kv">memory_id <b>${esc(scope.memory_id || "—")}</b></span>
          <span class="kv">user_id <b>${esc(scope.user_id || "—")}</b></span>
          <span class="kv">MemoRizz agent <b>${esc(s.agent_id ? s.agent_id.slice(0, 8) : "not built yet")}</b></span>
        </div>
        <p>Parts build on each other as in the notebook: a later page first runs the setup of the Parts before it (persona v1, the runbook, the tools, the authored skill). Reset deletes this session's rows with exact-scope deletes.</p>
      </div>
      <div class="lab-actions">
        <a class="btn btn-accent" href="#/1">${I.play} Start at Part 1</a>
        <a class="btn" href="#/tokenomics">${I.chart} Tokenomics</a>
        <button class="btn btn-ghost" id="reset-lab" type="button">${I.refresh} Reset session</button>
      </div>
    </section>
    <section class="home-explorer" aria-labelledby="home-explorer-title">
      <div class="home-explorer-mark">${I.db}</div>
      <div class="home-explorer-copy">
        <div class="home-explorer-kicker">Live memory storage</div>
        <h2 id="home-explorer-title">Memory Data Explorer</h2>
        <p>Your <code>SCRATCH_*</code> tables next to MemoRizz's tables in the MEMORIZZ schema, limited to this session or across the schema, with live read/write activity.</p>
        <div class="home-explorer-summary" id="home-explorer-summary">${esc($("#explorer-summary")?.textContent || "Connecting to the application database…")}</div>
      </div>
      <button class="btn btn-accent" id="home-explorer-open" type="button">${I.db} Open Data Explorer</button>
    </section>
    <div class="ladder">${rungs}</div>`, "var(--r6)");
  $("#home-explorer-open").addEventListener("click", () => toggleExplorer(true));
  $("#reset-lab").addEventListener("click", resetSession);
}

async function resetSession() {
  const button = $("#reset-lab");
  if (button) { button.disabled = true; button.innerHTML = `<span class="spinner"></span> Resetting…`; }
  try { await postJSON("/api/session/reset"); } catch (error) { warn($(".view"), error.message); }
  await refreshSession();
  route();
}

// ── tables ───────────────────────────────────────────────────────────
function cellText(value) {
  if (value === null || value === undefined) return "";
  const text = typeof value === "object" ? JSON.stringify(value) : String(value);
  return text.length > 180 ? text.slice(0, 180) + "…" : text;
}
function simpleTable(columns, rows) {
  if (!rows || !rows.length) return `<div class="explorer-empty">No rows yet.</div>`;
  const head = columns.map((c) => `<th>${esc(c)}</th>`).join("");
  const body = rows.map((row) => `<tr>${columns.map((c) => {
    const full = row[c] === null || row[c] === undefined ? "" : (typeof row[c] === "object" ? JSON.stringify(row[c]) : String(row[c]));
    return `<td title="${esc(full.slice(0, 600))}">${esc(cellText(row[c]))}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="rows-wrap"><table class="explorer-data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function tableCard(data, side) {
  const extra = side === "scratch"
    ? `<details><summary>Your DDL</summary><pre>${esc(data.ddl || "")}</pre></details>`
    : `<div class="col-list">${(data.all_columns || []).map((c) => `<code>${esc(c)}</code>`).join("")}</div>`;
  return `<div class="table-card">
    <div class="table-card-head"><b>${esc(data.table.toUpperCase())}</b><span>${data.row_count} row${data.row_count === 1 ? "" : "s"} in this session</span>
      <button class="chip open-table" type="button" data-table="${esc(data.table)}">${I.db} explore</button></div>
    ${extra}${simpleTable(data.columns, data.rows)}</div>`;
}
document.addEventListener("click", (event) => {
  const button = event.target.closest(".open-table");
  if (!button) return;
  toggleExplorer(true);
  setTimeout(() => selectExplorerTable(button.dataset.table, 0), 120);
});

// ── answers and the context rail ─────────────────────────────────────
function metric(label, value, cls = "") { return `<span class="metric ${cls}">${esc(label)} <b>${esc(value)}</b></span>`; }
function replyHTML(a) {
  if (!a) return `<div class="reply-empty">Send a message to see this agent's answer.</div>`;
  const m = [metric("seconds", a.seconds), metric("input tokens", (a.input_tokens ?? 0).toLocaleString())];
  if (a.cached_tokens) m.push(metric("cached", a.cached_tokens.toLocaleString()));
  if (a.tool_calls && a.tool_calls.length) m.push(metric("tools", a.tool_calls.join(", ")));
  if (a.cache_hit !== null && a.cache_hit !== undefined) m.push(metric("cache hit · distance", a.cache_hit, "hit"));
  if (a.dropped) m.push(metric("history dropped", a.dropped));
  if (a.routed) m.push(metric("routed to", a.routed, "hit"));
  if (a.semantic_cache) m.push(metric("cache hits / writes / bypasses", `${a.semantic_cache.hits} / ${a.semantic_cache.writes} / ${a.semantic_cache.bypasses}`));
  if (a.raw) m.push(metric("raw model call", "no memory"));
  if (a.accuracy && a.accuracy.score !== null && a.accuracy.score !== undefined)
    m.push(metric("LLM judge", a.accuracy.score ? "correct" : "incorrect", a.accuracy.score ? "hit" : "bad"));
  const link = a.turn ? `<a class="cw-link" href="#/context/${a.turn}">${I.window} See this turn's context window</a>` : "";
  return `<div class="answer-body">${renderRich(a.text)}</div><div class="metrics">${m.join("")}</div>${link}`;
}
function renderCtxRail(last) {
  const el = $("#ctxrail"); if (!el) return;
  const s = last?.scratch, mz = last?.memorizz;
  let body = `<div class="ctx-empty">Send a message on a Part page: this rail shows what each agent sent to the model.</div>`;
  if (s || mz) {
    const total = s?.context?.find((r) => r.part === "total")?.tokens || 1;
    const rows = (s?.context || []).filter((r) => r.part !== "total").map((r) => `
      <div class="ctx-row"><span title="${esc(r.part)}">${esc(r.part)}</span><b>${r.tokens}</b><div class="bar"><i style="width:${Math.max(2, Math.round((r.tokens / total) * 100))}%"></i></div></div>`).join("");
    const counts = Object.entries(mz?.source_counts || {}).filter(([, v]) => v).map(([k, v]) => `<div class="ctx-row"><span>${esc(k)}</span><b>${v}</b></div>`).join("") || `<div class="ctx-empty">no memory sources reported</div>`;
    body = `
      <div class="ctx-side scratch"><h4>From scratch · ${total} tokens (tiktoken)</h4>${rows || '<div class="ctx-empty">—</div>'}
        ${s?.layers ? `<div class="layers-line">${esc(s.layers)}</div>` : ""}</div>
      <div class="ctx-side memorizz"><h4>MemoRizz · ${(mz?.input_tokens ?? 0).toLocaleString()} input tokens</h4>
        ${mz?.raw ? '<div class="ctx-empty">Part 1: raw model call, no memory.</div>' : `
        <div class="ctx-row"><span>cached by the provider</span><b>${(mz?.cached_tokens ?? 0).toLocaleString()}</b></div>
        <div class="ctx-row"><span>model calls</span><b>${mz?.calls ?? 0}</b></div>
        <h4>Memory sources supplied</h4>${counts}
        <h4>Active memory types</h4><div class="layers-line">${esc((mz?.memory_types || []).join(" · "))}</div>`}</div>`;
  }
  const turn = s?.turn || mz?.turn;
  el.innerHTML = `<div class="ctx-title">${I.window} Model context</div>
    <div class="ctx-sub">${last ? esc(`Part ${last.part} · thread ${last.thread}`) : "idle"}</div>
    <div class="ctx-legend">${body}</div>
    ${turn ? `<a class="btn cw-rail-link" href="#/context/${turn}">${I.window} Open the full context window</a>` : ""}
    <div class="ctx-foot">Scratch counts every block it sent; MemoRizz reports its own usage and evidence. Both are real gpt-5.5 calls.</div>`;
}

// ── Part actions ─────────────────────────────────────────────────────
const ACTION_UI = {
  1: [{ name: "baseline", label: "Run two raw model calls" }],
  2: [{ name: "restore", label: "Restore both agents in fresh objects" }],
  3: [{ name: "evolve", label: "Evolve the persona on both sides", fields: [
    { key: "field", label: "field", type: "select", options: ["goals", "style"] },
    { key: "value", label: "new value", value: "Help platform engineers ship reliable, grounded and cost-aware AI systems.", wide: true },
    { key: "reason", label: "reason", value: "The platform team adopted cost budgets.", wide: true }] }],
  5: [{ name: "search", label: "Search the runbook", fields: [
    { key: "query", label: "query", value: "When am I allowed to rebuild the retrieval-api vector index, and what ticket do I need?", wide: true }] }],
  6: [{ name: "preview", label: "Preview tool selection", fields: [
    { key: "query", label: "request", value: "Check docs_hnsw and the vector pool.", wide: true }] }],
  9: [{ name: "propose", label: "Propose skills from repeated workflows" }, { name: "approve", label: "Approve candidates" }],
  11: [{ name: "compact", label: "Compact the migration thread (keep 4)" }],
  12: [{ name: "invalidate", label: "Invalidate a cache domain", fields: [{ key: "domain", label: "domain", value: "runbook" }] }],
  13: [{ name: "review", label: "Draft → Rev reviews → revise", fields: [
    { key: "plan_request", label: "plan request", value: "Draft a five-step plan for tonight's retrieval-api index rebuild. Tonight is Wednesday.", wide: true }] }],
  14: [{ name: "scores", label: "Score the runbook chunks", fields: [{ key: "query", label: "query", value: "Who do I page when the rebuild fails?", wide: true }] },
       { name: "suppress", label: "Plan and suppress (both sides)" }, { name: "restore", label: "Restore everything suppressed" }],
  15: [{ name: "route", label: "Route the eight items (chat model vs Jev)" },
       { name: "file", label: "Route and file one item", fields: [{ key: "item", label: "item", value: ROUTING_ITEMS[1], wide: true }] }],
  16: [{ name: "save_restore", label: "Save and restore both agents" },
       { name: "compare", label: "One request to both restored agents", fields: [{ key: "request", label: "request", wide: true,
         value: "It's Tuesday 02:20 UTC. I'm about to rebuild the retrieval-api vector index. Check docs_hnsw and the vector pool, then give me a go or no-go and the exact steps." }] },
       { name: "observability", label: "Operational evidence" }],
};

function actionsPanel(p) {
  const ui = ACTION_UI[p.n];
  if (!ui) return "";
  const forms = ui.map((a) => `
    <form class="action-form" data-action="${a.name}">
      ${(a.fields || []).map((f) => f.type === "select"
        ? `<label>${esc(f.label)}<select name="${f.key}">${f.options.map((o) => `<option>${esc(o)}</option>`).join("")}</select></label>`
        : `<label class="${f.wide ? "wide" : ""}" style="${f.wide ? "flex:3 1 260px" : ""}">${esc(f.label)}<input name="${f.key}" value="${esc(f.value || "")}" /></label>`).join("")}
      <button class="btn btn-accent" type="submit">${I.play} ${esc(a.label)}</button>
    </form>`).join("");
  return `<div class="panel" style="margin-top:18px">
    <div class="panel-head"><span class="panel-title">${I.tool} Part ${p.n} actions</span></div>
    <div class="panel-body">${forms}<div class="action-result" id="action-result"></div></div></div>`;
}

function probBars(probabilities) {
  return `<div class="prob-bars">${Object.entries(probabilities || {}).map(([k, v]) => `
    <div class="prob-bar"><span>${esc(k)}</span><span><i style="width:${Math.round(v * 100)}%"></i></span><span>${Number(v).toFixed(2)}</span></div>`).join("")}</div>`;
}
function genericHTML(value) {
  if (value === null || value === undefined) return '<span class="explorer-null">—</span>';
  if (Array.isArray(value)) {
    if (value.length && typeof value[0] === "object" && !Array.isArray(value[0])) return simpleTable(Object.keys(value[0]), value);
    return esc(value.map((v) => typeof v === "object" ? JSON.stringify(v) : v).join(", ") || "—");
  }
  if (typeof value === "object") {
    return `<dl class="kv-grid">${Object.entries(value).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${genericHTML(v)}</dd>`).join("")}</dl>`;
  }
  if (typeof value === "string" && value.length > 120) return `<div class="answer-body">${renderRich(value)}</div>`;
  return esc(String(value));
}
function duoHTML(left, right, leftTitle = "From scratch", rightTitle = "With MemoRizz") {
  return `<div class="duo">
    <section class="side scratch"><div class="side-head"><i></i><b>${esc(leftTitle)}</b></div><div class="reply">${left}</div></section>
    <section class="side memorizz"><div class="side-head"><i></i><b>${esc(rightTitle)}</b></div><div class="reply">${right}</div></section></div>`;
}
const ACTION_RENDER = {
  baseline: (r) => duoHTML(`<div class="answer-label">Call 1</div>${renderRich(r.first)}`, `<div class="answer-label">Call 2</div>${renderRich(r.second)}`, "First call", "Second call, no shared messages"),
  restore: (r) => duoHTML(renderRich(r.scratch), renderRich(r.memorizz) + `<div class="metrics">${metric("agent_id", r.agent_id)}</div>`, "Fresh ScratchMemo", "MemAgent.load()"),
  search: (r) => duoHTML(simpleTable(["chunk_index", "distance", "content"], r.scratch), simpleTable(["score", "content"], r.memorizz),
    "VECTOR_DISTANCE … COSINE (lower is closer)", "provider.retrieve_by_query (higher is closer)"),
  preview: (r) => duoHTML(simpleTable(["name", "distance"], r.scratch), genericHTML(r.memorizz), "select_tools (top 3 are disclosed)", "semantic_tool_router.preview"),
  review: (r) => duoHTML(
    `<div class="answer-label">Memo's plan</div>${renderRich(r.scratch.plan)}<div class="answer-label">Rev's report</div>${renderRich(r.scratch.findings)}<div class="answer-label">Revised plan</div>${renderRich(r.scratch.revised)}`,
    `<div class="answer-label">Memo's plan</div>${renderRich(r.memorizz.plan)}<div class="answer-label">Rev's report</div>${renderRich(r.memorizz.findings)}<div class="answer-label">Revised plan</div>${renderRich(r.memorizz.revised)}${genericHTML(r.memorizz.blackboard)}`),
  compare: (r) => duoHTML(
    replyHTML({ text: r.scratch.text, seconds: r.scratch.seconds, input_tokens: r.scratch.input_tokens, tool_calls: r.scratch.tool_calls, turn: r.scratch.turn }),
    replyHTML({ text: r.memorizz.text, seconds: r.memorizz.seconds, input_tokens: r.memorizz.input_tokens, cached_tokens: r.memorizz.cached_tokens, tool_calls: r.memorizz.tool_calls, turn: r.memorizz.turn }),
    "Restored scratch Memo", "Restored MemoRizz Memo"),
  route: (r) => `
    <div class="metrics">${metric("chat model", `${r.llm_seconds}s · accuracy ${Math.round((r.accuracy.llm ?? 0) * 100)}%`)}${metric("Jev", `${r.jev_seconds}s · accuracy ${Math.round((r.accuracy.jev ?? 0) * 100)}%`, "hit")}${metric("active fine-tuned router", r.active_fine_tuned_router ? "yes" : "none")}${metric("Jev cost (MemoRizz client)", `$${r.jev_usage?.cost_usd ?? 0}`)}</div>
    <div class="table-card"><div class="rows-wrap" style="max-height:none"><table class="explorer-data-table wrap"><thead><tr>
      <th>item</th><th>expected</th><th>chat model</th><th>Jev (your question)</th><th>MemoRizz question → place()</th></tr></thead><tbody>
      ${r.rows.map((row) => `<tr><td title="${esc(row.item)}">${esc(row.item)}</td><td>${esc(row.expected || "—")}</td>
        <td>${esc(row.llm)} <span class="muted">(${row.llm_confidence})</span></td><td>${probBars(row.jev_probabilities)}</td>
        <td>${esc(row.memorizz_jev)} · ${row.memorizz_p}<br><span class="muted">${esc(row.filed_to ?? "not stored")}${row.next_step ? " · " + esc(row.next_step) : ""}</span></td></tr>`).join("")}
    </tbody></table></div></div>`,
  file: (r) => duoHTML(`${genericHTML({ store: r.scratch_store, filed_to: r.scratch_filed })}${probBars(r.scratch_probabilities)}`,
    genericHTML({ jev_answer: r.memorizz_answer, filed: r.memorizz_filed }), "Jev → file_memory()", "memory_routing_spec → MemoRizz write path"),
};
function renderActionResult(name, result) {
  const host = $("#action-result"); if (!host) return;
  const render = ACTION_RENDER[name];
  host.innerHTML = `<div class="lab-title">${esc(name.replace("_", " "))} · ${result.seconds ?? ""}s</div>` + (render ? render(result) : genericHTML(Object.fromEntries(Object.entries(result).filter(([k]) => k !== "seconds"))));
}

async function runAction(p, name, form) {
  if (state.busy) return;
  const params = Object.fromEntries(new FormData(form).entries());
  const button = form.querySelector("button");
  const label = button.innerHTML;
  state.busy = true; button.disabled = true; button.innerHTML = `<span class="spinner"></span> Running…`;
  const host = $("#action-result");
  if (host) host.innerHTML = `<div class="plan-note">Running ${esc(name.replace("_", " "))} on both agents…</div>`;
  try {
    const result = await postJSON(`/api/parts/${p.n}/actions/${name}`, { params });
    renderActionResult(name, result);
    await loadPage(p);
  } catch (error) {
    if (host) host.innerHTML = ""; warn(host, error.message);
  } finally {
    state.busy = false;
    if (document.body.contains(button)) { button.disabled = false; button.innerHTML = label; }
  }
}

// ── view: one Part ────────────────────────────────────────────────────
function promptControls(p) {
  const threads = p.threads || ["migration"];
  return `
    ${threads.length > 1 ? `<label>thread<select id="thread">${threads.map((t) => `<option>${esc(t)}</option>`).join("")}</select></label>` : ""}
    ${p.budget ? `<label>budget (tokens) <span id="budget-value" class="mono">8000</span><input id="budget" type="range" min="300" max="8000" step="100" value="8000" /></label>` : ""}
    ${p.page ? `<label class="wide">request context: open page<input id="open-page" value="incident INC-4821: retrieval-api p95 latency above 800 ms" /></label><label style="flex:0 1 auto;flex-direction:row;align-items:center;gap:6px"><input id="attach-page" type="checkbox" checked style="width:auto" /> attach to this turn</label>` : ""}
    ${p.cache ? `<label>cache domain<input id="cache-domain" value="runbook" /></label><label>data version<input id="data-version" value="2026-10-17" /></label>` : ""}`;
}

// One stored unit as the table row it is in the database: what SELECT * returns, nested values as stored JSON.
function unitTable(json) {
  const row = JSON.parse(json);
  const cell = (value) => {
    const text = value === null ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value);
    return `<td title="${esc(text)}"${value === null ? ' class="null"' : ""}>${esc(text)}</td>`;
  };
  return `<div class="unit-table-view"><div class="unit-table-wrap"><table class="unit-table">
      <thead><tr>${Object.keys(row).map((column) => `<th>${esc(column)}</th>`).join("")}</tr></thead>
      <tbody><tr>${Object.values(row).map(cell).join("")}</tr></tbody></table></div>
    <p class="unit-table-note">One row, one column per field. Scroll sideways for every column; hover a cell for its full value.</p></div>`;
}
// JSON or Row: one choice for every Part, remembered in this browser.
const UNIT_VIEW_KEY = "zth-unit-view";
const unitView = () => (document.documentElement.getAttribute("data-unitview") === "row" ? "row" : "json");
function setUnitView(view) {
  document.documentElement.setAttribute("data-unitview", view);
  try { localStorage.setItem(UNIT_VIEW_KEY, view); } catch (_) {}
  $$(".unit-view [data-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.view === view)));
}

// The memory unit behind a Part: definition, one stored unit as JSON or as a row, and when to use it (units.js).
function unitCard(p) {
  const u = typeof UNITS !== "undefined" ? UNITS[String(p.n)] : null;
  if (!u) return "";
  const inline = (text) => esc(text).replace(/`([^`]+?)`/g, "<code>$1</code>");
  const relational = !u.table.startsWith("(");        // Part 10's unit is the request itself: never a stored row
  const toggle = relational ? `<span class="unit-view" role="group" aria-label="Show the unit as">${[["json", "JSON"], ["row", "Row"]]
    .map(([view, label]) => `<button type="button" data-view="${view}" aria-pressed="${unitView() === view}">${label}</button>`).join("")}</span>` : "";
  return `
    <section class="panel unit-card${relational ? " relational" : ""}" aria-label="The memory unit">
      <div class="unit-copy">
        <div class="unit-label">The memory unit</div>
        <p class="unit-definition">${inline(u.definition)}</p>
        <div class="unit-label">Use it when</div>
        <ul class="unit-uses">${u.uses.map((item) => `<li>${inline(item)}</li>`).join("")}</ul>
        <p class="unit-avoid"><b>Not for:</b> ${inline(u.avoid)}</p>
      </div>
      <div class="unit-row">
        <div class="unit-label unit-head"><span>One unit, as stored · <code>${esc(u.table)}</code></span>${toggle}</div>
        <pre class="unit-json">${esc(u.row)}</pre>
        ${relational ? unitTable(u.row) : ""}
      </div>
    </section>`;
}

function viewPart(p) {
  const defaults = { 14: ["Who do I page when the rebuild fails?"], 16: ["What is the rebuild policy for embedding-worker vector indexes?"] };
  const suggestions = p.suggest.length ? p.suggest : (defaults[p.n] || []);
  setStage(`
    <header class="ff-head">
      <div class="ff-numeral">${p.n}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">Part ${p.n} · ${esc(GROUPS[p.group].name)} · <code>${esc(p.unit)}</code></div>
        <h1 class="ff-title">${esc(p.title)}</h1>
        <p class="ff-desc">${p.idea}</p>
      </div>
    </header>
    <div id="page-banner">${healthBanner()}</div>
    <div class="watch"><b>What to watch</b> ${esc(p.watch)}</div>
    ${unitCard(p)}
    <div class="panel" style="margin-top:18px">
      <div class="panel-head"><span class="panel-title">${I.send} One message to both agents, built up to Part ${p.n}</span><span class="setup-line" id="setup-line"></span></div>
      <div class="panel-body prompt-box">
        <div class="chips">${suggestions.map((s) => `<button class="chip chip-suggest" type="button" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>
        <textarea id="message" aria-label="Message to both agents" maxlength="2000">${esc(suggestions[0] || "")}</textarea>
        <div class="prompt-row">${promptControls(p)}<button class="btn btn-accent" id="send" type="button">${I.send} Send to both</button></div>
      </div>
    </div>
    ${actionsPanel(p)}
    <div class="duo">
      <section class="side scratch" aria-label="From scratch">
        <div class="side-head"><i></i><b>From scratch</b> · your SCRATCH_* tables</div>
        <div class="reply" id="reply-scratch">${replyHTML(null)}</div>
        <div id="tables-scratch"></div>
      </section>
      <section class="side memorizz" aria-label="With MemoRizz">
        <div class="side-head"><i></i><b>${p.n === 1 ? "Raw model call" : "With MemoRizz"}</b> · ${p.n === 1 ? "no memory at all" : "MemoRizz 0.17.4 tables"}</div>
        <div class="reply" id="reply-memorizz">${replyHTML(null)}</div>
        <div id="tables-memorizz"></div>
      </section>
    </div>`, accentOf(p));
  $$("[data-suggest]").forEach((chip) => chip.addEventListener("click", () => { $("#message").value = chip.dataset.suggest; $("#message").focus(); }));
  $("#send").addEventListener("click", () => sendMessage(p));
  const budget = $("#budget");
  if (budget) budget.addEventListener("input", () => { $("#budget-value").textContent = budget.value; });
  $$("form.action-form").forEach((form) => form.addEventListener("submit", (event) => { event.preventDefault(); runAction(p, form.dataset.action, form); }));
  loadPage(p);
}

async function loadPage(p) {
  try {
    const data = await getJSON(`/api/parts/${p.n}`);
    if (state.route !== String(p.n)) return;
    state.page = data;
    if (data.unavailable) $("#page-banner").innerHTML = healthBanner(data.unavailable);
    const left = $("#tables-scratch"), right = $("#tables-memorizz");
    if (left) left.innerHTML = data.scratch.map((t) => tableCard(t, "scratch")).join("");
    if (right) right.innerHTML = data.memorizz.map((t) => tableCard(t, "memorizz")).join("") +
      (data.extra && Object.keys(data.extra).length ? `<div class="table-card"><div class="table-card-head"><b>Runtime stats</b></div><div style="padding:10px 12px">${genericHTML(data.extra)}</div></div>` : "");
    if (data.last && !$("#reply-scratch .answer-body")) {
      $("#reply-scratch").innerHTML = replyHTML(data.last.scratch);
      $("#reply-memorizz").innerHTML = replyHTML(data.last.memorizz);
      renderCtxRail(data.last);
    }
    if (data.action && $("#action-result") && !$("#action-result").innerHTML.trim()) renderActionResult(data.action.name, data.action.result);
  } catch (error) {
    if (state.route === String(p.n)) $("#page-banner").innerHTML = healthBanner(error.message);
  }
}

async function sendMessage(p) {
  if (state.busy) return;
  const message = $("#message").value.trim();
  if (!message) return;
  const body = { message, thread: $("#thread")?.value || (p.threads || ["migration"])[0] };
  if ($("#budget")) body.budget = Number($("#budget").value);
  if ($("#open-page") && $("#attach-page")?.checked && $("#open-page").value.trim()) body.open_page = $("#open-page").value.trim();
  if ($("#cache-domain")) { body.cache_domain = $("#cache-domain").value.trim(); body.data_version = $("#data-version").value.trim(); }
  const button = $("#send");
  state.busy = true; button.disabled = true; button.innerHTML = `<span class="spinner"></span> Running…`;
  const result = { part: p.n, thread: body.thread };
  state.abort = new AbortController();
  $("#setup-line").textContent = "";
  try {
    await streamSSE(`/api/parts/${p.n}/chat`, body, (event) => {
      if (event.type === "setup") $("#setup-line").textContent = event.status === "running" ? `setting up Part ${event.part}…` : `Part ${event.part} set up · ${event.seconds}s`;
      else if (event.type === "start") $(`#reply-${event.side}`).innerHTML = `<div class="reply-empty"><span class="spinner"></span> thinking…</div>`;
      else if (event.type === "answer") { result[event.side] = event; $(`#reply-${event.side}`).innerHTML = replyHTML(event); }
      else if (event.type === "judging") $("#setup-line").textContent = "a golden question: the LLM judge is grading both answers…";
      else if (event.type === "judged") {
        for (const side of ["scratch", "memorizz"]) if (result[side]) { result[side].accuracy = event[side]; $(`#reply-${side}`).innerHTML = replyHTML(result[side]); }
        $("#setup-line").textContent = `LLM judge · scratch ${event.scratch.verdict} · MemoRizz ${event.memorizz.verdict}`;
      }
      else if (event.type === "error") warn($("#page-banner"), event.message);
      else if (event.type === "done") { state.session = event.session; renderSidebar(state.route); }
    }, state.abort.signal);
    if (result.scratch || result.memorizz) renderCtxRail(result);
    await loadPage(p);
  } catch (error) {
    if (error.name !== "AbortError") warn($("#page-banner"), error.message);
  } finally {
    state.abort = null; state.busy = false;
    if (document.body.contains(button)) { button.disabled = false; button.innerHTML = `${I.send} Send to both`; }
  }
}

// ── persistent Data Explorer ─────────────────────────────────────────
async function explorerJSON(url) {
  const response = await fetch(url);
  let payload = {};
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function toggleExplorer(force) {
  const explorer = $("#data-explorer");
  const opening = force ?? !explorer.classList.contains("open");
  explorer.classList.toggle("open", opening);
  $("#explorer-body").hidden = !opening;
  $("#explorer-toggle").setAttribute("aria-expanded", String(opening));
  document.body.classList.toggle("explorer-open", opening);
  if (opening && !explorerState.tables.length) loadExplorerCatalog();
}

function initializeExplorerResize(storageKey) {
  const explorer = $("#data-explorer");
  const handle = $("#explorer-resizer");
  const saved = Number(localStorage.getItem(storageKey));
  if (Number.isFinite(saved) && saved >= 220) {
    document.documentElement.style.setProperty("--explorer-height", `${Math.min(saved, window.innerHeight - 80)}px`);
  }
  handle.addEventListener("pointerdown", (event) => {
    if (!explorer.classList.contains("open")) return;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const startY = event.clientY;
    const startHeight = explorer.getBoundingClientRect().height;
    explorer.classList.add("resizing");
    document.body.classList.add("explorer-resizing");
    const move = (moveEvent) => {
      const next = Math.max(220, Math.min(window.innerHeight - 80, startHeight + startY - moveEvent.clientY));
      document.documentElement.style.setProperty("--explorer-height", `${Math.round(next)}px`);
    };
    const stop = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      handle.removeEventListener("pointercancel", stop);
      explorer.classList.remove("resizing");
      document.body.classList.remove("explorer-resizing");
      localStorage.setItem(storageKey, String(Math.round(explorer.getBoundingClientRect().height)));
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
    handle.addEventListener("pointercancel", stop);
  });
}

async function loadExplorerCatalog() {
  const refresh = $("#explorer-refresh");
  refresh.disabled = true;
  try {
    const payload = await explorerJSON("/api/data_explorer/tables");
    explorerState.tables = payload.tables || [];
    const totalRows = explorerState.tables.reduce((total, table) => total + Math.max(0, table.row_count), 0);
    const summary =
      `${explorerState.tables.length} tables · ${totalRows.toLocaleString()} rows · ${payload.backend}${payload.schema ? ` · ${payload.schema}` : ""}`;
    $("#explorer-summary").textContent = summary;
    const homeSummary = $("#home-explorer-summary");
    if (homeSummary) homeSummary.textContent = summary;
    renderExplorerTables();
    const stillAvailable = explorerState.tables.some((table) => table.name === explorerState.selected);
    if (!stillAvailable) {
      const preferred = explorerState.tables.find((table) => table.name.toLowerCase() === explorerState.preferredTable);
      const firstPopulated = explorerState.tables.find((table) => table.row_count > 0);
      const initial = (preferred?.row_count > 0 ? preferred : null) || firstPopulated || preferred || explorerState.tables[0];
      if (initial) await selectExplorerTable(initial.name);
    }
  } catch (error) {
    $("#explorer-summary").textContent = error.message;
    const homeSummary = $("#home-explorer-summary");
    if (homeSummary) homeSummary.textContent = error.message;
    $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(error.message)}</div>`;
  } finally {
    refresh.disabled = false;
  }
}

function renderExplorerTables() {
  const filter = ($("#explorer-filter").value || "").toLowerCase();
  const visible = explorerState.tables.filter((table) =>
    !filter || `${table.name} ${table.layer}`.toLowerCase().includes(filter)
  );
  $("#explorer-table-list").innerHTML = visible.map((table) => {
    const key = table.name.toLowerCase();
    const event = explorerState.active.get(key);
    const recent = explorerState.recent.get(key);
    const pulse = event ? `tx-${event.operation.toLowerCase()}` : recent ? `flash-${recent.operation.toLowerCase()}` : "";
    return `<button class="explorer-table-item ${explorerState.selected === table.name ? "selected" : ""} ${pulse}" data-explorer-table="${esc(table.name)}">
      <span><i></i>${esc(table.name)}</span><b>${table.row_count < 0 ? "—" : Number(table.row_count).toLocaleString()}</b>
      ${event ? `<em>${esc(event.operation)}</em>` : ""}
    </button>`;
  }).join("") || '<div class="explorer-empty">No matching tables.</div>';
  $("#explorer-table-list").querySelectorAll("[data-explorer-table]").forEach((button) => {
    button.addEventListener("click", () => selectExplorerTable(button.dataset.explorerTable));
  });
}

async function selectExplorerTable(name, offset = 0) {
  explorerState.selected = name;
  explorerState.offset = offset;
  renderExplorerTables();
  $("#explorer-grid").innerHTML = '<div class="explorer-empty">Reading rows…</div>';
  try {
    explorerState.result = await explorerJSON(
      `/api/data_explorer/tables/${encodeURIComponent(name)}/rows?limit=${explorerState.limit}&offset=${offset}&scope=${explorerState.scope}`
    );
    renderExplorerRows();
  } catch (error) {
    $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(error.message)}</div>`;
  }
}

function explorerCellText(value) {
  if (value === null || value === undefined) return "";
  const rendered = typeof value === "object" ? JSON.stringify(value) : String(value);
  return rendered.length > 220 ? rendered.slice(0, 220) + "…" : rendered;
}

function formatExplorerCell(value) {
  if (value === null || value === undefined) return '<span class="explorer-null">NULL</span>';
  return esc(explorerCellText(value));
}

function toggleExplorerScope() {
  explorerState.scope = explorerState.scope === "run" ? "all" : "run";
  const button = $("#explorer-scope");
  button.textContent = explorerState.scope === "run" ? "This run" : "All rows";
  button.classList.toggle("active", explorerState.scope === "run");
  if (explorerState.selected) selectExplorerTable(explorerState.selected, 0);
}

function renderExplorerRows() {
  const data = explorerState.result;
  if (!data) return;
  const table = explorerState.tables.find((item) => item.name.toLowerCase() === data.table.toLowerCase());
  $("#explorer-layer").textContent = `${table?.layer || "database"} · ${data.columns.length} columns · ${data.scope === "run" ? "this run's rows" : "all rows"}`;
  $("#explorer-table-name").textContent = data.table;
  const knownTotal = data.row_count >= 0;
  const start = data.rows.length ? data.offset + 1 : 0;
  const end = data.offset + data.rows.length;
  $("#explorer-page").textContent = knownTotal
    ? `${start.toLocaleString()}–${end.toLocaleString()} of ${Number(data.row_count).toLocaleString()}`
    : `${start.toLocaleString()}–${end.toLocaleString()}`;
  $("#explorer-prev").disabled = data.offset === 0;
  $("#explorer-next").disabled = knownTotal ? end >= data.row_count : data.rows.length < data.limit;

  if (!data.columns.length) {
    $("#explorer-grid").innerHTML = '<div class="explorer-empty">This table has no discoverable columns.</div>';
    return;
  }
  const key = data.table.toLowerCase();
  const event = explorerState.active.get(key);
  const recent = explorerState.recent.get(key);
  const pulse = event || recent;
  const prefix = event ? "tx" : "flash";
  const pulseClass = pulse ? `${prefix}-${pulse.operation.toLowerCase()}` : "";
  const head = data.columns.map((column) =>
    `<th><span>${esc(column.name)}</span><small>${esc(column.type)}${column.primary_key ? " · PK" : ""}</small></th>`
  ).join("");
  const body = data.rows.map((row, index) => {
    const rowPulse = pulse && (!pulse.row_key || pulse.row_key === data.row_keys[index]) ? pulseClass : "";
    const cells = data.columns.map((column) => {
      const text = explorerCellText(row[column.name]);
      return `<td title="${esc(text)}">${formatExplorerCell(row[column.name])}</td>`;
    }).join("");
    return `<tr class="${rowPulse}" data-row-key="${esc(data.row_keys[index])}">${cells}</tr>`;
  }).join("");
  $("#explorer-grid").innerHTML = data.rows.length
    ? `<table class="explorer-data-table ${pulseClass}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`
    : '<div class="explorer-empty">The table is currently empty.</div>';
}

function onExplorerTransaction(event) {
  explorerState.events.unshift(event);
  explorerState.events = explorerState.events.slice(0, 40);
  const table = event.table.toLowerCase();
  if (event.status === "active") {
    explorerState.active.set(table, event);
  } else {
    if (explorerState.active.get(table)?.transaction_id === event.transaction_id) explorerState.active.delete(table);
    explorerState.recent.set(table, event);
    setTimeout(() => {
      if (explorerState.recent.get(table)?.transaction_id === event.transaction_id) {
        explorerState.recent.delete(table);
        renderExplorerTables();
        if (explorerState.result?.table.toLowerCase() === table) renderExplorerRows();
      }
    }, 1400);
    if (event.status === "committed" && event.operation === "WRITE") {
      clearTimeout(explorerState.refreshTimer);
      explorerState.refreshTimer = setTimeout(async () => {
        const selected = explorerState.selected;
        await loadExplorerCatalog();
        if (selected && selected.toLowerCase() === table) await selectExplorerTable(selected, 0);
      }, 250);
    }
  }
  const latest = [...explorerState.active.values()].at(-1);
  $("#explorer-live-label").textContent = latest ? `${latest.operation} · ${latest.table}` : "Live transactions";
  $("#data-explorer").classList.toggle("transacting", explorerState.active.size > 0);
  renderExplorerTables();
  if (explorerState.result?.table.toLowerCase() === table) renderExplorerRows();
  renderExplorerActivity();
}

function renderExplorerActivity() {
  $("#explorer-activity-list").innerHTML = explorerState.events.map((event) =>
    `<div class="explorer-activity-event ${event.status} ${event.operation.toLowerCase()}"><i></i><div>
      <strong>${esc(event.operation)} <span>${esc(event.table)}</span> <em>${esc(event.status.replace("_", " "))}</em></strong>
      <small>${esc(event.route)} · ${esc(event.detail || event.status)}</small>
    </div><time>${new Date(event.occurred_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>`
  ).join("") || '<div class="explorer-empty">Waiting for database activity…</div>';
}

function connectExplorerActivity() {
  if (explorerState.source) explorerState.source.close();
  const source = new EventSource("/api/data_explorer/activity");
  explorerState.source = source;
  source.addEventListener("transaction", (event) => {
    try { onExplorerTransaction(JSON.parse(event.data)); } catch (_) {}
  });
  source.addEventListener("ready", () => { $("#explorer-live-label").textContent = "Live transactions"; });
  source.onerror = () => { $("#explorer-live-label").textContent = "Reconnecting…"; };
}

async function loadRecentExplorerActivity() {
  try {
    const payload = await explorerJSON("/api/data_explorer/activity/recent");
    explorerState.events = payload.events || [];
    renderExplorerActivity();
  } catch (_) {}
}

function initializeDataExplorer(storageKey) {
  $("#explorer-toggle").addEventListener("click", () => toggleExplorer());
  $("#explorer-refresh").addEventListener("click", loadExplorerCatalog);
  $("#explorer-filter").addEventListener("input", renderExplorerTables);
  $("#explorer-prev").addEventListener("click", () =>
    selectExplorerTable(explorerState.selected, Math.max(0, explorerState.offset - explorerState.limit))
  );
  $("#explorer-next").addEventListener("click", () =>
    selectExplorerTable(explorerState.selected, explorerState.offset + explorerState.limit)
  );
  initializeExplorerResize(storageKey);
  connectExplorerActivity();
  loadRecentExplorerActivity();
  loadExplorerCatalog();
}

// ── router ───────────────────────────────────────────────────────────
function route() {
  cancelStream();
  state.busy = false;
  const id = (location.hash.replace(/^#\/?/, "").trim()) || "";
  state.route = id;
  renderSidebar(id.startsWith("context") ? "context" : id || "home");
  renderCtxRail(null);
  if (PART_BY_N[id]) viewPart(PART_BY_N[id]);
  else if (id === "tokenomics") viewTokenomics();
  else if (id === "context" || id.startsWith("context/")) viewContext(Number(id.split("/")[1]) || null);
  else viewHome();
  tkRenderToast();
  if (window.innerWidth <= 760) closeMenu();
}

// ── mobile menu ──────────────────────────────────────────────────────
function openMenu() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

// ── boot ─────────────────────────────────────────────────────────────
async function boot() {
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);
  $("#explorer-scope").addEventListener("click", toggleExplorerScope);
  $("#ctxrail-mini").innerHTML = `${I.window}<span>Model context</span>`;
  $("#ctxrail-toggle").addEventListener("click", toggleCtxRail);
  document.addEventListener("click", (e) => {
    const button = e.target.closest(".unit-view [data-view]");
    if (button) setUnitView(button.dataset.view);
  });
  $("#ctxrail-mini").addEventListener("click", toggleCtxRail);
  syncCtxRailToggle();

  window.addEventListener("hashchange", route);
  await refreshSession();
  route();
  tkPollStatus();                                  // a workload already running shows its notification
  initializeDataExplorer("zth-explorer-height");

  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); }
    catch (_) {}
    const mem = state.health && state.health.memory;
    if (!mem || (!mem.ready && !mem.error)) setTimeout(poll, 1500);
    else {
      if (!state.route) viewHome();
      else if (PART_BY_N[state.route] && !state.busy) loadPage(PART_BY_N[state.route]);
      loadExplorerCatalog();
    }
  }
  poll();
}
boot();
