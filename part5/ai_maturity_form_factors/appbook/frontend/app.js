/* ======================================================================
   The AI Maturity Ladder — single-page app
   Vanilla JS. Hash router, theme toggle, SSE-over-fetch streaming client,
   and one interactive view per form factor.
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
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM9 13h.01M15 13h.01"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
};

// ── form factors ─────────────────────────────────────────────────────
const FF = [
  {
    id: "chatbot", rung: 1, nav: "LLM Chatbot", icon: I.chat, accent: "var(--r1)",
    title: "The Chatbot", kicker: "Form Factor 01 — Generate text",
    desc: "The simplest useful thing you can build with Claude: send a question, get an answer. No database, no tools, no retrieval. Memory is just the growing list of messages you resend each turn.",
    term: "<b>LLM (Large Language Model):</b> a model trained to predict text. On its own it has no memory between calls, no access to your data, and no ability to act. It maps a prompt to a response — nothing more.",
    meta: { Flow: "You — one call", Data: "Training data only", Acts: "No" },
  },
  {
    id: "rag", rung: 2, nav: "RAG Chatbot", icon: I.rag, accent: "var(--r2)",
    title: "Retrieval-Augmented Generation", kicker: "Form Factor 02 — Ground in your data",
    desc: "The same LLM, now grounded in Acme Cloud's real documentation stored in Oracle AI Database. Retrieve the relevant docs first, then hand them to the model with the question — answers reflect real data, with citations.",
    term: "<b>RAG:</b> retrieve the documents relevant to a question, then hand them to the LLM alongside the question. Retrieval quality is the single biggest lever on answer quality — compare vector, keyword, and hybrid below.",
    meta: { Flow: "You — retrieve → generate", Data: "+ Your documents", Acts: "No" },
  },
  {
    id: "workflow", rung: 3, nav: "LLM Workflow", icon: I.flow, accent: "var(--r3)",
    title: "The LLM-Driven Workflow", kicker: "Form Factor 03 — Reliable pipelines",
    desc: "Several LLM calls and ordinary code composed into a fixed, predictable pipeline: classify → route → retrieve → draft → review-and-revise. Your code owns the sequence; the model fills in each step.",
    term: "<b>Workflow:</b> the steps are decided by you, in code. Breaking a task into small, single-purpose steps with checks between them yields far more consistent results than one big do-everything prompt.",
    meta: { Flow: "Your code — fixed steps", Data: "+ Your documents", Acts: "Within the pipeline" },
  },
  {
    id: "agent", rung: 4, nav: "Autonomous Agent", icon: I.agent, accent: "var(--r4)",
    title: "The Agent", kicker: "Form Factor 04 — Model-chosen tools",
    desc: "An LLM running in a loop with tools. The model decides which tool to call, inspects the result, and decides what to do next — repeating until the job is done. We give it two tools (search the docs, open a ticket) and a goal.",
    term: "<b>Agent:</b> an LLM in a loop with tools. Unlike a workflow, the model chooses the trajectory. Built on the <code>claude-agent-sdk</code> — the same runtime that powers Claude Code.",
    meta: { Flow: "The model — dynamic", Data: "+ Tools you provide", Acts: "Via tools" },
  },
  {
    id: "builder", rung: 5, nav: "Agent That Builds", icon: I.build, accent: "var(--r5)",
    title: "The Autonomous Agent", kicker: "Form Factor 05 — Write & run code",
    desc: "The top rung: an agent equipped with file and shell tools that doesn't just answer — it writes a script, runs it, and fixes its own errors until it works. It produces durable automation, all on its own.",
    term: "<b>Autonomous agent:</b> an agent with tools that change the world — here, writing files and running shell commands inside a sandbox. From answering to building.",
    meta: { Flow: "The model — dynamic", Data: "+ Files & shell", Acts: "Yes — writes & runs code" },
  },
];
const FF_BY_ID = Object.fromEntries(FF.map((f) => [f.id, f]));

// ── tiny utils ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

function renderRich(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+?)`/g, "<code>$1</code>");
  h = h.replace(/\[(\d+)\]/g, '<span class="cite">[$1]</span>');
  return h.split(/\n{2,}/).map((p) => "<p>" + p.replace(/\n/g, "<br>") + "</p>").join("");
}

// SSE-over-fetch: POST a JSON body, parse the text/event-stream response.
async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
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

// ── app state ──────────────────────────────────────────────────────────
const state = {
  health: null,
  chatSession: uid(),
  abort: null, // current streaming AbortController
  galleries: null, // page -> [{src, caption}] concept diagrams
  currentRoute: "",
};

function cancelStream() {
  if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; }
}

// ── sidebar ──────────────────────────────────────────────────────────
function renderSidebar(activeId) {
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" style="--c:var(--text-2);animation-delay:0ms">
       <span class="nav-node">${I.home}</span><span class="nav-label">Overview</span>
     </a>`,
    ...FF.map((f, i) => `
      <a class="nav-item ${activeId === f.id ? "active" : ""}" href="#/${f.id}" style="--c:${f.accent};animation-delay:${(i + 1) * 55}ms">
        <span class="nav-node">${f.rung}</span>
        <span class="nav-label">${f.nav}</span>
        <span class="nav-rung">${f.icon}</span>
      </a>`),
  ].join("");

  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.ladder}</span>
      <span class="brand-text"><b>Maturity Ladder</b><span>Five AI form factors</span></span>
    </div>
    <div class="rail-label">The Ladder</div>
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

function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const rb = h.retrieval || {};
  const ready = rb.ready;
  const backend = rb.backend === "oracle" ? "Oracle AI DB" : rb.backend === "memory" ? "In-memory" : "warming…";
  const rdot = !ready ? "warn pulse" : "ok";
  const adot = h.agent_available ? "ok" : "off";
  return `
    <div class="status-row"><span class="k">Model</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Retrieval</span><span class="dot ${rdot}"></span><span>${backend}</span></div>
    <div class="status-row"><span class="k">Agents</span><span class="dot ${adot}"></span><span>${h.agent_available ? "ready" : "CLI not found"}</span></div>`;
}

function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("aiml-theme", next); } catch (_) {}
  $("#theme-label").textContent = themeLabel();
  $("#theme-toggle").querySelector("svg").outerHTML = themeIcon();
}

function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

// ── header / shells ──────────────────────────────────────────────────
function ffHeader(f) {
  return `
    <header class="ff-head">
      <div class="ff-numeral">${f.rung}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">${esc(f.kicker)}</div>
        <h1 class="ff-title">${esc(f.title)}</h1>
        <p class="ff-desc">${esc(f.desc)}</p>
        <div class="ff-term">${f.term}</div>
      </div>
    </header>`;
}

function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "var(--r5)");
  stage.innerHTML = `<div class="view view-enter">${html}</div>`;
  stage.scrollTop = 0;
}

// ── overview figure: a faithful replica of the workshop's ladder diagram ─
const FIG = {
  bubble: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.5 4h15A2.5 2.5 0 0 1 22 6.5v7A2.5 2.5 0 0 1 19.5 16H12l-4.6 3.8A1 1 0 0 1 5.8 19v-3H4.5A2.5 2.5 0 0 1 2 13.5v-7A2.5 2.5 0 0 1 4.5 4Z"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="currentColor"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 8.4c1.6 1.2 4.6 1.9 8 1.9s6.4-.7 8-1.9v4.1c0 1.66-3.58 3-8 3s-8-1.34-8-3V8.4Z" opacity=".82"/><path d="M4 14.9c1.6 1.2 4.6 1.9 8 1.9s6.4-.7 8-1.9V19c0 1.66-3.58 3-8 3s-8-1.34-8-3v-4.1Z" opacity=".64"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M8 11.2 15 6.8M8 12.8l7 4.4"/><circle cx="6" cy="12" r="2.5" fill="currentColor" stroke="none"/><circle cx="17.5" cy="6" r="2.5" fill="currentColor" stroke="none"/><circle cx="17.5" cy="18" r="2.5" fill="currentColor" stroke="none"/></svg>',
  robot: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="3.4" r="1.6"/><rect x="11.2" y="4.2" width="1.6" height="3.4" rx=".8"/><rect x="3.5" y="7" width="17" height="12" rx="4.2"/><rect x="1.6" y="11" width="1.8" height="4.2" rx=".9"/><rect x="20.6" y="11" width="1.8" height="4.2" rx=".9"/><circle cx="9.2" cy="12.8" r="1.75" fill="var(--lad-icon-bg)"/><circle cx="14.8" cy="12.8" r="1.75" fill="var(--lad-icon-bg)"/><rect x="9.2" y="15.6" width="5.6" height="1.5" rx=".75" fill="var(--lad-icon-bg)"/></svg>',
  term: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 8.5 4 3.5-4 3.5"/><path d="M12.5 15.5h6"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h13m-5-6 6 6-6 6"/></svg>',
};
const LADDER_FIG = [
  { id: "chatbot", n: 1, name: "Chatbot", icon: FIG.bubble, desc: "A stateless LLM. Prompt in, text out, drawing only on training knowledge." },
  { id: "rag", n: 2, name: "RAG", icon: FIG.db, desc: "The same LLM, grounded in your own documents retrieved at question time." },
  { id: "workflow", n: 3, name: "Workflow", icon: FIG.flow, tag: "Automation", desc: "Several LLM calls your code stitches into a fixed, reliable pipeline." },
  { id: "agent", n: 4, name: "Agent", icon: FIG.robot, tag: "Autonomy", desc: "The model picks its own tools and loops until the task is done." },
  { id: "builder", n: 5, name: "Autonomous Agent", icon: FIG.term, desc: "An agent that writes and runs code to build durable automation." },
];
function figCard(c, delay) {
  return `<a class="lcard${c.tag ? " has-tag" : ""}" href="#/${c.id}" style="animation-delay:${delay}ms" aria-label="${esc(c.name)}">
      <span class="lcard-num">${c.n}</span>
      ${c.tag ? `<span class="lcard-tag">${esc(c.tag)}</span>` : ""}
      <span class="lcard-icon">${c.icon}</span>
      <span class="lcard-name">${esc(c.name)}</span>
      <span class="lcard-desc">${esc(c.desc)}</span>
    </a>`;
}

// ── view: home / overview ───────────────────────────────────────────────
function viewHome() {
  const arrow = `<span class="lfig-arrow" aria-hidden="true">${FIG.arrow}</span>`;
  const figure = `
    <figure class="ladder-fig">
      <figcaption class="lfig-head">
        <div class="lfig-eyebrow">The AI Maturity Ladder</div>
        <h1 class="lfig-title">Five Form Factors of AI Applications</h1>
        <p class="lfig-sub">Climb from a plain LLM chatbot to an autonomous agent. Each rung adds exactly one new capability.</p>
      </figcaption>
      <div class="lfig-track">
        ${figCard(LADDER_FIG[0], 120)}
        ${arrow}
        ${figCard(LADDER_FIG[1], 190)}
        ${arrow}
        <div class="lgroup" style="animation-delay:250ms">
          ${figCard(LADDER_FIG[2], 300)}
          ${figCard(LADDER_FIG[3], 360)}
        </div>
        ${arrow}
        ${figCard(LADDER_FIG[4], 440)}
      </div>
      <div class="lfig-axis">
        <span class="lfig-axis-cap">Simpler · Cheaper · Predictable</span>
        <span class="lfig-axis-cap">More Capable · More Autonomous</span>
      </div>
      <div class="lfig-axisline" aria-hidden="true"></div>
    </figure>`;

  const rungs = FF.map((f, i) => `
    <a class="rung" href="#/${f.id}" style="--c:${f.accent};animation-delay:${i * 70 + 160}ms">
      <div class="rung-num">${f.rung}</div>
      <div class="rung-main">
        <h3>${esc(f.nav)} <span class="muted" style="font-weight:400;font-size:14px">· ${esc(f.title)}</span></h3>
        <p>${esc(f.desc)}</p>
      </div>
      <div class="rung-meta">
        ${Object.entries(f.meta).map(([k, v]) => `<div class="meta-line"><span class="mk">${k}</span><span class="mv">${esc(v)}</span></div>`).join("")}
      </div>
      <div class="rung-go">${I.arrow}</div>
    </a>`).join("");

  setStage(`
    ${figure}
    <div class="explore-label">Explore each rung — live</div>
    <div class="ladder">${rungs}</div>`, "var(--r2)");
}

// ── view: chatbot (FF1) ─────────────────────────────────────────────────
const CHAT_SYSTEM = "You are a helpful assistant.";   // mirrors the backend SYSTEM
const CTX_WINDOW_DEFAULT = 200000;
const I_WINDOW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M3 9h18M9 9v12"/></svg>';
const I_CHEVRON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';

function viewChatbot() {
  const f = FF_BY_ID.chatbot;
  setStage(`${ffHeader(f)}
    <div class="chat-layout" id="chat-layout">
      <div class="panel chat-panel">
        <div class="panel-head">
          <span class="panel-title">${I.chat} Conversation</span>
          <div class="row" style="gap:8px;flex-wrap:nowrap">
            <button class="btn btn-ghost" id="ctx-show" title="Show context window">${I_WINDOW} Context</button>
            <button class="btn btn-ghost" id="new-chat">${I.refresh} New chat</button>
          </div>
        </div>
        <div class="panel-body">
          <div class="chat-wrap">
            <div class="chat-scroll" id="chat-scroll">
              <div class="empty">Ask anything. Each reply re-sends the whole conversation — that's the "memory".</div>
            </div>
            <div class="memory-note" id="mem-note"></div>
            <div class="composer">
              <textarea id="chat-input" placeholder="Message Claude…  (e.g. My name is Sam and I'm an analytics engineer)" rows="1"></textarea>
              <button class="btn btn-accent" id="chat-send">${I.send} Send</button>
            </div>
          </div>
        </div>
      </div>
      <aside class="ctx-pane" id="ctx-pane">
        <div class="ctx-head">
          <span class="panel-title">${I_WINDOW} Context window</span>
          <button class="ctx-x" id="ctx-hide" title="Collapse">${I_CHEVRON}</button>
        </div>
        <div class="ctx-meter-box">
          <div class="ctx-cap" id="ctx-cap">— / ${CTX_WINDOW_DEFAULT.toLocaleString()} tokens</div>
          <div class="ctx-meter"><div class="ctx-fill" id="ctx-fill"></div></div>
          <div class="ctx-legend">
            <span><span class="dot-sq used"></span><b id="ctx-used">0</b> used</span>
            <span><span class="dot-sq free"></span><b id="ctx-free">${CTX_WINDOW_DEFAULT.toLocaleString()}</b> free</span>
          </div>
        </div>
        <div class="ctx-note">Everything below is re-sent to the model on every turn — it <b>is</b> the chatbot's memory. Tokens grow with each message until the window fills.</div>
        <div class="ctx-list" id="ctx-list"></div>
      </aside>
    </div>`, f.accent);

  const scroll = $("#chat-scroll"), input = $("#chat-input"), send = $("#chat-send");
  const layout = $("#chat-layout");
  let first = true;
  const ctx = [{ role: "system", text: CHAT_SYSTEM }];

  const estTok = (s) => Math.max(1, Math.ceil((s || "").length / 4));
  function renderCtx(tokens, win) {
    $("#ctx-list").innerHTML = ctx.map((m) => `
      <div class="ctx-msg ${m.role}">
        <div class="ctx-msg-top"><span class="ctx-role">${m.role}</span><span class="ctx-tok">~${estTok(m.text)} tok</span></div>
        <div class="ctx-text">${esc(m.text)}</div>
      </div>`).join("");
    const list = $("#ctx-list"); list.scrollTop = list.scrollHeight;
    if (tokens != null) {
      win = win || CTX_WINDOW_DEFAULT;
      const pct = Math.min(100, (tokens / win) * 100);
      $("#ctx-fill").style.width = (tokens > 0 ? Math.max(pct, 0.5) : 0) + "%";
      $("#ctx-used").textContent = tokens.toLocaleString();
      $("#ctx-free").textContent = Math.max(0, win - tokens).toLocaleString();
      $("#ctx-cap").textContent = `${tokens.toLocaleString()} / ${win.toLocaleString()} tokens · ${pct < 1 ? pct.toFixed(2) : pct.toFixed(1)}% used`;
    }
  }
  renderCtx(0, CTX_WINDOW_DEFAULT);

  const showCtx = (open) => layout.classList.toggle("ctx-closed", !open);
  $("#ctx-hide").addEventListener("click", () => showCtx(false));
  $("#ctx-show").addEventListener("click", () => showCtx(true));

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
          $("#mem-note").innerHTML = `memory: <b>${ev.turns}</b> messages · <b>${(ev.context_tokens || 0).toLocaleString()}</b> tokens re-sent next turn`;
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
    scroll.innerHTML = `<div class="empty">New conversation. Previous memory cleared.</div>`;
    $("#mem-note").innerHTML = ""; first = true;
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
function autosize(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 160) + "px"; }

// ── view: RAG (FF2) ─────────────────────────────────────────────────────
const RAG_SAMPLES = [
  "What is the exact API rate limit on the Pro plan?",
  "How do I keep my data safe and recoverable?",
  "Which plans include SSO?",
  "How long are backups retained?",
];
const RAG_TECH = {
  vector: {
    name: "Vector",
    desc: "Embeds the query and ranks by cosine similarity — matches meaning even when no words overlap.",
    arch: [
      { kind: "q", label: "Query", sub: "natural language" },
      { label: "Embed", sub: "→ 768-dim vector" },
      { kind: "idx", label: "HNSW vector index", sub: "approx. nearest-neighbour" },
      { label: "acme_docs.embedding", sub: "VECTOR_DISTANCE · COSINE" },
      { kind: "out", label: "Top-k by cosine" },
    ],
  },
  keyword: {
    name: "Keyword",
    desc: "Matches exact terms via Oracle Text. Precise for known words; blind to synonyms.",
    arch: [
      { kind: "q", label: "Query", sub: "→ terms (ACCUM)" },
      { kind: "idx", label: "Oracle Text index", sub: "inverted index" },
      { label: "CONTAINS()", sub: "acme_docs.content" },
      { label: "SCORE(1)", sub: "relevance rank" },
      { kind: "out", label: "Top-k by score" },
    ],
  },
  hybrid: {
    name: "Hybrid · RRF",
    desc: "Runs vector and keyword search, then fuses their rankings with Reciprocal Rank Fusion — robust when either misses.",
    arch: [
      { kind: "q", label: "Query" },
      { kind: "split", label: "Vector index  ‖  Text index", sub: "two ranked lists" },
      { kind: "idx", label: "Reciprocal Rank Fusion", sub: "Σ 1 / (k + rank)" },
      { kind: "out", label: "Top-k fused" },
    ],
  },
  graph: {
    name: "Graph",
    desc: "Vector-seeds the graph, then expands over SIMILAR_TO and same-category edges — surfaces related docs a flat search misses.",
    arch: [
      { kind: "q", label: "Query", sub: "→ vector seed" },
      { kind: "idx", label: "ACME_GRAPH", sub: "SQL property graph" },
      { label: "SIMILAR_TO + IN_CATEGORY", sub: "1-hop (GRAPH_TABLE)" },
      { label: "Blend seed + edge", sub: "weighted scores" },
      { kind: "out", label: "Top-k blended" },
    ],
  },
};
const RAG_ORDER = ["vector", "keyword", "hybrid", "graph"];

function archDiagram(nodes) {
  return '<div class="arch">' + nodes.map((n, i) =>
    `<div class="arch-node ${n.kind || ""}"><span class="arch-label">${esc(n.label)}</span>${n.sub ? `<span class="arch-sub">${esc(n.sub)}</span>` : ""}</div>` +
    (i < nodes.length - 1 ? '<div class="arch-down" aria-hidden="true"></div>' : "")
  ).join("") + "</div>";
}

function viewRAG() {
  const f = FF_BY_ID.rag;
  setStage(`${ffHeader(f)}
    <div class="rag-layout" id="rag-layout">
      <div class="rag-main">
        <div class="panel mb">
          <div class="panel-body">
            <div class="row spread mb">
              <div class="row">
                <span class="hint mono">Technique</span>
                <div class="seg" id="rag-tech">
                  ${RAG_ORDER.map((t, i) => `<button class="${i === 0 ? "active" : ""}" data-t="${t}">${esc(RAG_TECH[t].name)}</button>`).join("")}
                </div>
              </div>
              <span class="hint" id="rag-backend"></span>
            </div>
            <div class="tech-desc" id="rag-desc">${esc(RAG_TECH.vector.desc)}</div>
            <div class="field" style="margin-top:14px">
              <textarea id="rag-input" rows="1" placeholder="Ask about Acme Cloud…"></textarea>
              <button class="btn btn-accent" id="rag-ask">${I.send} Ask</button>
              <button class="btn btn-ghost" id="rag-how" title="How it works">${I.flow}</button>
            </div>
            <div class="chips mb" style="margin-top:12px">${RAG_SAMPLES.map((s) => `<button class="chip">${esc(s)}</button>`).join("")}</div>
          </div>
        </div>
        <div class="grid-2">
          <div class="panel">
            <div class="panel-head"><span class="panel-title">${I.bot} Grounded answer</span></div>
            <div class="panel-body"><div id="rag-answer" class="bubble" style="background:transparent;border:none;padding:0"><div class="empty">The answer will cite its sources like [1].</div></div></div>
          </div>
          <div class="panel">
            <div class="panel-head"><span class="panel-title">${I.rag} Retrieved context</span></div>
            <div class="panel-body"><div id="rag-sources" class="sources"><div class="empty">Retrieved documents appear here.</div></div></div>
          </div>
        </div>
      </div>
      <aside class="rag-pane" id="rag-pane">
        <div class="ctx-head">
          <span class="panel-title">${I.flow} How <span id="rag-pane-tech">vector</span> retrieval works</span>
          <button class="ctx-x" id="rag-pane-hide" title="Collapse">${I_CHEVRON}</button>
        </div>
        <div class="rag-pane-body">
          <div class="rag-arch-title">Reference architecture</div>
          <div class="rag-arch" id="rag-arch"></div>
          <div class="rag-sql-head">Oracle SQL <span class="hint" id="rag-sql-note"></span></div>
          <pre class="rag-sql" id="rag-sql">—</pre>
        </div>
      </aside>
    </div>`, f.accent);

  let technique = "vector";
  const seg = $("#rag-tech"), input = $("#rag-input"), ask = $("#rag-ask");
  const layout = $("#rag-layout");

  async function selectTech(t) {
    technique = t;
    $("#rag-desc").textContent = RAG_TECH[t].desc;
    $("#rag-pane-tech").textContent = t;
    $("#rag-arch").innerHTML = archDiagram(RAG_TECH[t].arch);
    try {
      const d = await getJSON("/api/rag/sql?technique=" + t);
      $("#rag-sql").textContent = d.sql;
      $("#rag-sql-note").textContent = d.backend === "oracle" ? "" : "· in-memory fallback active (Oracle equivalent shown)";
    } catch (_) { $("#rag-sql").textContent = "—"; }
  }
  selectTech("vector");

  seg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    seg.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    selectTech(b.dataset.t);
  });

  const showPane = (open) => layout.classList.toggle("rag-closed", !open);
  $("#rag-pane-hide").addEventListener("click", () => showPane(false));
  $("#rag-how").addEventListener("click", () => showPane(true));

  $$(".chip", $("#stage")).forEach((c) => c.addEventListener("click", () => { input.value = c.textContent; runRAG(); }));

  async function runRAG() {
    const q = input.value.trim();
    if (!q || state.abort) return;
    const ans = $("#rag-answer"), src = $("#rag-sources");
    ans.innerHTML = '<span class="caret"></span>'; src.innerHTML = `<div class="empty"><span class="spinner" style="display:inline-block"></span> retrieving…</div>`;
    ask.disabled = true;
    let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/rag/answer", { query: q, technique, k: 4 }, (ev) => {
        if (ev.type === "sources") {
          $("#rag-backend").innerHTML = `backend: <b class="mono" style="color:var(--accent)">${ev.backend === "oracle" ? "Oracle AI Database" : "in-memory NumPy"}</b> · ${ev.technique}`;
          src.innerHTML = ev.hits.length ? ev.hits.map((h, i) => sourceCard(h, i)).join("") : `<div class="empty">No matches for this technique.</div>`;
        } else if (ev.type === "delta") { acc += ev.text; ans.innerHTML = renderRich(acc) + '<span class="caret"></span>'; }
        else if (ev.type === "done") { ans.innerHTML = renderRich(acc) || `<div class="empty">No answer.</div>`; }
      }, state.abort.signal);
    } catch (e) { ans.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; ask.disabled = false; }
  }
  ask.addEventListener("click", runRAG);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runRAG(); } });
  input.addEventListener("input", () => autosize(input));
  input.focus();
}
function sourceCard(h, i) {
  return `<div class="source" style="animation-delay:${i * 50}ms">
    <div class="source-top"><span class="source-idx">${i + 1}</span><span class="source-title">${esc(h.title)}</span><span class="source-cat">${esc(h.category)}</span><span class="source-score">${(+h.score).toFixed(3)}</span></div>
    <div class="source-body">${esc(h.content)}</div></div>`;
}

// ── view: workflow (FF3) ────────────────────────────────────────────────
const WF_SAMPLES = [
  "I've been double-charged for my Pro seats this month and need this fixed before our board demo tomorrow.",
  "How do I rotate my API keys without breaking my app?",
  "Can I change my project's region after creation?",
];
const WF_STAGES = { classify: "Classify", route: "Route", retrieve: "Retrieve", draft: "Draft reply" };
const I_HANDOFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="m16 11 2 2 4-4"/></svg>';
function viewWorkflow() {
  const f = FF_BY_ID.workflow;
  setStage(`${ffHeader(f)}
    <div class="panel mb">
      <div class="panel-body">
        <div class="field">
          <textarea id="wf-input" rows="2" placeholder="Paste an incoming support message…">${esc(WF_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="wf-run">${I.play} Run pipeline</button>
        </div>
        <div class="chips" style="margin-top:12px">${WF_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 46))}…</button>`).join("")}</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.flow} Fixed pipeline · draft pauses for your approval</span><span class="hint mono" id="wf-status"></span></div>
      <div class="panel-body"><div class="pipeline" id="wf-pipe"><div class="empty">Run the pipeline; at the draft it hands off to you to approve or decline.</div></div></div>
    </div>`, f.accent);

  const input = $("#wf-input"), run = $("#wf-run"), pipe = $("#wf-pipe");
  $$(".chip", $("#stage")).forEach((c, i) => c.addEventListener("click", () => { input.value = WF_SAMPLES[i]; autosize(input); }));
  const pending = {};

  function handleEvent(ev) {
    if (ev.type === "step") {
      if (ev.status === "running") { pending[ev.step] = addStage(pipe, ev.step); }
      else if (ev.status === "done") { fillStage(pending[ev.step] || addStage(pipe, ev.step), ev.step, ev.data); pending[ev.step] = null; }
    } else if (ev.type === "handoff") {
      renderHandoff(ev);
    } else if (ev.type === "final") {
      $("#wf-status").textContent = "sent";
      const box = document.createElement("div");
      box.className = "stage-row done";
      box.innerHTML = `<div class="stage-rail"><div class="stage-dot">${I.check}</div></div>
        <div class="stage-card" style="border-color:color-mix(in oklab,var(--accent) 30%,transparent)">
          <div class="stage-name">Sent reply ${ev.escalated ? '<span class="tag high">escalated</span>' : '<span class="tag ok">auto-handled</span>'} <span class="tag ok">human-approved</span></div>
          <div class="final-reply">${renderRich(ev.reply)}</div></div>`;
      pipe.appendChild(box);
      box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else if (ev.type === "error") {
      $("#wf-status").textContent = "";
      pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>${esc(ev.message)}</div></div>`);
    }
  }

  function renderHandoff(ev) {
    pending.draft = null;
    $("#wf-status").textContent = "awaiting your approval";
    const box = document.createElement("div");
    box.className = "stage-row handoff";
    box.innerHTML = `
      <div class="stage-rail"><div class="stage-dot handoff-dot">${I_HANDOFF}</div></div>
      <div class="stage-card handoff-card">
        <div class="stage-name">Human handoff <span class="stage-sub">attempt ${ev.attempt} · your approval required</span></div>
        <div class="handoff-draft">${renderRich(ev.draft)}</div>
        <textarea class="hf-reason" rows="2" placeholder="Optional — why send it back? The model uses this feedback to redraft…"></textarea>
        <div class="handoff-actions">
          <button class="btn btn-accent hf-approve">${I.check} Approve &amp; send</button>
          <button class="btn hf-submit">${I.refresh} Send back for revision</button>
        </div>
      </div>`;
    pipe.appendChild(box);
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const reason = box.querySelector(".hf-reason");
    box.querySelector(".hf-approve").addEventListener("click", () => resolve(box, ev.workflow_id, true, ""));
    box.querySelector(".hf-submit").addEventListener("click", () => resolve(box, ev.workflow_id, false, reason.value.trim()));
  }

  function markResolved(box, approved, reason) {
    box.classList.add("resolved");
    box.querySelectorAll("button, textarea").forEach((el) => (el.disabled = true));
    const r = box.querySelector(".hf-reason"); if (r) r.remove();
    box.querySelector(".handoff-actions").innerHTML = approved
      ? `<span class="tag ok">${I.check} approved by you</span>`
      : `<span class="tag no">declined</span> <span class="muted" style="font-size:13px">${esc(reason || "(no reason given)")}</span>`;
  }

  async function resolve(box, wid, approved, reason) {
    if (state.abort) return;
    markResolved(box, approved, reason);
    $("#wf-status").textContent = approved ? "finalizing…" : "revising…";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/workflow/decision", { workflow_id: wid, approved, reason }, handleEvent, state.abort.signal);
    } catch (e) { pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>Error: ${esc(e.message)}</div></div>`); }
    finally { state.abort = null; }
  }

  async function runWF() {
    const message = input.value.trim();
    if (!message || state.abort) return;
    pipe.innerHTML = ""; run.disabled = true; $("#wf-status").textContent = "running…";
    for (const k in pending) delete pending[k];
    state.abort = new AbortController();
    try {
      await streamSSE("/api/workflow/start", { message }, handleEvent, state.abort.signal);
    } catch (e) { pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>Error: ${esc(e.message)}</div></div>`); }
    finally { state.abort = null; run.disabled = false; }
  }
  run.addEventListener("click", runWF);
  autosize(input);
}
function addStage(pipe, step) {
  if (pipe.querySelector(".empty")) pipe.innerHTML = "";
  const row = document.createElement("div");
  row.className = "stage-row running";
  row.innerHTML = `<div class="stage-rail"><div class="stage-dot"><span class="spinner"></span></div><div class="stage-line"></div></div>
    <div class="stage-card"><div class="stage-name">${esc(WF_STAGES[step] || step)} <span class="stage-sub">working…</span></div><div class="stage-content"></div></div>`;
  pipe.appendChild(row);
  pipe.scrollIntoView; return row;
}
function fillStage(row, step, data) {
  if (!row) return;
  row.className = "stage-row done";
  const dot = $(".stage-dot", row); const n = Object.keys(WF_STAGES).indexOf(step) + 1;
  dot.innerHTML = step === "review" ? (data.approved ? I.check : "↻") : String(n || "•");
  const name = $(".stage-name", row), content = $(".stage-content", row);
  if (step === "classify") {
    name.innerHTML = `Classify <span class="stage-sub">structured output</span>`;
    content.innerHTML = `<span class="kv">category <b>${esc(data.category)}</b></span><span class="kv">urgency <span class="tag ${esc(data.urgency)}">${esc(data.urgency)}</span></span><div style="margin-top:6px">${esc(data.summary)}</div>`;
  } else if (step === "route") {
    name.innerHTML = `Route <span class="stage-sub">your code decides</span>`;
    content.innerHTML = `${data.escalated ? '<span class="tag high">escalate → human</span>' : '<span class="tag ok">automated</span>'} <span class="muted">${esc(data.reason)}</span>`;
  } else if (step === "retrieve") {
    name.innerHTML = `Retrieve <span class="stage-sub">${data.hits.length} docs · ${esc(data.backend)}</span>`;
    content.innerHTML = `<div class="chips">${data.hits.map((h) => `<span class="chip" style="cursor:default">${esc(h.title)}</span>`).join("")}</div>`;
  } else if (step === "draft") {
    name.innerHTML = `Draft reply <span class="stage-sub">attempt ${data.attempt}${data.revising ? " · revising" : ""}</span>`;
    content.innerHTML = data.draft ? renderRich(data.draft) : "";
  } else if (step === "review") {
    name.innerHTML = `Review <span class="stage-sub">attempt ${data.attempt} · QA gate</span>`;
    content.innerHTML = `${data.approved ? '<span class="tag ok">approved</span>' : '<span class="tag no">needs revision</span>'} <span class="muted">${esc(data.feedback || "")}</span>`;
  }
}

// ── agent log (shared by FF4 & FF5) ────────────────────────────────────
function addEvent(log, ev) {
  if (log.querySelector(".empty")) log.innerHTML = "";
  const node = document.createElement("div");
  if (ev.type === "text") {
    if (!ev.text || !ev.text.trim()) return null;
    node.className = "ev text"; node.innerHTML = `<div class="ev-icon">${I.bot}</div><div class="ev-text"><div class="ev-bubble">${renderRich(ev.text)}</div></div>`;
  } else if (ev.type === "tool_use") {
    const args = Object.entries(ev.input || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
    node.className = "ev tool"; node.innerHTML = `<div class="ev-icon">${I.tool}</div><div class="ev-text"><div class="ev-bubble"><span class="tname">${esc(ev.name)}</span>(<span class="tool-args">${esc(args)}</span>)</div></div>`;
  } else if (ev.type === "tool_result") {
    node.className = "ev result"; node.innerHTML = `<div class="ev-icon">${I.check}</div><div class="ev-text"><div class="ev-bubble mono" style="font-size:12.5px;white-space:pre-wrap">${esc(ev.text)}</div></div>`;
  } else if (ev.type === "result") {
    node.className = "ev result"; const bits = [];
    if (ev.num_turns != null) bits.push(`${ev.num_turns} turns`);
    if (ev.duration_ms != null) bits.push(`${(ev.duration_ms / 1000).toFixed(1)}s`);
    if (ev.cost_usd != null) bits.push(`$${(+ev.cost_usd).toFixed(4)}`);
    node.className = "ev result"; node.innerHTML = `<div class="ev-icon">${I.check}</div><div class="ev-text"><div class="ev-meta">agent finished · ${bits.join(" · ") || "ok"}</div></div>`;
  } else if (ev.type === "error") {
    node.className = "ev err"; node.innerHTML = `<div class="ev-icon">${I.alert}</div><div class="ev-text"><div class="ev-bubble">${esc(ev.message)}</div></div>`;
  } else return null;
  log.appendChild(node); log.scrollTop = log.scrollHeight; return node;
}

// ── view: agent (FF4) ───────────────────────────────────────────────────
const AGENT_SAMPLES = [
  "I'm on the Pro plan and keep hitting rate limits right before our launch tomorrow. What are my options, and can you escalate this for me?",
  "What's included in the Enterprise plan?",
  "My webhooks stopped firing and it's urgent — please look into it and open a ticket.",
];
function viewAgent() {
  const f = FF_BY_ID.agent;
  const unavailable = state.health && !state.health.agent_available;
  setStage(`${ffHeader(f)}
    ${unavailable ? agentBanner() : ""}
    <div class="panel mb">
      <div class="panel-body">
        <div class="field">
          <textarea id="ag-input" rows="2" placeholder="Give the agent a goal…">${esc(AGENT_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="ag-run" ${unavailable ? "disabled" : ""}>${I.play} Run agent</button>
        </div>
        <div class="chips" style="margin-top:12px">${AGENT_SAMPLES.map((s, i) => `<button class="chip">${esc(i === 0 ? "Rate limits + escalate" : s.slice(0, 40) + "…")}</button>`).join("")}</div>
        <div class="hint" style="margin-top:10px">Tools: <span class="mono" style="color:var(--accent)">search_docs</span>, <span class="mono" style="color:var(--accent)">create_support_ticket</span> — the model chooses which to call, and when.</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.agent} Agent trajectory</span><span class="hint mono" id="ag-status"></span></div>
      <div class="panel-body"><div class="log" id="ag-log"><div class="empty">The agent's reasoning and tool calls stream here as it decides its own path.</div></div></div>
    </div>`, f.accent);

  const input = $("#ag-input"), run = $("#ag-run"), log = $("#ag-log");
  $$(".chip", $("#stage")).forEach((c, i) => c.addEventListener("click", () => { input.value = AGENT_SAMPLES[i]; autosize(input); }));
  run && run.addEventListener("click", async () => {
    const prompt = input.value.trim(); if (!prompt || state.abort) return;
    log.innerHTML = ""; run.disabled = true; $("#ag-status").innerHTML = '<span class="spinner" style="display:inline-block"></span>';
    state.abort = new AbortController();
    try { await streamSSE("/api/agent/run", { prompt }, (ev) => addEvent(log, ev), state.abort.signal); }
    catch (e) { addEvent(log, { type: "error", message: e.message }); }
    finally { state.abort = null; run.disabled = false; $("#ag-status").textContent = "done"; }
  });
  autosize(input);
}
function agentBanner() {
  return `<div class="banner warn">${I.alert}<div>The Claude Agent SDK CLI wasn't found, so Form Factors 4 &amp; 5 are disabled. Install it with <span class="mono">npm i -g @anthropic-ai/claude-code</span> and restart the server.</div></div>`;
}

// ── view: builder (FF5) ─────────────────────────────────────────────────
function viewBuilder() {
  const f = FF_BY_ID.builder;
  const unavailable = state.health && !state.health.agent_available;
  setStage(`${ffHeader(f)}
    ${unavailable ? agentBanner() : `<div class="banner warn">${I.alert}<div>This agent executes code (Write / Edit / Bash) with permissions bypassed, confined to a sandbox directory. That's the point of the demo — run it locally.</div></div>`}
    <div class="panel mb">
      <div class="panel-body">
        <div class="row spread mb"><span class="panel-title">${I.build} Build task</span><span class="hint mono">sandbox seeded with <b>support_messages.csv</b></span></div>
        <textarea id="bd-input" rows="6" placeholder="Describe what to build…"></textarea>
        <div class="row" style="margin-top:12px">
          <button class="btn btn-accent" id="bd-run" ${unavailable ? "disabled" : ""}>${I.play} Build &amp; run</button>
          <button class="btn btn-ghost" id="bd-reset">${I.refresh} Reset task</button>
        </div>
      </div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.agent} Build trajectory</span><span class="hint mono" id="bd-status"></span></div>
        <div class="panel-body"><div class="log" id="bd-log"><div class="empty">The agent writes a script, runs it, and fixes errors until it works.</div></div></div>
      </div>
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.file} Sandbox artifacts</span><button class="btn btn-ghost" id="bd-refresh">${I.refresh}</button></div>
        <div class="panel-body"><div class="files" id="bd-files"><div class="empty">Files the agent creates will appear here.</div></div></div>
      </div>
    </div>
    <div class="panel mb">
      <div class="panel-head"><span class="panel-title">${I.check} Save as automation</span><span class="hint">snapshot the built script + data, then re-run it on demand or a schedule</span></div>
      <div class="panel-body">
        <div class="au-save-row">
          <div class="au-fld"><label>Name</label><input id="au-name" type="text" placeholder="daily-triage"></div>
          <div class="au-fld grow"><label>Run command</label><input id="au-cmd" type="text" placeholder="python triage.py --input support_messages.csv --output report.json"></div>
          <button class="btn btn-accent" id="au-save">${I.check} Save automation</button>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.play} Automations · create once, re-run on a schedule</span><button class="btn btn-ghost" id="au-refresh">${I.refresh}</button></div>
      <div class="panel-body"><div class="automations" id="au-list"><div class="empty">No automations yet — build a script above, then "Save as automation".</div></div></div>
    </div>`, f.accent);

  const input = $("#bd-input"), run = $("#bd-run"), log = $("#bd-log");
  let defaultTask = "";
  getJSON("/api/builder/default-task").then((d) => { defaultTask = d.task || ""; if (!input.value) input.value = defaultTask; autosize2(input); }).catch(() => {});
  loadArtifacts();
  getJSON("/api/builder/default-command").then((d) => { const el = $("#au-cmd"); if (el && !el.value) el.value = d.command || ""; }).catch(() => {});
  loadAutomations();
  $("#au-save").addEventListener("click", async () => {
    const name = ($("#au-name").value || "").trim() || "automation";
    const command = ($("#au-cmd").value || "").trim();
    const btn = $("#au-save"); btn.disabled = true;
    try {
      await fetch("/api/builder/automations/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, command }) });
      $("#au-name").value = ""; await loadAutomations();
    } catch (_) {} finally { btn.disabled = false; }
  });
  $("#au-refresh").addEventListener("click", loadAutomations);

  run && run.addEventListener("click", async () => {
    const task = input.value.trim(); if (!task || state.abort) return;
    log.innerHTML = ""; run.disabled = true; $("#bd-status").innerHTML = '<span class="spinner" style="display:inline-block"></span> building…';
    state.abort = new AbortController();
    try {
      await streamSSE("/api/builder/run", { task }, (ev) => {
        if (ev.type === "artifacts_ready") loadArtifacts();
        else addEvent(log, ev);
      }, state.abort.signal);
    } catch (e) { addEvent(log, { type: "error", message: e.message }); }
    finally { state.abort = null; run.disabled = false; $("#bd-status").textContent = "done"; loadArtifacts(); }
  });
  $("#bd-reset").addEventListener("click", () => { input.value = defaultTask; autosize2(input); });
  $("#bd-refresh").addEventListener("click", loadArtifacts);
}
async function loadArtifacts() {
  const box = $("#bd-files"); if (!box) return;
  try {
    const d = await getJSON("/api/builder/artifacts");
    if (!d.files || !d.files.length) { box.innerHTML = `<div class="empty">No files yet.</div>`; return; }
    box.innerHTML = d.files.map((file, i) => {
      const isNew = file.name !== "support_messages.csv";
      const body = file.content != null
        ? `<div class="filebox"><pre>${esc(file.content)}</pre></div>`
        : (file.truncated ? `<div class="filebox"><pre class="muted">(file too large to preview)</pre></div>` : "");
      return `<div class="file">
        <div class="file-head" data-i="${i}">${I.file}<span class="file-name">${esc(file.name)}</span>${isNew ? '<span class="file-new">new</span>' : ""}<span class="file-size">${file.size} B</span></div>
        ${body}</div>`;
    }).join("");
    $$(".file-head", box).forEach((h) => h.addEventListener("click", () => { const b = h.nextElementSibling; if (b && b.classList.contains("filebox")) b.style.display = b.style.display === "none" ? "" : "none"; }));
  } catch (_) { box.innerHTML = `<div class="empty">Couldn't load artifacts.</div>`; }
}
function autosize2(el) { if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 260) + "px"; } }

// ── FF5 automations: save / run-now / schedule / runs history ────────────
function fmtTime(epoch) {
  try { return new Date(epoch * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch (_) { return ""; }
}
async function loadAutomations() {
  const box = $("#au-list"); if (!box) return;
  let d; try { d = await getJSON("/api/builder/automations"); } catch (_) { return; }
  if (!d.automations || !d.automations.length) {
    box.innerHTML = `<div class="empty">No automations yet — build a script above, then "Save as automation".</div>`; return;
  }
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
    <div class="auto-top">
      <span class="auto-name">${esc(a.name)}</span>
      <span class="auto-sched mono">${esc(a.schedule_label)}${next}</span>
      <span class="auto-last ${lastCls}">${lastTxt}</span>
    </div>
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
      <button class="btn btn-ghost au-del" title="Delete">${I.alert}</button>
    </div>
    <div class="auto-runs" hidden></div>
  </div>`;
}
function wireAuto(el) {
  const id = el.dataset.id;
  const type = el.querySelector(".au-type"), num = el.querySelector(".au-num"),
        at = el.querySelector(".au-at"), unit = el.querySelector(".au-unit");
  function sync() {
    const t = type.value, showNum = t === "interval" || t === "once";
    num.hidden = !showNum; unit.hidden = !showNum; at.hidden = t !== "daily";
  }
  sync();
  type.addEventListener("change", sync);
  el.querySelector(".au-run").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true; b.innerHTML = `<span class="spinner" style="display:inline-block"></span> running`;
    try { await fetch(`/api/builder/automations/${id}/run`, { method: "POST" }); } catch (_) {}
    await loadAutomations();
  });
  el.querySelector(".au-set").addEventListener("click", async () => {
    const body = { type: type.value, every_minutes: +num.value || 5, delay_minutes: +num.value || 5, at: at.value || "08:00" };
    try { await fetch(`/api/builder/automations/${id}/schedule`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); } catch (_) {}
    await loadAutomations();
  });
  el.querySelector(".au-del").addEventListener("click", async () => {
    try { await fetch(`/api/builder/automations/${id}`, { method: "DELETE" }); } catch (_) {}
    await loadAutomations();
  });
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

// helper: querySelectorAll
function $$(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

// ── concept-diagram gallery (per-page carousel + lightbox) ──────────────
const I_IMAGES = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="14" rx="2.5"/><circle cx="8.5" cy="9" r="1.5"/><path d="m21 14-4.5-4.5L6 20"/></svg>';
const I_X = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>';

function buildGallery(pageKey) {
  const imgs = (state.galleries || {})[pageKey] || [];
  if (!imgs.length) return null;
  const single = imgs.length === 1;
  const el = document.createElement("section");
  el.className = "gallery" + (single ? " single" : "");
  el.innerHTML = `
    <div class="gallery-head">
      <span class="panel-title">${I_IMAGES} Concept diagrams${single ? "" : ` <span class="gallery-count">${imgs.length}</span>`}</span>
      <button class="ctx-x gallery-collapse" title="Collapse">${I_CHEVRON}</button>
    </div>
    <div class="gallery-main">
      <button class="gallery-nav prev" aria-label="Previous">${I_CHEVRON}</button>
      <div class="gallery-stage"><img class="gallery-img" alt="" loading="lazy" title="Click to enlarge"></div>
      <button class="gallery-nav next" aria-label="Next">${I_CHEVRON}</button>
    </div>
    <div class="gallery-foot">
      <span class="gallery-caption"></span>
      <span class="gallery-counter"></span>
    </div>
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
  const old = view.querySelector(":scope > .gallery");
  if (old) old.remove();
  const g = buildGallery(pageKey);
  if (!g) return;
  const first = view.firstElementChild;
  if (first) first.insertAdjacentElement("afterend", g); else view.appendChild(g);
}

function openLightbox(imgs, start) {
  let i = start || 0;
  const ov = document.createElement("div");
  ov.className = "lightbox";
  ov.innerHTML = `
    <button class="lb-btn lb-close" aria-label="Close">${I_X}</button>
    <button class="lb-btn lb-prev" aria-label="Previous">${I_CHEVRON}</button>
    <figure class="lb-fig"><img alt=""><figcaption></figcaption></figure>
    <button class="lb-btn lb-next" aria-label="Next">${I_CHEVRON}</button>`;
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

// ── router ───────────────────────────────────────────────────────────
const ROUTES = { "": viewHome, chatbot: viewChatbot, rag: viewRAG, workflow: viewWorkflow, agent: viewAgent, builder: viewBuilder };
function route() {
  cancelStream();
  const id = (location.hash.replace(/^#\/?/, "").trim()) || "";
  const render = ROUTES[id] || viewHome;
  state.currentRoute = id || "home";
  renderSidebar(id || "home");
  render();
  injectGallery(state.currentRoute);
  if (window.innerWidth <= 760) closeMenu();
}

// ── mobile menu ──────────────────────────────────────────────────────
function openMenu() { $("#sidebar").classList.add("open"); const s = $("#scrim"); s.hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

// ── boot ─────────────────────────────────────────────────────────────
async function boot() {
  // mobile menu button
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);

  window.addEventListener("hashchange", route);
  route();

  // Load the concept diagrams once, then drop the per-page gallery into the current view.
  getJSON("/api/images").then((d) => { state.galleries = d.pages || {}; injectGallery(state.currentRoute); }).catch(() => {});

  // poll health until retrieval is warm
  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); }
    catch (_) {}
    if (!state.health || !state.health.retrieval || !state.health.retrieval.ready) setTimeout(poll, 1500);
  }
  poll();
}
boot();
