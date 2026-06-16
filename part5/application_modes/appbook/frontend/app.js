/* ======================================================================
   Application Modes — single-page app
   Vanilla JS. Hash router, theme toggle, SSE-over-fetch streaming, and one
   interactive view per application mode — each with a live memory panel.
   ====================================================================== */

const I = {
  brain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4.5a2.5 2.5 0 0 0-2.5 2.5 2.5 2.5 0 0 0-1 4.8A2.5 2.5 0 0 0 6.5 16 2.5 2.5 0 0 0 9 19.5 2.5 2.5 0 0 0 12 17V6.5 A2 2 0 0 0 9 4.5ZM15 4.5A2.5 2.5 0 0 1 17.5 7a2.5 2.5 0 0 1 1 4.8A2.5 2.5 0 0 1 17.5 16 2.5 2.5 0 0 1 15 19.5 2.5 2.5 0 0 1 12 17"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5M3 16.5 12 21l9-4.5"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12Z"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="6" rx="1.5"/><rect x="14" y="9" width="7" height="6" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/><path d="M10 6h2.5a1.5 1.5 0 0 1 1.5 1.5V9M10 18h2.5a1.5 1.5 0 0 0 1.5-1.5V15"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 16-8-6 16-3-7-7-1Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM9 13h.01M15 13h.01"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  win: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.01"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>',
};

// ── modes ────────────────────────────────────────────────────────────
const MODES = [
  {
    id: "assistant", n: "01", nav: "Assistant", icon: I.chat, accent: "var(--r1)",
    title: "The Assistant", kicker: "Mode 01 — Conversational & reactive",
    desc: "Conversational, reactive, relationship-driven. It operates in an interactive, turn-by-turn loop — request, respond, wait — holding short-term context and retrieving long-term preferences or past interactions when they're relevant.",
    term: "<b>Memory profile: short-term context window + long-term preference retrieval.</b> Each turn recalls the operator's <span class='rec preference'>preference</span> and <span class='rec memory'>memory</span> records from Oracle AI Agent Memory, answers with them, then writes the turn back.",
    meta: { Loop: "request → respond → wait", Memory: "context + preferences", Demo: "Logistics ops copilot" },
  },
  {
    id: "workflow", n: "02", nav: "Workflow", icon: I.flow, accent: "var(--r3)",
    title: "The Workflow", kicker: "Mode 02 — Stateful process execution",
    desc: "Multi-step, goal-oriented, stateful process execution. It follows a structured procedure — plan, execute, verify, complete — branching or retrying when conditions aren't met, like an autonomous worker running a task start to finish.",
    term: "<b>Memory profile: working state + tool outputs.</b> At each stage the pipeline recalls policy (<span class='rec fact'>fact</span> / <span class='rec guideline'>guideline</span>) and writes an audit <span class='rec memory'>memory</span> — a complete, queryable trail.",
    meta: { Loop: "plan → execute → verify", Memory: "working state + tool outputs", Demo: "Mortgage approval pipeline" },
  },
  {
    id: "research", n: "03", nav: "Deep Research", icon: I.search, accent: "var(--r5)",
    title: "Deep Research", kicker: "Mode 03 — Long-horizon investigation",
    desc: "Long-horizon reasoning, synthesis, and multi-source investigation — the most memory-intensive mode. It runs extended investigations that pull from diverse sources, iterating, reflecting, and consolidating knowledge over time.",
    term: "<b>Memory profile: episodic + semantic + working.</b> It recalls prior <span class='rec fact'>fact</span> findings (semantic), searches the web (episodic), saves new findings, and consolidates a running digest (working memory).",
    meta: { Loop: "explore → gather → reflect → synthesise", Memory: "episodic + semantic + working", Demo: "Web research analyst" },
  },
];
const MODE_BY_ID = Object.fromEntries(MODES.map((m) => [m.id, m]));

// ── use-case write-ups (the "Explain this use case" modal) ───────────────
const USE_CASES = {
  assistant: {
    scenario: "A West Coast logistics operations desk. The operator, Morgan, fields questions all day about shipments for customers like Acme Industrial and Belden Foods, and has to answer in each customer's preferred way.",
    dataset: "All synthetic, seeded into Oracle AI Agent Memory at startup: three customer/operator preferences (e.g. Acme wants delay notices by phone) and three operational notes (live shipment statuses such as SHP-1003 delayed to May 14). Nothing is hard-coded into the prompt — it's recalled from memory.",
    usecase: "A conversational copilot. Each turn it RECALLS the preferences and notes relevant to your message, answers using them (honouring, say, a customer's preferred channel), then WRITES the turn back. The conversation thread is its short-term memory; the preference/memory records are its long-term memory — so it stays coherent across a working day and across sessions.",
    records: ["preference", "memory"],
  },
  workflow: {
    scenario: "A regulated mortgage back-office. An underwriter, Alex, runs every application through the same fixed compliance pipeline so that decisions are consistent and auditable.",
    dataset: "Four synthetic applicant fixtures (A-001…A-004, with identity / credit / income / loan figures) plus underwriting policy stored in memory — thresholds as `fact` records and behavioural rules as `guideline` records. In production the fixtures would be live KYC / bureau / payroll API calls.",
    usecase: "A deterministic pipeline — identity → credit → income → DTI → decide — where YOUR CODE owns the control flow (including the conditional short-circuits). At each stage it recalls the relevant policy and writes an audit `memory`. The working state grows stage by stage (that's the context window), and the full audit trail is queryable afterwards.",
    records: ["fact", "guideline", "memory"],
  },
  research: {
    scenario: "A research analyst investigating a topic across many questions and sessions — the demo defaults to BRCA1 genetics, but any question works.",
    dataset: "No fixed dataset: live web results via Tavily, plus the agent's own accumulating findings stored as `fact` records (semantic memory) in Oracle AI Agent Memory. The knowledge base is something the agent builds for itself, run after run.",
    usecase: "The most memory-intensive loop: RECALL prior findings (semantic) → SEARCH the web (episodic) → SYNTHESISE a cited answer → SAVE new findings → CONSOLIDATE a running digest (working memory). Re-ask a related question and watch it build on what it already knows instead of starting from scratch.",
    records: ["fact"],
  },
};

// ── utils ──────────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

function renderRich(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+?)`/g, "<code>$1</code>");
  h = h.replace(/(https?:\/\/[^\s<)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  return h.split(/\n{2,}/).map((p) => "<p>" + p.replace(/\n/g, "<br>") + "</p>").join("");
}

async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body), signal,
  });
  if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
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
async function getJSON(url) { const r = await fetch(url); return r.json(); }

// ── state ──────────────────────────────────────────────────────────────
const state = { health: null, assistantSession: uid(), abort: null, galleries: null, ctx: { window: null, card: null } };
function cancelStream() { if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; } }

// ── sidebar ────────────────────────────────────────────────────────────
function renderSidebar(activeId) {
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" style="--c:var(--text-2);animation-delay:0ms">
       <span class="nav-node">${I.home}</span><span class="nav-label">Overview</span></a>`,
    ...MODES.map((m, i) => `
      <a class="nav-item ${activeId === m.id ? "active" : ""}" href="#/${m.id}" style="--c:${m.accent};animation-delay:${(i + 1) * 55}ms">
        <span class="nav-node">${m.n.replace(/^0/, "")}</span>
        <span class="nav-label">${m.nav}</span>
        <span class="nav-rung">${m.icon}</span></a>`),
  ].join("");

  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.layers}</span>
      <span class="brand-text"><b>Application Modes</b><span>Memory-backed agents</span></span>
    </div>
    <div class="rail-label">The Three Modes</div>
    <nav class="ladder-rail">${items}</nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle">
        <span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span id="theme-label">${themeLabel()}</span></span>
        <span class="toggle-track"></span>
      </button>
    </div>`;
  $("#theme-toggle").addEventListener("click", toggleTheme);
}

function backendLabel() {
  const mem = state.health && state.health.memory;
  if (!mem) return "warming…";
  if (mem.backend === "oracle") return "Oracle AI DB";
  if (mem.backend === "memory") return "in-process";
  return "warming…";
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const mem = h.memory || {};
  const mdot = !mem.ready ? "warn pulse" : "ok";
  const wdot = h.web_search ? "ok" : "off";
  return `
    <div class="status-row"><span class="k">Model</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Memory</span><span class="dot ${mdot}"></span><span>${backendLabel()}</span></div>
    <div class="status-row"><span class="k">Web</span><span class="dot ${wdot}"></span><span>${h.web_search ? "Tavily" : "model-only"}</span></div>`;
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("appmodes-theme", next); } catch (_) {}
  $("#theme-label").textContent = themeLabel();
  $("#theme-toggle").querySelector("svg").outerHTML = themeIcon();
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

// ── shells ─────────────────────────────────────────────────────────────
function modeHeader(m) {
  return `
    <header class="ff-head">
      <div class="ff-numeral">${m.n}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">${esc(m.kicker)}</div>
        <h1 class="ff-title">${esc(m.title)}</h1>
        <p class="ff-desc">${esc(m.desc)}</p>
        <div class="ff-term">${m.term}</div>
        <div class="row" style="margin-top:14px">
          <button class="btn btn-ghost" data-usecase="${m.id}">${I.info} Explain this use case</button>
          <button class="btn btn-ghost" id="open-ctx">${I.win} Context window</button>
        </div>
      </div>
    </header>`;
}

// ── use-case modal ──────────────────────────────────────────────────────
function openUseCase(id) {
  const m = MODE_BY_ID[id], u = USE_CASES[id];
  if (!u) return;
  const recs = (u.records || []).map((r) => `<span class="rec ${r}">${r}</span>`).join("");
  showModal(`
    <div class="modal-card" style="--accent:${m.accent}">
      <div class="modal-head">
        <div><div class="ff-kicker" style="margin:0">${esc(m.kicker)}</div><h2 class="modal-title">${esc(m.title)} · use case</h2></div>
        <button class="btn btn-ghost" id="modal-x">${I.close} Close</button>
      </div>
      <div class="modal-body">
        <section class="uc-sec"><h4>${I.bot} Scenario</h4><p>${esc(u.scenario)}</p></section>
        <section class="uc-sec"><h4>${I.layers} Dataset</h4><p>${esc(u.dataset)}</p>${recs ? `<div class="profile-tags">${recs}</div>` : ""}</section>
        <section class="uc-sec"><h4>${I.brain} Use case &amp; memory loop</h4><p>${esc(u.usecase)}</p></section>
      </div>
    </div>`);
}
function showModal(inner) {
  let m = $("#modal");
  if (!m) { m = document.createElement("div"); m.id = "modal"; m.className = "modal"; document.body.appendChild(m); }
  m.innerHTML = `<div class="modal-scrim" id="modal-scrim"></div>${inner}`;
  requestAnimationFrame(() => m.classList.add("open"));
  $("#modal-scrim").addEventListener("click", closeModal);
  const x = $("#modal-x"); if (x) x.addEventListener("click", closeModal);
}
function closeModal() { const m = $("#modal"); if (m) m.classList.remove("open"); }
function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "var(--r1)");
  stage.innerHTML = `<div class="view view-enter">${html}</div>`;
  stage.scrollTop = 0;
}

// ── memory panel (shared) ──────────────────────────────────────────────
const REC_COLORS = { memory: "var(--rec-memory)", fact: "var(--rec-fact)", guideline: "var(--rec-guideline)", preference: "var(--rec-preference)", context_card: "var(--r4)" };
function memPanel(legendTypes, emptyText) {
  const legend = legendTypes.map((t) => `<span class="rec ${t}">${t}</span>`).join("");
  return `
    <div class="panel mem-panel">
      <div class="panel-head"><span class="panel-title">${I.brain} Memory · <span class="mono" style="color:var(--accent)">${backendLabel()}</span></span></div>
      <div class="mem-legend">${legend}</div>
      <div class="mem-digest" id="mem-digest" hidden></div>
      <div class="mem-scroll" id="mem-scroll"><div class="mem-empty">${esc(emptyText)}</div></div>
    </div>`;
}
function addMem(dir, type, content) {
  const scroll = $("#mem-scroll"); if (!scroll) return;
  if (scroll.querySelector(".mem-empty")) scroll.innerHTML = "";
  const node = document.createElement("div");
  node.className = "mem-event";
  node.style.setProperty("--c", REC_COLORS[type] || "var(--line-2)");
  node.innerHTML = `<div class="mem-top"><span class="mem-dir ${dir === "read" ? "read" : "write"}">${dir === "read" ? "recall" : "write"}</span><span class="rec ${esc(type)}">${esc(type)}</span></div><div class="mem-content">${esc(content)}</div>`;
  scroll.appendChild(node); scroll.scrollTop = scroll.scrollHeight;
}
function setDigest(text) {
  const d = $("#mem-digest"); if (!d) return;
  d.hidden = false;
  d.innerHTML = `<div class="mem-digest-label">${I.brain} Working memory · digest</div>${esc(text)}`;
}

// ── context-window drawer (the collapsible right pane) ──────────────────
const CTX_ROLE_COLORS = {
  system: "var(--text-3)", memory: "var(--rec-fact)", preference: "var(--rec-preference)",
  user: "var(--rec-memory)", assistant: "var(--accent)", state: "#34c759",
  web: "var(--r2)", input: "var(--r4)",
};
const fmtNum = (n) => (+n).toLocaleString();

function ensureCtxDrawer() {
  if ($("#ctx-drawer")) return;
  const drawer = document.createElement("aside");
  drawer.id = "ctx-drawer"; drawer.className = "ctx-drawer";
  drawer.innerHTML = `
    <div class="ctx-head">
      <span class="panel-title">${I.win} Context Window</span>
      <button class="btn btn-ghost" id="ctx-close">${I.close}</button>
    </div>
    <div class="ctx-gauge" id="ctx-gauge"></div>
    <div class="ctx-card" id="ctx-card" hidden></div>
    <div class="ctx-blocks" id="ctx-blocks"><div class="mem-empty">Run a mode to watch its context window fill — in real time, with capacity used vs free.</div></div>`;
  document.body.appendChild(drawer);
  const toggle = document.createElement("button");
  toggle.id = "ctx-toggle"; toggle.className = "ctx-toggle";
  toggle.innerHTML = `<span class="ctx-toggle-label">${I.win} Context</span><span class="ctx-toggle-pct" id="ctx-toggle-pct">—</span>`;
  document.body.appendChild(toggle);
  toggle.addEventListener("click", () => setCtxOpen(!document.body.classList.contains("ctx-open")));
  $("#ctx-close").addEventListener("click", () => setCtxOpen(false));
}
function setCtxOpen(open) {
  document.body.classList.toggle("ctx-open", open);
}
function ctxReset() {
  state.ctx = { window: null, card: null };
  renderCtx();
}
function ctxSetWindow(w) { state.ctx.window = w; renderCtx(); }
function ctxSetCard(c) { state.ctx.card = c; renderCtx(); }

function gaugeHTML(w) {
  if (!w) return `<div class="gauge-empty mono">awaiting a run…</div>`;
  const pct = Math.min(100, (w.used / w.capacity) * 100);
  const pctLabel = pct < 0.1 ? pct.toFixed(2) : pct < 1 ? pct.toFixed(1) : pct.toFixed(0);
  const pre = w.measured ? "" : "≈";
  const badge = w.measured
    ? `<span class="gauge-badge measured">measured · count_tokens</span>`
    : `<span class="gauge-badge est">≈ estimated</span>`;
  return `
    <div class="gauge-top"><div class="gauge-nums"><b>${pre}${fmtNum(w.used)}</b> <span class="muted">/ ${fmtNum(w.capacity)} tokens</span></div>${badge}</div>
    <div class="gauge-bar"><div class="gauge-fill" style="width:${Math.max(pct, 0.5)}%"></div></div>
    <div class="gauge-foot"><span>${pctLabel}% used</span><span>free ${pre}${fmtNum(w.free)}</span></div>
    <div class="gauge-hint">${w.note ? esc(w.note) : "Memory keeps the working context lean — most of a 1M-token window stays free (avoiding “context rot”)."}</div>`;
}
function ctxBlockHTML(b) {
  const c = CTX_ROLE_COLORS[b.role] || "var(--line-2)";
  return `<div class="ctx-block" style="--c:${c}">
    <div class="ctx-block-top"><span class="ctx-role" style="color:${c};border-color:color-mix(in oklab,${c} 45%,transparent)">${esc(b.role)}</span><span class="ctx-label">${esc(b.label)}</span><span class="ctx-tok">≈${fmtNum(b.tokens)}</span></div>
    <div class="ctx-block-body">${esc(b.content)}</div></div>`;
}
function renderCtx() {
  const g = $("#ctx-gauge"); if (!g) return;
  const w = state.ctx.window;
  g.innerHTML = gaugeHTML(w);
  const pctEl = $("#ctx-toggle-pct");
  if (pctEl) {
    if (!w) pctEl.textContent = "—";
    else { const pct = (w.used / w.capacity) * 100; pctEl.textContent = (pct < 1 ? pct.toFixed(1) : pct.toFixed(0)) + "%"; }
  }
  const cardEl = $("#ctx-card");
  if (cardEl) {
    if (state.ctx.card) { cardEl.hidden = false; cardEl.innerHTML = `<div class="ctx-card-label">${I.brain} Context card · consolidated working memory (this turn)</div><div class="ctx-card-body">${esc(state.ctx.card)}</div>`; }
    else cardEl.hidden = true;
  }
  const blocks = $("#ctx-blocks");
  if (blocks) {
    if (!w || !w.blocks || !w.blocks.length) blocks.innerHTML = `<div class="mem-empty">Run a mode to watch its context window fill — in real time, with capacity used vs free.</div>`;
    else blocks.innerHTML = `<div class="ctx-blocks-label">In context · ${w.blocks.length} block${w.blocks.length === 1 ? "" : "s"}</div>` + w.blocks.map(ctxBlockHTML).join("");
  }
}
// route context + context_card SSE events into the drawer (used by every mode)
function handleCtxEvent(ev) {
  if (ev.type === "context") { ctxSetWindow(ev.window); return true; }
  if (ev.type === "context_card") { ctxSetCard(ev.card); return true; }
  return false;
}

// ── view: overview ──────────────────────────────────────────────────────
function viewHome() {
  const rungs = MODES.map((m, i) => `
    <a class="rung" href="#/${m.id}" style="--c:${m.accent};animation-delay:${i * 70 + 80}ms">
      <div class="rung-num">${m.n}</div>
      <div class="rung-main">
        <h3>${esc(m.nav)} <span class="muted" style="font-weight:400;font-size:14px">· ${esc(m.title)}</span></h3>
        <p>${esc(m.desc)}</p>
      </div>
      <div class="rung-meta">
        ${Object.entries(m.meta).map(([k, v]) => `<div class="meta-line"><span class="mk">${k}</span><span class="mv">${esc(v)}</span></div>`).join("")}
      </div>
      <div class="rung-go">${I.arrow}</div>
    </a>`).join("");

  setStage(`
    <section class="hero">
      <div class="hero-kicker"><span class="pip"></span> Application Modes</div>
      <h1>The same agent, three <em>operational modes</em> — each with a different memory profile.</h1>
      <p>How an agent is <b>shaped</b> determines what it must <b>remember</b>. Each mode below is explained and demoed live on <b>Oracle AI Agent Memory</b> — watch the right-hand panel fill as records are recalled and written.</p>
    </section>
    <div class="ladder">${rungs}</div>`, "var(--r1)");
}

// ── view: Assistant ─────────────────────────────────────────────────────
const ASSISTANT_SAMPLES = [
  "What's the latest on Acme's shipments, and how should I tell them?",
  "Belden has a shipment at Newark — anything I should flag on the update?",
  "Give me a rundown of everything that needs attention right now.",
];
function viewAssistant() {
  const m = MODE_BY_ID.assistant;
  setStage(`${modeHeader(m)}
    <div class="grid-main">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.chat} Conversation</span><button class="btn btn-ghost" id="new-chat">${I.refresh} New</button></div>
        <div class="panel-body">
          <div class="chat-wrap">
            <div class="chat-scroll" id="chat-scroll"><div class="empty">Ask the assistant. It recalls preferences &amp; notes before each reply.</div></div>
            <div class="composer">
              <textarea id="chat-input" rows="1" placeholder="Message the assistant…"></textarea>
              <button class="btn btn-accent" id="chat-send">${I.send} Send</button>
            </div>
          </div>
          <div class="chips" style="margin-top:12px">${ASSISTANT_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 42))}…</button>`).join("")}</div>
        </div>
      </div>
      ${memPanel(["preference", "memory"], "Recalled & written records appear here as you chat.")}
    </div>`, m.accent);

  const scroll = $("#chat-scroll"), input = $("#chat-input"), send = $("#chat-send");
  let first = true;
  $$(".chip").forEach((c, i) => c.addEventListener("click", () => { input.value = ASSISTANT_SAMPLES[i]; sendMsg(); }));

  // Seed the memory panel with what's already on file.
  getJSON("/api/assistant/state?session_id=" + state.assistantSession).then((d) => {
    (d.preferences || []).forEach((p) => addMem("read", "preference", p.content));
  }).catch(() => {});

  async function sendMsg() {
    const text = input.value.trim();
    if (!text || state.abort) return;
    if (first) { scroll.innerHTML = ""; first = false; }
    input.value = ""; autosize(input);
    addMsg(scroll, "user", text);
    const bubble = addMsg(scroll, "bot", "");
    bubble.innerHTML = '<span class="caret"></span>';
    send.disabled = true;
    let acc = "";
    ctxReset();
    state.abort = new AbortController();
    try {
      await streamSSE("/api/assistant/message", { session_id: state.assistantSession, message: text }, (ev) => {
        if (handleCtxEvent(ev)) return;
        if (ev.type === "memory_recall") (ev.hits || []).forEach((h) => addMem("read", h.record_type || ev.scope, h.content));
        else if (ev.type === "delta") { acc += ev.text; bubble.innerHTML = renderRich(acc) + '<span class="caret"></span>'; scroll.scrollTop = scroll.scrollHeight; }
        else if (ev.type === "memory_write") addMem("write", ev.record.record_type, ev.record.content);
        else if (ev.type === "done") bubble.innerHTML = renderRich(acc);
      }, state.abort.signal);
    } catch (e) { bubble.innerHTML = `<span style="color:#ef5a44">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; send.disabled = false; input.focus(); }
  }
  send.addEventListener("click", sendMsg);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  input.addEventListener("input", () => autosize(input));
  $("#new-chat").addEventListener("click", () => {
    cancelStream();
    fetch("/api/assistant/reset?session_id=" + state.assistantSession, { method: "POST" }).catch(() => {});
    state.assistantSession = uid();
    route(); // re-render the view fresh
  });
  input.focus();
}
function addMsg(scroll, role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="avatar ${role}">${role === "bot" ? I.bot : "YOU"}</div><div class="bubble">${role === "bot" ? "" : renderRich(text)}</div>`;
  scroll.appendChild(wrap); scroll.scrollTop = scroll.scrollHeight;
  return wrap.querySelector(".bubble");
}
function autosize(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 150) + "px"; }

// ── view: Workflow ──────────────────────────────────────────────────────
const WF_STEPS = { identity: "Identity", credit: "Credit", income: "Income", dti: "DTI ratio", decide: "Decision" };
function viewWorkflow() {
  const m = MODE_BY_ID.workflow;
  setStage(`${modeHeader(m)}
    <div class="panel mb">
      <div class="panel-body">
        <div class="row spread">
          <div class="row"><span class="hint mono">Applicant</span><div class="chips" id="wf-apps"><span class="hint">loading…</span></div></div>
          <button class="btn btn-accent" id="wf-run">${I.play} Run pipeline</button>
        </div>
      </div>
    </div>
    <div class="grid-main">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.flow} Fixed pipeline · your code owns the flow</span><span class="hint mono" id="wf-status"></span></div>
        <div class="panel-body"><div class="pipeline" id="wf-pipe"><div class="empty">Pick an applicant and run the pipeline.</div></div></div>
      </div>
      ${memPanel(["fact", "guideline", "memory"], "Policy recalled and audit records written per stage.")}
    </div>`, m.accent);

  let chosen = "A-001";
  const run = $("#wf-run"), pipe = $("#wf-pipe");
  getJSON("/api/workflow/applicants").then((d) => {
    const box = $("#wf-apps");
    box.innerHTML = (d.applicants || []).map((a, i) => `<button class="chip ${i === 0 ? "active" : ""}" data-id="${a.id}">${a.id} · ${esc(a.name)}</button>`).join("");
    $$("button", box).forEach((b) => b.addEventListener("click", () => {
      $$("button", box).forEach((x) => x.classList.toggle("active", x === b));
      chosen = b.dataset.id;
    }));
  }).catch(() => {});

  run.addEventListener("click", async () => {
    if (state.abort) return;
    pipe.innerHTML = ""; const ms = $("#mem-scroll"); if (ms) ms.innerHTML = '<div class="mem-empty">Policy recalled and audit records written per stage.</div>';
    run.disabled = true; $("#wf-status").textContent = "running…";
    const pending = {};
    ctxReset();
    state.abort = new AbortController();
    try {
      await streamSSE("/api/workflow/run", { applicant_id: chosen }, (ev) => {
        if (handleCtxEvent(ev)) return;
        if (ev.type === "step") {
          if (ev.status === "running") pending[ev.step] = addStage(pipe, ev.step);
          else if (ev.status === "done") { fillStage(pending[ev.step] || addStage(pipe, ev.step), ev.step, ev.data); pending[ev.step] = null; }
        } else if (ev.type === "memory_recall") (ev.hits || []).forEach((h) => addMem("read", h.record_type, h.content));
        else if (ev.type === "memory_write") addMem("write", ev.record.record_type, ev.record.content);
        else if (ev.type === "final") {
          $("#wf-status").textContent = "done";
          const box = document.createElement("div");
          box.className = "stage-row done";
          box.innerHTML = `<div class="stage-rail"><div class="stage-dot">${I.check}</div></div>
            <div class="stage-card" style="border-color:color-mix(in oklab,var(--accent) 30%,transparent)">
              <div class="stage-name">Decision · ${esc(ev.name)} <span class="tag ${esc(ev.decision)}">${esc(ev.decision.replace("_", " "))}</span></div>
              <div class="final-reply">${esc(ev.reason)}${ev.rationale ? "\n\n" + esc(ev.rationale) : ""}</div></div>`;
          pipe.appendChild(box);
        }
      }, state.abort.signal);
    } catch (e) { pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>Error: ${esc(e.message)}</div></div>`); }
    finally { state.abort = null; run.disabled = false; }
  });
}
function addStage(pipe, step) {
  if (pipe.querySelector(".empty")) pipe.innerHTML = "";
  const row = document.createElement("div");
  row.className = "stage-row running";
  row.innerHTML = `<div class="stage-rail"><div class="stage-dot"><span class="spinner"></span></div><div class="stage-line"></div></div>
    <div class="stage-card"><div class="stage-name">${esc(WF_STEPS[step] || step)} <span class="stage-sub">working…</span></div><div class="stage-content"></div></div>`;
  pipe.appendChild(row); return row;
}
function fillStage(row, step, data) {
  if (!row) return;
  row.className = "stage-row done";
  const dot = $(".stage-dot", row), n = Object.keys(WF_STEPS).indexOf(step) + 1;
  dot.textContent = step === "decide" ? "✓" : String(n || "•");
  const name = $(".stage-name", row), content = $(".stage-content", row);
  if (step === "identity") { name.innerHTML = `Identity <span class="stage-sub">KYC</span>`; content.innerHTML = data.verified ? '<span class="tag ok">verified</span>' : '<span class="tag no">failed</span>'; }
  else if (step === "credit") { name.innerHTML = `Credit <span class="stage-sub">bureau</span>`; content.innerHTML = `<span class="kv">score <b>${esc(data.score)}</b></span>`; }
  else if (step === "income") { name.innerHTML = `Income <span class="stage-sub">verified</span>`; content.innerHTML = `<span class="kv">income <b>$${(+data.income).toLocaleString()}</b></span><span class="kv">debt <b>$${(+data.debt).toLocaleString()}</b></span>`; }
  else if (step === "dti") { name.innerHTML = `DTI ratio <span class="stage-sub">computed</span>`; content.innerHTML = `<span class="kv">DTI <b>${(data.dti * 100).toFixed(1)}%</b></span>`; }
  else if (step === "decide") { name.innerHTML = `Decision <span class="stage-sub">gate</span>`; content.innerHTML = `<span class="tag ${esc(data.decision)}">${esc(data.decision.replace("_", " "))}</span> <span class="muted">${esc(data.reason)}</span>`; }
}

// ── view: Deep Research ─────────────────────────────────────────────────
const RESEARCH_SAMPLES = [
  "What is BRCA1 and its role in DNA repair?",
  "What lifetime breast cancer risk is linked to pathogenic BRCA1 variants?",
  "How do BRCA1 and BRCA2 cooperate in homologous recombination?",
];
function viewResearch() {
  const m = MODE_BY_ID.research;
  const noWeb = state.health && !state.health.web_search;
  setStage(`${modeHeader(m)}
    ${noWeb ? `<div class="banner warn">${I.alert}<div>No Tavily key set — research answers from model knowledge + memory only. Set <span class="mono">TAVILY_API_KEY</span> for live web search.</div></div>` : ""}
    <div class="panel mb">
      <div class="panel-body">
        <div class="field">
          <textarea id="rs-input" rows="2" placeholder="Ask a research question…">${esc(RESEARCH_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="rs-run">${I.play} Research</button>
        </div>
        <div class="chips" style="margin-top:12px">${RESEARCH_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 40))}…</button>`).join("")}</div>
        <div class="hint" style="margin-top:8px">Recall prior findings → search the web → synthesise → save findings → consolidate a digest. Re-ask a related question to see it build on memory.</div>
      </div>
    </div>
    <div class="grid-main">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.search} Investigation</span><span class="hint mono" id="rs-status"></span></div>
        <div class="panel-body"><div class="log" id="rs-log"><div class="empty">The research trajectory streams here.</div></div></div>
      </div>
      ${memPanel(["fact"], "Prior findings (recall) and new findings (write) appear here; the digest sits on top.")}
    </div>`, m.accent);

  const input = $("#rs-input"), run = $("#rs-run"), log = $("#rs-log");
  $$(".chip").forEach((c, i) => c.addEventListener("click", () => { input.value = RESEARCH_SAMPLES[i]; autosize(input); }));

  run.addEventListener("click", async () => {
    const question = input.value.trim(); if (!question || state.abort) return;
    log.innerHTML = ""; run.disabled = true; $("#rs-status").innerHTML = '<span class="spinner"></span>';
    let answerBubble = null, acc = "";
    ctxReset();
    state.abort = new AbortController();
    try {
      await streamSSE("/api/research/run", { question }, (ev) => {
        if (handleCtxEvent(ev)) return;
        if (ev.type === "memory_recall") {
          if (ev.hits && ev.hits.length) { logEvent(log, "tool", I.brain, `recall_research_findings → ${ev.hits.length} prior finding(s)`); ev.hits.forEach((h) => addMem("read", "fact", h.content)); }
          else logEvent(log, "tool", I.brain, "recall_research_findings → none yet");
        } else if (ev.type === "tool_use") logEvent(log, "tool", I.globe, `web_search(${esc(JSON.stringify(ev.input.query))})`);
        else if (ev.type === "tool_result") logEvent(log, "result", I.check, ev.text);
        else if (ev.type === "note") logEvent(log, "tool", I.alert, ev.text);
        else if (ev.type === "delta") { if (!answerBubble) answerBubble = logEvent(log, "text", I.bot, ""); acc += ev.text; answerBubble.innerHTML = renderRich(acc); log.scrollTop = log.scrollHeight; }
        else if (ev.type === "memory_write") addMem("write", ev.record.record_type, ev.record.content);
        else if (ev.type === "digest") setDigest(ev.summary);
        else if (ev.type === "done") $("#rs-status").textContent = `${ev.findings_saved} saved · ${ev.prior_recalled} recalled`;
      }, state.abort.signal);
    } catch (e) { logEvent(log, "err", I.alert, e.message); }
    finally { state.abort = null; run.disabled = false; if ($("#rs-status").querySelector(".spinner")) $("#rs-status").textContent = "done"; }
  });
  autosize(input);
}
function logEvent(log, kind, icon, text) {
  if (log.querySelector(".empty")) log.innerHTML = "";
  const node = document.createElement("div");
  node.className = "ev " + kind;
  node.innerHTML = `<div class="ev-icon">${icon}</div><div class="ev-text"><div class="ev-bubble">${kind === "text" ? renderRich(text) : esc(text)}</div></div>`;
  log.appendChild(node); log.scrollTop = log.scrollHeight;
  return node.querySelector(".ev-bubble");
}

// ── router ───────────────────────────────────────────────────────────
// ── concept-diagram gallery (per-page carousel + lightbox) ──────────────
const I_IMAGES = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="14" rx="2.5"/><circle cx="8.5" cy="9" r="1.5"/><path d="m21 14-4.5-4.5L6 20"/></svg>';
const I_GCHEV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
const I_GX = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';
function buildGallery(pageKey) {
  const imgs = (state.galleries || {})[pageKey] || [];
  if (!imgs.length) return null;
  const single = imgs.length === 1;
  const el = document.createElement("section");
  el.className = "gallery" + (single ? " single" : "");
  el.innerHTML = `
    <div class="gallery-head">
      <span class="panel-title">${I_IMAGES} Concept diagrams${single ? "" : ` <span class="gallery-count">${imgs.length}</span>`}</span>
      <button class="gallery-collapse" title="Collapse">${I_GCHEV}</button>
    </div>
    <div class="gallery-main">
      <button class="gallery-nav prev" aria-label="Previous">${I_GCHEV}</button>
      <div class="gallery-stage"><img class="gallery-img" alt="" loading="lazy" title="Click to enlarge"></div>
      <button class="gallery-nav next" aria-label="Next">${I_GCHEV}</button>
    </div>
    <div class="gallery-foot"><span class="gallery-caption"></span><span class="gallery-counter"></span></div>
    <div class="gallery-dots">${single ? "" : imgs.map((_, i) => `<button class="gdot" data-i="${i}" aria-label="Diagram ${i + 1}"></button>`).join("")}</div>`;
  let idx = 0;
  const img = el.querySelector(".gallery-img"), cap = el.querySelector(".gallery-caption"), counter = el.querySelector(".gallery-counter");
  function show(i) {
    idx = (i + imgs.length) % imgs.length;
    img.src = imgs[idx].src; img.alt = imgs[idx].caption;
    cap.textContent = imgs[idx].caption;
    counter.textContent = single ? "" : `${idx + 1} / ${imgs.length}`;
    el.querySelectorAll(".gdot").forEach((d, j) => d.classList.toggle("active", j === idx));
  }
  show(0);
  el.querySelector(".prev").addEventListener("click", () => show(idx - 1));
  el.querySelector(".next").addEventListener("click", () => show(idx + 1));
  el.querySelectorAll(".gdot").forEach((d) => d.addEventListener("click", () => show(+d.dataset.i)));
  el.querySelector(".gallery-collapse").addEventListener("click", () => el.classList.toggle("collapsed"));
  img.addEventListener("click", () => openLightbox(imgs, idx));
  return el;
}
function injectGallery(pageKey) {
  const view = document.querySelector("#stage .view");
  if (!view) return;
  const old = view.querySelector(":scope > .gallery"); if (old) old.remove();
  const g = buildGallery(pageKey); if (!g) return;
  const first = view.firstElementChild;
  if (first) first.insertAdjacentElement("afterend", g); else view.appendChild(g);
}
function openLightbox(imgs, start) {
  let i = start || 0;
  const ov = document.createElement("div"); ov.className = "lightbox";
  ov.innerHTML = `
    <button class="lb-btn lb-close" aria-label="Close">${I_GX}</button>
    <button class="lb-btn lb-prev" aria-label="Previous">${I_GCHEV}</button>
    <figure class="lb-fig"><img alt=""><figcaption></figcaption></figure>
    <button class="lb-btn lb-next" aria-label="Next">${I_GCHEV}</button>`;
  document.body.appendChild(ov);
  const img = ov.querySelector("img"), cap = ov.querySelector("figcaption");
  const show = (n) => { i = (n + imgs.length) % imgs.length; img.src = imgs[i].src; cap.textContent = `${imgs[i].caption}  ·  ${i + 1} / ${imgs.length}`; };
  show(i);
  const close = () => { ov.remove(); document.removeEventListener("keydown", onKey); };
  function onKey(e) { if (e.key === "Escape") close(); else if (e.key === "ArrowLeft") show(i - 1); else if (e.key === "ArrowRight") show(i + 1); }
  ov.querySelector(".lb-close").addEventListener("click", close);
  ov.querySelector(".lb-prev").addEventListener("click", () => show(i - 1));
  ov.querySelector(".lb-next").addEventListener("click", () => show(i + 1));
  ov.addEventListener("click", (e) => { if (e.target === ov) close(); });
  document.addEventListener("keydown", onKey);
  if (imgs.length === 1) ov.querySelectorAll(".lb-prev,.lb-next").forEach((b) => (b.style.display = "none"));
}

const ROUTES = { "": viewHome, assistant: viewAssistant, workflow: viewWorkflow, research: viewResearch };
function route() {
  cancelStream();
  closeModal();
  const id = (location.hash.replace(/^#\/?/, "").trim()) || "";
  const render = ROUTES[id] || viewHome;
  renderSidebar(id || "home");
  render();
  injectGallery(id || "home");
  ctxReset();
  const showCtx = id !== "" && id in ROUTES;  // hide the toggle on the overview
  document.body.classList.toggle("has-ctx", showCtx);
  if (!showCtx) setCtxOpen(false);
  if (window.innerWidth <= 760) closeMenu();
}
function openMenu() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

// ── boot ─────────────────────────────────────────────────────────────
async function boot() {
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);

  ensureCtxDrawer();
  // delegated clicks: per-mode "Explain use case" and "Context window" buttons
  $("#stage").addEventListener("click", (e) => {
    const uc = e.target.closest("[data-usecase]");
    if (uc) { openUseCase(uc.dataset.usecase); return; }
    if (e.target.closest("#open-ctx")) setCtxOpen(true);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); setCtxOpen(false); } });

  window.addEventListener("hashchange", route);
  route();

  getJSON("/api/images").then((d) => { state.galleries = d.pages || {}; injectGallery(location.hash.split("/")[1] || "home"); }).catch(() => {});
  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); } catch (_) {}
    if (!state.health || !state.health.memory || !state.health.memory.ready) setTimeout(poll, 1500);
  }
  poll();
}
boot();
