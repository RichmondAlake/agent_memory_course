/* ======================================================================
   Agent Memory Benchmarks — single-page app
   Vanilla JS. Hash router, theme toggle, SSE-over-fetch streaming client,
   and one interactive stop per concept in the memory-benchmark journey.
   ====================================================================== */

const I = {
  gauge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/><path d="m13.4 12.6 4-4"/><path d="M4 18a8 8 0 1 1 16 0"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="7" ry="2.7"/><path d="M5 5.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/><path d="M5 11.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/></svg>',
  scale: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M7 21h10M5 7h14l-2.5 6a3 3 0 0 1-4.9 0L9 7M5 7l-2.5 6a3 3 0 0 0 4.9 0L10 7"/><path d="M5 7 12 5l7 2"/></svg>',
  triangle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4 3 19h18L12 4Z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M5 9h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM9 13h.01M15 13h.01"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m4 12 16-8-6 16-3-7-7-1Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  bulb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.2 1 2.5h6c0-1.3.3-1.8 1-2.5A6 6 0 0 0 12 3Z"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
};

// ── the journey ──────────────────────────────────────────────────────
const STOPS = [
  {
    id: "naive", n: 1, nav: "Naive Memory", icon: I.history, accent: "var(--s1)",
    kicker: "Stop 01 — Re-send everything",
    title: "Naive Memory", desc: "The simplest way to give a chatbot memory: keep every message and re-send the whole conversation on each turn. It works — but the prompt grows without bound. Chat below and watch the token meter climb.",
    term: "<b>Naive memory:</b> the agent's memory <i>is</i> the growing message list. Nothing is stored or retrieved — every fact you've ever mentioned rides along in the prompt, every single turn.",
  },
  {
    id: "memory", n: 2, nav: "Oracle Agent Memory", icon: I.db, accent: "var(--s2)",
    kicker: "Stop 02 — Persist, extract, retrieve",
    title: "Oracle Agent Memory", desc: "The same Claude model, but each turn is persisted into Oracle AI Database, durable facts are extracted, and only a small, relevant context card is retrieved — instead of replaying the whole transcript. Watch the memory store fill on the right.",
    term: "<b>OAMP:</b> memory becomes a durable, searchable store. The prompt stays small and flat because the agent retrieves the facts it needs rather than carrying all of them.",
  },
  {
    id: "benchmark", n: 3, nav: "Head-to-Head", icon: I.scale, accent: "var(--s3)",
    kicker: "Stop 03 — Measure the trade-off",
    title: "The Head-to-Head Benchmark", desc: "Run a scripted conversation through both agents at once and watch the metrics diverge live: input tokens, latency, and an LLM-as-a-judge quality verdict. This is the heart of the notebook, in motion.",
    term: "<b>The benchmark:</b> identical model, identical questions — only the memory strategy differs. The charts make the cost of each strategy impossible to miss.",
  },
  {
    id: "patterns", n: 4, nav: "Pick Any Two", icon: I.triangle, accent: "var(--s4)",
    kicker: "Stop 04 — The central trade-off",
    title: "Pick Any Two", desc: "Low tokens, low latency, durable memory — you can cleanly optimise any two. The cache-friendly hybrid and offline extraction show how to choose, and when. The synthesis of everything the benchmark taught.",
    term: "<b>The trade-off:</b> there is no single 'best' memory design — only the right pair of guarantees for your workload. This is the decision the whole journey leads to.",
  },
];
const STOP_BY_ID = Object.fromEntries(STOPS.map((s) => [s.id, s]));

// ── utils ───────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
const fmtN = (n) => (n == null ? "—" : Number(n).toLocaleString());

function renderRich(text) {
  let h = esc(text);
  h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/`([^`]+?)`/g, "<code>$1</code>");
  return h.split(/\n{2,}/).map((p) => "<p>" + p.replace(/\n/g, "<br>") + "</p>").join("");
}

async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
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

// ── state ───────────────────────────────────────────────────────────
const state = { health: null, naiveSession: uid(), memSession: uid(), abort: null };
function cancelStream() { if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; } }

// ── sidebar ─────────────────────────────────────────────────────────
function renderSidebar(activeId) {
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" style="--c:var(--text-2);animation-delay:0ms"><span class="nav-node">${I.home}</span><span class="nav-label">Overview</span></a>`,
    ...STOPS.map((s, i) => `<a class="nav-item ${activeId === s.id ? "active" : ""}" href="#/${s.id}" style="--c:${s.accent};animation-delay:${(i + 1) * 55}ms"><span class="nav-node">${s.n}</span><span class="nav-label">${s.nav}</span><span class="nav-rung">${s.icon}</span></a>`),
  ].join("");
  $("#sidebar").innerHTML = `
    <div class="brand"><span class="brand-glyph">${I.gauge}</span><span class="brand-text"><b>Memory Bench</b><span>OAMP vs naive, on Claude</span></span></div>
    <div class="rail-label">The Journey</div>
    <nav class="ladder-rail">${items}</nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle"><span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span id="theme-label">${themeLabel()}</span></span><span class="toggle-track"></span></button>
    </div>`;
  $("#theme-toggle").addEventListener("click", toggleTheme);
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const mem = h.memory || {};
  const mdot = mem.backend === "oracle" ? "ok" : mem.backend === "error" ? "off" : "warn pulse";
  const mlabel = mem.backend === "oracle" ? "Oracle AI DB" : mem.backend === "error" ? "unavailable" : "warming…";
  return `
    <div class="status-row"><span class="k">Agents</span><span class="mono" style="color:var(--text)">${esc(h.agent_model)}</span></div>
    <div class="status-row"><span class="k">Extract</span><span class="mono">${esc(h.small_model)}</span></div>
    <div class="status-row"><span class="k">Memory</span><span class="dot ${mdot}"></span><span>${mlabel}</span></div>`;
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("membench-theme", next); } catch (_) {}
  $("#theme-label").textContent = themeLabel();
  $("#theme-toggle").querySelector("svg").outerHTML = themeIcon();
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

// ── header / stage ──────────────────────────────────────────────────
function stopHeader(s) {
  return `<header class="ff-head"><div class="ff-numeral">${s.n}</div><div class="ff-head-body">
    <div class="ff-kicker">${esc(s.kicker)}</div><h1 class="ff-title">${esc(s.title)}</h1>
    <p class="ff-desc">${esc(s.desc)}</p><div class="ff-term">${s.term}</div></div></header>`;
}
function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "var(--s3)");
  stage.innerHTML = `<div class="view view-enter">${html}</div>`;
  stage.scrollTop = 0;
}
function autosize(el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 150) + "px"; }
function memWarmBanner() {
  const m = state.health && state.health.memory;
  if (m && m.backend === "oracle") return "";
  if (m && m.backend === "error") return `<div class="banner warn">${I.alert}<div>Oracle Agent Memory couldn't connect: <span class="mono">${esc(m.error || "")}</span>. The naive stop still works; start the local <span class="mono">oracle-free</span> database and reload for the OAMP stops.</div></div>`;
  return `<div class="banner warn">${I.alert}<div>Oracle Agent Memory is still warming up (loading the embedder + connecting to Oracle). Give it a few seconds and reload.</div></div>`;
}

// ── overview ────────────────────────────────────────────────────────
function viewHome() {
  const stops = STOPS.map((s, i) => `
    <a class="stop" href="#/${s.id}" style="--c:${s.accent};animation-delay:${i * 70 + 120}ms">
      <div class="stop-num">${s.n}</div>
      <div class="stop-main"><h3>${esc(s.nav)} <span class="muted" style="font-weight:400;font-size:13.5px">· ${esc(s.title)}</span></h3><p>${esc(s.desc)}</p></div>
      <div class="stop-go">${I.arrow}</div></a>`).join("");

  // three-goods triangle
  const tri = `
    <div class="triangle-card">
      <h2>The memory trilemma</h2>
      <p class="sub">Every agent-memory design trades among three goods. You can cleanly have any <b>two</b>; getting all three means giving something back. The whole journey is about choosing your pair.</p>
      <div class="tri-wrap">
        <div class="tri">
          <svg viewBox="0 0 260 220" role="img" aria-label="Trilemma triangle">
            <polygon points="130,18 26,196 234,196" fill="none" stroke="var(--line-2)" stroke-width="1.5"/>
            <circle class="tri-vert" cx="130" cy="18" r="7" stroke="var(--oamp)"/>
            <circle class="tri-vert" cx="26" cy="196" r="7" stroke="var(--naive)"/>
            <circle class="tri-vert" cx="234" cy="196" r="7" stroke="var(--cached)"/>
            <text class="tri-good" x="130" y="8" text-anchor="middle">Low tokens</text>
            <text class="tri-good" x="20" y="212" text-anchor="start">Low latency</text>
            <text class="tri-good" x="240" y="212" text-anchor="end">Durable memory</text>
            <text class="tri-edge" x="58" y="100" text-anchor="middle" transform="rotate(-60 58 100)">OAMP basic</text>
            <text class="tri-edge" x="204" y="100" text-anchor="middle" transform="rotate(60 204 100)">cache-friendly</text>
            <text class="tri-edge" x="130" y="210" text-anchor="middle">naive</text>
          </svg>
        </div>
        <div class="tri-legend">
          <div class="tri-row"><span class="tri-chip" style="background:color-mix(in oklab,var(--naive) 18%,transparent);color:var(--naive)">naive</span><span class="d"><b>Low latency + simple</b>, but tokens grow every turn and memory dies with the process.</span></div>
          <div class="tri-row"><span class="tri-chip" style="background:color-mix(in oklab,var(--oamp) 18%,transparent);color:var(--oamp)">OAMP basic</span><span class="d"><b>Low tokens + durable</b>, at the cost of extra latency from inline extraction.</span></div>
          <div class="tri-row"><span class="tri-chip" style="background:color-mix(in oklab,var(--cached) 18%,transparent);color:var(--cached)">cache-friendly</span><span class="d"><b>Low latency + durable</b>, by giving the token savings back (caching + offline extraction).</span></div>
        </div>
      </div>
    </div>`;

  setStage(`
    <div class="hero">
      <div class="hero-kicker"><span class="pip"></span> Oracle AI Agent Memory · benchmarked on Claude Opus 4.8</div>
      <h1>How should an agent <em>remember</em>?</h1>
      <p>Re-send the whole conversation every turn, or persist it and retrieve only what matters? This is the question that decides an agent's token bill, its latency, and whether it learns anything that outlives a single session. Walk the four stops to feel the trade-off — live.</p>
    </div>
    ${tri}
    <div class="explore-label">Walk the journey — live</div>
    <div class="path">${stops}</div>`, "var(--s2)");
}

// ── Stop 1 · naive ──────────────────────────────────────────────────
function viewNaive() {
  const s = STOP_BY_ID.naive;
  const win = (state.health && state.health.context_window) || 200000;
  setStage(`${stopHeader(s)}
    <div class="chat-layout" id="naive-layout">
      <div class="panel chat-panel">
        <div class="panel-head"><span class="panel-title">${I.history} Conversation</span>
          <button class="btn btn-ghost" id="naive-reset">${I.refresh} New chat</button></div>
        <div class="panel-body"><div class="chat-wrap">
          <div class="chat-scroll" id="naive-scroll"><div class="empty">Tell the assistant some facts, then ask it to recall them. Every reply re-sends the whole conversation — watch the meter climb.</div></div>
          <div class="memory-note" id="naive-note"></div>
          <div class="composer"><textarea id="naive-input" rows="1" placeholder="Message Claude…  (e.g. My name is Sam and our launch is March 14)"></textarea><button class="btn btn-accent" id="naive-send">${I.send} Send</button></div>
        </div></div>
      </div>
      <aside class="side-pane">
        <div class="side-head"><span class="panel-title">${I.gauge} Context window</span></div>
        <div class="meter-box">
          <div class="meter-cap" id="naive-cap">0 / ${fmtN(win)} tokens</div>
          <div class="meter"><div class="meter-fill" id="naive-fill"></div></div>
          <div class="meter-legend"><span><b id="naive-used">0</b> used</span><span><b id="naive-free">${fmtN(win)}</b> free</span></div>
        </div>
        <div class="side-note">Everything the assistant "remembers" is re-sent on every turn — it <b>is</b> the prompt. Tokens climb with each message until the window fills.</div>
        <div class="side-list" id="naive-list"></div>
      </aside>
    </div>`, s.accent);

  const scroll = $("#naive-scroll"), input = $("#naive-input"), send = $("#naive-send");
  let first = true;
  const turns = [];

  function pushTurn(role, text, tok) {
    turns.push({ role, text, tok });
    $("#naive-list").innerHTML = turns.map((t) => `<div class="mem-item"><span class="mk">${t.role}${t.tok ? " · " + fmtN(t.tok) + " tok prompt" : ""}</span>${esc(t.text)}</div>`).join("");
    const l = $("#naive-list"); l.scrollTop = l.scrollHeight;
  }
  function setMeter(tokens, win) {
    const pct = Math.min(100, (tokens / win) * 100);
    $("#naive-fill").style.width = (tokens > 0 ? Math.max(pct, 0.5) : 0) + "%";
    $("#naive-used").textContent = fmtN(tokens);
    $("#naive-free").textContent = fmtN(Math.max(0, win - tokens));
    $("#naive-cap").textContent = `${fmtN(tokens)} / ${fmtN(win)} tokens · ${pct < 1 ? pct.toFixed(2) : pct.toFixed(1)}%`;
  }

  async function sendMsg() {
    const text = input.value.trim();
    if (!text || state.abort) return;
    if (first) { scroll.innerHTML = ""; first = false; }
    input.value = ""; autosize(input);
    addMsg(scroll, "user", text);
    pushTurn("user", text, 0);
    const bubble = addMsg(scroll, "bot", ""); bubble.innerHTML = '<span class="caret"></span>';
    send.disabled = true; let acc = "";
    state.abort = new AbortController();
    try {
      await streamSSE("/api/naive/message", { session_id: state.naiveSession, message: text }, (ev) => {
        if (ev.type === "delta") { acc += ev.text; bubble.innerHTML = renderRich(acc) + '<span class="caret"></span>'; scroll.scrollTop = scroll.scrollHeight; }
        else if (ev.type === "done") {
          bubble.innerHTML = renderRich(acc);
          $("#naive-note").innerHTML = `memory: <b>${ev.turns}</b> messages · <b>${fmtN(ev.input_tokens)}</b> input tokens sent this turn`;
          setMeter(ev.input_tokens, ev.context_window);
          pushTurn("assistant", acc, ev.input_tokens);
        } else if (ev.type === "error") { bubble.innerHTML = `<span style="color:var(--naive)">Error: ${esc(ev.message)}</span>`; }
      }, state.abort.signal);
    } catch (e) { bubble.innerHTML = `<span style="color:var(--naive)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; send.disabled = false; input.focus(); }
  }
  send.addEventListener("click", sendMsg);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  input.addEventListener("input", () => autosize(input));
  $("#naive-reset").addEventListener("click", async () => {
    cancelStream();
    await fetch("/api/naive/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: state.naiveSession }) }).catch(() => {});
    state.naiveSession = uid(); scroll.innerHTML = `<div class="empty">New conversation — memory cleared.</div>`;
    $("#naive-note").innerHTML = ""; first = true; turns.length = 0; $("#naive-list").innerHTML = ""; setMeter(0, win);
  });
  setMeter(0, win); input.focus();
}

function addMsg(scroll, role, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="avatar ${role}">${role === "bot" ? I.bot : "YOU"}</div><div class="bubble">${role === "bot" ? "" : renderRich(text)}</div>`;
  scroll.appendChild(wrap); scroll.scrollTop = scroll.scrollHeight;
  return wrap.querySelector(".bubble");
}

// ── Stop 2 · OAMP ───────────────────────────────────────────────────
function viewMemory() {
  const s = STOP_BY_ID.memory;
  setStage(`${stopHeader(s)}
    ${memWarmBanner()}
    <div class="chat-layout" id="mem-layout">
      <div class="panel chat-panel">
        <div class="panel-head"><span class="panel-title">${I.db} Conversation · OAMP-backed</span>
          <button class="btn btn-ghost" id="mem-reset">${I.refresh} New thread</button></div>
        <div class="panel-body"><div class="chat-wrap">
          <div class="chat-scroll" id="mem-scroll"><div class="empty">Tell the assistant facts, then ask it to recall them. Each turn is persisted to Oracle and the prompt stays small — see the retrieved card &amp; stored memories on the right.</div></div>
          <div class="memory-note" id="mem-note"></div>
          <div class="composer"><textarea id="mem-input" rows="1" placeholder="Message the OAMP agent…"></textarea><button class="btn btn-accent" id="mem-send">${I.send} Send</button></div>
        </div></div>
      </div>
      <aside class="side-pane">
        <div class="side-head"><span class="panel-title">${I.db} Memory store (Oracle)</span></div>
        <div class="side-note">Durable facts OAMP extracted with <b id="mem-small">the small model</b> and stored as searchable vectors. The retrieved <b>context card</b> — not the full transcript — is what's sent to the model.</div>
        <div class="side-list" id="mem-list"><div class="empty">Memories appear after a couple of turns.</div></div>
        <div style="padding:12px;border-top:1px solid var(--line)"><div class="meter-cap" style="margin-bottom:8px">Latest context card sent to the model</div><div class="card-xml" id="mem-card">—</div></div>
      </aside>
    </div>`, s.accent);

  if (state.health) $("#mem-small").textContent = state.health.small_model;
  const scroll = $("#mem-scroll"), input = $("#mem-input"), send = $("#mem-send");
  let first = true;

  function renderMemories(list) {
    $("#mem-list").innerHTML = (list && list.length)
      ? list.map((m, i) => `<div class="mem-item"><span class="mk">memory ${i + 1}</span>${esc(m)}</div>`).join("")
      : `<div class="empty">No durable memories yet — keep chatting.</div>`;
  }

  async function sendMsg() {
    const text = input.value.trim();
    if (!text || state.abort) return;
    if (first) { scroll.innerHTML = ""; first = false; }
    input.value = ""; autosize(input);
    addMsg(scroll, "user", text);
    const bubble = addMsg(scroll, "bot", "");
    bubble.innerHTML = `<span class="spinner"></span> <span class="muted" id="mem-stage">persisting + retrieving from Oracle…</span>`;
    send.disabled = true;
    state.abort = new AbortController();
    try {
      await streamSSE("/api/memory/message", { session_id: state.memSession, message: text }, (ev) => {
        if (ev.type === "working") { const st = $("#mem-stage"); if (st) st.textContent = ev.stage; }
        else if (ev.type === "answer") { bubble.innerHTML = renderRich(ev.text); }
        else if (ev.type === "done") {
          bubble.insertAdjacentHTML("beforeend", `<div class="metrics"><span class="metric tok">prompt <b>${fmtN(ev.input_tokens)}</b> tok</span><span class="metric lat">retrieve <b>${ev.retrieval_s}s</b></span><span class="metric lat">total <b>${ev.total_s}s</b></span></div>`);
          $("#mem-note").innerHTML = `OAMP sent a <b>${fmtN(ev.input_tokens)}</b>-token prompt — a small retrieved card, not the whole history`;
          renderMemories(ev.memories);
          $("#mem-card").textContent = ev.context_card || "—";
          scroll.scrollTop = scroll.scrollHeight;
        } else if (ev.type === "error") { bubble.innerHTML = `<span style="color:var(--naive)">Error: ${esc(ev.message)}</span>`; }
      }, state.abort.signal);
    } catch (e) { bubble.innerHTML = `<span style="color:var(--naive)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; send.disabled = false; input.focus(); }
  }
  send.addEventListener("click", sendMsg);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
  input.addEventListener("input", () => autosize(input));
  $("#mem-reset").addEventListener("click", async () => {
    cancelStream();
    await fetch("/api/memory/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: state.memSession }) }).catch(() => {});
    state.memSession = uid(); scroll.innerHTML = `<div class="empty">New thread — fresh memory.</div>`;
    $("#mem-note").innerHTML = ""; first = true; renderMemories([]); $("#mem-card").textContent = "—";
  });
  input.focus();
}

// ── Stop 3 · benchmark ──────────────────────────────────────────────
function lineChartSVG(series, n, ymax, opts) {
  const W = 520, H = 220, pl = 46, pr = 12, pt = 12, pb = 26;
  const iw = W - pl - pr, ih = H - pt - pb;
  const xs = (i) => pl + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const ys = (v) => pt + ih - (ymax <= 0 ? 0 : (v / ymax) * ih);
  let g = "";
  for (let t = 0; t <= 4; t++) {
    const y = pt + (t / 4) * ih, val = ymax * (1 - t / 4);
    g += `<line class="gridline" x1="${pl}" y1="${y.toFixed(1)}" x2="${W - pr}" y2="${y.toFixed(1)}"/>`;
    g += `<text class="axis-label" x="${pl - 6}" y="${(y + 3).toFixed(1)}" text-anchor="end">${opts.yfmt(val)}</text>`;
  }
  g += `<line class="axis" x1="${pl}" y1="${pt + ih}" x2="${W - pr}" y2="${pt + ih}"/>`;
  for (let i = 0; i < n; i++) g += `<text class="axis-label" x="${xs(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${i + 1}</text>`;
  for (const s of series) {
    if (!s.data.length) continue;
    const pts = s.data.map((v, i) => `${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");
    g += `<polyline class="series ${s.cls}" points="${pts}"/>`;
    g += s.data.map((v, i) => `<circle class="dot-pt ${s.cls}" cx="${xs(i).toFixed(1)}" cy="${ys(v).toFixed(1)}" r="3"/>`).join("");
  }
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${g}</svg>`;
}

function viewBenchmark() {
  const s = STOP_BY_ID.benchmark;
  const def = (state.health && state.health.benchmark_turns) || 8;
  const maxT = (state.health && state.health.max_turns) || def;
  setStage(`${stopHeader(s)}
    ${memWarmBanner()}
    <div class="panel mb"><div class="panel-body">
      <div class="bench-controls">
        <button class="btn btn-accent" id="bench-run">${I.play} Run head-to-head</button>
        <span class="bench-turns">turns <input type="text" id="bench-n" value="${def}" inputmode="numeric"> <span class="hint">of ${maxT}</span></span>
        <span class="hint" id="bench-status">Runs a recall-dense scripted conversation through both agents, then judges every answer. Each OAMP turn does live extraction with the capable model (~20s), so the full run takes a few minutes.</span>
      </div>
    </div></div>
    <div class="bench-grid">
      <div class="chart-card"><div class="panel-head"><span class="panel-title">${I.gauge} Input tokens / turn</span>
        <span class="legend"><span class="lk"><span class="sw" style="background:var(--naive)"></span>naive</span><span class="lk"><span class="sw" style="background:var(--oamp)"></span>OAMP</span></span></div>
        <div class="chart" id="chart-tok"><div class="empty">Run the benchmark to plot token growth.</div></div></div>
      <div class="chart-card"><div class="panel-head"><span class="panel-title">${I.gauge} End-to-end latency / turn (s)</span>
        <span class="legend"><span class="lk"><span class="sw" style="background:var(--naive)"></span>naive</span><span class="lk"><span class="sw" style="background:var(--oamp)"></span>OAMP</span></span></div>
        <div class="chart" id="chart-lat"><div class="empty">Latency per turn appears here.</div></div></div>
    </div>
    <div class="summary-cards" id="bench-summary"></div>
    <div class="grid-2" style="margin-top:18px">
      <div class="panel"><div class="panel-head"><span class="panel-title">${I.scale} Per-turn feed</span></div>
        <div class="panel-body"><div class="bench-feed" id="bench-feed"><div class="empty">Live token &amp; latency per turn.</div></div></div></div>
      <div class="panel"><div class="panel-head"><span class="panel-title">${I.check} Quality — LLM-as-judge</span><span class="hint mono" id="judge-status"></span></div>
        <div class="panel-body"><div id="judge-box"><div class="empty">After the run, each turn-pair is judged by ${esc((state.health && state.health.agent_model) || "Claude")}.</div></div></div></div>
    </div>
    <div class="takeaway">${I.bulb}<div><b>What to watch:</b> the naive token line climbs every turn while OAMP stays flat — that's memory turning a growing cost into a constant one. Latency tells the opposite story (OAMP does extra retrieval/extraction work), and the judge shows quality holds. That tension is Stop 4.</div></div>`, s.accent);

  const runBtn = $("#bench-run");
  const data = { naiveTok: [], oampTok: [], naiveLat: [], oampLat: [] };

  function redraw() {
    const n = Math.max(data.naiveTok.length, data.oampTok.length);
    if (!n) return;
    const tokMax = Math.max(1, ...data.naiveTok, ...data.oampTok) * 1.1;
    $("#chart-tok").innerHTML = lineChartSVG(
      [{ data: data.naiveTok, cls: "naive" }, { data: data.oampTok, cls: "oamp" }], n, tokMax, { yfmt: (v) => v >= 1000 ? (v / 1000).toFixed(0) + "k" : Math.round(v) });
    const latMax = Math.max(0.1, ...data.naiveLat, ...data.oampLat) * 1.1;
    $("#chart-lat").innerHTML = lineChartSVG(
      [{ data: data.naiveLat, cls: "naive" }, { data: data.oampLat, cls: "oamp" }], n, latMax, { yfmt: (v) => v.toFixed(1) });
  }
  function summary() {
    const sumN = data.naiveTok.reduce((a, b) => a + b, 0), sumO = data.oampTok.reduce((a, b) => a + b, 0);
    const save = sumN ? (1 - sumO / sumN) * 100 : 0;
    $("#bench-summary").innerHTML = `
      <div class="scard naive"><div class="sk">Naive — total input tokens</div><div class="sv">${fmtN(sumN)}</div><div class="sd">full history, every turn</div></div>
      <div class="scard oamp"><div class="sk">OAMP — total input tokens</div><div class="sv">${fmtN(sumO)}</div><div class="sd">retrieved context card</div></div>
      <div class="scard"><div class="sk">Tokens saved by OAMP</div><div class="sv" style="color:var(--oamp)">${save.toFixed(0)}%</div><div class="sd">fewer input tokens overall</div></div>`;
  }

  runBtn.addEventListener("click", async () => {
    if (state.abort) return;
    const n = Math.max(2, Math.min(parseInt($("#bench-n").value, 10) || def, maxT));
    $("#bench-n").value = n;  // reflect the clamp (e.g. 100 -> max) so the count is never misleading
    data.naiveTok = []; data.oampTok = []; data.naiveLat = []; data.oampLat = [];
    $("#chart-tok").innerHTML = ""; $("#chart-lat").innerHTML = "";
    $("#bench-feed").innerHTML = ""; $("#bench-summary").innerHTML = ""; $("#judge-box").innerHTML = "";
    $("#judge-status").textContent = ""; runBtn.disabled = true;
    $("#bench-status").innerHTML = '<span class="spinner"></span> starting…';
    const wins = { oamp: 0, naive: 0, tie: 0 };
    state.abort = new AbortController();
    try {
      await streamSSE("/api/benchmark/run", { turns: n, judge: true }, (ev) => {
        if (ev.type === "starting") { $("#bench-status").innerHTML = `<span class="spinner"></span> starting a ${ev.total}-turn run — the first point lands after turn 1 (~20s)…`; }
        else if (ev.type === "superseded") { $("#bench-status").innerHTML = `superseded by a newer run`; }
        else if (ev.type === "turn") { $("#bench-status").innerHTML = `<span class="spinner"></span> turn ${ev.turn}/${ev.total} — ${esc(ev.query.slice(0, 60))}…`; }
        else if (ev.type === "metric") {
          data.naiveTok.push(ev.naive.tokens); data.oampTok.push(ev.oamp.tokens);
          data.naiveLat.push(ev.naive.latency); data.oampLat.push(ev.oamp.latency);
          redraw(); summary();
          const feed = $("#bench-feed"); if (feed.querySelector(".empty")) feed.innerHTML = "";
          feed.insertAdjacentHTML("beforeend", `<div class="tline"><div class="tl-top"><span class="tl-n">${ev.turn}</span><span class="tl-q">${esc(ev.naive.answer ? "" : "")}${esc((ev.oamp.answer || "").slice(0, 70))}…</span></div><div class="tl-metrics"><span class="nv">naive ${fmtN(ev.naive.tokens)} tok · ${ev.naive.latency}s</span><span class="om">OAMP ${fmtN(ev.oamp.tokens)} tok · ${ev.oamp.latency}s</span></div></div>`);
          feed.scrollTop = feed.scrollHeight;
        }
        else if (ev.type === "judge") { wins[ev.winner]++; $("#judge-status").innerHTML = `<span class="spinner"></span> judging ${ev.turn}…`; renderJudge(wins); }
        else if (ev.type === "judge_done") { $("#judge-status").textContent = "done"; renderJudge(ev.wins); }
        else if (ev.type === "error") { $("#bench-status").innerHTML = `<span style="color:var(--naive)">${esc(ev.message)}</span>`; }
        else if (ev.type === "done") { $("#bench-status").innerHTML = `<span style="color:var(--oamp)">${I.check} complete — ${data.naiveTok.length} turns</span>`; }
      }, state.abort.signal);
    } catch (e) { $("#bench-status").innerHTML = `<span style="color:var(--naive)">Error: ${esc(e.message)}</span>`; }
    finally { state.abort = null; runBtn.disabled = false; }
  });

  function renderJudge(wins) {
    const total = wins.oamp + wins.naive + wins.tie || 1;
    const row = (k, cls, label) => `<div class="jbar ${cls}"><span class="jk">${label}</span><div class="jtrack"><div class="jfill" style="width:${(wins[k] / total * 100).toFixed(0)}%"></div></div><span class="jv">${wins[k]}</span></div>`;
    $("#judge-box").innerHTML = `<div class="judge-bars">${row("oamp", "oamp", "OAMP")}${row("naive", "naive", "Naive")}${row("tie", "tie", "Tie")}</div>
      <div class="hint" style="margin-top:12px">Within one session the naive agent holds the full transcript, so a close score at a fraction of the tokens is the real win. OAMP's edge is durability across sessions.</div>`;
  }
}

// ── Stop 4 · pick any two ───────────────────────────────────────────
function viewPatterns() {
  const s = STOP_BY_ID.patterns;
  setStage(`${stopHeader(s)}
    <div class="prose">
      <h2>You can have any two</h2>
      <p>The benchmark made the tension concrete. <b>Naive</b> memory keeps latency low (prompt caching makes re-sending a long history cheap on wall-clock time) but its token count climbs forever, and its "memory" vanishes when the process ends. <b>OAMP basic</b> keeps the prompt small and the memory durable, but pays for it with extra latency — every turn does a database write, a vector retrieval, and (periodically) an LLM extraction call.</p>
      <p>So can you get all three — low tokens, low latency, <i>and</i> durable memory? Not cleanly. But a <b>cache-friendly hybrid</b> gets you the two that usually matter most in production: <b>low latency + durable memory</b>.</p>

      <h3>The cache-friendly hybrid</h3>
      <p>It combines four ideas:</p>
      <ul>
        <li><b>Append-only history</b> with an explicit <code>cache_control</code> breakpoint, so Anthropic re-reads the stable prefix from cache at ~0.1× cost and near-zero prefill latency.</li>
        <li>A short <b>retrieved memory tail</b> appended to the latest turn — durable hints from prior sessions.</li>
        <li><b>Durable write-behind</b> to Oracle — a fast DB write, with <b>no LLM extraction on the user's critical path</b>.</li>
        <li><b>Periodic compaction</b> with the small model, so the cached prefix can't grow forever.</li>
      </ul>
      <p>The catch: it <b>gives the token savings back</b> (it sends the full history). That's the trade — you recover caching and durability by accepting token growth. Pick the two your workload needs.</p>

      <h3>Strategy 6 — move extraction offline</h3>
      <p>The hybrid never extracted memories while the user waited. Instead, a background job mines the <b>entire</b> persisted transcript in one pass with the cheap model (<code>claude-haiku-4-5</code>) — in a worker, a queue consumer, or a nightly cron. You get persistence <i>now</i> and rich, searchable memories <i>later</i>, without ever adding latency to a turn.</p>

      <h2>Recommended production pattern</h2>
      <table class="ptable">
        <thead><tr><th>Pattern</th><th>Tokens / turn</th><th>Latency</th><th>Cross-session memory</th><th>Use when</th></tr></thead>
        <tbody>
          <tr><td><b>Naive</b></td><td>grows linearly</td><td>low (cached)</td><td>none</td><td>short chats, prototypes</td></tr>
          <tr><td><b>OAMP basic</b></td><td>flat &amp; small</td><td>higher</td><td>durable</td><td>long agents, tight token budgets</td></tr>
          <tr><td><b>Cache-friendly + batch extract</b></td><td>grows (cached)</td><td>low</td><td>durable</td><td>high-volume production</td></tr>
        </tbody>
      </table>
      <p class="muted" style="font-size:13.5px">Rule of thumb: start naive, move to OAMP basic when prompt size or cost bites, and adopt the cache-friendly hybrid when you need low latency <i>and</i> durable memory at scale.</p>

      <div class="takeaway">${I.bulb}<div><b>The one idea to keep:</b> agent memory is a resource-allocation choice among low tokens, low latency, and durable memory. There's no universally best design — only the right pair for your workload. Oracle AI Agent Memory is what makes the durable-memory corner of that triangle real: persistent, searchable memory that outlives any single session. <span style="display:block;margin-top:8px">Run the full 30-turn benchmark — including the cache-friendly agent and offline extraction — in the companion <span class="mono">oracle_agent_memory_benchmarks.ipynb</span> notebook.</span></div></div>
    </div>`, s.accent);
}

// ── router ──────────────────────────────────────────────────────────
const ROUTES = { "": viewHome, "/": viewHome, "/naive": viewNaive, "/memory": viewMemory, "/benchmark": viewBenchmark, "/patterns": viewPatterns };
function route() {
  cancelStream();
  const hash = location.hash.replace(/^#/, "") || "/";
  const view = ROUTES[hash] || viewHome;
  const id = hash === "/" || hash === "" ? "home" : hash.slice(1);
  renderSidebar(STOP_BY_ID[id] ? id : "home");
  view();
  $("#sidebar").classList.remove("open");
  const scrim = $("#scrim"); if (scrim) scrim.hidden = true;
}

async function init() {
  renderSidebar("home");
  // Load health BEFORE the first render so views see the real memory status and max_turns
  // (otherwise the benchmark page can render a stale "warming" / "of 8" placeholder).
  try { state.health = await getJSON("/api/health"); } catch (_) {}
  route();
  window.addEventListener("hashchange", route);
  // mobile menu
  document.body.insertAdjacentHTML("beforeend", `<button class="menu-btn" id="menu-btn">${I.menu}</button>`);
  $("#menu-btn").addEventListener("click", () => { $("#sidebar").classList.add("open"); const sc = $("#scrim"); if (sc) sc.hidden = false; });
  const scrim = $("#scrim"); if (scrim) scrim.addEventListener("click", () => { $("#sidebar").classList.remove("open"); scrim.hidden = true; });
  // keep polling while OAMP warms; re-render the current view when it becomes ready so a
  // "warming" banner clears on its own (unless a stream is in flight).
  let wasReady = !!(state.health && state.health.memory && state.health.memory.backend === "oracle");
  for (let i = 0; i < 40; i++) {
    try {
      state.health = await getJSON("/api/health");
      refreshStatus();
      const ready = !!(state.health.memory && state.health.memory.backend === "oracle");
      if (ready && !wasReady && !state.abort) route();
      wasReady = ready;
      if (state.health.memory && state.health.memory.backend !== "warming") break;
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 2000));
  }
}
init();
