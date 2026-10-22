/* ======================================================================
   Evaluation Studio — the AI Maturity Ladder (Acme Home Loans)
   Core: utilities, inline-SVG charts, the sidebar, the suite runner,
   the Overview and Gates pages, the Data Explorer, the router.
   The Graders page and the five rung pages live in pages.js.
   ====================================================================== */

const I = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  scale: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M7 21h10M4 7h16M7 7l-3 7a3 3 0 0 0 6 0L7 7M17 7l-3 7a3 3 0 0 0 6 0l-3-7"/></svg>',
  gate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21V5l8-2 8 2v16"/><path d="M9 21v-6h6v6M9 10h6"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  stop: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 6-6 6 6 6"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  ladder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M7 3v18M17 3v18M7 7h10M7 12h10M7 17h10"/></svg>',
};
const PALETTE = ["#22d3ee", "#c084fc", "#fb923c", "#34d399", "#facc15", "#60a5fa", "#f472b6", "#a3e635"];
const GRADER_COLOR = { clef: "#fb923c", jev: "#facc15", judge: "#c084fc" };

const RUNGS = [
  { id: "chatbot", n: 1, nav: "Chatbot", accent: "var(--r1)" },
  { id: "rag", n: 2, nav: "RAG", accent: "var(--r2)" },
  { id: "workflow", n: 3, nav: "Workflow", accent: "var(--r3)" },
  { id: "agent", n: 4, nav: "Agent", accent: "var(--r4)" },
  { id: "autonomous", n: 5, nav: "Autonomous agent", accent: "var(--r5)" },
];
const RUNG_LABEL = { chatbot: "① chatbot", rag: "② RAG", workflow: "③ workflow", agent: "④ agent", autonomous: "⑤ autonomous", graders: "graders" };

// ── utilities ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v, d = 0) => (v == null || isNaN(v) ? "—" : (v * 100).toFixed(d) + "%");
const num = (v, d = 3) => (v == null || isNaN(v) ? "—" : Number(v).toFixed(d));
const money = (v) => (v == null || isNaN(v) ? "—" : "$" + Number(v).toFixed(Number(v) < 0.01 ? 5 : 3));
const fmtWhen = (iso) => { try { return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); } catch (_) { return iso || "—"; } };

async function getJSON(url) {
  const r = await fetch(url);
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "HTTP " + r.status);
  return d;
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  let d = {};
  try { d = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "HTTP " + r.status);
  return d;
}
function setHTML(sel, html) { const el = $(sel); if (el) el.innerHTML = html; }
function pill(text, cls) { return `<span class="pill ${esc(cls || String(text).toLowerCase().replace(/\s+/g, ""))}">${esc(text)}</span>`; }
function tile(label, value, sub, cls = "") { return `<div class="tile ${cls}"><div class="tk">${esc(label)}</div><div class="tv">${value}</div>${sub ? `<div class="ts">${esc(sub)}</div>` : ""}</div>`; }
function wilson(k, n, z = 1.96) {
  if (!n) return [0, 1];
  const p = k / n, c = (p + z * z / (2 * n)) / (1 + z * z / n);
  const h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n);
  return [Math.max(0, c - h), Math.min(1, c + h)];
}
function rateText(k, n) { if (!n) return "—"; const [lo, hi] = wilson(k, n); return `${k}/${n} · ${pct(k / n)} [${pct(lo)}–${pct(hi)}]`; }
function table(columns, rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${esc(opts.empty || "Nothing yet.")}</div>`;
  const head = columns.map((c) => `<th${c.num ? ' class="num"' : ""}>${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr>${columns.map((c) => {
    const v = typeof c.get === "function" ? c.get(r) : r[c.key];
    const cls = [c.num ? "num" : "", c.wrap ? "wrap" : "", typeof c.cls === "function" ? c.cls(r) : (c.cls || "")].filter(Boolean).join(" ");
    return `<td${cls ? ` class="${cls}"` : ""}>${c.html ? v : esc(Array.isArray(v) ? v.join(", ") : typeof v === "object" && v !== null ? JSON.stringify(v) : v ?? "—")}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table class="data-table compact"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// ── inline-SVG charts ─────────────────────────────────────────────────
function svgBars(items, { max = 1, width = 520, fmt = (v) => pct(v), threshold = null } = {}) {
  const row = 26, left = 170, right = 60, h = items.length * row + 10;
  const scale = (v) => ((width - left - right) * Math.max(0, Math.min(v ?? 0, max))) / max;
  const bars = items.map((it, i) => {
    const y = 6 + i * row;
    return `<text x="${left - 8}" y="${y + 15}" text-anchor="end" font-size="11">${esc(it.label)}</text>
      <rect x="${left}" y="${y + 4}" width="${width - left - right}" height="14" rx="3" fill="var(--panel-3)"/>
      <rect x="${left}" y="${y + 4}" width="${scale(it.value)}" height="14" rx="3" fill="${it.color || PALETTE[i % PALETTE.length]}"/>
      <text x="${left + scale(it.value) + 6}" y="${y + 15}" font-size="11">${esc(it.value == null ? "—" : fmt(it.value))}</text>`;
  }).join("");
  const t = threshold == null ? "" : `<line x1="${left + scale(threshold)}" x2="${left + scale(threshold)}" y1="2" y2="${h - 2}" stroke="#facc15" stroke-dasharray="4 3"/>`;
  return `<svg viewBox="0 0 ${width} ${h}" role="img">${bars}${t}</svg>`;
}
function svgStacked(rows, keys, colors, width = 520) {
  const row = 30, left = 150, h = rows.length * row + 26;
  const body = rows.map((r, i) => {
    let x = left;
    const y = 6 + i * row;
    const total = keys.reduce((s, k) => s + (r[k] || 0), 0) || 1;
    const parts = keys.map((k, j) => {
      const w = ((width - left - 10) * (r[k] || 0)) / total;
      const out = `<rect x="${x}" y="${y}" width="${w}" height="20" fill="${colors[j]}"/>${w > 34 ? `<text x="${x + w / 2}" y="${y + 14}" text-anchor="middle" font-size="10.5" style="fill:#0b0c0f">${pct((r[k] || 0) / total)}</text>` : ""}`;
      x += w;
      return out;
    }).join("");
    return `<text x="${left - 8}" y="${y + 14}" text-anchor="end" font-size="11">${esc(r.label)}</text>${parts}`;
  }).join("");
  const legend = keys.map((k, j) => `<rect x="${left + j * 110}" y="${h - 14}" width="10" height="10" fill="${colors[j]}"/><text x="${left + j * 110 + 14}" y="${h - 5}" font-size="10.5">${esc(k)}</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${h}" role="img">${body}${legend}</svg>`;
}
function svgReliability(series, size = 300) {
  const pad = 34, s = size - pad - 10;
  const X = (p) => pad + p * s, Y = (p) => 10 + (1 - p) * s;
  const grid = [0, 0.25, 0.5, 0.75, 1].map((g) => `<line x1="${X(g)}" x2="${X(g)}" y1="${Y(0)}" y2="${Y(1)}" stroke="var(--line)"/><line x1="${X(0)}" x2="${X(1)}" y1="${Y(g)}" y2="${Y(g)}" stroke="var(--line)"/><text x="${X(g)}" y="${Y(0) + 14}" font-size="9" text-anchor="middle">${g}</text><text x="${pad - 6}" y="${Y(g) + 3}" font-size="9" text-anchor="end">${g}</text>`).join("");
  const lines = Object.entries(series).map(([name, pts]) => {
    if (!pts.length) return "";
    const d = pts.map((p, i) => `${i ? "L" : "M"}${X(p.p).toFixed(1)},${Y(p.observed).toFixed(1)}`).join(" ");
    return `<path d="${d}" fill="none" stroke="${GRADER_COLOR[name] || "#22d3ee"}" stroke-width="2"/>${pts.map((p) => `<circle cx="${X(p.p)}" cy="${Y(p.observed)}" r="3.5" fill="${GRADER_COLOR[name] || "#22d3ee"}"><title>${esc(name)}: p≈${p.p.toFixed(2)}, observed ${p.observed.toFixed(2)}, n=${p.n}</title></circle>`).join("")}`;
  }).join("");
  const legend = Object.keys(series).map((n, i) => `<text x="${pad + 6}" y="${22 + i * 14}" font-size="10" style="fill:${GRADER_COLOR[n] || "#22d3ee"}">● ${esc(n)}</text>`).join("");
  return `<svg viewBox="0 0 ${size} ${size + 6}" role="img">${grid}<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="#64748b" stroke-dasharray="3 3"/>${lines}${legend}</svg>`;
}
function svgLines(curves, width = 520, height = 200) {
  const all = curves.flat();
  if (!all.length) return "";
  const max = Math.max(...all), n = Math.max(...curves.map((c) => c.length));
  const pad = 40, X = (i) => pad + (i * (width - pad - 10)) / Math.max(1, n - 1), Y = (v) => 10 + (1 - v / max) * (height - 34);
  const lines = curves.map((c, j) => `<path d="${c.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ")}" fill="none" stroke="${PALETTE[j % PALETTE.length]}" stroke-width="1.8"/>`).join("");
  const axis = [0, 0.5, 1].map((g) => `<text x="${pad - 6}" y="${Y(g * max) + 3}" font-size="9" text-anchor="end">${Math.round(g * max)}</text><line x1="${pad}" x2="${width - 10}" y1="${Y(g * max)}" y2="${Y(g * max)}" stroke="var(--line)"/>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" role="img">${axis}${lines}<text x="${width / 2}" y="${height - 4}" font-size="10" text-anchor="middle">turn</text></svg>`;
}

// ── state, sidebar, theme ─────────────────────────────────────────────
const state = { health: null, streams: {}, runId: null };

function renderSidebar(active) {
  const item = (href, id, node, label, accent, delay) => `
    <a class="nav-item ${active === id ? "active" : ""}" href="${href}" title="${esc(label)}" aria-label="${esc(label)}" style="--c:${accent};animation-delay:${delay}ms">
      <span class="nav-node">${node}</span><span class="nav-label">${esc(label)}</span></a>`;
  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.scale}</span>
      <span class="brand-text"><b>Evaluation Studio</b><span>The AI Maturity Ladder</span></span>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button"></button>
    </div>
    <div class="rail-label">Evaluate</div>
    <nav class="ladder-rail" aria-label="Pages">
      ${item("#/", "home", I.home, "Overview", "var(--text-2)", 0)}
      ${item("#/graders", "graders", "G", "Graders", "#fb923c", 40)}
      ${RUNGS.map((r, i) => item(`#/${r.id}`, r.id, r.n, `${r.n}. ${r.nav}`, r.accent, 80 + i * 40)).join("")}
      ${item("#/gates", "gates", I.gate, "Release gates", "#facc15", 300)}
    </nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle" type="button"><span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span id="theme-label">${themeLabel()}</span></span><span class="toggle-track"></span></button>
    </div>`;
  syncSidebarToggle();
  $("#sidebar-toggle").addEventListener("click", toggleSidebar);
  $("#theme-toggle").addEventListener("click", toggleTheme);
}
function sidebarCollapsed() { return document.documentElement.getAttribute("data-sidebar") === "collapsed"; }
function syncSidebarToggle() {
  const t = $("#sidebar-toggle"); if (!t) return;
  const c = sidebarCollapsed();
  t.innerHTML = c ? I.expand : I.collapse;
  t.setAttribute("aria-label", c ? "Expand side navigation" : "Collapse side navigation");
}
function toggleSidebar() {
  const next = sidebarCollapsed() ? "expanded" : "collapsed";
  document.documentElement.setAttribute("data-sidebar", next);
  try { localStorage.setItem("ffeval-sidebar", next); } catch (_) {}
  syncSidebarToggle();
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("ffeval-theme", next); } catch (_) {}
  renderSidebar(state.route || "home");
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const dot = (ok) => `<span class="dot ${ok ? "ok" : "off"}"></span>`;
  return `
    <div class="status-row"><span class="k">Under test</span><span class="mono" style="color:var(--text)">${esc(h.model)}</span></div>
    <div class="status-row"><span class="k">Judge</span><span class="mono">${esc(h.judge.model)}</span></div>
    <div class="status-row"><span class="k">Clef</span>${dot(h.clef.status !== "error")}<span>${esc(h.clef.status === "remote" ? "remote" : h.clef.status)}</span></div>
    <div class="status-row"><span class="k">Jev</span>${dot(h.jev.available)}<span>${h.jev.available ? "available" : "no key"}</span></div>
    <div class="status-row"><span class="k">Oracle</span>${dot(h.oracle.ready)}<span>${h.oracle.ready ? `${h.runs.total} runs` : esc(h.oracle.backend)}</span></div>`;
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }
function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "#fb923c");
  stage.innerHTML = `<div class="view full view-enter">${html}</div>`;
  stage.scrollTop = 0;
}
function needsDB() {
  const h = state.health;
  if (h && h.oracle && h.oracle.ready) return "";
  return `<div class="banner warn">${I.alert}<div>${h && h.oracle && h.oracle.error ? `Oracle AI Database is unavailable: <span class="mono">${esc(h.oracle.error)}</span>. Start it with <span class="mono">./oracle.sh start</span> in <span class="mono">part7/</span>.` : "Oracle AI Database is still starting; this page fills in as soon as it is ready."}</div></div>`;
}

// ── the suite runner: start, stop, and an event stream that survives navigation ──
function runbar(kind, sizes = ["quick", "full"], note = "") {
  return `<div class="panel mb"><div class="panel-body runbar">
      <div class="seg" id="size-${kind}">${sizes.map((s, i) => `<button type="button" data-size="${s}" class="${i === 0 ? "active" : ""}">${s}</button>`).join("")}</div>
      <button class="btn btn-accent" id="run-${kind}">${I.play} Run</button>
      <button class="btn btn-ghost" id="stop-${kind}" disabled>${I.stop} Stop</button>
      <span class="status-line" id="status-${kind}">idle</span>
      ${note ? `<span class="hint" style="flex-basis:100%">${esc(note)}</span>` : ""}
    </div></div>`;
}
function wireRunbar(kind, handlers) {
  $$(`#size-${kind} button`).forEach((b) => b.addEventListener("click", () => { $$(`#size-${kind} button`).forEach((x) => x.classList.remove("active")); b.classList.add("active"); }));
  $(`#run-${kind}`).addEventListener("click", async () => {
    const size = $(`#size-${kind} button.active`)?.dataset.size || "quick";
    try {
      await postJSON(`/api/suites/${kind}/start`, { size });
      handlers.onStart && handlers.onStart(size);
      attachStream(kind, handlers, 0);
    } catch (e) { setHTML(`#status-${kind}`, `<span style="color:var(--bad)">${esc(e.message)}</span>`); }
  });
  $(`#stop-${kind}`).addEventListener("click", async () => { await postJSON(`/api/suites/${kind}/stop`); setHTML(`#status-${kind}`, "stopping after the current case…"); });
}
function setRunning(kind, running) {
  const run = $(`#run-${kind}`), stop = $(`#stop-${kind}`);
  if (run) run.disabled = running;
  if (stop) stop.disabled = !running;
}
function attachStream(kind, handlers, since = 0) {
  if (state.streams[kind]) state.streams[kind].close();
  setRunning(kind, true);
  const source = new EventSource(`/api/suites/${kind}/stream?since=${since}`);
  state.streams[kind] = source;
  source.onmessage = (m) => {
    let e; try { e = JSON.parse(m.data); } catch (_) { return; }
    if (!e || !e.type) return;
    if (e.type === "start") setHTML(`#status-${kind}`, `running · <b>${esc(e.run_id)}</b> · ${esc(e.size)}`);
    if (e.type === "phase") setHTML(`#status-${kind}`, `running · <b>${esc(e.name)}</b> · ${esc(e.detail || "")}`);
    if (e.type === "cost") handlers.onCost && handlers.onCost(e);
    if (e.type === "error") setHTML(`#status-${kind}`, `<span style="color:var(--bad)">error: ${esc(e.message)}</span>`);
    if (e.type === "end") {
      setRunning(kind, false);
      const old = $(`#status-${kind}`)?.textContent || "";
      if (!/error/.test(old)) setHTML(`#status-${kind}`, `${esc(e.status)} in ${e.seconds}s`);
      source.close();
      delete state.streams[kind];
      handlers.onEnd && handlers.onEnd(e);
    }
    handlers.onEvent && handlers.onEvent(e);
  };
  source.addEventListener("end", () => { source.close(); setRunning(kind, false); });
  source.onerror = () => { source.close(); setRunning(kind, false); };
}
async function resumeIfRunning(kind, handlers) {
  try {
    const s = await getJSON(`/api/suites/${kind}/status`);
    if (s.status === "running") { handlers.onStart && handlers.onStart(s.size); attachStream(kind, handlers, 0); return true; }
  } catch (_) {}
  return false;
}
function closeStreams() { Object.values(state.streams).forEach((s) => s.close()); state.streams = {}; }

// ── Overview: every run, notebook or appbook, and the scorecard of one ──
function headlineFor(rung, s) {
  if (!s) return null;
  return {
    chatbot: { v: s.closed_book_correct, l: "closed-book answers correct", x: `confident errors ${pct(s.confident_errors)} · buffer recall ${pct(s.buffer_recall)}` },
    rag: { v: s.correct, l: "answers correct", x: `recall@3 ${pct(s["recall@3"])} · faithful ${pct(s.faithfulness)} · cited ${pct(s.citation_coverage)} · stale ${s.stale ?? "—"}` },
    workflow: { v: s.end_to_end, l: "end-to-end outcomes right", x: `fields ${pct(s.extraction_all_fields)} · decision on gold ${pct(s.decision_on_gold)} · unsafe ${s.unsafe_errors ?? "—"}` },
    agent: { v: s["pass@1"], l: "task attempts passed", x: `pass^${s.k} ${pct(s["pass^k"])} · forbidden actions ${s.forbidden_actions}` },
    autonomous: { v: s.hidden_tests, l: "hidden tests passed", x: `sandbox events ${s.sandbox_events} · reuse ${s.reuse_ok == null ? "not run" : s.reuse_ok ? "works" : "fails"}` },
    graders: { v: s.min_kappa, l: "lowest κ of a chosen grader", x: (s.choices || []).map((c) => `${c.kind}: ${c.grader}`).join(" · "), fmt: (v) => num(v, 2) },
  }[rung];
}
async function viewHome() {
  setStage(`
    <header class="eval-head">
      <div class="eval-kicker">Evaluation studio · Acme Home Loans</div>
      <h1 class="eval-title">How well does each rung <em>actually</em> work?</h1>
      <p class="eval-desc">The maturity ladder builds one mortgage application five ways. This studio evaluates each rung step by step, the way its own failures demand: golden sets labelled in advance, graders validated before use (code, two decision models, an LLM judge), evidence in Oracle AI Database, and release gates. Runs from the evaluation notebook and from this app sit side by side.</p>
    </header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-head"><span class="panel-title">${I.ladder} Scorecard · <span id="score-run" class="mono">—</span></span><span id="score-readiness"></span></div>
      <div class="panel-body"><div class="rung-cards" id="score-cards"><div class="empty">Reading the evidence…</div></div></div></div>
    <div class="panel"><div class="panel-head"><span class="panel-title">Runs in FFEVAL_RUNS</span><button class="btn btn-ghost" id="runs-refresh">${I.refresh}</button></div>
      <div class="panel-body" id="runs-table"><div class="empty">Loading…</div></div></div>`, "#22d3ee");
  $("#runs-refresh").addEventListener("click", loadRuns);
  await loadRuns();
}
async function loadRuns() {
  try {
    const d = await getJSON("/api/runs?limit=80");
    const runs = d.runs || [];
    if (!state.runId || !runs.some((r) => r.run_id === state.runId)) {
      const full = runs.find((r) => r.source === "notebook" && r.form_factors.length >= 3) || runs[0];
      state.runId = full ? full.run_id : null;
    }
    setHTML("#runs-table", table([
      { label: "Run", html: true, get: (r) => `<a href="#/" data-run="${esc(r.run_id)}" class="mono">${esc(r.run_id)}</a>` },
      { label: "Started", get: (r) => fmtWhen(r.started_at) },
      { label: "Source", html: true, get: (r) => pill(r.source, r.source === "notebook" ? "ready" : "refer") },
      { label: "Suite", key: "suite" }, { label: "Model", key: "model" }, { label: "Judge", key: "judge_model" },
      { label: "Measured", get: (r) => r.form_factors.map((f) => RUNG_LABEL[f] || f).join(" · ") || "—" },
      { label: "Rows", num: true, get: (r) => r.results + r.checks },
    ], runs, { empty: "No runs yet: run the evaluation notebook, or a suite from any page." }));
    $$("[data-run]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); state.runId = a.dataset.run; loadScorecard(); }));
    await loadScorecard();
  } catch (e) { setHTML("#runs-table", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
async function loadScorecard() {
  if (!state.runId) { setHTML("#score-cards", `<div class="empty">No runs yet.</div>`); return; }
  setHTML("#score-run", esc(state.runId));
  const d = await getJSON(`/api/runs/${encodeURIComponent(state.runId)}`);
  const cards = ["graders", ...RUNGS.map((r) => r.id)].map((rung) => {
    const h = headlineFor(rung, d.summary[rung]);
    const ready = d.readiness[rung];
    const href = rung === "graders" ? "#/graders" : `#/${rung}`;
    if (!h) return `<a class="rung-card" href="${href}"><div class="rc-h"><span class="rc-n">${esc(RUNG_LABEL[rung])}</span>${pill("not measured", "notmeasured")}</div><div class="rc-l">This run did not measure this rung.</div></a>`;
    return `<a class="rung-card" href="${href}"><div class="rc-h"><span class="rc-n">${esc(RUNG_LABEL[rung])}</span>${pill(ready, ready.replace(" ", ""))}</div>
      <div class="rc-v">${h.fmt ? h.fmt(h.v) : pct(h.v)}</div><div class="rc-l">${esc(h.l)}</div><div class="rc-x">${esc(h.x)}</div></a>`;
  }).join("");
  setHTML("#score-cards", cards);
  const counts = Object.values(d.readiness).reduce((a, v) => { a[v] = (a[v] || 0) + 1; return a; }, {});
  setHTML("#score-readiness", `${pill(`${counts.ready || 0} ready`, "ready")} ${pill(`${counts.blocked || 0} blocked`, "blocked")}`);
}

// ── Gates page ────────────────────────────────────────────────────────
async function viewGates() {
  setStage(`
    <header class="eval-head"><div class="eval-kicker">Release gates</div>
      <h1 class="eval-title">Ready or <em>blocked</em>, per rung</h1>
      <p class="eval-desc">A gate is a metric, a direction and a threshold agreed before the run. A rung is ready when every gate it measured passes. The thresholds are the evaluation notebook's examples of what a lender might require; a gate the selected run did not measure shows as not measured.</p></header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-body row"><label class="hint">Run</label><select id="gate-run"></select></div></div>
    <div class="rung-cards mb" id="gate-ready"></div>
    <div class="panel"><div class="panel-body" id="gate-table"><div class="empty">Loading…</div></div></div>`, "#facc15");
  try {
    const runs = (await getJSON("/api/runs?limit=80")).runs || [];
    if (!state.runId && runs.length) state.runId = (runs.find((r) => r.source === "notebook" && r.form_factors.length >= 3) || runs[0]).run_id;
    $("#gate-run").innerHTML = runs.map((r) => `<option value="${esc(r.run_id)}" ${r.run_id === state.runId ? "selected" : ""}>${esc(r.run_id)} · ${esc(r.source)} · ${esc(r.form_factors.join(", ") || "—")}</option>`).join("");
    $("#gate-run").addEventListener("change", (e) => { state.runId = e.target.value; loadGates(); });
    await loadGates();
  } catch (e) { setHTML("#gate-table", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
async function loadGates() {
  if (!state.runId) return;
  const d = await getJSON(`/api/runs/${encodeURIComponent(state.runId)}`);
  setHTML("#gate-ready", Object.entries(d.readiness).map(([rung, r]) => `<div class="rung-card"><div class="rc-h"><span class="rc-n">${esc(RUNG_LABEL[rung])}</span>${pill(r, r.replace(" ", ""))}</div></div>`).join(""));
  setHTML("#gate-table", table([
    { label: "Rung", key: "label" }, { label: "Gate", key: "gate" },
    { label: "Value", num: true, get: (g) => g.value == null ? "—" : (Math.abs(g.value) <= 1 && !Number.isInteger(g.value) ? num(g.value, 3) : g.value) },
    { label: "Rule", get: (g) => `${g.op} ${g.threshold}` },
    { label: "Result", html: true, get: (g) => g.passed == null ? pill("not measured", "notmeasured") : pill(g.passed ? "pass" : "fail") },
  ], d.gates));
}

// ── Data Explorer (read-only) ─────────────────────────────────────────
const explorer = { tables: [], selected: null, offset: 0, limit: 40 };
function toggleExplorer(force) {
  const el = $("#data-explorer");
  const open = force ?? !el.classList.contains("open");
  el.classList.toggle("open", open);
  $("#explorer-body").hidden = !open;
  $("#explorer-toggle").setAttribute("aria-expanded", String(open));
  document.body.classList.toggle("explorer-open", open);
  if (open) loadExplorerTables();
}
async function loadExplorerTables() {
  try {
    const d = await getJSON("/api/data_explorer/tables");
    explorer.tables = d.tables;
    $("#explorer-summary").textContent = `${d.tables.length} tables · ${d.schema}`;
    $("#explorer-table-list").innerHTML = d.tables.map((t) => `<button class="explorer-table-item ${explorer.selected === t.name ? "selected" : ""}" data-t="${esc(t.name)}" title="${esc(t.role)}"><span><i></i>${esc(t.name)}</span><b>${t.rows < 0 ? "—" : t.rows.toLocaleString()}</b></button>`).join("");
    $$("#explorer-table-list [data-t]").forEach((b) => b.addEventListener("click", () => selectExplorer(b.dataset.t, 0)));
    if (!explorer.selected && d.tables.length) selectExplorer((d.tables.find((t) => t.name === "ffeval_results") || d.tables[0]).name, 0);
  } catch (e) { $("#explorer-summary").textContent = e.message; }
}
async function selectExplorer(name, offset) {
  explorer.selected = name; explorer.offset = offset;
  $$("#explorer-table-list [data-t]").forEach((b) => b.classList.toggle("selected", b.dataset.t === name));
  const run = ($("#explorer-run").value || "").trim();
  try {
    const d = await getJSON(`/api/data_explorer/tables/${encodeURIComponent(name)}/rows?limit=${explorer.limit}&offset=${offset}${run ? `&run_id=${encodeURIComponent(run)}` : ""}`);
    $("#explorer-table-name").textContent = d.table;
    $("#explorer-role").textContent = (explorer.tables.find((t) => t.name === name) || {}).role || "";
    $("#explorer-page").textContent = `${d.rows.length ? offset + 1 : 0}–${offset + d.rows.length} of ${d.total}`;
    $("#explorer-prev").disabled = offset === 0;
    $("#explorer-next").disabled = offset + d.rows.length >= d.total;
    const cell = (v) => v == null ? '<span class="explorer-null">NULL</span>' : esc(typeof v === "object" ? JSON.stringify(v).slice(0, 200) : String(v).slice(0, 200));
    $("#explorer-grid").innerHTML = d.rows.length ? `<table class="explorer-data-table"><thead><tr>${d.columns.map((c) => `<th><span>${esc(c)}</span></th>`).join("")}</tr></thead><tbody>${d.rows.map((r) => `<tr>${d.columns.map((c) => `<td>${cell(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>` : '<div class="explorer-empty">No rows.</div>';
  } catch (e) { $("#explorer-grid").innerHTML = `<div class="explorer-error">${esc(e.message)}</div>`; }
}
function initExplorer() {
  $("#explorer-toggle").addEventListener("click", () => toggleExplorer());
  $("#explorer-refresh").addEventListener("click", loadExplorerTables);
  $("#explorer-run").addEventListener("change", () => explorer.selected && selectExplorer(explorer.selected, 0));
  $("#explorer-prev").addEventListener("click", () => selectExplorer(explorer.selected, Math.max(0, explorer.offset - explorer.limit)));
  $("#explorer-next").addEventListener("click", () => selectExplorer(explorer.selected, explorer.offset + explorer.limit));
}

// ── router and boot ───────────────────────────────────────────────────
function routes() {
  return { "": viewHome, graders: viewGraders, gates: viewGates, chatbot: () => viewRung("chatbot"), rag: () => viewRung("rag"),
           workflow: () => viewRung("workflow"), agent: () => viewRung("agent"), autonomous: () => viewRung("autonomous") };
}
function route() {
  closeStreams();
  const id = location.hash.replace(/^#\/?/, "").split("?")[0].trim();
  state.route = id || "home";
  renderSidebar(state.route);
  (routes()[id] || viewHome)();
  if (window.innerWidth <= 760) closeMenu();
}
function openMenu() { $("#sidebar").classList.add("open"); $("#scrim").hidden = false; }
function closeMenu() { $("#sidebar").classList.remove("open"); $("#scrim").hidden = true; }
async function boot() {
  const mb = document.createElement("button");
  mb.className = "menu-btn"; mb.innerHTML = I.menu; mb.setAttribute("aria-label", "Menu");
  mb.addEventListener("click", openMenu); document.body.appendChild(mb);
  $("#scrim").addEventListener("click", closeMenu);
  window.addEventListener("hashchange", route);
  initExplorer();
  try { state.health = await getJSON("/api/health"); } catch (_) {}
  route();
  let wasReady = !!(state.health && state.health.oracle.ready);
  async function poll() {
    try { state.health = await getJSON("/api/health"); refreshStatus(); } catch (_) {}
    const ready = !!(state.health && state.health.oracle.ready);
    if (ready && !wasReady) { wasReady = true; route(); }
    setTimeout(poll, ready ? 15000 : 2000);
  }
  setTimeout(poll, 2000);
}
window.addEventListener("DOMContentLoaded", boot);
