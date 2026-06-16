/* ======================================================================
   The Agent Memory Stack — single-page app
   Vanilla JS. Hash router, theme toggle, SSE-over-fetch streaming client,
   one interactive view per memory layer. Backend: memorizz + Oracle/FS.
   ====================================================================== */

// ── icons ──────────────────────────────────────────────────────────────
const I = {
  stack: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5M3 16.5l9 5 9-5"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12Z"/></svg>',
  rag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="7" ry="2.7"/><path d="M5 5.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/><path d="M5 11.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="6" rx="1.5"/><rect x="14" y="9" width="7" height="6" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/><path d="M10 6h2.5a1.5 1.5 0 0 1 1.5 1.5V9M10 18h2.5a1.5 1.5 0 0 0 1.5-1.5V15"/></svg>',
  agent: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="7" width="14" height="12" rx="2.5"/><path d="M12 7V4M9 3.5h6M9 12h.01M15 12h.01M9.5 16h5"/></svg>',
  id: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M5.5 17a3.5 3.5 0 0 1 7 0M15 9h4M15 13h4"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 16-8-6 16-3-7-7-1Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  reload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM9 13h.01M15 13h.01"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
};

// ── memory layers ─────────────────────────────────────────────────────
const FF = [
  {
    id: "conversation", rung: 1, nav: "Conversation", icon: I.chat, accent: "var(--r1)",
    title: "Episodic Conversation Memory", kicker: "Layer 01 — Remember the dialogue",
    desc: "A MemAgent backed by Oracle (or a filesystem fallback) that remembers across turns — and across a process restart. Reload the agent from storage by its id and watch it still recall who you are.",
    term: "<b>Episodic memory</b> (<code>CONVERSATION_MEMORY</code>): the time-stamped record of interactions. <code>agent.run()</code> retrieves prior turns, reasons, then persists the new ones — automatically.",
    meta: { Type: "Episodic", Store: "CONVERSATION_MEMORY", Survives: "Restarts" },
  },
  {
    id: "semantic", rung: 2, nav: "Persona & Entities", icon: I.id, accent: "var(--r2)",
    title: "Semantic Memory", kicker: "Layer 02 — Identity & facts",
    desc: "A stable persona (identity, voice) plus entity memory: tell the agent durable facts about people, services, and systems, and it records them as structured entities it can recall precisely.",
    term: "<b>Semantic memory</b> (<code>PERSONAS</code> + <code>ENTITY_MEMORY</code>): durable identity and facts, not events. Use it for who-the-agent-is and what-is-true.",
    meta: { Type: "Semantic", Store: "PERSONAS · ENTITY_MEMORY", Recall: "Structured" },
  },
  {
    id: "knowledge", rung: 3, nav: "Knowledge Base", icon: I.rag, accent: "var(--r3)",
    title: "Knowledge Base — RAG", kicker: "Layer 03 — Ground in your docs",
    desc: "Ingest documents via memorizz KnowledgeBase, retrieve the most relevant passages by vector search, then answer grounded only in them — with bracketed citations. Oracle AI Database, or filesystem fallback.",
    term: "<b>Semantic memory</b> (<code>KNOWLEDGE_BASE</code>): long-term document memory. Chunk → embed → vector-search → ground the answer. This is RAG, living inside the memory system.",
    meta: { Type: "Semantic", Store: "KNOWLEDGE_BASE", Retrieval: "Vector" },
  },
  {
    id: "procedural", rung: 4, nav: "Procedural", icon: I.tool, accent: "var(--r4)",
    title: "Procedural Memory", kicker: "Layer 04 — How to act",
    desc: "How an agent acts: callable tools it can invoke, a stored workflow (runbook) recalled by intent, and a skillbox of how-to guides retrieved as a manifest. Watch each piece resolve, then the agent answers.",
    term: "<b>Procedural memory</b> (<code>TOOLBOX</code> · <code>WORKFLOW_MEMORY</code> · skillbox): tools, runbooks, and guides — the agent's skills, retrievable by intent.",
    meta: { Type: "Procedural", Store: "TOOLBOX · WORKFLOW", Acts: "Via tools" },
  },
  {
    id: "coordination", rung: 5, nav: "Coordination", icon: I.agent, accent: "var(--r5)",
    title: "Shared Memory — Multi-Agent", kicker: "Layer 05 — A coordinating team",
    desc: "The top layer: a lead orchestrator delegates to a Researcher and a Reviewer that collaborate over a shared blackboard, then the lead synthesizes one recommendation. Built on memorizz's MultiAgentOrchestrator.",
    term: "<b>Shared memory</b> (<code>SHARED_MEMORY</code>): a blackboard multiple agents read and write — commands, reports, artifacts — so a team can coordinate with a common trail.",
    meta: { Type: "Social", Store: "SHARED_MEMORY", Agents: "Lead + 2" },
  },
];
const FF_BY_ID = Object.fromEntries(FF.map((f) => [f.id, f]));

// ── tiny utils ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
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
  try { resetCtxRail(); } catch (_) {}
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
      if (data) {
        try {
          const obj = JSON.parse(data);
          if (obj && obj.type === "context") { try { updateCtxRail(obj); } catch (_) {} }
          else if (obj && (obj.type === "architecture" || obj.type === "flow" || obj.type === "agent_context")) { try { handleCoordEvent(obj); } catch (_) {} }
          onEvent(obj);
        } catch (_) {}
      }
    }
  }
}

async function getJSON(url) { const r = await fetch(url); return r.json(); }

// ── app state ──────────────────────────────────────────────────────────
const state = {
  health: null,
  session: uid(),     // shared conversation id for stateful layers
  abort: null,
  galleries: null,
};
function cancelStream() { if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; } }

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
      <span class="brand-glyph">${I.stack}</span>
      <span class="brand-text"><b>Memory Stack</b><span>Five layers of agent memory</span></span>
    </div>
    <div class="rail-label">The Stack</div>
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
  const mem = h.memory || {};
  const ready = mem.ready;
  const backend = mem.backend === "oracle" ? "Oracle AI DB" : mem.backend === "filesystem" ? "Filesystem" : "warming…";
  const mdot = !ready ? "warn pulse" : "ok";
  const kdot = h.api_key_set ? "ok" : "off";
  return `
    <div class="status-row"><span class="k">Model</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Memory</span><span class="dot ${mdot}"></span><span>${backend}</span></div>
    <div class="status-row"><span class="k">OpenAI key</span><span class="dot ${kdot}"></span><span>${h.api_key_set ? "set" : "missing"}</span></div>`;
}

function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("amem-theme", next); } catch (_) {}
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
function backendLabel() {
  const b = state.health && state.health.memory && state.health.memory.backend;
  return b === "oracle" ? "Oracle AI Database" : b === "filesystem" ? "filesystem (FAISS)" : "warming…";
}

// ── view: home ─────────────────────────────────────────────────────────
function viewHome() {
  const rungs = FF.map((f, i) => `
    <a class="rung" href="#/${f.id}" style="--c:${f.accent};animation-delay:${i * 70 + 80}ms">
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
    <section class="hero">
      <div class="hero-kicker"><span class="pip"></span> The Agent Memory Stack</div>
      <h1>Grow an agent from a goldfish into a colleague — <em>one memory layer at a time</em>.</h1>
      <p>One copilot — <b>Memo</b>, for a fictional <b>Acme Cloud</b> platform team — built up across five layers of memory with the <b>memorizz</b> framework on <b>Oracle AI Database</b> (with a filesystem fallback). Each layer adds exactly one capability the layer below was missing.</p>
    </section>
    <div class="ladder">${rungs}</div>`, "var(--r5)");
}

// ── view: conversation (Layer 1) ─────────────────────────────────────────
function viewConversation() {
  const f = FF_BY_ID.conversation;
  setStage(`${ffHeader(f)}
    <div class="panel">
      <div class="panel-head">
        <span class="panel-title">${I.chat} Conversation</span>
        <div class="row">
          <button class="btn btn-ghost" id="reload-agent" title="Reconstruct the agent from storage by its id">${I.reload} Reload from storage</button>
          <button class="btn btn-ghost" id="new-chat">${I.refresh} New chat</button>
        </div>
      </div>
      <div class="panel-body">
        <div class="chat-wrap">
          <div class="chat-scroll" id="chat-scroll">
            <div class="empty">Tell Memo something about you and your work, then ask it later. It persists to ${esc(backendLabel())}.</div>
          </div>
          <div class="memory-note" id="mem-note"></div>
          <div class="composer">
            <textarea id="chat-input" placeholder="Message Memo…  (e.g. I'm Ada, migrating our RAG stack to Oracle 23ai)" rows="1"></textarea>
            <button class="btn btn-accent" id="chat-send">${I.send} Send</button>
          </div>
        </div>
      </div>
    </div>`, f.accent);

  const scroll = $("#chat-scroll"), input = $("#chat-input"), send = $("#chat-send");
  let first = true;

  async function send_(url, body, label) {
    if (state.abort) return;
    if (first) { scroll.innerHTML = ""; first = false; }
    const bubble = addMsg(scroll, "bot", "");
    bubble.innerHTML = '<span class="caret"></span>';
    send.disabled = true;
    let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE(url, body, (ev) => {
        if (ev.type === "reloaded") { bubble.innerHTML = `<span class="muted">↻ reloaded agent <span class="mono">${esc((ev.agent_id||"").slice(0,8))}</span> from ${esc(ev.backend||"")}…</span><br>` ; }
        else if (ev.type === "delta") { acc += ev.text; bubble.innerHTML = renderRich(acc) + '<span class="caret"></span>'; scroll.scrollTop = scroll.scrollHeight; }
        else if (ev.type === "done") {
          bubble.innerHTML = renderRich(acc);
          const note = ev.reloaded ? `recalled after reload · agent <b class="mono">${esc((ev.agent_id||"").slice(0,8))}</b> · ${esc(ev.backend||"")}`
                                   : `persisted to <b>${esc(ev.backend||"")}</b> · turn <b>${ev.turns}</b> · agent <span class="mono">${esc((ev.agent_id||"").slice(0,8))}</span>`;
          $("#mem-note").innerHTML = note;
        } else if (ev.type === "error") { bubble.innerHTML = `<span style="color:var(--r5)">${esc(ev.message)}</span>`; }
      }, state.abort.signal);
    } catch (e) { bubble.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; send.disabled = false; input.focus(); }
  }

  async function sendMsg() {
    const text = input.value.trim();
    if (!text) return;
    input.value = ""; autosize(input);
    addMsg(scroll, "user", text);
    await send_("/api/conversation/message", { session_id: state.session, message: text });
  }

  send.addEventListener("click", sendMsg);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  input.addEventListener("input", () => autosize(input));
  $("#reload-agent").addEventListener("click", () => {
    if (first) { scroll.innerHTML = ""; first = false; }
    addMsg(scroll, "user", "⟳ (simulated restart) — recall what you know about me");
    send_("/api/conversation/reload", { session_id: state.session, message: "" });
  });
  $("#new-chat").addEventListener("click", async () => {
    cancelStream();
    await fetch("/api/conversation/reset?session_id=" + state.session, { method: "POST" }).catch(() => {});
    state.session = uid();
    scroll.innerHTML = `<div class="empty">New conversation. A fresh agent with empty memory.</div>`;
    $("#mem-note").innerHTML = ""; first = true;
  });
  input.focus();
}

function addMsg(scroll, role, text) {
  if (scroll.querySelector(".empty")) scroll.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="avatar ${role}">${role === "bot" ? I.bot : "YOU"}</div><div class="bubble">${role === "bot" ? "" : renderRich(text)}</div>`;
  scroll.appendChild(wrap);
  scroll.scrollTop = scroll.scrollHeight;
  return wrap.querySelector(".bubble");
}
function autosize(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 160) + "px"; }

// ── view: semantic (Layer 2) ─────────────────────────────────────────────
const SEM_SAMPLES = [
  "For the record: our on-call tool is PagerPilot, and Ada owns it.",
  "I'm Ada, a senior ML engineer; my current project is the RAG migration to Oracle 23ai.",
  "Who owns PagerPilot, and what is my current project?",
];
function viewSemantic() {
  const f = FF_BY_ID.semantic;
  setStage(`${ffHeader(f)}
    <div class="grid-2 mb">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.id} Persona</span></div>
        <div class="panel-body"><div id="sem-persona" class="persona"><div class="empty">Loading persona…</div></div></div>
      </div>
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.db} Entity memory</span><button class="btn btn-ghost" id="sem-refresh">${I.refresh}</button></div>
        <div class="panel-body"><div id="sem-entities" class="sources"><div class="empty">Facts you state become structured entities here.</div></div></div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.chat} Talk to Memo</span></div>
      <div class="panel-body">
        <div class="field">
          <textarea id="sem-input" rows="1" placeholder="State a fact, or ask Memo to recall one…">${esc(SEM_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="sem-send">${I.send} Send</button>
        </div>
        <div class="chips" style="margin-top:12px">${SEM_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 40))}…</button>`).join("")}</div>
        <div id="sem-answer" class="bubble" style="margin-top:14px"><div class="empty">Memo answers in character, recording and recalling facts.</div></div>
      </div>
    </div>`, f.accent);

  getJSON("/api/semantic/persona").then((d) => renderPersona(d.persona)).catch(() => {});
  loadEntities();
  const input = $("#sem-input"), sendb = $("#sem-send");
  $$(".chip", $("#stage")).forEach((c, i) => c.addEventListener("click", () => { input.value = SEM_SAMPLES[i]; autosize(input); }));

  async function ask() {
    const msg = input.value.trim(); if (!msg || state.abort) return;
    const ans = $("#sem-answer"); ans.innerHTML = '<span class="caret"></span>';
    sendb.disabled = true; let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/semantic/message", { session_id: state.session, message: msg }, (ev) => {
        if (ev.type === "delta") { acc += ev.text; ans.innerHTML = renderRich(acc) + '<span class="caret"></span>'; }
        else if (ev.type === "done") { ans.innerHTML = renderRich(acc) || `<div class="empty">No answer.</div>`; if (ev.entities) renderEntities(ev.entities); }
        else if (ev.type === "error") { ans.innerHTML = `<span style="color:var(--r5)">${esc(ev.message)}</span>`; }
      }, state.abort.signal);
    } catch (e) { ans.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; sendb.disabled = false; }
  }
  sendb.addEventListener("click", ask);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
  input.addEventListener("input", () => autosize(input));
  $("#sem-refresh").addEventListener("click", loadEntities);
  autosize(input);
}
function renderPersona(p) {
  const box = $("#sem-persona"); if (!box) return;
  if (!p) { box.innerHTML = `<div class="empty">No persona.</div>`; return; }
  box.innerHTML = `
    <div class="persona-name">${esc(p.name)} <span class="tag ok">${esc(p.role)}</span></div>
    <div class="kv2"><span class="mk">Goals</span><span>${esc(p.goals)}</span></div>
    <div class="kv2"><span class="mk">Background</span><span>${esc(p.background)}</span></div>`;
}
async function loadEntities() { try { const d = await getJSON("/api/semantic/entities"); renderEntities(d.entities); } catch (_) {} }
function renderEntities(list) {
  const box = $("#sem-entities"); if (!box) return;
  if (!list || !list.length) { box.innerHTML = `<div class="empty">No entities yet — state a durable fact.</div>`; return; }
  box.innerHTML = list.map((e, i) => `
    <div class="source" style="animation-delay:${i * 50}ms">
      <div class="source-top"><span class="source-title">${esc(e.name)}</span><span class="source-cat">${esc(e.entity_type || "entity")}</span></div>
      <div class="source-body">${(e.attributes && e.attributes.length) ? e.attributes.map((a) => `<span class="kv">${esc(a.name)} <b>${esc(a.value)}</b></span>`).join(" ") : '<span class="muted">no attributes captured</span>'}</div>
    </div>`).join("");
}

// ── view: knowledge (Layer 3) ────────────────────────────────────────────
const KB_SAMPLES = [
  "What is the exact API rate limit on the Pro plan?",
  "How long are backups retained?",
  "Which plans include SSO?",
  "Can I change my project's region after creation?",
];
function viewKnowledge() {
  const f = FF_BY_ID.knowledge;
  setStage(`${ffHeader(f)}
    <div class="panel mb">
      <div class="panel-body">
        <div class="row spread mb"><span class="hint">Ask about <b>Acme Cloud</b> — answered only from the ingested docs.</span><span class="hint" id="kb-backend"></span></div>
        <div class="field">
          <textarea id="kb-input" rows="1" placeholder="Ask about Acme Cloud…"></textarea>
          <button class="btn btn-accent" id="kb-ask">${I.send} Ask</button>
        </div>
        <div class="chips" style="margin-top:12px">${KB_SAMPLES.map((s) => `<button class="chip">${esc(s)}</button>`).join("")}</div>
      </div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.bot} Grounded answer</span></div>
        <div class="panel-body"><div id="kb-answer" class="bubble" style="background:transparent;border:none;padding:0"><div class="empty">The answer cites its sources like [1].</div></div></div>
      </div>
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.rag} Retrieved context</span></div>
        <div class="panel-body"><div id="kb-sources" class="sources"><div class="empty">Retrieved passages appear here.</div></div></div>
      </div>
    </div>`, f.accent);

  const input = $("#kb-input"), ask = $("#kb-ask");
  $$(".chip", $("#stage")).forEach((c) => c.addEventListener("click", () => { input.value = c.textContent; runKB(); }));

  async function runKB() {
    const q = input.value.trim(); if (!q || state.abort) return;
    const ans = $("#kb-answer"), src = $("#kb-sources");
    ans.innerHTML = '<span class="caret"></span>'; src.innerHTML = `<div class="empty"><span class="spinner" style="display:inline-block"></span> retrieving…</div>`;
    ask.disabled = true; let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/knowledge/answer", { query: q, k: 4 }, (ev) => {
        if (ev.type === "sources") {
          $("#kb-backend").innerHTML = `backend: <b class="mono" style="color:var(--accent)">${ev.backend === "oracle" ? "Oracle AI Database" : "filesystem (FAISS)"}</b>`;
          src.innerHTML = ev.hits.length ? ev.hits.map((h, i) => sourceCard(h, i)).join("") : `<div class="empty">No matches.</div>`;
        } else if (ev.type === "delta") { acc += ev.text; ans.innerHTML = renderRich(acc) + '<span class="caret"></span>'; }
        else if (ev.type === "done") { ans.innerHTML = renderRich(acc) || `<div class="empty">No answer.</div>`; }
        else if (ev.type === "error") { ans.innerHTML = `<span style="color:var(--r5)">${esc(ev.message)}</span>`; src.innerHTML = `<div class="empty">—</div>`; }
      }, state.abort.signal);
    } catch (e) { ans.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; ask.disabled = false; }
  }
  ask.addEventListener("click", runKB);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runKB(); } });
  input.addEventListener("input", () => autosize(input));
  input.focus();
}
function sourceCard(h, i) {
  return `<div class="source" style="animation-delay:${i * 50}ms">
    <div class="source-top"><span class="source-idx">${i + 1}</span><span class="source-title">${esc(h.title)}</span><span class="source-cat">${esc(h.category)}</span><span class="source-score">${(+h.score).toFixed(3)}</span></div>
    <div class="source-body">${esc(h.content)}</div></div>`;
}

// ── pipeline rendering (shared by procedural + coordination) ──────────────
function addStage(pipe, step, labels) {
  if (pipe.querySelector(".empty")) pipe.innerHTML = "";
  const row = document.createElement("div");
  row.className = "stage-row running";
  row.dataset.step = step;
  row.innerHTML = `<div class="stage-rail"><div class="stage-dot"><span class="spinner"></span></div><div class="stage-line"></div></div>
    <div class="stage-card"><div class="stage-name">${esc(labels[step] || step)} <span class="stage-sub">working…</span></div><div class="stage-content"></div></div>`;
  pipe.appendChild(row); return row;
}

// ── view: procedural (Layer 4) ───────────────────────────────────────────
const PROC_SAMPLES = [
  "Is the vector-search-svc healthy right now?",
  "We expect 2,000,000 requests/month at ~800 tokens each on gpt-4o-mini input. Monthly cost?",
  "Our retrieval service is down — what's our process, and what should I check first?",
];
const PROC_LABELS = { tools: "Tools available", workflow: "Workflow recalled", skill: "Skill recalled", answer: "Agent answer" };
function viewProcedural() {
  const f = FF_BY_ID.procedural;
  setStage(`${ffHeader(f)}
    <div class="panel mb">
      <div class="panel-body">
        <div class="field">
          <textarea id="pr-input" rows="2" placeholder="Ask something that needs a tool, a runbook, or a skill…">${esc(PROC_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="pr-run">${I.play} Run</button>
        </div>
        <div class="chips" style="margin-top:12px">${PROC_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 44))}…</button>`).join("")}</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.tool} Procedural memory in action</span><span class="hint mono" id="pr-status"></span></div>
      <div class="panel-body"><div class="pipeline" id="pr-pipe"><div class="empty">Run to see tools, a recalled workflow, a skill, then the answer.</div></div></div>
    </div>`, f.accent);

  const input = $("#pr-input"), run = $("#pr-run"), pipe = $("#pr-pipe");
  $$(".chip", $("#stage")).forEach((c, i) => c.addEventListener("click", () => { input.value = PROC_SAMPLES[i]; autosize(input); }));

  async function runProc() {
    const message = input.value.trim(); if (!message || state.abort) return;
    pipe.innerHTML = ""; run.disabled = true; $("#pr-status").textContent = "running…";
    const pending = {}; let answerRow = null, acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/procedural/run", { message }, (ev) => {
        if (ev.type === "step") {
          if (ev.status === "running") pending[ev.step] = addStage(pipe, ev.step, PROC_LABELS);
          else fillProc(pending[ev.step] || addStage(pipe, ev.step, PROC_LABELS), ev.step, ev.data || {});
        } else if (ev.type === "delta") {
          if (!answerRow) { answerRow = pending.answer || addStage(pipe, "answer", PROC_LABELS); answerRow.className = "stage-row done"; $(".stage-dot", answerRow).innerHTML = I.bot; $(".stage-name", answerRow).innerHTML = "Agent answer"; }
          acc += ev.text; $(".stage-content", answerRow).innerHTML = renderRich(acc);
          pipe.scrollTop = pipe.scrollHeight;
        } else if (ev.type === "final") { $("#pr-status").textContent = "done"; }
        else if (ev.type === "error") { pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>${esc(ev.message)}</div></div>`); }
      }, state.abort.signal);
    } catch (e) { pipe.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>Error: ${esc(e.message)}</div></div>`); }
    finally { state.abort = null; run.disabled = false; }
  }
  run.addEventListener("click", runProc);
  autosize(input);
}
function fillProc(row, step, data) {
  if (!row) return;
  row.className = "stage-row done";
  const dot = $(".stage-dot", row), name = $(".stage-name", row), content = $(".stage-content", row);
  dot.innerHTML = I.check;
  if (step === "tools") {
    name.innerHTML = `Tools available <span class="stage-sub">toolbox</span>`;
    content.innerHTML = `<div class="chips">${(data.tools || []).map((t) => `<span class="chip" style="cursor:default" title="${esc(t.desc)}">${esc(t.name)}</span>`).join("")}</div>`;
  } else if (step === "workflow") {
    name.innerHTML = `Workflow recalled <span class="stage-sub">WORKFLOW_MEMORY</span>`;
    content.innerHTML = data.workflow ? `<b>${esc(data.workflow.name)}</b> <span class="muted">→ ${(data.workflow.steps || []).map(esc).join(" · ")}</span>` : `<span class="muted">No workflow matched.</span>`;
  } else if (step === "skill") {
    name.innerHTML = `Skill recalled <span class="stage-sub">skillbox manifest</span>`;
    content.innerHTML = data.skill ? `<b>${esc(data.skill.name)}</b> <span class="muted">— ${esc(data.skill.description)}</span>` : `<span class="muted">No skill matched.</span>`;
  } else if (step === "answer") {
    name.innerHTML = `Agent answer <span class="stage-sub">uses tools as needed</span>`;
  }
}

// ── view: coordination (Layer 5) ─────────────────────────────────────────
const CO_SAMPLES = [
  "Should we move our embeddings from text-embedding-3-small (256d) to a larger model? Weigh quality vs cost and recommend.",
  "Is it worth adding a semantic cache in front of our support agent? Give a recommendation.",
  "Should we switch our vector index from HNSW to IVF for our workload?",
];
function viewCoordination() {
  const f = FF_BY_ID.coordination;
  setStage(`${ffHeader(f)}
    <div class="panel mb">
      <div class="panel-body">
        <div class="field">
          <textarea id="co-input" rows="2" placeholder="Give the team a decision to make…">${esc(CO_SAMPLES[0])}</textarea>
          <button class="btn btn-accent" id="co-run">${I.play} Run team</button>
        </div>
        <div class="chips" style="margin-top:12px">${CO_SAMPLES.map((s) => `<button class="chip">${esc(s.slice(0, 44))}…</button>`).join("")}</div>
        <div class="hint" style="margin-top:10px">Lead delegates to <span class="mono" style="color:var(--accent)">Researcher</span> + <span class="mono" style="color:var(--accent)">Reviewer</span> over shared memory — <b>watch the live agentic flow in the right pane →</b> and hover any agent to see its context window. Several LLM calls, so give it a moment.</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><span class="panel-title">${I.bot} Synthesized recommendation</span><span class="hint mono" id="co-status"></span></div>
      <div class="panel-body"><div id="co-answer" class="bubble" style="background:transparent;border:none;padding:0"><div class="empty">The Lead's final recommendation streams here once the specialists report back — the agents' instructions and reports appear live in the right pane.</div></div></div>
    </div>`, f.accent);

  const input = $("#co-input"), run = $("#co-run"), ans = $("#co-answer");
  $$(".chip", $("#stage")).forEach((c, i) => c.addEventListener("click", () => { input.value = CO_SAMPLES[i]; autosize(input); }));

  async function runCo() {
    const prompt = input.value.trim(); if (!prompt || state.abort) return;
    ans.innerHTML = '<span class="caret"></span>'; run.disabled = true;
    $("#co-status").innerHTML = '<span class="spinner" style="display:inline-block"></span> coordinating…';
    let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/coordination/run", { prompt }, (ev) => {
        if (ev.type === "delta") { acc += ev.text; ans.innerHTML = renderRich(acc) + '<span class="caret"></span>'; }
        else if (ev.type === "final") { ans.innerHTML = renderRich(acc) || renderRich(ev.reply || ""); $("#co-status").textContent = "done"; }
        else if (ev.type === "error") { ans.innerHTML = `<span style="color:var(--r5)">${esc(ev.message)}</span>`; $("#co-status").textContent = "error"; }
      }, state.abort.signal);
    } catch (e) { ans.innerHTML = `<span style="color:var(--r5)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; run.disabled = false; if (($("#co-status").textContent || "").includes("coordinating")) $("#co-status").textContent = ""; }
  }
  run.addEventListener("click", runCo);
  autosize(input);
}

// ── agent log (kept for completeness) ────────────────────────────────────
function addEvent(log, ev) {
  if (log.querySelector(".empty")) log.innerHTML = "";
  const node = document.createElement("div");
  if (ev.type === "delta" || ev.type === "text") {
    node.className = "ev text"; node.innerHTML = `<div class="ev-icon">${I.bot}</div><div class="ev-text"><div class="ev-bubble">${renderRich(ev.text || "")}</div></div>`;
  } else if (ev.type === "error") {
    node.className = "ev err"; node.innerHTML = `<div class="ev-icon">${I.alert}</div><div class="ev-text"><div class="ev-bubble">${esc(ev.message)}</div></div>`;
  } else return null;
  log.appendChild(node); log.scrollTop = log.scrollHeight; return node;
}

// ── context window rail (right side, every page) ─────────────────────────
const CTX_COLORS = {
  system: "#8b8f98", persona: "var(--r2)", history: "var(--r1)", entity: "var(--r3)",
  knowledge: "var(--r4)", summary: "#a78bfa", tools: "var(--r5)", shared: "#22d3ee",
  query: "#10b981", extra: "#94a3b8",
};
const ctxColor = (k) => CTX_COLORS[k] || "#94a3b8";

// shared renderers so the main rail AND the per-agent coordination view show
// identical segmented bars + expandable content rows.
function ctxBarHTML(segs, win) {
  return segs.map((s) =>
    `<span class="ctx-seg" title="${esc(s.label)} · ${s.tokens} tok" style="width:${((s.tokens / win) * 100).toFixed(2)}%;background:${ctxColor(s.kind)}"></span>`).join("");
}
function ctxLegendHTML(segs, prefix) {
  return segs.map((s, i) => {
    const preview = s.preview != null ? String(s.preview) : "";
    const trunc = s.truncated
      ? `<div class="ctx-trunc">showing ${preview.length.toLocaleString()} of ${(s.chars || preview.length).toLocaleString()} chars in this segment</div>`
      : "";
    const body = preview ? esc(preview) : '<span class="muted">(no text content)</span>';
    return `<div class="ctx-leg-item">
      <button class="ctx-leg" data-c="${prefix}-${i}" type="button" title="Click to view contents">
        <span class="sw" style="background:${ctxColor(s.kind)}"></span>
        <span class="nm">${esc(s.label)}</span>
        <span class="tk">${s.tokens.toLocaleString()}</span>
        <span class="cx-caret">${I.arrow}</span>
      </button>
      <div class="ctx-content" id="${prefix}-${i}" hidden><pre>${body}</pre>${trunc}</div>
    </div>`;
  }).join("");
}
function attachCtxToggles(root) {
  $$(".ctx-leg", root).forEach((b) => b.addEventListener("click", () => {
    const c = document.getElementById(b.dataset.c); if (!c) return;
    if (c.hasAttribute("hidden")) { c.removeAttribute("hidden"); b.classList.add("open"); }
    else { c.setAttribute("hidden", ""); b.classList.remove("open"); }
  }));
}

function renderCtxRail() {
  const el = $("#ctxrail"); if (!el) return;
  if (state.route === "coordination") { renderCoordRail(); return; }
  el.innerHTML = `
    <div class="ctx-title">${I.stack} Context Window</div>
    <div class="ctx-readout"><span class="ctx-pct" id="ctx-pct">0<span class="lbl">%</span></span></div>
    <div class="ctx-sub" id="ctx-sub">idle — run a turn to watch it fill</div>
    <div class="ctx-bar" id="ctx-bar"></div>
    <div class="ctx-legend" id="ctx-legend"><div class="ctx-empty">As the agent assembles each turn, the memory packed into its prompt appears here in real time — persona, conversation, entities, knowledge, tools, and your query.</div></div>
    <div class="ctx-foot">Estimates of what fills the model's context window per turn; the final value reconciles to the agent's reported token usage.</div>`;
}

function resetCtxRail() {
  if (state.route === "coordination") { renderCoordRail(); return; }
  const sub = $("#ctx-sub"), leg = $("#ctx-legend"), bar = $("#ctx-bar"), pct = $("#ctx-pct");
  if (!sub) return;
  sub.textContent = "assembling context…";
  if (leg) leg.innerHTML = `<div class="ctx-empty">assembling…</div>`;
  if (bar) bar.innerHTML = "";
  if (pct) pct.innerHTML = `0<span class="lbl">%</span>`;
}

function updateCtxRail(ev) {
  const bar = $("#ctx-bar"), leg = $("#ctx-legend"), pct = $("#ctx-pct"), sub = $("#ctx-sub");
  if (!bar) return;
  const win = ev.window || 1, used = ev.used || 0, segs = ev.segments || [];
  const p = Math.min(100, (used / win) * 100);
  pct.innerHTML = (p < 1 ? p.toFixed(2) : p.toFixed(1)) + `<span class="lbl">% of ${Math.round(win / 1000)}k</span>`;
  sub.textContent = `${used.toLocaleString()} / ${win.toLocaleString()} tokens` + (ev.stage === "prefill" ? " · filling…" : " · packed");
  bar.innerHTML = ctxBarHTML(segs, win);
  if (!segs.length) { leg.innerHTML = `<div class="ctx-empty">—</div>`; return; }
  leg.innerHTML = ctxLegendHTML(segs, "ctxc");
  attachCtxToggles(leg);
}

// ── coordination agent-flow rail (memory layer 5) ────────────────────────
const COORD_POS = { lead: [50, 16], researcher: [21, 52], reviewer: [79, 52], output: [50, 90] };
const COORD_LABEL = { lead: "Lead", researcher: "Researcher", reviewer: "Reviewer", output: "Recommendation" };
let coordCtx = {};
const _coordSeen = {};
function _coordSeenReset() { for (const k in _coordSeen) delete _coordSeen[k]; }

function renderCoordRail() {
  const el = $("#ctxrail"); if (!el) return;
  coordSelected = null;
  el.innerHTML = `
    <div class="ctx-title">${I.agent} Agentic Flow</div>
    <div class="cflow" id="cflow"><div class="ctx-empty" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:0 14px">Run the team to watch the Lead delegate to specialists in real time. Click an agent to inspect its context window.</div></div>
    <div id="coord-ctx" class="coord-ctx"><div class="ctx-empty">Click an agent above to inspect its full context window — segment by segment, with contents.</div></div>
    <div class="ctx-title" style="margin-top:4px">Live transcript</div>
    <div class="ctranscript" id="ctranscript"><div class="ctx-empty">Instructions and reports stream here as agents hand off work over the shared blackboard.</div></div>
    <div class="ctx-foot">A Lead agent delegates to a Researcher and a Reviewer over shared memory, then synthesizes — the same pattern as memorizz's MultiAgentOrchestrator, shown step by step.</div>`;
}

function drawCoordGraph(arch) {
  const wrap = $("#cflow"); if (!wrap) return;
  coordCtx = {};
  const drawn = {}; let lines = "";
  (arch.edges || []).forEach((e) => {
    const other = e.src === "lead" ? e.dst : e.src; const key = "lead-" + other;
    if (drawn[key]) return; drawn[key] = 1;
    const a = COORD_POS.lead, b = COORD_POS[other]; if (!a || !b) return;
    lines += `<line id="edge-${key}" class="cedge" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"></line>`;
  });
  const nodes = (arch.agents || []).map((a) => {
    const p = COORD_POS[a.id]; if (!p) return "";
    return `<div class="cnode ${a.role === "output" ? "output" : ""}" id="node-${a.id}" data-agent="${a.id}" title="${esc(a.desc || "")}" style="left:${p[0]}%;top:${p[1]}%"><div class="chip"><span class="role-dot"></span>${esc(a.name)}</div><div class="role">${esc(a.role)}</div></div>`;
  }).join("");
  wrap.innerHTML = `<svg viewBox="0 0 100 100" preserveAspectRatio="none">${lines}</svg>${nodes}`;
  $$(".cnode", wrap).forEach((n) => {
    n.addEventListener("click", () => showAgentContext(n.dataset.agent));
  });
  coordSelected = null;
  const cc = $("#coord-ctx"); if (cc) cc.innerHTML = `<div class="ctx-empty">Click an agent above to inspect its full context window.</div>`;
  const t = $("#ctranscript"); if (t) t.innerHTML = `<div class="ctx-empty">delegating…</div>`;
}

function handleCoordEvent(ev) {
  if (ev.type === "architecture") { _coordSeenReset(); drawCoordGraph(ev); return; }
  if (ev.type === "agent_context") {
    coordCtx[ev.agent] = ev;
    if (coordSelected === ev.agent) showAgentContext(ev.agent);  // live-refresh the open panel
    return;
  }
  if (ev.type !== "flow") return;
  const other = ev.src === "lead" ? ev.dst : ev.src;
  const edge = $("#edge-lead-" + other);
  $$(".cnode").forEach((n) => n.classList.remove("busy"));
  if (ev.status === "active") {
    if (edge) edge.classList.add("active");
    const dst = $("#node-" + ev.dst); if (dst) dst.classList.add("busy");
  } else if (edge) { edge.classList.remove("active"); edge.classList.add("done"); }
  const showIt = (ev.kind === "instruction" && ev.status === "active") || (ev.kind !== "instruction" && ev.status === "done");
  const seenKey = ev.id + ":" + ev.status;
  if (showIt && ev.content && !_coordSeen[seenKey]) {
    _coordSeen[seenKey] = 1;
    const log = $("#ctranscript"); if (!log) return;
    if (log.querySelector(".ctx-empty")) log.innerHTML = "";
    const div = document.createElement("div");
    div.className = "cmsg kind-" + ev.kind;
    const dstLabel = COORD_LABEL[ev.dst] || ev.dst;
    div.innerHTML = `<div class="hd">${esc(COORD_LABEL[ev.src] || ev.src)} <span class="arrow">→</span> ${esc(dstLabel)} <span style="margin-left:auto">${esc(ev.kind)}</span></div><div class="bd">${renderRich(String(ev.content).slice(0, 280))}</div>`;
    log.appendChild(div); log.scrollTop = log.scrollHeight;
  }
}

let coordSelected = null;
function showAgentContext(agentId) {
  coordSelected = agentId;
  $$(".cnode").forEach((n) => n.classList.toggle("sel", n.dataset.agent === agentId));
  const box = $("#coord-ctx"); if (!box) return;
  const ctx = coordCtx[agentId];
  const label = COORD_LABEL[agentId] || agentId;
  if (!ctx || !ctx.window) {
    box.innerHTML = `<div class="ctx-title" style="margin-top:6px">${I.stack} Context · ${esc(label)}</div><div class="ctx-empty">No context captured yet — run the team, then click ${esc(label)}.</div>`;
    return;
  }
  const segs = ctx.segments || [], win = ctx.window || 1, used = ctx.used || 0;
  const p = Math.min(100, (used / win) * 100);
  box.innerHTML = `
    <div class="ctx-title" style="margin-top:6px">${I.stack} Context · ${esc(label)}</div>
    <div class="ctx-sub">${used.toLocaleString()} / ${win.toLocaleString()} tokens · ${p.toFixed(1)}% · click a row to read its contents</div>
    <div class="ctx-bar">${ctxBarHTML(segs, win)}</div>
    <div class="ctx-legend">${ctxLegendHTML(segs, "coordctx")}</div>`;
  attachCtxToggles(box);
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

const ROUTES = {
  "": viewHome, conversation: viewConversation, semantic: viewSemantic,
  knowledge: viewKnowledge, procedural: viewProcedural, coordination: viewCoordination,
};
function route() {
  cancelStream();
  const id = (location.hash.replace(/^#\/?/, "").trim()) || "";
  state.route = id;
  const render = ROUTES[id] || viewHome;
  renderSidebar(id || "home");
  renderCtxRail();
  render();
  injectGallery(id || "home");
  if (window.innerWidth <= 760) closeMenu();
}

// ── mobile menu ──────────────────────────────────────────────────────
function openMenu() { $("#sidebar").classList.add("open"); const s = $("#scrim"); s.hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }

// ── boot ─────────────────────────────────────────────────────────────
async function boot() {
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);

  window.addEventListener("hashchange", route);
  route();

  getJSON("/api/images").then((d) => { state.galleries = d.pages || {}; injectGallery(location.hash.split("/")[1] || "home"); }).catch(() => {});

  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); }
    catch (_) {}
    if (!state.health || !state.health.memory || !state.health.memory.ready) setTimeout(poll, 1500);
  }
  poll();
}
boot();
