/* ======================================================================
   The query explorer, the tuning playground and the decision guide.
   ====================================================================== */

const streams = {};
function closeStreams() { Object.values(streams).forEach((s) => s.close()); Object.keys(streams).forEach((k) => delete streams[k]); }
function dsSelect(id, value) {
  return `<select id="${id}">${Object.entries(DS_NAME).map(([k, v]) => `<option value="${k}" ${k === value ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>`;
}

// ── Query explorer ────────────────────────────────────────────────────
const qx = { ds: "fiqa", queries: [] };

async function viewExplore() {
  setStage(`
    <header class="eval-head"><div class="eval-kicker">Query explorer</div>
      <h1 class="eval-title">One query, <em>five strategies</em></h1>
      <p class="eval-desc">Each strategy runs live as SQL on Oracle AI Database with the best configuration the stored run chose for this dataset. A stored test query uses its stored vector and its relevance judgements; a query you type is embedded with bge-small-en-v1.5 and has no judgements.</p></header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-body">
      <div class="qx-controls">
        <label>Dataset${dsSelect("qx-ds", qx.ds)}</label>
        <label>Test query<select id="qx-query"><option>Loading…</option></select></label>
        <div class="row"><button class="btn btn-ghost" id="qx-random">Random</button><button class="btn btn-accent" id="qx-run">Search</button></div>
      </div>
      <div class="qx-or">or type your own</div>
      <div class="qx-controls">
        <span class="hint">No judgements, so no relevance marks or metrics.</span>
        <label><span class="sr-only">Your query</span><textarea id="qx-text" placeholder="e.g. Should I pay off my mortgage early or invest?"></textarea></label>
        <div class="row"><button class="btn" id="qx-run-typed">Search typed query</button></div>
      </div>
    </div></div>
    <div id="qx-out"><div class="empty">Pick a test query and press Search, or type one.</div></div>`, "#c084fc");
  $("#qx-ds").addEventListener("change", (e) => { qx.ds = e.target.value; loadQueries(); });
  $("#qx-random").addEventListener("click", () => { const s = $("#qx-query"); if (s.options.length) { s.selectedIndex = Math.floor(Math.random() * s.options.length); runExplore(s.value, null); } });
  $("#qx-run").addEventListener("click", () => runExplore($("#qx-query").value, null));
  $("#qx-run-typed").addEventListener("click", () => runExplore(null, $("#qx-text").value));
  await loadQueries();
}
async function loadQueries() {
  try {
    const d = await getJSON(`/api/explore/queries?dataset=${qx.ds}`);
    qx.queries = d.queries;
    $("#qx-query").innerHTML = d.queries.map((q) => `<option value="${esc(q.id)}">${esc(q.id)} · ${esc(q.text.slice(0, 110))}${q.text.length > 110 ? "…" : ""}</option>`).join("");
  } catch (e) { setHTML("#qx-out", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
async function runExplore(queryId, typed) {
  if (!queryId && !(typed || "").trim()) { setHTML("#qx-out", `<div class="empty">Type a query first.</div>`); return; }
  setHTML("#qx-out", `<div class="empty">Running five strategies${typed ? " (the first typed query loads bge-small-en-v1.5)" : ""}; the reranker loads on first use…</div>`);
  try {
    if (!state.runId) await loadRuns();
    const d = await postJSON("/api/explore/run", { dataset: qx.ds, query_id: queryId, text: typed, run_id: state.runId });
    renderExplore(d);
  } catch (e) { setHTML("#qx-out", `<div class="empty">${esc(e.message)}</div>`); }
}
function renderExplore(d) {
  const relevant = new Set(d.judged.map((j) => j.doc_id));
  const cols = STRATEGIES.filter((s) => d.strategies[s]).map((s) => {
    const r = d.strategies[s];
    const m = r.metrics;
    const metricsLine = m ? `<span>nDCG@10 <b>${num(m.ndcg10)}</b></span><span>P@5 <b>${num(m.p5, 2)}</b></span><span>R@10 <b>${num(m.r10, 2)}</b></span>${r.stored_ndcg10 != null ? `<span title="nDCG@10 stored for this query in the run">stored ${num(r.stored_ndcg10)}</span>` : ""}`
      : `<span>no judgements</span>`;
    const timing = `<span>${ms(r.db_ms)} ms${s === "rerank" ? " (first stage + cross-encoder)" : " database"}</span>${r.embed_ms ? `<span>+ ${ms(r.embed_ms)} ms embed</span>` : ""}`;
    const docs = r.top.map((doc, i) => `<details class="qx-doc ${doc.grade ? "rel" : ""}"><summary><span class="rk">${i + 1}</span><span><span class="snip">${doc.grade ? `<span class="gr">rel ${doc.grade}</span>` : ""}${esc(doc.text.slice(0, 220))}</span><span class="id">${esc(doc.doc_id)} · ${num(doc.score, 3)}</span></span></summary><div class="body">${esc(doc.text)}</div></details>`).join("");
    return `<div class="qx-col" style="--c:${S_COLOR[s]}" data-strategy="${s}"><h3>${esc(s)}</h3><div class="qx-cfg">${esc(r.config)}</div><div class="qx-metrics">${metricsLine}</div><div class="qx-metrics">${timing}</div>${docs || '<div class="hint">No documents matched.</div>'}</div>`;
  }).join("");
  const found = d.judged.length ? table([
    { label: "Relevant document", key: "doc_id" }, { label: "Grade", num: true, key: "grade" },
    ...STRATEGIES.filter((s) => d.strategies[s]).map((s) => ({ label: s, num: true, get: (j) => { const i = d.strategies[s].top.findIndex((t) => t.doc_id === j.doc_id); return i < 0 ? "—" : `#${i + 1}`; } })),
  ], d.judged) : "";
  setHTML("#qx-out", `
    <div class="panel mb"><div class="panel-head"><span class="panel-title">${d.typed ? "Your query" : `${esc(d.split)} query ${esc(d.query_id)}`} · ${esc(DS_NAME[d.dataset])}</span>${d.typed ? pill("no judgements", "idle") : pill(`${d.judged.length} relevant`, "ready")}</div>
      <div class="panel-body"><div class="qx-query">${esc(d.text)}</div>
      ${d.typed ? `<div class="note" style="margin-top:12px">A typed query has no relevance judgements, so the lists below carry no relevance marks and no metrics. Pick a stored test query to see them.</div>` : ""}
      ${found ? `<div style="margin-top:12px">${found}</div>` : ""}</div></div>
    <div class="qx-grid" id="qx-grid">${cols}</div>
    ${howto(["Green <b>rel</b> tags mark documents judged relevant, with their grade; click a document to read it.",
             "nDCG@10, P@5 and R@10 are this query's own scores; <b>stored</b> is the value the run recorded for the same query, so you can check the live search reproduces it.",
             "The table above shows where each relevant document landed in each strategy's top 10."])}`);
}

// ── Tuning playground ─────────────────────────────────────────────────
const pg = { ds: "fiqa", chosen: null, grid: {}, timer: null };
const DECAYS = [0, 0.001, 0.0025, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2];

async function viewPlayground() {
  setStage(`
    <header class="eval-head"><div class="eval-kicker">Tuning playground · dev queries</div>
      <h1 class="eval-title">Move a dial, <em>watch the dev score</em></h1>
      <p class="eval-desc">Fusion and graph expansion are recomputed for every dev query from cached candidate lists: each dev query's top 100 from the stored run's best lexical and vector configurations, and the graph neighbours of its top 20 vector hits. The cache is built on first use, in memory only. The yellow tick on each slider is the notebook's chosen setting.</p></header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-body row"><label class="hint" for="pg-ds">Dataset</label>${dsSelect("pg-ds", pg.ds)}<span class="status-line hint" id="pg-status">checking the cache…</span></div>
      <div class="panel-body" style="padding-top:0"><div class="progress" id="pg-progress" hidden><i></i></div></div></div>
    <div class="pg-grid">
      <div class="panel"><div class="panel-head"><span class="panel-title">Hybrid fusion</span><div class="seg" id="pg-method"><button type="button" data-m="weighted" class="active">weighted α</button><button type="button" data-m="rrf">RRF k</button></div></div>
        <div class="panel-body" id="pg-hybrid"><div class="empty">Waiting for the cache…</div></div></div>
      <div class="panel"><div class="panel-head"><span class="panel-title">Graph expansion</span></div>
        <div class="panel-body" id="pg-graph"><div class="empty">Waiting for the cache…</div></div></div>
    </div>
    ${howto(["Each tile is the mean over the dev queries; the arrow is the change against vector search alone (the dashed baseline in the notebook).",
             "When a slider sits on a setting the notebook tried, <b>notebook</b> shows the value it stored for it."])}`, "#34d399");
  $("#pg-ds").addEventListener("change", (e) => { pg.ds = e.target.value; openPlayground(); });
  $$("#pg-method button").forEach((b) => b.addEventListener("click", () => { $$("#pg-method button").forEach((x) => x.classList.remove("active")); b.classList.add("active"); renderHybridControls(); }));
  await openPlayground();
}
async function openPlayground() {
  const ds = pg.ds;
  pg.chosen = null; pg.grid = {};
  setHTML("#pg-hybrid", `<div class="empty">Waiting for the cache…</div>`);
  setHTML("#pg-graph", `<div class="empty">Waiting for the cache…</div>`);
  try {
    if (!state.runId) await loadRuns();
    const s = await getJSON(`/api/playground/${ds}/status?run_id=${encodeURIComponent(state.runId || "")}`);
    if (ds !== pg.ds) return;                       // the dataset changed while this request was in flight
    pg.chosen = s.chosen; pg.grid = s.grid;
    const method = s.chosen.hybrid.method === "RRF" ? "rrf" : "weighted";
    $$("#pg-method button").forEach((b) => b.classList.toggle("active", b.dataset.m === method));
    if (s.state === "ready") { setHTML("#pg-status", `cached ${s.queries} dev queries in ${s.seconds} s (lexical: ${esc(s.chosen.lexical)} · vector: ${esc(s.chosen.vector)})`); renderPlayground(); return; }
    await postJSON(`/api/playground/${ds}/prepare?run_id=${encodeURIComponent(state.runId || "")}`);
    if (ds === pg.ds) followCache(ds);
  } catch (e) { setHTML("#pg-status", `<span style="color:var(--bad)">${esc(e.message)}</span>`); }
}
function followCache(ds, onDone) {
  if (streams[ds]) streams[ds].close();
  const bar = $("#pg-progress");
  if (bar) bar.hidden = false;
  const source = new EventSource(`/api/playground/${ds}/stream?since=0`);
  streams[ds] = source;
  source.onmessage = (m) => {
    let e; try { e = JSON.parse(m.data); } catch (_) { return; }
    const status = $("#pg-status") || $("#gd-status");
    if (e.type === "start" && status) status.textContent = `building the cache for ${e.queries} dev queries…`;
    if (e.type === "progress") {
      if (status) status.textContent = `${e.stage}: ${e.done}/${e.total} · ${e.seconds} s`;
      if (bar) $("i", bar).style.width = `${Math.round((100 * e.done) / Math.max(1, e.total))}%`;
    }
    if (e.type === "error" && status) status.innerHTML = `<span style="color:var(--bad)">${esc(e.message)}</span>`;
    if (e.type === "done") {
      source.close(); delete streams[ds];
      if (bar) bar.hidden = true;
      if (status) status.textContent = `cached ${e.queries} dev queries and ${e.edges.toLocaleString()} graph edges in ${e.seconds} s`;
      if (onDone) onDone(); else if (ds === pg.ds && $("#pg-hybrid")) renderPlayground();
    }
  };
  source.addEventListener("end", () => { source.close(); delete streams[ds]; });
  source.onerror = () => { source.close(); delete streams[ds]; };
}
function slider(id, label, min, max, step, value, chosen, fmt = (v) => v) {
  const pos = (v) => `${(100 * (v - min)) / (max - min)}%`;
  return `<div class="slider"><div class="sl-head"><span>${esc(label)}</span><b id="${id}-v">${fmt(value)}</b></div>
    <div class="track"><input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${value}" aria-label="${esc(label)}" />${chosen == null ? "" : `<span class="mark" style="left:${pos(chosen)}" title="notebook's choice"></span>`}</div>
    ${chosen == null ? "" : `<div class="mark-label">notebook's choice: ${fmt(chosen)}</div>`}</div>`;
}
function renderPlayground() { renderHybridControls(); renderGraphControls(); }
function renderHybridControls() {
  if (!pg.chosen) return;
  const c = pg.chosen.hybrid;
  const method = $("#pg-method button.active").dataset.m;
  const html = method === "weighted"
    ? slider("pg-alpha", "α, the weight on the vector list", 0, 1, 0.05, c.method === "weighted" ? c.alpha : 0.8, c.method === "weighted" ? c.alpha : null, (v) => Number(v).toFixed(2))
    : slider("pg-k", "RRF k", 1, 100, 1, c.method === "RRF" ? c.k : 60, c.method === "RRF" ? c.k : null) +
      slider("pg-w", "w, the RRF weight on the vector list", 0, 1, 0.05, c.method === "RRF" ? c.w : 0.5, c.method === "RRF" ? c.w : null, (v) => Number(v).toFixed(2));
  setHTML("#pg-hybrid", `${html}${slider("pg-depth", "depth of each list", 10, 100, 10, c.depth, c.depth)}<div class="tiles" id="pg-hybrid-tiles"></div><div class="hint" id="pg-hybrid-note"></div>`);
  $$("#pg-hybrid input").forEach((i) => i.addEventListener("input", () => { $(`#${i.id}-v`).textContent = i.id === "pg-k" || i.id === "pg-depth" ? i.value : Number(i.value).toFixed(2); scheduleScore("hybrid"); }));
  scoreNow("hybrid");
}
function renderGraphControls() {
  if (!pg.chosen) return;
  const c = pg.chosen.graph;
  const di = Math.max(0, DECAYS.indexOf(c.decay));
  setHTML("#pg-graph", `${slider("pg-m", "M, neighbours per node", 1, 20, 1, c.m, c.m)}${slider("pg-seeds", "seeds", 1, 20, 1, c.seeds, c.seeds)}
    ${slider("pg-decay", "decay", 0, DECAYS.length - 1, 1, di, di, (v) => DECAYS[v])}<div class="tiles" id="pg-graph-tiles"></div><div class="hint" id="pg-graph-note"></div>`);
  $$("#pg-graph input").forEach((i) => i.addEventListener("input", () => { $(`#${i.id}-v`).textContent = i.id === "pg-decay" ? DECAYS[i.value] : i.value; scheduleScore("graph"); }));
  scoreNow("graph");
}
function scheduleScore(which) { clearTimeout(pg.timer); pg.timer = setTimeout(() => scoreNow(which), 140); }
function deltaTile(label, v, base) {
  const d = base == null || v == null ? null : v - base;
  return tile(label, num(v), d == null ? "" : `<span class="delta ${d >= 0 ? "up" : "down"}">${d >= 0 ? "▲" : "▼"} ${signed(d)} vs vector</span>`);
}
async function scoreNow(which) {
  let body, label;
  if (which === "hybrid") {
    const method = $("#pg-method button.active").dataset.m;
    const depth = Number($("#pg-depth").value);
    const tenth = (v) => (Math.abs(v * 10 - Math.round(v * 10)) < 1e-9 ? v.toFixed(1) : String(v));
    if (method === "weighted") { const a = Number($("#pg-alpha").value); body = { kind: "weighted", alpha: a, depth }; label = `hybrid|weighted · alpha=${tenth(a)} · depth=${depth}`; }
    else { const k = Number($("#pg-k").value), w = Number($("#pg-w").value); body = { kind: "rrf", k, w, depth }; label = `hybrid|RRF · k=${k} · w=${tenth(w)} · depth=${depth}`; }
  } else {
    const m = Number($("#pg-m").value), seeds = Number($("#pg-seeds").value), decay = DECAYS[Number($("#pg-decay").value)];
    body = { kind: "graph", m, seeds, decay }; label = `graph|M=${m} · seeds=${seeds} · decay=${decay}`;
  }
  const ds = pg.ds;
  try {
    const r = await postJSON("/api/playground/score", { dataset: ds, ...body });
    if (ds !== pg.ds) return;
    const base = r.baselines.vector;
    setHTML(`#pg-${which}-tiles`, deltaTile("nDCG@10", r.ndcg10, base.ndcg10) + deltaTile("MRR@10", r.mrr10, base.mrr10) + deltaTile("R@100", r.r100, base.r100));
    const stored = pg.grid[label];
    setHTML(`#pg-${which}-note`, `${r.queries} dev queries · ${r.ms} ms · vector alone ${num(base.ndcg10)}, lexical alone ${num(r.baselines.lexical.ndcg10)} nDCG@10${stored ? ` · <b>notebook</b> stored ${num(stored.ndcg10)} for this setting` : ""}`);
  } catch (e) { setHTML(`#pg-${which}-note`, `<span style="color:var(--bad)">${esc(e.message)}</span>`); }
}

// ── Decision guide ────────────────────────────────────────────────────
async function viewGuide() {
  setStage(`
    <header class="eval-head"><div class="eval-kicker">Decision guide</div>
      <h1 class="eval-title">Which strategy for <em>which data?</em></h1>
      <p class="eval-desc">Diagnostics computed from the stored corpora predict the direction; the stored run's results decide. The flowchart is the notebook's; under each step is the evidence behind it from the run you selected.</p></header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Dataset diagnostics</span><span class="hint" id="gd-status">computed from the stored corpora on first visit</span></div>
      <div class="panel-body" id="gd-diag"><div class="empty">Computing the diagnostics…</div></div></div>
    <div class="guide-grid">
      <div class="panel"><div class="panel-head"><span class="panel-title">The flowchart</span></div><div class="panel-body"><img src="/img/decision_guide.png" alt="Decision guide: vector search first, then weighted hybrid if keywords carry signal, graph only if relevant documents link, reranker only if it wins on dev, HNSW when exact search is too slow" /></div></div>
      <div class="panel"><div class="panel-head"><span class="panel-title">Each step, with its evidence</span></div><div class="panel-body" id="gd-steps"><div class="empty">Reading the stored run…</div></div></div>
    </div>`, "#facc15");
  loadGuideEvidence();
  loadDiagnostics();
}
async function loadDiagnostics() {
  const rows = [], errors = [];
  for (const ds of Object.keys(DS_NAME)) {
    try { rows.push(await getJSON(`/api/guide/diagnostics/${ds}`)); }
    catch (e) { errors.push(`${DS_NAME[ds]}: ${e.message}`); }
    renderDiagnostics(rows, errors);
  }
}
function renderDiagnostics(rows, errors = []) {
  const reachCell = (r) => r.reach ? `${num(r.reach.share_reachable, 2)} · hop ${num(r.reach.hop_precision, 4)} vs list ${num(r.reach.tail_precision, 4)}` : `<button class="btn btn-ghost" data-reach="${r.dataset}">measure</button>`;
  setHTML("#gd-diag", table([
    { label: "Dataset", key: "name" },
    { label: "Query words (median)", num: true, key: "query_words_median" },
    { label: "Document words (median)", num: true, key: "document_words_median" },
    { label: "Relevant per query", num: true, key: "relevant_per_query" },
    { label: "Word overlap", num: true, get: (r) => num(r.lexical_overlap) },
    { label: "Vocabulary mismatch", num: true, get: (r) => num(r.vocabulary_mismatch) },
    { label: "Cohesion: relevant vs random", num: true, get: (r) => r.cohesion_relevant == null ? `n/a vs ${num(r.cohesion_random)}` : `${num(r.cohesion_relevant)} vs ${num(r.cohesion_random)}` },
    { label: "One-hop reach (share · precision)", html: true, get: reachCell },
  ], rows) + (errors.length ? `<div class="note" style="margin-top:10px">${errors.map(esc).join("<br/>")}</div>` : "") + howto([
    "<b>Word overlap</b>: share of a query's content words found in its relevant document. <b>Vocabulary mismatch</b>: share of query–relevant pairs sharing at most one content word. High mismatch means keywords have little to match on.",
    "<b>Cohesion</b>: mean cosine similarity of two relevant documents of one query, against two random documents. A cluster is what a graph can follow.",
    "<b>One-hop reach</b>: share of the relevant documents vector search's top 10 missed that one hop from its top 10 reaches, and the hop's precision against simply reading ranks 11–100. It needs the playground's dev cache; <b>measure</b> builds it.",
  ]));
  $$("#gd-diag [data-reach]").forEach((b) => b.addEventListener("click", async () => {
    const ds = b.dataset.reach;
    b.disabled = true; b.textContent = "building…";
    await postJSON(`/api/playground/${ds}/prepare?run_id=${encodeURIComponent(state.runId || "")}`);
    followCache(ds, loadDiagnostics);
  }));
}
async function loadGuideEvidence() {
  try {
    if (!state.runId) await loadRuns();
    const d = await getJSON(`/api/guide/evidence?run_id=${encodeURIComponent(state.runId || "")}`);
    const per = (f) => Object.values(d.datasets).map((r) => `${esc(r.name)}: ${f(r)}`).join("<br/>");
    const sig = (v) => v ? `${signed(v.diff)} (Holm p ${num(v.p_holm, 4)}${v.significant ? ", significant" : ", not significant"})` : "—";
    const steps = [
      { t: "1 · Start with vector search", p: "A retrieval-trained embedding model is the baseline to beat, and the model is the biggest lever.",
        e: per((r) => `vector ${num(r.ndcg10.vector)} vs lexical ${num(r.ndcg10.lexical)} on test · dev by model: ${Object.entries(r.model_dev).map(([m, v]) => `${esc(m)} ${num(v)}`).join(", ")}`) },
      { t: "2 · Weighted hybrid when keywords carry their own signal", p: "Weight the lists towards the stronger one and tune on dev; equal-weight RRF gives a weak list an equal vote.",
        e: per((r) => `hybrid vs vector ${sig(r.hybrid_vs_vector)} · dev: plain RRF (k=60, w=0.5) ${num(r.plain_rrf_dev)} vs vector ${num(r.vector_dev)}`) },
      { t: "3 · Graph expansion only when relevant documents point to each other", p: "Measure the one-hop reach first; a kNN graph from the same vectors mostly re-encodes them.",
        e: per((r) => `graph vs vector ${sig(r.graph_vs_vector)}`) },
      { t: "4 · A reranker only if it beats the first stage on dev", p: "A cross-encoder trained for web search can lower the ranking of a strong first stage, at a high cost per query.",
        e: per((r) => `rerank vs vector ${sig(r.rerank_vs_vector)} · p50 ${ms(r.rerank_p50_ms)} ms vs ${ms(r.vector_p50_ms)} ms`) },
      { t: "5 · HNSW when the exact scan is too slow", p: "Tune TARGET ACCURACY by measuring recall against exact search on your own queries.",
        e: per((r) => r.hnsw ? `HNSW target 90: ${num(r.hnsw.ndcg10)} at ${ms(r.hnsw.p50_ms)} ms vs exact ${num(r.ndcg10.vector)} at ${ms(r.vector_p50_ms)} ms (database time)` : "no HNSW side run stored") },
    ];
    setHTML("#gd-steps", steps.map((s) => `<div class="step"><h4>${esc(s.t)}</h4><p>${esc(s.p)}</p><div class="ev">${s.e}</div></div>`).join("") +
      `<div class="hint">Run ${esc(d.run_id)} · test nDCG@10 and Holm-corrected paired tests from the leaderboard.</div>`);
  } catch (e) { setHTML("#gd-steps", `<div class="empty">${esc(e.message)}</div>`); }
}
