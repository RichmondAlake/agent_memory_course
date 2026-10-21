/* ======================================================================
   The AI Maturity Ladder — Acme Home Loans
   Vanilla JS. Core: icons, utilities, SSE client, sidebar, overview,
   chatbot, the shared agent log, automations and the Data Explorer.
   Each other rung lives in its own file (rag.js, workflow.js, agent.js,
   builder.js); boot() runs once every file has loaded.
   ====================================================================== */

// ── icons ──────────────────────────────────────────────────────────────
const I = {
  ladder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M7 3v18M17 3v18M7 7h10M7 12h10M7 17h10"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12Z"/></svg>',
  rag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="7" ry="2.7"/><path d="M5 5.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/><path d="M5 11.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="6" rx="1.5"/><rect x="14" y="9" width="7" height="6" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/><path d="M10 6h2.5a1.5 1.5 0 0 1 1.5 1.5V9M10 18h2.5a1.5 1.5 0 0 0 1.5-1.5V15"/></svg>',
  agent: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="7" width="14" height="12" rx="2.5"/><path d="M12 7V4M9 3.5h6M9 12h.01M15 12h.01M9.5 16h5"/></svg>',
  build: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m8 8-4 4 4 4M16 8l4 4-4 4"/><path d="m13.5 5-3 14"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 16-8-6 16-3-7-7-1Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6.5" y="5" width="3.6" height="14" rx="1"/><rect x="13.9" y="5" width="3.6" height="14" rx="1"/></svg>',
  step: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5.5v13l8.5-6.5z" fill="currentColor"/><path d="M18 5v14"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM9 13h.01M15 13h.01"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="m21 16-5-5-9 9"/></svg>',
  memory: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3M9 9h6v6H9z"/></svg>',
  branch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5" r="2.2"/><circle cx="6" cy="19" r="2.2"/><circle cx="18" cy="8" r="2.2"/><path d="M6 7.2v9.6M18 10.2c0 4-6 3.5-11 7"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 6-6 6 6 6"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>',
  window: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M3 9h18M9 9v12"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>',
  space: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="6" cy="16" r="1.6"/><circle cx="11" cy="8" r="1.6"/><circle cx="17" cy="13" r="1.6"/><circle cx="18" cy="5" r="1.6"/><path d="M3 21h18M3 21V3"/></svg>',
};

// ── form factors ─────────────────────────────────────────────────────
const FF = [
  {
    id: "chatbot", rung: 1, nav: "LLM Chatbot", icon: I.chat, accent: "var(--r1)",
    title: "The Chatbot", kicker: "Form Factor 01 — Generate text",
    desc: "An applicant asks, Claude Haiku 5.5 answers. No database, no tools, no retrieval. The memory is the growing list of messages the app resends every turn — watch it grow, and watch a correction get appended instead of applied.",
    term: "<b>LLM:</b> a model trained to predict text. It has no memory between calls, no access to Acme's policy, and no ability to act. Its only memory here is the conversation buffer.",
    limitation: "It cannot know Acme Home Loans' DTI limit or reserve rules. Grounding answers in the lender's own policy needs retrieval — the next rung, RAG.",
    memTypes: ["short-term"],
    memory: "Conversation buffer · Python list, lost on restart",
    meta: { Flow: "You — one call per turn", Data: "Training data only", Memory: "Conversation buffer" },
  },
  {
    id: "rag", rung: 2, nav: "RAG Chatbot", icon: I.rag, accent: "var(--r2)",
    title: "Retrieval-Augmented Generation", kicker: "Form Factor 02 — Ground in your data",
    desc: "The same model, grounded in Acme's seventeen policy sections stored in Oracle AI Database. Retrieve, then generate, with citations. Watch each technique work through the index, explore the embedding space, and update the policy in place.",
    term: "<b>RAG:</b> retrieve the passages relevant to a question, then hand them to the model with the question. Retrieval quality is the biggest lever on answer quality, so every technique is shown step by step.",
    limitation: "It follows one fixed retrieve → generate path. Deciding an application needs several steps — extract, measure, decide, explain, record — wired together by code.",
    memTypes: ["semantic"],
    memory: "Policy knowledge in Oracle · updated in place, with versions",
    meta: { Flow: "You — retrieve → generate", Data: "+ Acme's policy (Oracle)", Memory: "Semantic, versioned" },
  },
  {
    id: "workflow", rung: 3, nav: "LLM Workflow", icon: I.flow, accent: "var(--r3)",
    title: "The Underwriting Workflow", kicker: "Form Factor 03 — Fixed steps, a decision model",
    desc: "Claude reads the emailed application, Python measures it, the open-source Clef decision model approves or declines it against the written policy, a gate refers borderline cases to a person, and every decision is recorded. Run one, or several in parallel.",
    term: "<b>Workflow:</b> your code fixes the sequence; each model does one narrow job. <b>Decision model:</b> Clef returns a probability for every allowed answer in one forward pass — it can only choose among the options you give it.",
    limitation: "It can only follow the path you wired. A returning applicant with changed facts needs steps chosen on the fly — the model picking its own tools as an agent.",
    memTypes: ["episodic"],
    memory: "Applications and decisions in Oracle · appended, never overwritten",
    meta: { Flow: "Your code — fixed steps", Data: "+ Policy + application", Memory: "Episodic decisions" },
  },
  {
    id: "agent", rung: 4, nav: "Tool-Using Agent", icon: I.agent, accent: "var(--r4)",
    title: "The Agent", kicker: "Form Factor 04 — Model-chosen tools",
    desc: "An LLM in a loop with four lender tools: search the policy, read a case history, re-assess with Clef, file a case note. It chooses the path. Its own conversation is a session stored in Oracle — resume it, fork it, or branch from an earlier turn.",
    term: "<b>Agent:</b> an LLM in a tool loop, built on the Claude Agent SDK. <b>Session:</b> the agent's transcript — prompt, tool calls, results, replies — kept by the SDK and mirrored to Oracle by a SessionStore.",
    limitation: "It acts only through the tools you gave it and ends with an answer or a record. Building a reusable program needs file and shell tools.",
    memTypes: ["session", "episodic"],
    memory: "Its own sessions (resume, fork, branch), kept in Oracle as a record of past conversations + the case notes it writes",
    meta: { Flow: "The model — dynamic", Data: "+ Tools over MCP", Memory: "Episodic + session" },
  },
  {
    id: "builder", rung: 5, nav: "Autonomous Agent", icon: I.build, accent: "var(--r5)",
    title: "The Autonomous Agent", kicker: "Form Factor 05 — Write & run code",
    desc: "Chat with an agent that writes and runs Python in a sandbox: it builds tools, draws charts and images, and sets up scheduled automations. Every step lights up the reference architecture. Its sessions survive a refresh, and the tools it builds become procedural memory for later sessions.",
    term: "<b>Autonomous agent:</b> an agent with tools that change the world — files and a shell — confined by a path hook and the OS sandbox. <b>Procedural memory:</b> a tool and its README that later sessions reuse.",
    limitation: "Maximum autonomy brings the most cost, nondeterminism and risk. Use it when a durable artifact is worth strict sandboxing, permissions and verification.",
    memTypes: ["procedural"],
    memory: "Tools and READMEs on disk · procedural, reused by later sessions",
    meta: { Flow: "The model — dynamic", Data: "+ Files & shell", Memory: "Procedural + session" },
  },
];
const FF_BY_ID = Object.fromEntries(FF.map((f) => [f.id, f]));

// ── memory types: the common kinds of memory each rung introduces ────
const MEM_TYPES = {
  "short-term": { label: "Short-term", def: "What the model can see right now: the current conversation, resent every turn." },
  semantic: { label: "Semantic", def: "Facts about the domain that hold whoever asks, kept in a knowledge base. Here: Acme's lending policy." },
  episodic: { label: "Episodic", def: "Records of specific events: what happened, to whom and when. Here: applications, decisions, case notes and stored conversations." },
  session: { label: "Session", def: "One conversation's full transcript, which the agent can continue, resume, fork or branch." },
  procedural: { label: "Procedural", def: "How to do a job: tools, scripts and their instructions, reused by later sessions." },
};
function memBadge(type, compact = false) {
  const m = MEM_TYPES[type];
  return `<span class="mem-badge ${type}" title="${esc(`${m.label} memory: ${m.def}`)}">${I.memory}${esc(compact ? m.label : `${m.label} memory`)}</span>`;
}

// ── tiny utils ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
const pct = (v, d = 1) => (v == null || isNaN(v) ? "—" : (v * 100).toFixed(d) + "%");
const money = (v) => (v == null ? "—" : "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function renderRich(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+?)`/g, "<code>$1</code>");
  h = h.replace(/\[(\d+)\]/g, '<span class="cite">[$1]</span>');
  const blocks = h.split(/\n{2,}/).map((p) => {
    const lines = p.split("\n");
    if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) return "<ul>" + lines.map((l) => "<li>" + l.replace(/^\s*[-•*]\s+/, "") + "</li>").join("") + "</ul>";
    if (lines.length > 1 && lines.every((l) => /^\s*\|.*\|\s*$/.test(l))) return mdTable(lines);
    return "<p>" + p.replace(/\n/g, "<br>") + "</p>";
  });
  return blocks.join("");
}
function mdTable(lines) {
  const rows = lines.filter((l) => !/^\s*\|[\s:-]+\|/.test(l.replace(/[^|:\-\s]/g, "x")) || /[a-z0-9]/i.test(l)).filter((l) => !/^\s*\|(\s*:?-+:?\s*\|)+\s*$/.test(l));
  const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  const [head, ...body] = rows;
  return `<table class="md-table"><thead><tr>${cells(head).map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${body.map((r) => `<tr>${cells(r).map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

// SSE-over-fetch: POST a JSON body, parse the text/event-stream response.
async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok || !res.body) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (_) {}
    throw new Error(detail || "HTTP " + res.status);
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
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(d.detail || "HTTP " + r.status);
  return d;
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "HTTP " + r.status);
  return d;
}
// Async handlers can finish after the user has navigated away, so updates must tolerate missing elements.
function setText(sel, text) { const el = $(sel); if (el) el.textContent = text; }
function setHTML(sel, html) { const el = $(sel); if (el) el.innerHTML = html; }

// ── app state ──────────────────────────────────────────────────────────
const state = { health: null, chatSession: uid(), abort: null, currentRoute: "" };
const explorerState = {
  tables: [], selected: null, result: null, offset: 0, limit: 40,
  events: [], active: new Map(), recent: new Map(), source: null,
  refreshTimer: null, preferredTable: "policy_docs",
};
const SIDEBAR_STORAGE_KEY = "aiml-sidebar";

function cancelStream() {
  if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; }
}

// ── sidebar ──────────────────────────────────────────────────────────
function renderSidebar(activeId) {
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" aria-label="Overview" title="Overview" style="--c:var(--text-2);animation-delay:0ms">
       <span class="nav-node">${I.home}</span><span class="nav-label">Overview</span>
     </a>`,
    ...FF.map((f, i) => `
      <a class="nav-item ${activeId === f.id ? "active" : ""}" href="#/${f.id}" aria-label="${esc(`${f.rung}. ${f.nav}`)}" title="${esc(`${f.rung}. ${f.nav}`)}" style="--c:${f.accent};animation-delay:${(i + 1) * 55}ms">
        <span class="nav-node">${f.rung}</span>
        <span class="nav-label">${f.nav}</span>
        <span class="nav-rung">${f.icon}</span>
      </a>`),
  ].join("");

  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.ladder}</span>
      <span class="brand-text"><b>Maturity Ladder</b><span>Acme Home Loans</span></span>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button" aria-controls="sidebar-nav"></button>
    </div>
    <div class="rail-label">The Ladder</div>
    <nav class="ladder-rail" id="sidebar-nav" aria-label="AI maturity form factors">${items}</nav>
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

function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const rb = h.retrieval || {};
  const db = rb.ready ? "Oracle AI DB" : rb.backend === "unavailable" ? "unavailable" : "starting…";
  const dm = h.decision_model || {};
  const dmText = { ready: "Clef ready", loading: "Clef loading…", "not loaded": "Clef on first use", remote: "Clef (remote)", error: "Clef error" }[dm.status] || "—";
  const dmDot = dm.status === "ready" || dm.status === "remote" ? "ok" : dm.status === "error" ? "off" : dm.status === "loading" ? "warn pulse" : "off";
  return `
    <div class="status-row"><span class="k">Model</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Memory</span><span class="dot ${rb.ready ? "ok" : rb.backend === "unavailable" ? "off" : "warn pulse"}"></span><span>${db}</span></div>
    <div class="status-row"><span class="k">Decision</span><span class="dot ${dmDot}"></span><span>${dmText}</span></div>
    <div class="status-row"><span class="k">Agents</span><span class="dot ${h.agent_available ? "ok" : "off"}"></span><span>${h.agent_available ? "ready" : "CLI not found"}</span></div>`;
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("aiml-theme", next); } catch (_) {}
  $("#theme-label").textContent = themeLabel();
  $("#theme-toggle").querySelector("svg").outerHTML = themeIcon();
  document.dispatchEvent(new CustomEvent("themechange"));
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

// ── header / shells ──────────────────────────────────────────────────
function ffHeader(f) {
  return `
    <header class="ff-head">
      <div class="ff-numeral">${f.rung}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">${esc(f.kicker)}<span class="mem-badges">${f.memTypes.map((t) => memBadge(t)).join("")}</span></div>
        <h1 class="ff-title">${esc(f.title)}</h1>
        <p class="ff-desc">${esc(f.desc)}</p>
        <div class="ff-term">${f.term}</div>
        <div class="ff-row">
          <div class="ff-limit"><span>${f.rung < FF.length ? "Limitation → why climb" : "Limitation → guardrail"}</span>${esc(f.limitation)}</div>
          <div class="ff-memory"><span>${I.memory} Memory this rung adds</span>${esc(f.memory)}</div>
        </div>
      </div>
    </header>`;
}

function setStage(html, accent, wide = true) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "var(--r5)");
  stage.innerHTML = `<div class="view ${wide ? "full" : ""} view-enter">${html}</div>`;
  stage.scrollTop = 0;
}

function needsDB() {
  const h = state.health;
  if (h && h.retrieval && h.retrieval.ready) return "";
  const err = h && h.retrieval && h.retrieval.error;
  return `<div class="banner warn">${I.alert}<div>${err ? `Oracle AI Database is unavailable: <span class="mono">${esc(err)}</span>. Start it with <span class="mono">./oracle.sh start</span> in <span class="mono">part7/</span>, then restart the appbook.` : "Oracle AI Database is still starting; this page fills in as soon as it is ready."}</div></div>`;
}

// ── overview: the ladder with the memory each rung adds ───────────────
const FIG = {
  bubble: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.5 4h15A2.5 2.5 0 0 1 22 6.5v7A2.5 2.5 0 0 1 19.5 16H12l-4.6 3.8A1 1 0 0 1 5.8 19v-3H4.5A2.5 2.5 0 0 1 2 13.5v-7A2.5 2.5 0 0 1 4.5 4Z"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="currentColor"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 8.4c1.6 1.2 4.6 1.9 8 1.9s6.4-.7 8-1.9v4.1c0 1.66-3.58 3-8 3s-8-1.34-8-3V8.4Z" opacity=".82"/><path d="M4 14.9c1.6 1.2 4.6 1.9 8 1.9s6.4-.7 8-1.9V19c0 1.66-3.58 3-8 3s-8-1.34-8-3v-4.1Z" opacity=".64"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M8 11.2 15 6.8M8 12.8l7 4.4"/><circle cx="6" cy="12" r="2.5" fill="currentColor" stroke="none"/><circle cx="17.5" cy="6" r="2.5" fill="currentColor" stroke="none"/><circle cx="17.5" cy="18" r="2.5" fill="currentColor" stroke="none"/></svg>',
  robot: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="3.4" r="1.6"/><rect x="11.2" y="4.2" width="1.6" height="3.4" rx=".8"/><rect x="3.5" y="7" width="17" height="12" rx="4.2"/><rect x="1.6" y="11" width="1.8" height="4.2" rx=".9"/><rect x="20.6" y="11" width="1.8" height="4.2" rx=".9"/><circle cx="9.2" cy="12.8" r="1.75" fill="var(--lad-icon-bg)"/><circle cx="14.8" cy="12.8" r="1.75" fill="var(--lad-icon-bg)"/><rect x="9.2" y="15.6" width="5.6" height="1.5" rx=".75" fill="var(--lad-icon-bg)"/></svg>',
  term: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 8.5 4 3.5-4 3.5"/><path d="M12.5 15.5h6"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h13m-5-6 6 6-6 6"/></svg>',
};
const LADDER_FIG = [
  { id: "chatbot", n: 1, name: "Chatbot", icon: FIG.bubble, desc: "Answers an applicant from training knowledge alone.", mem: "conversation buffer" },
  { id: "rag", n: 2, name: "RAG", icon: FIG.db, desc: "Answers from Acme's lending policy in Oracle, with citations.", mem: "knowledge base, versioned" },
  { id: "workflow", n: 3, name: "Workflow", icon: FIG.flow, tag: "Automation", desc: "Decides an application with the Clef decision model.", mem: "applications + decisions" },
  { id: "agent", n: 4, name: "Agent", icon: FIG.robot, tag: "Autonomy", desc: "Re-assesses a returning applicant with tools it picks.", mem: "sessions + case notes" },
  { id: "builder", n: 5, name: "Autonomous Agent", icon: FIG.term, desc: "Builds, runs and reuses tools in a sandbox.", mem: "tools + READMEs" },
];
function figCard(c, delay) {
  return `<a class="lcard${c.tag ? " has-tag" : ""}" href="#/${c.id}" style="animation-delay:${delay}ms" aria-label="${esc(c.name)}">
      <span class="lcard-num">${c.n}</span>
      ${c.tag ? `<span class="lcard-tag">${esc(c.tag)}</span>` : ""}
      <span class="lcard-icon">${c.icon}</span>
      <span class="lcard-name">${esc(c.name)}</span>
      <span class="lcard-desc">${esc(c.desc)}</span>
      <span class="lcard-mems">${FF_BY_ID[c.id].memTypes.map((t) => memBadge(t, true)).join("")}</span><span class="lcard-memtxt">${esc(c.mem)}</span>
    </a>`;
}

function viewHome() {
  const arrow = `<span class="lfig-arrow" aria-hidden="true">${FIG.arrow}</span>`;
  const figure = `
    <figure class="ladder-fig">
      <figcaption class="lfig-head">
        <div class="lfig-eyebrow">The AI Maturity Ladder · Acme Home Loans</div>
        <h1 class="lfig-title">Five Form Factors, One Mortgage Application</h1>
        <p class="lfig-sub">Climb from a chatbot to an autonomous agent on one job: deciding mortgage applications. Each rung adds one capability — and one kind of memory.</p>
      </figcaption>
      <div class="lfig-track">
        ${figCard(LADDER_FIG[0], 120)}${arrow}${figCard(LADDER_FIG[1], 190)}${arrow}
        <div class="lgroup" style="animation-delay:250ms">${figCard(LADDER_FIG[2], 300)}${figCard(LADDER_FIG[3], 360)}</div>
        ${arrow}${figCard(LADDER_FIG[4], 440)}
      </div>
      <div class="lfig-axis"><span class="lfig-axis-cap">Simpler · Cheaper · Predictable</span><span class="lfig-axis-cap">More Capable · More Autonomous</span></div>
      <div class="lfig-axisline" aria-hidden="true"></div>
    </figure>`;
  const rungs = FF.map((f, i) => `
    <a class="rung" href="#/${f.id}" style="--c:${f.accent};animation-delay:${i * 70 + 160}ms">
      <div class="rung-num">${f.rung}</div>
      <div class="rung-main"><h3>${esc(f.nav)} <span class="muted" style="font-weight:400;font-size:14px">· ${esc(f.title)}</span></h3><p>${esc(f.desc)}</p></div>
      <div class="rung-meta">${Object.entries(f.meta).map(([k, v]) => `<div class="meta-line"><span class="mk">${k}</span><span class="mv">${esc(v)}</span></div>`).join("")}</div>
      <div class="rung-go">${I.arrow}</div>
    </a>`).join("");

  setStage(`
    ${figure}
    <div class="explore-label">Explore each rung — live</div>
    <div class="ladder">${rungs}</div>
    <div class="panel" style="margin-top:34px">
      <div class="panel-head"><span class="panel-title">${I.memory} Memory ledger · how memory updates up the ladder</span>
        <span class="row" style="gap:8px"><button class="btn btn-ghost" id="ledger-refresh">${I.refresh}</button><button class="btn btn-ghost" id="demo-reset">${I.history} Reset demo data</button></span></div>
      <div class="panel-body"><div id="ledger"><div class="empty">Reading the memory stores…</div></div>
        <div class="hint" id="reset-note" style="margin-top:10px">Every store below lives in Oracle AI Database (the sandbox tools are files). Reset rebuilds the tables from the seed: policy back to version 1, no applications, no sessions.</div></div>
    </div>`, "var(--r2)", false);
  loadLedger();
  $("#ledger-refresh").addEventListener("click", loadLedger);
  let armed = false;
  $("#demo-reset").addEventListener("click", async (e) => {
    const b = e.currentTarget;
    if (!armed) { armed = true; b.innerHTML = `${I.alert} Click again to reset`; setTimeout(() => { armed = false; if (b.isConnected) b.innerHTML = `${I.history} Reset demo data`; }, 4000); return; }
    b.disabled = true; b.innerHTML = '<span class="spinner"></span> resetting…';
    try { await postJSON("/api/reset"); setText("#reset-note", "Reset complete: the policy is back to version 1 and every application, decision, note and session is gone."); }
    catch (err) { setText("#reset-note", "Reset failed: " + err.message); }
    finally { b.disabled = false; armed = false; b.innerHTML = `${I.history} Reset demo data`; loadLedger(); }
  });
}
async function loadLedger() {
  const box = $("#ledger"); if (!box) return;
  try {
    const d = await getJSON("/api/memory");
    box.innerHTML = `<table class="data-table"><thead><tr><th>Form factor</th><th>Memory</th><th>Kind</th><th>Lives in</th><th class="num">Items</th><th>Changes by</th></tr></thead><tbody>
      <tr><td>① chatbot</td><td>conversation buffer</td><td><span class="kind short-term">short-term</span></td><td class="mono">Python list (server process)</td><td class="num">per chat</td><td>append every turn; lost on restart</td></tr>
      ${d.ledger.map((r) => `<tr><td>${esc(r.form_factor)}</td><td>${esc(r.memory)}</td><td><span class="kind ${esc(r.kind.split(" ")[0])}">${esc(r.kind)}</span></td><td class="mono">${esc(r.table.includes(" ") ? r.table : "Oracle · " + r.table.toUpperCase())}</td><td class="num">${r.items}</td><td>${esc(r.changes_by)}</td></tr>`).join("")}</tbody></table>`;
  } catch (e) { box.innerHTML = needsDB() || `<div class="empty">${esc(e.message)}</div>`; }
}

// ── view: chatbot (FF1) ─────────────────────────────────────────────────
const CHAT_SYSTEM = "You are a helpful mortgage assistant. Keep answers under 80 words.";
const CTX_WINDOW_DEFAULT = 1000000;
const CHAT_SAMPLES = [
  "Hi! I'm Maya Patel. I earn $8,500 a month and I'm looking at a $420,000 home.",
  "What's my name, and what monthly income did I give you?",
  "Correction: my income is actually $9,200 a month, not $8,500.",
  "Which monthly income will you use for me now, and why?",
  "What is Acme Home Loans' maximum debt-to-income ratio, and how many months of cash reserves must I keep after closing on an investment property?",
];

function viewChatbot() {
  const f = FF_BY_ID.chatbot;
  setStage(`${ffHeader(f)}
    <div class="chat-layout" id="chat-layout">
      <div class="panel chat-panel">
        <div class="panel-head">
          <span class="panel-title">${I.chat} Conversation</span>
          <div class="row" style="gap:8px;flex-wrap:nowrap">
            <button class="btn btn-ghost" id="ctx-show" title="Show the memory">${I.window} Memory</button>
            <button class="btn btn-ghost" id="new-chat">${I.refresh} New chat</button>
          </div>
        </div>
        <div class="panel-body">
          <div class="chat-wrap">
            <div class="chat-scroll" id="chat-scroll"><div class="empty">Say who you are, ask what you said, then correct yourself. Each reply re-sends the whole conversation — that is the memory.</div></div>
            <div class="memory-note" id="mem-note"></div>
            <div class="chips" style="margin:10px 0 12px">${CHAT_SAMPLES.map((s, i) => `<button type="button" class="chip seed-chip" data-chat-sample="${i}" title="${esc(s)}">${i + 1}. ${esc(s.length > 48 ? s.slice(0, 46) + "…" : s)}</button>`).join("")}</div>
            <div class="composer">
              <textarea id="chat-input" placeholder="Message Claude…" rows="1"></textarea>
              <button class="btn btn-accent" id="chat-send">${I.send} Send</button>
            </div>
          </div>
        </div>
      </div>
      <aside class="ctx-pane" id="ctx-pane">
        <div class="ctx-head"><span class="panel-title">${I.window} The memory: everything resent ${memBadge("short-term", true)}</span><button class="ctx-x" id="ctx-hide" title="Collapse">${I.chevron}</button></div>
        <div class="ctx-meter-box">
          <div class="ctx-cap" id="ctx-cap">— / ${CTX_WINDOW_DEFAULT.toLocaleString()} tokens</div>
          <div class="ctx-meter"><div class="ctx-fill" id="ctx-fill"></div></div>
          <div class="ctx-legend"><span><span class="dot-sq used"></span><b id="ctx-used">0</b> used</span><span><span class="dot-sq free"></span><b id="ctx-free">${CTX_WINDOW_DEFAULT.toLocaleString()}</b> free</span></div>
        </div>
        <div class="turn-bars" id="turn-bars"><div class="hint">Input tokens per turn appear here: the bars only grow.</div></div>
        <div class="ctx-note">The buffer only grows. A correction is <b>appended</b> next to the fact it corrects — both are resent, and the model has to work out which is current.</div>
        <div class="ctx-list" id="ctx-list"></div>
      </aside>
    </div>`, f.accent);

  const scroll = $("#chat-scroll"), input = $("#chat-input"), send = $("#chat-send"), layout = $("#chat-layout");
  let first = true;
  const ctx = [{ role: "system", text: CHAT_SYSTEM }];
  const turnTokens = [];
  const estTok = (s) => Math.max(1, Math.ceil((s || "").length / 4));
  const facts = (t) => (t.match(/\$[\d,]+(?:\.\d+)?/g) || []);

  function renderCtx(tokens, win) {
    const seen = new Map();
    ctx.forEach((m, i) => facts(m.text).forEach((v) => { if (m.role === "user") seen.set(v, (seen.get(v) || []).concat(i)); }));
    $("#ctx-list").innerHTML = ctx.map((m) => {
      let text = esc(m.text);
      if (m.role === "user") facts(m.text).forEach((v) => { text = text.split(esc(v)).join(`<mark>${esc(v)}</mark>`); });
      return `<div class="ctx-msg ${m.role}"><div class="ctx-msg-top"><span class="ctx-role">${m.role}</span><span class="ctx-tok">~${estTok(m.text)} tok</span></div><div class="ctx-text">${text}</div></div>`;
    }).join("");
    const list = $("#ctx-list"); list.scrollTop = list.scrollHeight;
    if (tokens != null) {
      win = win || CTX_WINDOW_DEFAULT;
      const p = Math.min(100, (tokens / win) * 100);
      $("#ctx-fill").style.width = (tokens > 0 ? Math.max(p, 0.6) : 0) + "%";
      $("#ctx-used").textContent = tokens.toLocaleString();
      $("#ctx-free").textContent = Math.max(0, win - tokens).toLocaleString();
      $("#ctx-cap").textContent = `${tokens.toLocaleString()} / ${win.toLocaleString()} tokens · ${p < 1 ? p.toFixed(3) : p.toFixed(1)}% used`;
    }
    if (turnTokens.length) {
      const max = Math.max(...turnTokens);
      $("#turn-bars").innerHTML = `<div class="tb-title">Input tokens sent, per turn</div>` + turnTokens.map((t, i) =>
        `<div class="tb-row"><span class="tb-k">turn ${i + 1}</span><span class="tb-bar"><i style="width:${Math.max(4, (t / max) * 100)}%"></i></span><span class="tb-v">${t.toLocaleString()}</span></div>`).join("");
    }
  }
  renderCtx(0, CTX_WINDOW_DEFAULT);

  const showCtx = (open) => layout.classList.toggle("ctx-closed", !open);
  $("#ctx-hide").addEventListener("click", () => showCtx(false));
  $("#ctx-show").addEventListener("click", () => showCtx(true));
  $$("[data-chat-sample]").forEach((b) => b.addEventListener("click", () => { input.value = CHAT_SAMPLES[+b.dataset.chatSample]; autosize(input); input.focus(); }));

  async function sendMsg() {
    const text = input.value.trim();
    if (!text || state.abort) return;
    if (first) { scroll.innerHTML = ""; first = false; }
    input.value = ""; autosize(input);
    addMsg(scroll, "user", text);
    ctx.push({ role: "user", text }); renderCtx();
    const bubble = addMsg(scroll, "bot", "");
    bubble.innerHTML = '<span class="caret"></span>';
    send.disabled = true;
    let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/chat/message", { session_id: state.chatSession, message: text }, (ev) => {
        if (ev.type === "delta") { acc += ev.text; bubble.innerHTML = renderRich(acc) + '<span class="caret"></span>'; scroll.scrollTop = scroll.scrollHeight; }
        else if (ev.type === "done") {
          bubble.innerHTML = renderRich(acc);
          turnTokens.push(ev.input_tokens || 0);
          $("#mem-note").innerHTML = `memory: <b>${ev.turns}</b> messages · this turn sent <b>${(ev.input_tokens || 0).toLocaleString()}</b> input tokens · the next turn will send <b>${(ev.context_tokens || 0).toLocaleString()}</b>`;
          ctx.push({ role: "assistant", text: acc });
          renderCtx(ev.context_tokens, ev.context_window);
        }
      }, state.abort.signal);
    } catch (e) { bubble.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; send.disabled = false; input.focus(); }
  }
  send.addEventListener("click", sendMsg);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  input.addEventListener("input", () => autosize(input));
  $("#new-chat").addEventListener("click", async () => {
    cancelStream();
    await fetch("/api/chat/reset?session_id=" + state.chatSession, { method: "POST" }).catch(() => {});
    state.chatSession = uid();
    scroll.innerHTML = `<div class="empty">New conversation. The previous buffer is gone — nothing was stored anywhere else.</div>`;
    $("#mem-note").innerHTML = ""; first = true; turnTokens.length = 0;
    $("#turn-bars").innerHTML = '<div class="hint">Input tokens per turn appear here: the bars only grow.</div>';
    ctx.length = 0; ctx.push({ role: "system", text: CHAT_SYSTEM }); renderCtx(0, CTX_WINDOW_DEFAULT);
  });
  input.focus();
}

function addMsg(scroll, role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="avatar ${role}">${role === "bot" ? I.bot : "YOU"}</div><div class="bubble">${role === "bot" ? "" : renderRich(text)}</div>`;
  scroll.appendChild(wrap);
  scroll.scrollTop = scroll.scrollHeight;
  return wrap.querySelector(".bubble");
}
function autosize(el, max = 160) { if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, max) + "px"; } }

// ── shared agent log (FF4 & FF5) ───────────────────────────────────────
function toolLabel(name) { return (name || "").replace(/^mcp__\w+?__/, ""); }
function argsPreview(input, limit = 160) {
  const s = Object.entries(input || {}).map(([k, v]) => `${k}=${typeof v === "string" ? JSON.stringify(v.length > 80 ? v.slice(0, 78) + "…" : v) : JSON.stringify(v)}`).join(", ");
  return s.length > limit ? s.slice(0, limit) + "…" : s;
}
function addEvent(log, ev) {
  if (log.querySelector(".empty")) log.innerHTML = "";
  const node = document.createElement("div");
  if (ev.type === "text") {
    if (!ev.text || !ev.text.trim()) return null;
    node.className = "ev text"; node.innerHTML = `<div class="ev-icon">${I.bot}</div><div class="ev-text"><div class="ev-bubble">${renderRich(ev.text)}</div></div>`;
  } else if (ev.type === "tool_use") {
    node.className = "ev tool"; node.dataset.toolId = ev.id || "";
    node.innerHTML = `<div class="ev-icon">${I.tool}</div><div class="ev-text"><details class="ev-bubble"><summary><span class="tname">${esc(toolLabel(ev.name))}</span>(<span class="tool-args">${esc(argsPreview(ev.input))}</span>)</summary><pre class="ev-pre">${esc(JSON.stringify(ev.input, null, 2))}</pre><div class="ev-result" hidden></div></details></div>`;
  } else if (ev.type === "tool_result") {
    const owner = ev.id && log.querySelector(`.ev.tool[data-tool-id="${CSS.escape(ev.id)}"] .ev-result`);
    if (owner) { owner.hidden = false; owner.innerHTML = `<div class="ev-result-head">${ev.is_error ? "error" : "result"}</div><pre class="ev-pre">${esc((ev.text || "").slice(0, 3000))}</pre>`; owner.closest(".ev").classList.toggle("errored", !!ev.is_error); return owner; }
    node.className = "ev result"; node.innerHTML = `<div class="ev-icon">${I.check}</div><div class="ev-text"><div class="ev-bubble mono" style="font-size:12.5px;white-space:pre-wrap">${esc((ev.text || "").slice(0, 1200))}</div></div>`;
  } else if (ev.type === "hook") {
    node.className = "ev hook " + ev.decision;
    node.innerHTML = `<div class="ev-icon">${ev.decision === "deny" ? I.cross : I.check}</div><div class="ev-text"><div class="ev-meta">PreToolUse hook · <b>${esc(ev.tool)}</b> ${ev.decision === "deny" ? "denied" : "allowed"} · <span class="mono">${esc(ev.path || "")}</span>${ev.decision === "deny" ? ` · ${esc(ev.reason || "")}` : ""}</div></div>`;
  } else if (ev.type === "result") {
    const bits = [];
    if (ev.num_turns != null) bits.push(`${ev.num_turns} turns`);
    if (ev.duration_ms != null) bits.push(`${(ev.duration_ms / 1000).toFixed(1)}s`);
    if (ev.cost_usd != null) bits.push(`$${(+ev.cost_usd).toFixed(4)}`);
    if (ev.session_id) bits.push(`session ${ev.session_id.slice(0, 8)}…`);
    node.className = "ev result"; node.innerHTML = `<div class="ev-icon">${I.check}</div><div class="ev-text"><div class="ev-meta">${esc(ev.subtype === "success" ? "agent finished" : ev.subtype || "finished")} · ${bits.join(" · ") || "ok"}</div></div>`;
  } else if (ev.type === "error") {
    node.className = "ev err"; node.innerHTML = `<div class="ev-icon">${I.alert}</div><div class="ev-text"><div class="ev-bubble">${esc(ev.message)}</div></div>`;
  } else return null;
  log.appendChild(node); log.scrollTop = log.scrollHeight; return node;
}
function agentBanner() {
  return `<div class="banner warn">${I.alert}<div>The Claude Agent SDK isn't installed, so Form Factors 4 &amp; 5 are disabled. Install it with <span class="mono">pip install claude-agent-sdk</span> (the wheel bundles the <span class="mono">claude</span> CLI) and restart the server.</div></div>`;
}
function fmtWhen(ms) {
  if (!ms) return "";
  const d = new Date(ms);
  const today = new Date();
  return d.toDateString() === today.toDateString() ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ── automations (FF5): run now / schedule / runs history ────────────────
function fmtTime(epoch) {
  try { return new Date(epoch * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch (_) { return ""; }
}
async function loadAutomations() {
  const box = $("#au-list"); if (!box) return;
  let d; try { d = await getJSON("/api/builder/automations"); } catch (_) { return; }
  if (!d.automations || !d.automations.length) { box.innerHTML = `<div class="empty">No automations yet — ask the agent to set one up.</div>`; return; }
  box.innerHTML = d.automations.map(autoRow).join("");
  $$(".auto", box).forEach(wireAuto);
}
function autoRow(a) {
  const last = a.last_run;
  const lastTxt = last ? (last.ok ? `ran ${fmtTime(last.time)}` : `failed ${fmtTime(last.time)}`) : "never run";
  const lastCls = last ? (last.ok ? "ok" : "fail") : "muted";
  const next = a.next_run ? ` · next ${fmtTime(a.next_run)}` : "";
  const t = a.schedule.type || "manual";
  return `<div class="auto" data-id="${a.id}">
    <div class="auto-top"><span class="auto-name">${esc(a.name)}</span><span class="auto-sched mono">${esc(a.schedule_label)}${next}</span><span class="auto-last ${lastCls}">${lastTxt}</span></div>
    <div class="auto-cmd mono">$ ${esc(a.command)}</div>
    <div class="auto-actions">
      <button class="btn btn-accent au-run">${I.play} Run now</button>
      <span class="au-sched-ctl">
        <select class="au-type">
          <option value="manual"${t === "manual" ? " selected" : ""}>Manual</option>
          <option value="once"${t === "once" ? " selected" : ""}>Once, in</option>
          <option value="interval"${t === "interval" ? " selected" : ""}>Every</option>
          <option value="daily"${t === "daily" ? " selected" : ""}>Daily at</option>
        </select>
        <input class="au-num" type="number" min="1" value="${a.schedule.every_minutes || a.schedule.delay_minutes || 5}">
        <input class="au-at" type="time" value="${a.schedule.at || "08:00"}">
        <span class="au-unit hint">min</span>
        <button class="btn btn-ghost au-set">Set</button>
      </span>
      <button class="btn btn-ghost au-runs">Runs (${a.run_count})</button>
      <button class="btn btn-ghost au-del" title="Delete">${I.cross}</button>
    </div>
    <div class="auto-runs" hidden></div>
  </div>`;
}
function wireAuto(el) {
  const id = el.dataset.id;
  const type = el.querySelector(".au-type"), num = el.querySelector(".au-num"), at = el.querySelector(".au-at"), unit = el.querySelector(".au-unit");
  function sync() { const t = type.value, showNum = t === "interval" || t === "once"; num.hidden = !showNum; unit.hidden = !showNum; at.hidden = t !== "daily"; }
  sync();
  type.addEventListener("change", sync);
  el.querySelector(".au-run").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true; b.innerHTML = `<span class="spinner"></span> running`;
    try { await fetch(`/api/builder/automations/${id}/run`, { method: "POST" }); } catch (_) {}
    await loadAutomations(); document.dispatchEvent(new CustomEvent("sandboxchange"));
  });
  el.querySelector(".au-set").addEventListener("click", async () => {
    const body = { type: type.value, every_minutes: +num.value || 5, delay_minutes: +num.value || 5, at: at.value || "08:00" };
    try { await fetch(`/api/builder/automations/${id}/schedule`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); } catch (_) {}
    await loadAutomations();
  });
  el.querySelector(".au-del").addEventListener("click", async () => { try { await fetch(`/api/builder/automations/${id}`, { method: "DELETE" }); } catch (_) {} await loadAutomations(); });
  el.querySelector(".au-runs").addEventListener("click", async () => {
    const panel = el.querySelector(".auto-runs");
    if (!panel.hidden) { panel.hidden = true; return; }
    let d; try { d = await getJSON(`/api/builder/automations/${id}/runs`); } catch (_) { return; }
    panel.innerHTML = d.runs.length ? d.runs.map(runRow).join("") : `<div class="hint" style="padding:8px">No runs yet.</div>`;
    panel.hidden = false;
  });
}
function runRow(r) {
  return `<div class="run ${r.ok ? "ok" : "fail"}">
    <div class="run-top"><span class="run-dot"></span><span class="run-when mono">${fmtTime(r.time)}</span><span class="run-trigger">${esc(r.trigger)}</span><span class="run-status">${r.ok ? "ok" : "exit " + r.exit_code}</span></div>
    ${r.output ? `<pre class="run-out">${esc(r.output.slice(0, 400))}</pre>` : ""}
  </div>`;
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
  if (Number.isFinite(saved) && saved >= 220) document.documentElement.style.setProperty("--explorer-height", `${Math.min(saved, window.innerHeight - 80)}px`);
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
    $("#explorer-summary").textContent = `${explorerState.tables.length} tables · ${totalRows.toLocaleString()} rows · ${payload.backend}${payload.schema ? ` · ${payload.schema}` : ""}`;
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
    $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(error.message)}</div>`;
  } finally { refresh.disabled = false; }
}
function renderExplorerTables() {
  const filter = ($("#explorer-filter").value || "").toLowerCase();
  const visible = explorerState.tables.filter((table) => !filter || `${table.name} ${table.layer}`.toLowerCase().includes(filter));
  $("#explorer-table-list").innerHTML = visible.map((table) => {
    const key = table.name.toLowerCase();
    const event = explorerState.active.get(key);
    const recent = explorerState.recent.get(key);
    const pulse = event ? `tx-${opClass(event.operation)}` : recent ? `flash-${opClass(recent.operation)}` : "";
    return `<button class="explorer-table-item ${explorerState.selected === table.name ? "selected" : ""} ${pulse}" data-explorer-table="${esc(table.name)}" title="${esc(table.layer)}">
      <span><i></i>${esc(table.name)}</span><b>${table.row_count < 0 ? "—" : Number(table.row_count).toLocaleString()}</b>
      ${event ? `<em>${esc(event.operation)}</em>` : ""}
    </button>`;
  }).join("") || '<div class="explorer-empty">No matching tables.</div>';
  $("#explorer-table-list").querySelectorAll("[data-explorer-table]").forEach((button) => button.addEventListener("click", () => selectExplorerTable(button.dataset.explorerTable)));
}
function opClass(operation) { return operation === "READ" ? "read" : "write"; }
async function selectExplorerTable(name, offset = 0) {
  explorerState.selected = name;
  explorerState.offset = offset;
  renderExplorerTables();
  $("#explorer-grid").innerHTML = '<div class="explorer-empty">Reading rows…</div>';
  try {
    explorerState.result = await explorerJSON(`/api/data_explorer/tables/${encodeURIComponent(name)}/rows?limit=${explorerState.limit}&offset=${offset}`);
    renderExplorerRows();
  } catch (error) { $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(error.message)}</div>`; }
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
function renderExplorerRows() {
  const data = explorerState.result;
  if (!data) return;
  const table = explorerState.tables.find((item) => item.name.toLowerCase() === data.table.toLowerCase());
  $("#explorer-layer").textContent = `${table?.layer || "database"} · ${data.columns.length} columns`;
  $("#explorer-table-name").textContent = data.table;
  const knownTotal = data.row_count >= 0;
  const start = data.rows.length ? data.offset + 1 : 0;
  const end = data.offset + data.rows.length;
  $("#explorer-page").textContent = knownTotal ? `${start.toLocaleString()}–${end.toLocaleString()} of ${Number(data.row_count).toLocaleString()}` : `${start.toLocaleString()}–${end.toLocaleString()}`;
  $("#explorer-prev").disabled = data.offset === 0;
  $("#explorer-next").disabled = knownTotal ? end >= data.row_count : data.rows.length < data.limit;
  if (!data.columns.length) { $("#explorer-grid").innerHTML = '<div class="explorer-empty">This table has no discoverable columns.</div>'; return; }
  const key = data.table.toLowerCase();
  const event = explorerState.active.get(key);
  const recent = explorerState.recent.get(key);
  const pulse = event || recent;
  const pulseClass = pulse ? `${event ? "tx" : "flash"}-${opClass(pulse.operation)}` : "";
  const head = data.columns.map((column) => `<th><span>${esc(column.name)}</span><small>${esc(column.type)}${column.primary_key ? " · PK" : ""}</small></th>`).join("");
  const body = data.rows.map((row, index) => {
    const rowPulse = pulse && (!pulse.row_key || pulse.row_key === data.row_keys[index]) ? pulseClass : "";
    const cells = data.columns.map((column) => `<td title="${esc(explorerCellText(row[column.name]))}">${formatExplorerCell(row[column.name])}</td>`).join("");
    return `<tr class="${rowPulse}" data-row-key="${esc(data.row_keys[index])}">${cells}</tr>`;
  }).join("");
  $("#explorer-grid").innerHTML = data.rows.length ? `<table class="explorer-data-table ${pulseClass}"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` : '<div class="explorer-empty">The table is currently empty.</div>';
}
function onExplorerTransaction(event) {
  explorerState.events.unshift(event);
  explorerState.events = explorerState.events.slice(0, 40);
  const table = event.table.toLowerCase();
  if (event.status === "active") explorerState.active.set(table, event);
  else {
    if (explorerState.active.get(table)?.transaction_id === event.transaction_id) explorerState.active.delete(table);
    explorerState.recent.set(table, event);
    setTimeout(() => {
      if (explorerState.recent.get(table)?.transaction_id === event.transaction_id) {
        explorerState.recent.delete(table);
        renderExplorerTables();
        if (explorerState.result?.table.toLowerCase() === table) renderExplorerRows();
      }
    }, 1400);
    if (event.status === "committed" && event.operation !== "READ") {
      clearTimeout(explorerState.refreshTimer);
      explorerState.refreshTimer = setTimeout(async () => {
        if (!explorerState.tables.length) return;
        const selected = explorerState.selected;
        await loadExplorerCatalog();
        if (selected && selected.toLowerCase() === table) await selectExplorerTable(selected, 0);
      }, 300);
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
    `<div class="explorer-activity-event ${event.status} ${opClass(event.operation)}"><i></i><div>
      <strong>${esc(event.operation)} <span>${esc(event.table)}</span> <em>${esc(event.status.replace("_", " "))}</em></strong>
      <small>${esc(event.route)} · ${esc(event.detail || event.status)}</small>
    </div><time>${new Date(event.occurred_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>`
  ).join("") || '<div class="explorer-empty">Waiting for database activity…</div>';
}
function connectExplorerActivity() {
  if (explorerState.source) explorerState.source.close();
  const source = new EventSource("/api/data_explorer/activity");
  explorerState.source = source;
  source.addEventListener("transaction", (event) => { try { onExplorerTransaction(JSON.parse(event.data)); } catch (_) {} });
  source.addEventListener("ready", () => { $("#explorer-live-label").textContent = "Live transactions"; });
  source.onerror = () => { $("#explorer-live-label").textContent = "Reconnecting…"; };
}
async function loadRecentExplorerActivity() {
  try { const payload = await explorerJSON("/api/data_explorer/activity/recent"); explorerState.events = payload.events || []; renderExplorerActivity(); } catch (_) {}
}
function initializeDataExplorer(storageKey) {
  $("#explorer-toggle").addEventListener("click", () => toggleExplorer());
  $("#explorer-refresh").addEventListener("click", loadExplorerCatalog);
  $("#explorer-filter").addEventListener("input", renderExplorerTables);
  $("#explorer-prev").addEventListener("click", () => selectExplorerTable(explorerState.selected, Math.max(0, explorerState.offset - explorerState.limit)));
  $("#explorer-next").addEventListener("click", () => selectExplorerTable(explorerState.selected, explorerState.offset + explorerState.limit));
  initializeExplorerResize(storageKey);
  connectExplorerActivity();
  loadRecentExplorerActivity();
  loadExplorerCatalog();
}

// ── router ───────────────────────────────────────────────────────────
function routes() {
  return { "": viewHome, chatbot: viewChatbot, rag: viewRAG, workflow: viewWorkflow, agent: viewAgent, builder: viewBuilder };
}
function route() {
  cancelStream();
  document.dispatchEvent(new CustomEvent("routechange"));
  const id = (location.hash.replace(/^#\/?/, "").split("?")[0].trim()) || "";
  const render = routes()[id] || viewHome;
  state.currentRoute = id || "home";
  renderSidebar(id || "home");
  render();
  if (window.innerWidth <= 760) closeMenu();
}

// ── mobile menu ──────────────────────────────────────────────────────
function openMenu() { $("#sidebar").classList.add("open"); const s = $("#scrim"); s.hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

// ── boot (after every page module has loaded) ─────────────────────────
async function boot() {
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);
  window.addEventListener("hashchange", route);
  route();
  initializeDataExplorer("aiml-explorer-height");
  let rendered = false;
  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); } catch (_) {}
    const ready = state.health && state.health.retrieval && state.health.retrieval.ready;
    if (ready && !rendered && $(".banner.warn") && /still starting/.test($(".banner.warn").textContent)) { rendered = true; route(); }
    setTimeout(poll, ready && state.health.decision_model.status !== "loading" ? 10000 : 1500);
  }
  poll();
}
window.addEventListener("DOMContentLoaded", boot);
