/* ======================================================================
   Retrieval benchmark appbook — BEIR on Oracle AI Database
   Core: utilities, inline-SVG charts, the sidebar, the Leaderboard page,
   the Data Explorer, the router. The query explorer, the tuning
   playground and the decision guide live in pages.js.
   ====================================================================== */

const I = {
  board: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/></svg>',
  sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>',
  guide: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v5M12 8l-6 5M12 8l6 5M6 13v4M18 13v4"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/></svg>',
  db: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8M21 4v4h-4M21 12a9 9 0 0 1-15.5 6.2L3 16M3 20v-4h4"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  collapse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 6-6 6 6 6"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="m9.5 6 6 6-6 6"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
};
const STRATEGIES = ["lexical", "vector", "hybrid", "graph", "rerank"];
const S_COLOR = { lexical: "#facc15", vector: "#22d3ee", hybrid: "#c084fc", graph: "#34d399", rerank: "#fb923c" };
const DS_NAME = { fiqa: "FiQA-2018", scifact: "SciFact", arguana: "ArguAna" };
const METRICS = ["ndcg10", "p1", "p5", "p10", "r10", "r100", "mrr10", "map100", "hit10"];
const M_NAME = { ndcg10: "nDCG@10", p1: "P@1", p5: "P@5", p10: "P@10", r10: "R@10", r100: "R@100", mrr10: "MRR@10", map100: "MAP@100", hit10: "Hit@10" };
const M_DEF = {
  ndcg10: "Are the best documents at the very top? Graded gains of the top 10, discounted by log₂(rank + 1), over the best possible ordering.",
  p1: "Is the first result relevant?",
  p5: "Share of the top 5 that is relevant: what a reader or a model sees.",
  p10: "Share of the top 10 that is relevant.",
  r10: "Share of all relevant documents found in the top 10.",
  r100: "Share of all relevant documents in the top 100: what a reranker or a long-context model can still use.",
  mrr10: "1 / rank of the first relevant document in the top 10: how far down the first useful hit is.",
  map100: "Precision at each relevant document's rank, averaged over all relevant documents: are all of them high?",
  hit10: "Did any relevant document reach the top 10 at all?",
};

// ── utilities ─────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 3) => (v == null || isNaN(v) ? "—" : Number(v).toFixed(d));
const signed = (v, d = 3) => (v == null || isNaN(v) ? "—" : (v >= 0 ? "+" : "") + Number(v).toFixed(d));
const ms = (v) => (v == null || isNaN(v) ? "—" : Number(v) >= 100 ? Number(v).toFixed(0) : Number(v).toFixed(1));
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
function tile(label, value, sub, cls = "") { return `<div class="tile ${cls}"><div class="tk">${esc(label)}</div><div class="tv">${value}</div>${sub ? `<div class="ts">${sub}</div>` : ""}</div>`; }
function tag(strategy) { return `<span class="strategy-tag" style="--c:${S_COLOR[strategy] || "#94a3b8"}"><i></i>${esc(strategy)}</span>`; }
function table(columns, rows, opts = {}) {
  if (!rows.length) return `<div class="empty">${esc(opts.empty || "Nothing yet.")}</div>`;
  const head = columns.map((c) => `<th${c.num ? ' class="num"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr>${columns.map((c) => {
    const v = typeof c.get === "function" ? c.get(r) : r[c.key];
    const cls = [c.num ? "num" : "", c.wrap ? "wrap" : "", typeof c.cls === "function" ? c.cls(r) : (c.cls || "")].filter(Boolean).join(" ");
    return `<td${cls ? ` class="${cls}"` : ""}>${c.html ? v : esc(v ?? "—")}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table class="data-table compact"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function listJoin(items) { return items.length <= 1 ? (items[0] || "") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`; }
function howto(points, run) {
  return `<div class="howto"><b>How to read it.</b><ul>${points.map((p) => `<li>${p}</li>`).join("")}</ul>${run ? `<div style="margin-top:6px">${run}</div>` : ""}</div>`;
}

// ── inline-SVG charts ─────────────────────────────────────────────────
function svgIntervals(items, { width = 560, max = 1 } = {}) {
  // one row per item: a dot at the mean and a whisker for the 95% interval
  const row = 26, left = 120, right = 70, h = items.length * row + 26;
  const X = (v) => left + ((width - left - right) * Math.max(0, Math.min(v, max))) / max;
  const ticks = [0, 0.25, 0.5, 0.75, 1].filter((t) => t <= max).map((t) => `<line x1="${X(t)}" x2="${X(t)}" y1="4" y2="${h - 18}" stroke="var(--line)"/><text x="${X(t)}" y="${h - 4}" font-size="9.5" text-anchor="middle">${t}</text>`).join("");
  const rows = items.map((it, i) => {
    const y = 14 + i * row;
    return `<text x="${left - 8}" y="${y + 4}" text-anchor="end" font-size="11">${esc(it.label)}</text>
      <line x1="${X(it.lo)}" x2="${X(it.hi)}" y1="${y}" y2="${y}" stroke="${it.color}" stroke-width="2"/>
      <line x1="${X(it.lo)}" x2="${X(it.lo)}" y1="${y - 5}" y2="${y + 5}" stroke="${it.color}" stroke-width="2"/>
      <line x1="${X(it.hi)}" x2="${X(it.hi)}" y1="${y - 5}" y2="${y + 5}" stroke="${it.color}" stroke-width="2"/>
      <circle cx="${X(it.mean)}" cy="${y}" r="4.5" fill="${it.color}"/>
      <text x="${X(it.hi) + 8}" y="${y + 4}" font-size="11">${num(it.mean)}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${width} ${h}" role="img">${ticks}${rows}</svg>`;
}

// ── state, sidebar, theme ─────────────────────────────────────────────
const state = { health: null, runId: null, runs: [] };

function renderSidebar(active) {
  const item = (href, id, node, label, accent, delay) => `
    <a class="nav-item ${active === id ? "active" : ""}" href="${href}" title="${esc(label)}" aria-label="${esc(label)}" style="--c:${accent};animation-delay:${delay}ms">
      <span class="nav-node">${node}</span><span class="nav-label">${esc(label)}</span></a>`;
  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.board}</span>
      <span class="brand-text"><b>Retrieval benchmark</b><span>BEIR on Oracle AI Database</span></span>
      <button class="sidebar-toggle" id="sidebar-toggle" type="button"></button>
    </div>
    <div class="rail-label">Measure and choose</div>
    <nav class="ladder-rail" aria-label="Pages">
      ${item("#/", "home", I.board, "Leaderboard", "#22d3ee", 0)}
      ${item("#/explore", "explore", I.search, "Query explorer", "#c084fc", 40)}
      ${item("#/playground", "playground", I.sliders, "Tuning playground", "#34d399", 80)}
      ${item("#/guide", "guide", I.guide, "Decision guide", "#facc15", 120)}
      <a class="nav-item" href="#" id="nav-explorer" title="Data Explorer" aria-label="Data Explorer" style="--c:#fb923c;animation-delay:160ms"><span class="nav-node">${I.db}</span><span class="nav-label">Data Explorer</span></a>
    </nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle" type="button"><span style="display:flex;align-items:center;gap:8px">${themeIcon()} <span id="theme-label">${themeLabel()}</span></span><span class="toggle-track"></span></button>
    </div>`;
  syncSidebarToggle();
  $("#sidebar-toggle").addEventListener("click", toggleSidebar);
  $("#theme-toggle").addEventListener("click", toggleTheme);
  $("#nav-explorer").addEventListener("click", (e) => { e.preventDefault(); toggleExplorer(true); });
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
  try { localStorage.setItem("beir7-sidebar", next); } catch (_) {}
  syncSidebarToggle();
}
function themeIcon() { return document.documentElement.getAttribute("data-theme") === "light" ? I.sun : I.moon; }
function themeLabel() { return document.documentElement.getAttribute("data-theme") === "light" ? "Light" : "Dark"; }
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("beir7-theme", next); } catch (_) {}
  renderSidebar(state.route || "home");
}
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const dot = (ok) => `<span class="dot ${ok ? "ok" : "off"}"></span>`;
  const inv = h.inventory || {};
  const complete = ["fiqa", "scifact", "arguana"].filter((d) => inv[d] && inv[d].complete).length;
  return `
    <div class="status-row"><span class="k">Oracle</span>${dot(h.oracle.ready)}<span>${h.oracle.ready ? `${h.runs} run${h.runs === 1 ? "" : "s"}` : esc(h.oracle.backend)}</span></div>
    <div class="status-row"><span class="k">Corpora</span>${dot(complete === 3)}<span>${h.inventory ? `${complete}/3 complete` : "checking…"}</span></div>
    <div class="status-row"><span class="k">bge</span>${dot(h.models.bge === "loaded")}<span>${esc(h.models.bge)}</span></div>
    <div class="status-row"><span class="k">Reranker</span>${dot(h.models.reranker === "loaded")}<span>${esc(h.models.reranker)}</span></div>`;
}
function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }
function setStage(html, accent) {
  const stage = $("#stage");
  stage.style.setProperty("--accent", accent || "#22d3ee");
  stage.innerHTML = `<div class="view wide view-enter">${html}</div>`;
  stage.scrollTop = 0;
}
function needsDB() {
  const h = state.health;
  if (h && h.oracle && h.oracle.ready) {
    const inv = h.inventory;
    if (inv && !["fiqa", "scifact", "arguana"].every((d) => inv[d] && inv[d].complete)) {
      return `<div class="banner warn">${I.alert}<div>Some of the notebook's corpora, vectors, text indexes or graphs are missing from Oracle (the notebook's cleanup switch <span class="mono">BEIR7_DROP_CORPORA=1</span> removes them). Re-run the notebook to restore them; pages that need them say so.</div></div>`;
    }
    return "";
  }
  return `<div class="banner warn">${I.alert}<div>${h && h.oracle && h.oracle.error ? `Oracle AI Database is unavailable: <span class="mono">${esc(h.oracle.error)}</span>. Start it with <span class="mono">./oracle.sh start</span> in <span class="mono">part7/</span>.` : "Oracle AI Database is still starting; this page fills in as soon as it is ready."}</div></div>`;
}
async function loadRuns() {
  const d = await getJSON("/api/runs");
  state.runs = d.runs || [];
  if (!state.runId || !state.runs.some((r) => r.run_id === state.runId)) state.runId = d.default;
  return state.runs;
}
function runPicker(id) {
  return `<label class="hint" for="${id}">Run</label><select id="${id}">${state.runs.map((r) => `<option value="${esc(r.run_id)}" ${r.run_id === state.runId ? "selected" : ""}>${esc(r.run_id)} · ${fmtWhen(r.started_at)} · ${r.test_rows.toLocaleString()} test rows</option>`).join("")}</select>`;
}

// ── Leaderboard ───────────────────────────────────────────────────────
async function viewLeaderboard() {
  setStage(`
    <header class="eval-head">
      <div class="eval-kicker">BEIR retrieval benchmark · held-out test queries</div>
      <h1 class="eval-title">Which strategy wins, and <em>by how much?</em></h1>
      <p class="eval-desc">Every strategy ran as SQL on Oracle AI Database with its best configuration, tuned on dev queries and measured once on test queries the tuning never saw. Every number here is recomputed from the per-query rows the notebook stored in <span class="mono">BEIR7_RESULTS</span>, with its seed, so it matches the notebook.</p>
    </header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-body row" id="lb-run">Loading runs…</div></div>
    <details class="panel mb"><summary class="panel-head"><span class="panel-title">The metrics, in one line each</span><span class="hint">open</span></summary>
      <div class="panel-body"><div class="defs">${METRICS.map((m) => `<div><b>${M_NAME[m]}</b> ${esc(M_DEF[m])}</div>`).join("")}<div><b>95% interval</b> the middle 95% of 2,000 bootstrap resamples of the per-query values.</div><div><b>p50 / p95 ms</b> median and 95th percentile time per query: the database, plus the cross-encoder for rerank.</div></div></div></details>
    <div id="lb-body"><div class="empty">Reading the stored run…</div></div>`, "#22d3ee");
  try {
    await loadRuns();
    setHTML("#lb-run", runPicker("lb-run-select"));
    $("#lb-run-select").addEventListener("change", (e) => { state.runId = e.target.value; loadLeaderboard(); });
    await loadLeaderboard();
  } catch (e) { setHTML("#lb-body", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
async function loadLeaderboard() {
  setHTML("#lb-body", `<div class="empty">Computing intervals and paired tests…</div>`);
  const d = await getJSON(`/api/leaderboard?run_id=${encodeURIComponent(state.runId || "")}`);
  const blocks = Object.entries(d.datasets).map(([ds, rows]) => {
    if (!rows.length) return "";
    const best = {};
    METRICS.forEach((m) => { best[m] = Math.max(...rows.map((r) => r.metrics[m].mean)); });
    const cols = [
      { label: "Strategy", html: true, get: (r) => tag(r.strategy) },
      { label: "Configuration", key: "config", wrap: true },
      ...METRICS.map((m) => ({ label: M_NAME[m], num: true, html: true, title: M_DEF[m],
        cls: (r) => (Math.abs(r.metrics[m].mean - best[m]) < 1e-9 ? "best" : ""),
        get: (r) => `${num(r.metrics[m].mean)}<span class="ci">${num(r.metrics[m].ci[0], 2)}–${num(r.metrics[m].ci[1], 2)}</span>` })),
      { label: "p50 ms", num: true, get: (r) => ms(r.p50_ms) }, { label: "p95 ms", num: true, get: (r) => ms(r.p95_ms) },
    ];
    const chart = svgIntervals(rows.map((r) => ({ label: r.strategy, mean: r.metrics.ndcg10.mean, lo: r.metrics.ndcg10.ci[0], hi: r.metrics.ndcg10.ci[1], color: S_COLOR[r.strategy] })));
    const top = [...rows].sort((a, b) => b.metrics.ndcg10.mean - a.metrics.ndcg10.mean)[0];
    return `<div class="panel mb" data-ds="${ds}"><div class="panel-head"><span class="panel-title">${esc(DS_NAME[ds])} · ${rows[0].queries} test queries</span>${pill(`winner: ${top.strategy}`, "ready")}</div>
      <div class="panel-body">${table(cols, rows)}
        <div class="chart-row" style="margin-top:14px"><div class="chart-box"><h4>nDCG@10 with its 95% interval</h4>${chart}</div></div>
        ${howto(["Read nDCG@10 first, then P@1 (the first thing a reader sees) and R@100 (what a second stage can use). Green marks the best value of each metric.",
                 "Overlapping intervals do not settle a comparison; the paired tests below do."],
                `In this run ${esc(top.strategy)} leads ${esc(DS_NAME[ds])} with ${num(top.metrics.ndcg10.mean)} [${num(top.metrics.ndcg10.ci[0])}–${num(top.metrics.ndcg10.ci[1])}].`)}</div></div>`;
  }).join("");
  const tests = table([
    { label: "Dataset", get: (t) => DS_NAME[t.dataset] }, { label: "Comparison", key: "comparison" },
    { label: "A", html: true, get: (t) => tag(t.a) }, { label: "B", html: true, get: (t) => tag(t.b) },
    { label: "nDCG@10 A − B", num: true, get: (t) => signed(t.diff, 4) },
    { label: "95% CI", num: true, get: (t) => `${signed(t.ci[0])} to ${signed(t.ci[1])}` },
    { label: "p", num: true, get: (t) => num(t.p, 4) }, { label: "p (Holm)", num: true, get: (t) => num(t.p_holm, 4) },
    { label: "Significant", html: true, get: (t) => pill(t.significant ? "yes" : "no", t.significant ? "pass" : "idle") },
  ], d.tests);
  const gap = table([
    { label: "Dataset", get: (g) => DS_NAME[g.dataset] }, { label: "Strategy", html: true, get: (g) => tag(g.strategy) },
    { label: "Configuration", key: "config", wrap: true }, { label: "Dev queries", num: true, key: "dev_queries" },
    { label: "Dev nDCG@10", num: true, get: (g) => num(g.dev_ndcg10, 4) }, { label: "Test nDCG@10", num: true, get: (g) => num(g.test_ndcg10, 4) },
    { label: "Test − dev", num: true, html: true, get: (g) => `<span class="delta ${g.test_minus_dev >= 0 ? "up" : "down"}">${signed(g.test_minus_dev, 4)}</span>` },
  ], d.gap);
  const costs = table([
    { label: "Dataset", get: (c) => DS_NAME[c.dataset] }, { label: "Build step", key: "item" },
    { label: "Seconds", num: true, get: (c) => num(c.seconds, 1) }, { label: "MB", num: true, get: (c) => num(c.mb, 1) },
    { label: "Measured in", get: (c) => (c.run_id === d.run_id ? "this run" : c.run_id) },
  ], d.costs);
  const ot = listJoin(d.bm25.map((b) => `${num(b.oracle_text)} on ${esc(DS_NAME[b.dataset])}`));
  const pub = listJoin(d.bm25.map((b) => num(b.bm25)));
  const below = d.bm25.filter((b) => b.oracle_text < b.bm25).map((b) => DS_NAME[b.dataset]);
  const fiqaDocs = ((state.runs.find((r) => r.run_id === d.run_id) || {}).settings || {}).fiqa_docs;
  const verdict = below.length === d.bm25.length ? `Oracle Text is below BM25 on all three datasets, on FiQA even though its corpus here is a ${fiqaDocs ? Number(fiqaDocs).toLocaleString() + "-document " : ""}sample, which raises scores.`
    : `Oracle Text is below BM25 on ${esc(listJoin(below) || "none of the datasets")}.`;
  const hnsw = Object.entries(d.hnsw || {}).map(([ds, h]) => `${esc(DS_NAME[ds])} ${num(h.ndcg10)} at a median of ${ms(h.p50_ms)} ms`).join("; ");
  setHTML("#lb-body", `${blocks}
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Paired tests on the same test queries</span></div><div class="panel-body">${tests}
      ${howto(["Each row compares two strategies query by query: the mean difference in nDCG@10, its 95% interval, and a randomisation p-value (10,000 sign flips).",
               "<b>p (Holm)</b> corrects for running all these tests at once; trust it, not the raw p. Per dataset the rows are the top two strategies, then every other strategy against vector search."])}</div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">How optimistic were the dev scores?</span></div><div class="panel-body">${gap}
      ${howto(["Vector search had only two settings to choose from, so its gap is the difference between the two query sets.",
               "A tuned strategy that drops further on the same dataset shows the luck of picking the best of many settings."])}</div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">What each index cost to build</span></div><div class="panel-body">${costs}
      ${hnsw ? `<div class="howto">The HNSW side run (vector search through the approximate index at target accuracy 90) on the same test queries: ${hnsw}.</div>` : ""}</div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Oracle Text against BEIR's published BM25</span></div><div class="panel-body"><div class="note">On these test queries the best Oracle Text configuration scores nDCG@10 of ${ot}. The BEIR paper reports BM25 at ${pub} on the full corpora. ${verdict} The reason is the scoring formula: Oracle Text's default score has no document-length normalisation, while BM25 normalises by document length and saturates term frequency.</div></div></div>`);
}

// ── Data Explorer (read-only) ─────────────────────────────────────────
const explorer = { tables: [], selected: null, offset: 0, limit: 40, token: 0 };
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
    if (!explorer.selected && d.tables.length) selectExplorer((d.tables.find((t) => t.name === "beir7_results") || d.tables[0]).name, 0);
  } catch (e) { $("#explorer-summary").textContent = e.message; }
}
async function selectExplorer(name, offset) {
  explorer.selected = name; explorer.offset = offset;
  $$("#explorer-table-list [data-t]").forEach((b) => b.classList.toggle("selected", b.dataset.t === name));
  const run = ($("#explorer-run").value || "").trim();
  const token = ++explorer.token;
  try {
    const d = await getJSON(`/api/data_explorer/tables/${encodeURIComponent(name)}/rows?limit=${explorer.limit}&offset=${offset}${run ? `&run_id=${encodeURIComponent(run)}` : ""}`);
    if (token !== explorer.token) return;            // a later selection is already on its way
    $("#explorer-table-name").textContent = d.table;
    $("#explorer-role").textContent = (explorer.tables.find((t) => t.name === name) || {}).role || "";
    $("#explorer-page").textContent = `${d.rows.length ? offset + 1 : 0}–${offset + d.rows.length} of ${d.total.toLocaleString()}`;
    $("#explorer-prev").disabled = offset === 0;
    $("#explorer-next").disabled = offset + d.rows.length >= d.total;
    const cell = (v) => v == null ? '<span class="explorer-null">NULL</span>' : esc(String(v).slice(0, 300));
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
function routes() { return { "": viewLeaderboard, explore: viewExplore, playground: viewPlayground, guide: viewGuide }; }
function route() {
  closeStreams();
  const id = location.hash.replace(/^#\/?/, "").split("?")[0].trim();
  state.route = id || "home";
  renderSidebar(state.route);
  (routes()[id] || viewLeaderboard)();
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
