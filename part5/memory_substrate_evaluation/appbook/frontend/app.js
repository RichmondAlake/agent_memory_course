/* ======================================================================
   Memory Substrate Evaluation — SPA
   An educational progression comparing two agent-memory substrates:
   the filesystem (amber) and the Oracle AI Database (teal).
   ====================================================================== */
"use strict";

const ICONS = {
  files: '<path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M5 21V5a2 2 0 0 1 2-2h7l5 5v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/><path d="M9 9h1M9 13h6M9 17h6"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  zap: '<path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>',
  shuffle: '<path d="M16 3h5v5"/><path d="M4 20 21 3"/><path d="M21 16v5h-5"/><path d="m15 15 6 6"/><path d="M4 4l5 5"/>',
  award: '<circle cx="12" cy="8" r="6"/><path d="m8.2 13.4-1.2 7.6L12 18l5 3-1.2-7.6"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
  play: '<path d="m6 3 14 9-14 9V3z"/>',
  reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  home: '<path d="m3 10 9-7 9 7v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
  brain: '<path d="M12 5a3 3 0 0 0-5.9-.7A2.5 2.5 0 0 0 4 9a2.5 2.5 0 0 0 1 4 2.5 2.5 0 0 0 3 3 3 3 0 0 0 4 1 3 3 0 0 0 4-1 2.5 2.5 0 0 0 3-3 2.5 2.5 0 0 0 1-4 2.5 2.5 0 0 0-2.1-4.7A3 3 0 0 0 12 5z"/>',
};
const ic = (n) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[n] || ""}</svg>`;

const STEPS = [
  { id: "home", label: "Overview", icon: "home", accent: "var(--indigo)", home: true },
  { id: "substrates", n: 1, label: "Two Substrates", icon: "database", accent: "var(--indigo)" },
  { id: "ingest", n: 2, label: "Write & Ingest", icon: "zap", accent: "var(--indigo)" },
  { id: "retrieval", n: 3, label: "Retrieval", icon: "search", accent: "var(--indigo)" },
  { id: "concurrency", n: 4, label: "Concurrency & ACID", icon: "shuffle", accent: "var(--ok)" },
  { id: "scorecard", n: 5, label: "Scorecard", icon: "award", accent: "var(--indigo)" },
];

const state = {
  route: "home",
  health: null,
  corpus: null,
  ingested: false,
  lastIngest: null,
  lastSearch: null,
  lastAnswer: null,
  lastConcurrency: null,
};

const $ = (s, r = document) => r.querySelector(s);
const fmtMs = (x) => (x == null ? "—" : x < 1000 ? `${x.toFixed(x < 10 ? 2 : 0)} ms` : `${(x / 1000).toFixed(2)} s`);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
async function post(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : null });
}

/* ── boot ──────────────────────────────────────────────────────────────── */
async function boot() {
  bindChrome();
  try {
    const [health, corpus] = await Promise.all([api("/api/health"), api("/api/corpus")]);
    state.health = health;
    state.corpus = corpus;
  } catch (e) {
    state.health = { ok: false, error: String(e) };
  }
  render();
  pollHealth();
}

function pollHealth() {
  // DB substrate warms in the background (nomic download + Oracle connect); refresh the badge.
  let tries = 0;
  const t = setInterval(async () => {
    tries++;
    try {
      const h = await api("/api/health");
      const prev = JSON.stringify(state.health && state.health.db);
      state.health = h;
      if (JSON.stringify(h.db) !== prev) renderSidebar();
      if ((h.db && h.db.backend && h.db.backend !== "uninitialized") || tries > 20) clearInterval(t);
    } catch (e) { if (tries > 20) clearInterval(t); }
  }, 2500);
}

function bindChrome() {
  const menu = $("#menuBtn"), sidebar = $("#sidebar"), scrim = $("#scrim");
  if (menu) menu.onclick = () => { sidebar.classList.add("open"); scrim.hidden = false; };
  if (scrim) scrim.onclick = () => { sidebar.classList.remove("open"); scrim.hidden = true; };
}

function navigate(id) {
  state.route = id;
  $("#sidebar").classList.remove("open");
  $("#scrim").hidden = true;
  render();
  $("#stage").scrollTop = 0;
  $("#stage").focus();
}

/* ── sidebar ───────────────────────────────────────────────────────────── */
function renderSidebar() {
  const db = state.health && state.health.db;
  const fs = state.health && state.health.fs;
  const dbBackend = db ? db.backend : "…";
  const dbDot = !db ? "warn pulse" : db.backend === "oracle" ? "ok" : db.backend === "memory" ? "warn" : "warn pulse";
  const dbText = db ? (db.backend === "oracle" ? "Oracle AI Database" : db.backend === "memory" ? "In-memory (Oracle offline)" : "warming…") : "connecting…";
  const theme = document.documentElement.getAttribute("data-theme");

  const nav = STEPS.map((s) => `
    <a class="nav-item ${s.home ? "nav-home" : ""} ${state.route === s.id ? "active" : ""}" data-go="${s.id}" style="--c:${s.accent}">
      <span class="nav-node">${s.home ? ic("home") : s.n}</span>
      <span class="nav-label">${s.label}</span>
    </a>`).join("");

  $("#sidebar").innerHTML = `
    <div class="brand">
      <div class="brand-glyph"><span class="gf">${ic("files")}</span></div>
      <div class="brand-text"><b>Substrate Eval</b><span>Part 5 · Agent Memory</span></div>
    </div>
    <div class="rail-label">The Progression</div>
    <nav class="nav">${nav}</nav>
    <div class="sidebar-foot">
      <div class="status-card">
        <div class="status-row"><span class="k">DB</span><span class="dot ${dbDot}"></span><span>${dbText}</span></div>
        <div class="status-row"><span class="k">FS</span><span class="dot ok"></span><span>${fs ? fs.doc_count + " files" : "ready"}</span></div>
        <div class="status-row"><span class="k">Embed</span><span class="dot ok"></span><span class="mono" style="font-size:10px">nomic · 768d</span></div>
      </div>
      <button class="theme-toggle" id="themeToggle"><span>${theme === "light" ? "Light" : "Dark"}</span><span class="toggle-track"></span></button>
    </div>`;

  $("#sidebar").querySelectorAll("[data-go]").forEach((a) => (a.onclick = () => navigate(a.dataset.go)));
  const tt = $("#themeToggle");
  if (tt) tt.onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("substrate-theme", next); } catch (e) {}
    renderSidebar();
  };
}

/* ── render dispatch ───────────────────────────────────────────────────── */
function render() {
  renderSidebar();
  const stage = $("#stage");
  const view = { home: viewHome, substrates: viewSubstrates, ingest: viewIngest, retrieval: viewRetrieval, concurrency: viewConcurrency, scorecard: viewScorecard }[state.route] || viewHome;
  const step = STEPS.find((s) => s.id === state.route) || STEPS[0];
  stage.style.setProperty("--accent", step.accent);
  stage.innerHTML = `<div class="view view-enter">${view()}</div>`;
  bindView();
}

function head(step, kicker, title, desc, term) {
  return `
    <div class="ff-head">
      <div class="ff-numeral">${step.home ? "" : step.n}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">${kicker}</div>
        <h1 class="ff-title">${title}</h1>
        <p class="ff-desc">${desc}</p>
        ${term ? `<div class="ff-term">${term}</div>` : ""}
      </div>
    </div>`;
}

/* ── view: overview ────────────────────────────────────────────────────── */
function viewHome() {
  const rungs = STEPS.filter((s) => !s.home).map((s) => `
    <a class="rung" data-go="${s.id}" style="--c:${s.accent}">
      <div class="rung-num">${s.n}</div>
      <div class="rung-main"><h3>${s.label}</h3><p>${HOME_BLURB[s.id]}</p></div>
      <div class="rung-go">${ic("arrow")}</div>
    </a>`).join("");
  return `
    <div class="hero">
      <div class="hero-kicker"><span class="pip"></span> Memory Substrate Evaluation</div>
      <h1>Where should an agent keep its memory — the <em class="e-fs">filesystem</em> or the <em class="e-db">database</em>?</h1>
      <p>Two agents, the same tools, one difference: where memory lives. This app puts the two substrates side by side and runs the three benchmarks that actually decide it — <b>write latency</b>, <b>retrieval quality</b>, and <b>ACID concurrency</b> — live, on your machine.</p>
    </div>
    <div class="ladder">${rungs}</div>
    <div class="callout" style="--accent:var(--indigo)">Built on the same stack as the notebook: agent answers from <b>Claude Opus 4.8</b>, embeddings from local open-source <b>nomic</b> (768-dim, no API key), vectors in <b>Oracle AI Database</b>. Work top to bottom — each step builds on the last.</div>`;
}
const HOME_BLURB = {
  substrates: "Meet the two substrates and the identical corpus of agent-memory notes they will both hold.",
  ingest: "Write the same notes into both — and watch an instant file write trade off against an embed-and-index.",
  retrieval: "The headline: literal keyword search vs search by meaning. See where grep goes blind.",
  concurrency: "Race concurrent writers: a naive file loses data, a real database does not.",
  scorecard: "Put it together — when to reach for files, and when to reach for a database.",
};

/* ── view: substrates ──────────────────────────────────────────────────── */
function viewSubstrates() {
  const step = STEPS[1];
  const docs = (state.corpus && state.corpus.docs) || [];
  const docCards = docs.map((d) => `
    <div class="doc-card"><div class="doc-cat">${esc(d.category)}</div><h4>${esc(d.title)}</h4><p>${esc(d.content.slice(0, 110))}…</p></div>`).join("");
  return head(step, "Step 1 · The two substrates", "Same memory, two homes",
    "An agent's long-term memory is just stored text it can search. The question is the storage engine underneath. The <b>filesystem</b> keeps notes as markdown files; the <b>Oracle AI Database</b> keeps them as rows with a vector embedding. Both hold the identical corpus below.",
    "Throughout this app, <b style='color:var(--fs)'>amber</b> is the filesystem substrate and <b style='color:var(--db)'>teal</b> is the database substrate.") + `
    <div class="subs">
      <div class="sub-card fs">
        <div class="sub-head"><div class="sub-icon">${ic("files")}</div><div><h3>Filesystem</h3><div class="sub-sub">markdown on disk</div></div></div>
        <div class="sub-body">
          ${trait("Write", "Append/replace a <code>.md</code> file — instant local I/O")}
          ${trait("Search", "Literal keyword / grep — matches the words you typed")}
          ${trait("Readable", "Yes — open it in any editor, diff it in git")}
          ${trait("Concurrency", "Unsafe by default; needs explicit file locking")}
          ${trait("Best at", "Single-user tools, prototypes, human-auditable logs")}
        </div>
      </div>
      <div class="sub-card db">
        <div class="sub-head"><div class="sub-icon">${ic("database")}</div><div><h3>Oracle AI Database</h3><div class="sub-sub">rows + vector column</div></div></div>
        <div class="sub-body">
          ${trait("Write", "Embed the text, then INSERT a row with a VECTOR — costs an embed")}
          ${trait("Search", "Semantic — VECTOR_DISTANCE finds notes by meaning")}
          ${trait("Readable", "No — vectors aren't human-readable, but they're queryable")}
          ${trait("Concurrency", "ACID by default; concurrent writers never lose data")}
          ${trait("Best at", "Production, multi-user, semantic recall at scale")}
        </div>
      </div>
    </div>
    <div class="section-label">The shared corpus · ${docs.length} synthetic agent-memory notes</div>
    <div class="doc-grid">${docCards}</div>
    <div class="row" style="margin-top:22px"><button class="btn btn-accent" data-go="ingest">Next: write them into both ${ic("arrow")}</button></div>`;
}
const trait = (k, v) => `<div class="trait"><div class="tk">${k}</div><div class="tv">${v}</div></div>`;

/* ── view: ingest ──────────────────────────────────────────────────────── */
function viewIngest() {
  const step = STEPS[2];
  const r = state.lastIngest;
  return head(step, "Step 2 · Write & ingest", "What does a write cost?",
    "Press the button to write all notes into <b>both</b> substrates. The filesystem just drops files on disk. The database must <b>embed</b> each note into a 768-dim vector and index it — that's the price of semantic recall you'll cash in next step.") + `
    <div class="row" style="margin-bottom:18px">
      <button class="btn btn-accent" id="ingestBtn">${ic("zap")} Ingest corpus into both</button>
      <button class="btn" id="resetBtn">${ic("reset")} Reset</button>
      <span class="hint" id="ingestHint"></span>
    </div>
    <div id="ingestResults">${r ? renderIngest(r) : `<div class="banner info">${ic("zap")}<div>No writes yet — run the ingest to compare write latency across the two substrates. The first database write also downloads the local nomic model (one-time).</div></div>`}</div>`;
}
function renderIngest(r) {
  const fs = r.fs, db = r.db;
  const max = Math.max(fs.total_ms, db.total_ms, 1);
  return `
    <div class="subs">
      <div class="sub-card fs">
        <div class="sub-head"><div class="sub-icon">${ic("files")}</div><div><h3>Filesystem</h3><div class="sub-sub">${fs.doc_count} files written</div></div></div>
        <div class="sub-body">
          ${metric("Total write time", `<b>${fmtMs(fs.total_ms)}</b>`, "fs", (fs.total_ms / max) * 100)}
          ${metric("Per note", fmtMs(fs.per_doc_ms), "fs", (fs.per_doc_ms / (max / fs.doc_count)) * 100)}
          <div class="subnote">${esc(fs.note)}</div>
        </div>
      </div>
      <div class="sub-card db">
        <div class="sub-head"><div class="sub-icon">${ic("database")}</div><div><h3>Oracle AI Database</h3><div class="sub-sub">${db.backend === "oracle" ? "Oracle · " : "in-memory · "}${db.doc_count} notes · ${db.dim}d</div></div></div>
        <div class="sub-body">
          ${metric("Total write time", `<b>${fmtMs(db.total_ms)}</b>`, "db", (db.total_ms / max) * 100)}
          ${metric("— embedding (nomic)", fmtMs(db.embed_ms), "db", (db.embed_ms / max) * 100)}
          ${metric("— store / index", fmtMs(db.store_ms), "db", (db.store_ms / max) * 100)}
          <div class="subnote">${esc(db.note)}</div>
        </div>
      </div>
    </div>
    <div class="callout">The filesystem wins on raw write speed by a wide margin — it's doing far less. The database spent most of its time <b>embedding</b>. That embedding is not waste: it's what makes the next step possible. <b>Speed now, or intelligence later?</b> ${db.backend !== "oracle" ? "<br><br><span class='mono' style='color:var(--fs)'>Note: Oracle is offline, so the database substrate is using an in-memory index. Numbers still illustrate the trade-off; start the Oracle container for the real thing.</span>" : ""}</div>
    <div class="row" style="margin-top:18px"><button class="btn btn-accent" data-go="retrieval">Next: search both ${ic("arrow")}</button></div>`;
}
const metric = (name, val, cls, pct) => `
  <div class="metric"><div class="metric-top"><span class="metric-name">${name}</span><span class="metric-val">${val}</span></div>
  <div class="bar"><div class="bar-fill ${cls}" data-w="${Math.max(2, Math.min(100, pct || 0))}"></div></div></div>`;

/* ── view: retrieval ───────────────────────────────────────────────────── */
function viewRetrieval() {
  const step = STEPS[3];
  const chips = ((state.corpus && state.corpus.suggested_queries) || []).map((q) => `<button class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("");
  const needIngest = !state.ingested;
  return head(step, "Step 3 · Retrieval — the headline", "Keyword vs meaning",
    "Ask both substrates the same question. The filesystem matches the <b>words you typed</b>; the database matches the <b>meaning</b>. Try a question that uses different words than the notes — and watch keyword search go blind while vector search still finds it.") + `
    ${needIngest ? `<div class="banner warn">${ic("zap")}<div>Ingest the corpus first so both substrates have something to search. <a data-go="ingest" style="cursor:pointer">Go to Step 2 →</a></div></div>` : ""}
    <div class="panel"><div class="panel-body">
      <div class="field-row">
        <input type="text" id="q" placeholder="e.g. How does an agent cope when it runs out of room in the prompt?" />
        <button class="btn btn-accent" id="searchBtn" ${needIngest ? "disabled" : ""}>${ic("search")} Search both</button>
      </div>
      <div class="hint" style="margin:10px 0 8px">Try a paraphrased question — these use different words than any note:</div>
      <div class="chips">${chips}</div>
    </div></div>
    <div id="retrResults"></div>`;
}
function renderSearch(r) {
  const col = (s, cls, label, icon) => {
    const hits = s.hits || [];
    const max = Math.max(...hits.map((h) => h.score), 0.0001);
    const body = hits.length ? hits.map((h) => `
      <div class="hit" style="--c:var(--${cls})">
        <div class="hit-top"><span class="hit-title">${esc(h.title)}</span><span class="hit-score">${cls === "db" ? h.score.toFixed(3) : "×" + h.score}</span></div>
        <div class="hit-bar"><i style="width:${Math.max(6, (h.score / max) * 100)}%"></i></div>
        <div class="hit-snip">${esc(h.snippet)}</div>
        ${h.matched_terms && h.matched_terms.length ? `<div class="hit-terms">${h.matched_terms.map((t) => `<span class="term">${esc(t)}</span>`).join("")}</div>` : ""}
      </div>`).join("") : `<div class="empty-hit">No matches.<br>${cls === "fs" ? "None of those words appear literally in any note." : "—"}</div>`;
    return `
      <div class="sub-card ${cls}">
        <div class="sub-head"><div class="sub-icon">${ic(icon)}</div><div><h3>${label}</h3><div class="sub-sub">${esc(s.method)} · ${fmtMs(s.latency_ms)}</div></div></div>
        <div class="sub-body">${body}<div class="code">${esc(s.command)}</div></div>
      </div>`;
  };
  return `
    <div class="retr-grid">
      ${col(r.fs, "fs", "Filesystem · keyword", "files")}
      ${col(r.db, "db", "Database · semantic", "database")}
    </div>
    <div class="callout">${verdictForSearch(r)}</div>
    <div class="row" style="margin-top:16px">
      <button class="btn" id="answerBtn">${ic("brain")} Answer from each side with Claude</button>
      <span class="hint" id="answerHint"></span>
    </div>
    <div id="answerResults"></div>`;
}
function verdictForSearch(r) {
  const fsN = (r.fs.hits || []).length, dbN = (r.db.hits || []).length;
  if (fsN === 0 && dbN > 0)
    return `<b>This is the whole point.</b> Keyword search found <b style='color:var(--fs)'>nothing</b> — the question's words never appear literally in the notes. Vector search still surfaced <b style='color:var(--db)'>${dbN}</b> relevant note${dbN > 1 ? "s" : ""} by <b>meaning</b>. Paraphrase is invisible to grep but not to embeddings.`;
  if (fsN > 0 && dbN > 0)
    return `Both found results. Keyword search works when your wording matches the text; notice the database ranks by <b>semantic similarity</b> (0–1 cosine) while the filesystem ranks by raw term counts. The more a query paraphrases, the more the gap widens.`;
  return `Keyword found ${fsN}, semantic found ${dbN}. Try one of the paraphrased suggestions to see them diverge.`;
}
function renderAnswers(a) {
  const box = (side, cls, label) => `
    <div class="sub-card ${cls}">
      <div class="sub-head"><div class="sub-icon">${ic(cls === "fs" ? "files" : "database")}</div><div><h3>${label}</h3><div class="sub-sub">${(side.hits || []).length} passage(s) of context</div></div></div>
      <div class="sub-body"><div class="answer" style="--c:var(--${cls})"><div class="answer-label">Claude, grounded only in this side's context</div>${esc(side.answer)}</div></div>
    </div>`;
  return `<div class="retr-grid" style="margin-top:14px">${box(a.fs, "fs", "Filesystem answer")}${box(a.db, "db", "Database answer")}</div>
    ${a.model_present ? `<div class="callout">Same model, same question — only the <b>retrieved context</b> differs. When keyword search hands the model nothing relevant, even a strong model can only say it doesn't know. <b>Retrieval quality caps answer quality.</b></div>` : ""}`;
}

/* ── view: concurrency ─────────────────────────────────────────────────── */
function viewConcurrency() {
  const step = STEPS[4];
  const lanes = [
    { id: "fs", cls: "fs", name: "Filesystem (no lock)" },
    { id: "lock", cls: "lock", name: "Filesystem (flock)" },
    { id: "db", cls: "db", name: "Database (ACID)" },
  ];
  const laneHtml = lanes.map((l) => `
    <div class="lane ${l.cls}" id="lane-${l.id}">
      <div class="lane-top"><span class="lane-name">${esc(l.name)} <span class="lane-engine" data-engine></span></span><span class="lane-verdict pending" data-verdict>pending</span></div>
      <div class="lane-bar"><div class="lane-fill" data-fill></div><div class="lane-pct"><span data-count>—</span><span data-elapsed></span></div></div>
      <div class="lane-stats" data-stats></div>
      <div class="lane-note" data-note></div>
    </div>`).join("");
  return head(step, "Step 4 · Concurrency & ACID", "What happens under contention?",
    "Many writers, one memory, all at once. Each writer records the same number of entries. A naive file does <b>read-modify-write</b> with no coordination and loses updates; a locked file takes turns; a transactional database commits atomically. Run the race and count what survives.") + `
    <div class="panel"><div class="panel-body">
      <div class="field-row" style="align-items:flex-end;flex-wrap:wrap;gap:16px">
        <div><div class="hint" style="margin-bottom:6px">Concurrent writers</div><input type="number" id="writers" value="8" min="2" max="16" /></div>
        <div><div class="hint" style="margin-bottom:6px">Entries each</div><input type="number" id="perw" value="40" min="10" max="200" /></div>
        <div><div class="hint" style="margin-bottom:6px">Expected total</div><div class="kchip" id="expected" style="padding:9px 12px">320</div></div>
        <button class="btn btn-accent" id="raceBtn">${ic("play")} Run the race</button>
      </div>
    </div></div>
    ${laneHtml}
    <div id="raceVerdict"></div>`;
}

function runRace() {
  const writers = Math.max(2, Math.min(16, parseInt($("#writers").value) || 8));
  const per = Math.max(10, Math.min(200, parseInt($("#perw").value) || 40));
  const btn = $("#raceBtn");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Racing…`;
  ["fs", "lock", "db"].forEach((id) => {
    const lane = $("#lane-" + id);
    lane.classList.remove("running");
    lane.querySelector("[data-verdict]").className = "lane-verdict pending";
    lane.querySelector("[data-verdict]").textContent = "pending";
    lane.querySelector("[data-fill]").style.width = "0%";
    lane.querySelector("[data-count]").textContent = "—";
    lane.querySelector("[data-elapsed]").textContent = "";
    lane.querySelector("[data-stats]").innerHTML = "";
    lane.querySelector("[data-note]").textContent = "";
  });
  $("#raceVerdict").innerHTML = "";
  state.lastConcurrency = { writers, per, results: [] };

  const laneIdFor = (approach) => approach.includes("no lock") ? "fs" : approach.includes("flock") ? "lock" : "db";
  const es = new EventSource(`/api/benchmark/concurrency?writers=${writers}&per=${per}`);
  es.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.phase === "config") $("#expected").textContent = d.expected;
    if (d.phase === "start") { const l = $("#lane-" + laneIdFor(d.approach)); if (l) l.classList.add("running"); }
    if (d.phase === "result") applyLaneResult(d.result, laneIdFor(d.result.approach));
    if (d.phase === "done") { es.close(); btn.disabled = false; btn.innerHTML = `${ic("play")} Run again`; renderRaceVerdict(); }
  };
  es.addEventListener("end", () => { es.close(); btn.disabled = false; btn.innerHTML = `${ic("play")} Run again`; });
  es.onerror = () => { es.close(); btn.disabled = false; btn.innerHTML = `${ic("play")} Run again`; };
}
function applyLaneResult(res, id) {
  state.lastConcurrency.results.push(res);
  const lane = $("#lane-" + id);
  if (!lane) return;
  lane.classList.remove("running");
  const pct = (res.actual / res.expected) * 100;
  lane.querySelector("[data-fill]").style.width = Math.max(3, pct) + "%";
  lane.querySelector("[data-count]").textContent = `${res.actual} / ${res.expected}`;
  lane.querySelector("[data-elapsed]").textContent = fmtMs(res.elapsed_ms);
  lane.querySelector("[data-engine]").textContent = "· " + res.engine;
  const v = lane.querySelector("[data-verdict]");
  v.className = "lane-verdict " + (res.safe ? "safe" : "unsafe");
  v.textContent = res.safe ? "zero loss" : `${res.loss_rate}% lost`;
  lane.querySelector("[data-stats]").innerHTML =
    `<span>actual <b>${res.actual}</b></span><span class="${res.lost > 0 ? "lost" : ""}">lost <b>${res.lost}</b></span><span>time <b>${fmtMs(res.elapsed_ms)}</b></span>`;
  lane.querySelector("[data-note]").textContent = res.note;
}
function renderRaceVerdict() {
  const rs = state.lastConcurrency.results;
  const naive = rs.find((r) => r.approach.includes("no lock"));
  if (!naive) return;
  $("#raceVerdict").innerHTML = `<div class="callout" style="--accent:var(--ok)">
    The naive filesystem lost <b style="color:var(--bad)">${naive.lost}</b> of ${naive.expected} writes (${naive.loss_rate}%) — silent data loss. Locking fixes it, but only because someone <i>remembered</i> to lock every writer. The database lost <b style="color:var(--ok)">nothing</b> with no special effort: <b>ACID is the default, not an add-on.</b></div>
    <div class="row" style="margin-top:16px"><button class="btn btn-accent" data-go="scorecard">Next: the scorecard ${ic("arrow")}</button></div>`;
  $("#raceVerdict").querySelectorAll("[data-go]").forEach((a) => (a.onclick = () => navigate(a.dataset.go)));
}

/* ── view: scorecard ───────────────────────────────────────────────────── */
function viewScorecard() {
  const step = STEPS[5];
  const ing = state.lastIngest, conc = state.lastConcurrency;
  const rows = [
    ["Write latency", `<span class="tag good">fast</span>`, `<span class="tag mid">embed cost</span>`, "Files just write; the DB pays to embed."],
    ["Retrieval", `<span class="tag mid">literal</span>`, `<span class="tag good">semantic</span>`, "Grep needs exact words; vectors match meaning."],
    ["Human-readable", `<span class="tag good">yes</span>`, `<span class="tag bad">no</span>`, "Markdown diffs in git; vectors don't."],
    ["Concurrency", `<span class="tag bad">unsafe*</span>`, `<span class="tag good">ACID</span>`, "*Safe only with manual locking."],
    ["Scales to many docs", `<span class="tag mid">grep slows</span>`, `<span class="tag good">indexed</span>`, "Vector indexes beat scanning files."],
    ["Setup cost", `<span class="tag good">none</span>`, `<span class="tag mid">a database</span>`, "Files need nothing; the DB is infrastructure."],
  ].map((r) => `<tr><td>${r[0]}</td><td class="c-fs">${r[1]}</td><td class="c-db">${r[2]}</td><td class="muted">${r[3]}</td></tr>`).join("");

  const recap = (ing || conc) ? `
    <div class="section-label">Your measured numbers</div>
    <div class="subs">
      <div class="sub-card fs"><div class="sub-head"><div class="sub-icon">${ic("files")}</div><div><h3>Filesystem</h3><div class="sub-sub">this session</div></div></div>
        <div class="sub-body">
          ${ing ? metric("Corpus write", `<b>${fmtMs(ing.fs.total_ms)}</b>`, "fs", 100) : ""}
          ${conc ? `<div class="trait"><div class="tk">Concurrency</div><div class="tv">${naiveRecap(conc)}</div></div>` : ""}
          ${!ing && !conc ? `<div class="hint">Run Steps 2 and 4 to populate this.</div>` : ""}
        </div></div>
      <div class="sub-card db"><div class="sub-head"><div class="sub-icon">${ic("database")}</div><div><h3>Database</h3><div class="sub-sub">this session</div></div></div>
        <div class="sub-body">
          ${ing ? metric("Corpus write", `<b>${fmtMs(ing.db.total_ms)}</b> (${fmtMs(ing.db.embed_ms)} embed)`, "db", 100) : ""}
          ${conc ? `<div class="trait"><div class="tk">Concurrency</div><div class="tv">${dbRecap(conc)}</div></div>` : ""}
          ${!ing && !conc ? `<div class="hint">Run Steps 2 and 4 to populate this.</div>` : ""}
        </div></div>
    </div>` : "";

  return head(step, "Step 5 · Scorecard", "When to reach for which",
    "There's no universal winner — there's a fit. The filesystem is the right call when speed, simplicity, and human-readability matter and you control all access. The database earns its keep the moment you need semantic recall, scale, or many writers at once.") + `
    <div class="panel"><table class="grid">
      <thead><tr><th>Dimension</th><th>Filesystem</th><th>Oracle AI Database</th><th>Why</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${recap}
    <div class="subs" style="margin-top:8px">
      <div class="callout" style="--accent:var(--fs);margin-top:0">${ic("files")} <b>Reach for the filesystem</b> when: single-user CLI tools, quick prototypes, human-auditable transcripts, and you want git-friendly, zero-setup memory.</div>
      <div class="callout" style="--accent:var(--db);margin-top:0">${ic("database")} <b>Reach for the database</b> when: production and multi-user, semantic search over a growing corpus, and data integrity under concurrency is non-negotiable.</div>
    </div>
    <div class="callout">The mature answer is often <b>both</b>: write to the filesystem for a fast, readable record, and to the database for durable, queryable, concurrent-safe recall — exactly the hybrid the notebook builds toward.</div>`;
}
const naiveRecap = (c) => { const n = (c.results || []).find((r) => r.approach.includes("no lock")); return n ? `lost <b style="color:var(--bad)">${n.lost}</b>/${n.expected} writes (no lock)` : "—"; };
const dbRecap = (c) => { const d = (c.results || []).find((r) => r.approach.includes("ACID")); return d ? `<b style="color:var(--ok)">${d.lost} lost</b> · ${esc(d.engine)}` : "—"; };

/* ── per-view bindings ─────────────────────────────────────────────────── */
function bindView() {
  document.querySelectorAll("#stage [data-go]").forEach((a) => (a.onclick = () => navigate(a.dataset.go)));
  // animate any latency bars present
  requestAnimationFrame(() => document.querySelectorAll(".bar-fill[data-w]").forEach((b) => (b.style.width = b.dataset.w + "%")));

  if (state.route === "ingest") {
    const btn = $("#ingestBtn");
    if (btn) btn.onclick = async () => {
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Writing…`;
      $("#ingestHint").textContent = "Embedding notes (first run also downloads the nomic model)…";
      try {
        const r = await post("/api/ingest");
        state.lastIngest = r; state.ingested = true;
        $("#ingestResults").innerHTML = renderIngest(r);
        bindView();
      } catch (e) { $("#ingestHint").textContent = "Error: " + e.message; }
      finally { btn.disabled = false; btn.innerHTML = `${ic("zap")} Re-ingest`; $("#ingestHint").textContent = ""; }
    };
    const rb = $("#resetBtn");
    if (rb) rb.onclick = async () => { await post("/api/reset"); state.ingested = false; state.lastIngest = null; render(); };
  }

  if (state.route === "retrieval") {
    const run = async () => {
      const q = $("#q").value.trim();
      if (!q) return;
      const btn = $("#searchBtn");
      btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Searching…`;
      try {
        const r = await post("/api/search", { query: q, k: 4 });
        state.lastSearch = r;
        $("#retrResults").innerHTML = renderSearch(r);
        bindView();
      } catch (e) { $("#retrResults").innerHTML = `<div class="banner warn">${ic("x")}<div>${e.message}</div></div>`; }
      finally { btn.disabled = false; btn.innerHTML = `${ic("search")} Search both`; }
    };
    const sb = $("#searchBtn"); if (sb) sb.onclick = run;
    const qi = $("#q"); if (qi) qi.onkeydown = (e) => { if (e.key === "Enter") run(); };
    document.querySelectorAll("#stage [data-q]").forEach((c) => (c.onclick = () => { $("#q").value = c.dataset.q; run(); }));

    const ab = $("#answerBtn");
    if (ab) ab.onclick = async () => {
      const q = ($("#q").value || "").trim() || (state.lastSearch && state.lastSearch.query);
      if (!q) return;
      ab.disabled = true; ab.innerHTML = `<span class="spinner"></span> Asking Claude…`;
      try {
        const a = await post("/api/answer", { query: q, k: 3 });
        state.lastAnswer = a;
        $("#answerResults").innerHTML = renderAnswers(a);
        if (!a.model_present) $("#answerHint").textContent = "Set ANTHROPIC_API_KEY to enable grounded answers.";
      } catch (e) { $("#answerHint").textContent = "Error: " + e.message; }
      finally { ab.disabled = false; ab.innerHTML = `${ic("brain")} Answer from each side with Claude`; }
    };
  }

  if (state.route === "concurrency") {
    const sync = () => { const w = parseInt($("#writers").value) || 0, p = parseInt($("#perw").value) || 0; $("#expected").textContent = w * p; };
    const wi = $("#writers"), pi = $("#perw");
    if (wi) wi.oninput = sync; if (pi) pi.oninput = sync; sync();
    const rb = $("#raceBtn"); if (rb) rb.onclick = runRace;
  }
}

boot();
