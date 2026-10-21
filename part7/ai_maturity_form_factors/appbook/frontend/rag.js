/* ======================================================================
   Form Factor 2 — RAG over Acme's lending policy (Oracle AI Database).
   Left: question, technique, policy memory. Centre: cited answer and
   sources. Right: how the chosen technique walks the index for this very
   query. Below: the latent-space viewer with pre / in / post filtering.
   ====================================================================== */

const RAG_SAMPLES = [
  "What share of my salary can my monthly bills take up?",
  "What is Acme Home Loans' maximum debt-to-income ratio, and how many months of cash reserves must I keep after closing on an investment property?",
  "Do I need mortgage insurance with a small down payment?",
  "the home I want is a condo, is it eligible and what LTV applies?",
  "PMI",
  "down payment",
];
const RAG_TECH = {
  vector: { name: "Vector", desc: "Embeds the question and ranks every section by cosine similarity — it matches meaning, so a paraphrase with none of the policy's words still lands on the right section." },
  keyword: { name: "Keyword", desc: "Oracle Text looks each meaningful term up in an inverted index and ranks by SCORE. Exact and explainable, but blind to synonyms." },
  hybrid: { name: "Hybrid · RRF", desc: "Runs vector and keyword search separately, then fuses the two rankings with Reciprocal Rank Fusion: Σ 1 / (60 + rank). A section strong in either list rises." },
  graph: { name: "Graph", desc: "Seeds with vector search, then walks SIMILAR_TO and same-category edges in the POLICY_GRAPH property graph. Each hop decays by edge strength, so an expansion never outranks its seed." },
};
const RAG_ORDER = ["vector", "keyword", "hybrid", "graph"];
const CAT_COLORS = {
  affordability: "#22d3ee", collateral: "#34d399", credit: "#fb923c", eligibility: "#a3e635",
  documentation: "#60a5fa", compliance: "#f472b6", process: "#c084fc", products: "#facc15",
};
const catColor = (c) => CAT_COLORS[c] || "#94a3b8";
const ragState = { technique: "vector", k: 4, rerank: false, query: "", lastQuery: "", space: null, spaceMode: "2d", rot: { a: -0.6, b: 0.35 } };

function viewRAG() {
  const f = FF_BY_ID.rag;
  setStage(`${ffHeader(f)}${needsDB()}
    <div class="rag3">
      <section class="rag-col rag-left">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">${I.send} Ask the policy</span><span class="hint mono" id="rag-status"></span></div>
          <div class="panel-body">
            <div class="seg seg-full" id="rag-tech">${RAG_ORDER.map((t) => `<button class="${t === ragState.technique ? "active" : ""}" data-t="${t}">${esc(RAG_TECH[t].name)}</button>`).join("")}</div>
            <div class="tech-desc" id="rag-desc">${esc(RAG_TECH[ragState.technique].desc)}</div>
            <textarea id="rag-input" rows="3" placeholder="Ask about Acme Home Loans' lending policy…">${esc(ragState.query)}</textarea>
            <div class="row spread" style="margin-top:10px">
              <label class="slider-lab">top-k <input type="range" id="rag-k" min="1" max="8" value="${ragState.k}"><b id="rag-k-v">${ragState.k}</b></label>
              <label class="toggle-lab rr-toggle" title="Stage 2: an open cross-encoder (bge-reranker-v2-m3) re-orders 8 candidates"><input type="checkbox" id="rag-rerank" ${ragState.rerank ? "checked" : ""}> rerank</label>
              <button class="btn btn-accent" id="rag-ask">${I.send} Ask</button>
            </div>
            <div class="chips" style="margin-top:12px">${RAG_SAMPLES.map((s, i) => `<button type="button" class="chip seed-chip" data-rag-sample="${i}" title="${esc(s)}">${esc(s.length > 38 ? s.slice(0, 36) + "…" : s)}</button>`).join("")}</div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><span class="panel-title">${I.memory} Policy memory · versions ${memBadge("semantic", true)}</span><button class="btn btn-ghost" id="pol-refresh">${I.refresh}</button></div>
          <div class="panel-body"><div id="policy-box"><div class="empty">Reading POLICY_DOCS…</div></div></div>
        </div>
      </section>
      <section class="rag-col rag-center">
        <div class="panel">
          <div class="panel-head"><span class="panel-title">${I.bot} Grounded answer</span><span class="hint mono">Claude Haiku 5.5 · only from the context</span></div>
          <div class="panel-body"><div id="rag-answer" class="answer"><div class="empty">Ask a question. The answer cites the policy sections it used, like [1].</div></div></div>
        </div>
        <div class="panel">
          <div class="panel-head"><span class="panel-title">${I.rag} Retrieved context ${memBadge("semantic", true)}</span><span class="hint mono" id="rag-src-note"></span></div>
          <div class="panel-body"><div id="rag-sources" class="sources"><div class="empty">The top-k sections, with their versions, appear here.</div></div></div>
        </div>
      </section>
      <aside class="rag-col rag-right">
        <div class="panel viz-panel">
          <div class="panel-head"><span class="panel-title">${I.flow} How <b id="viz-tech">${esc(RAG_TECH[ragState.technique].name)}</b> retrieval works</span><button class="btn btn-ghost" id="viz-replay" title="Replay">${I.refresh}</button></div>
          <div class="panel-body"><div id="viz"><div class="empty">Ask a question to watch the query travel through the index.</div></div><div id="viz-rerank"></div>
            <details class="sql-box"><summary>Oracle SQL for this run</summary><pre class="rag-sql" id="rag-sql">—</pre></details>
          </div>
        </div>
      </aside>
    </div>

    <section class="panel space-panel" id="space-panel">
      <div class="panel-head"><span class="panel-title">${I.space} Latent space viewer · 768 dimensions, projected ${memBadge("semantic", true)}</span><span class="hint mono" id="space-var"></span></div>
      <div class="panel-body">
        <div class="space-controls">
          <div class="field" style="flex:1"><input type="text" id="space-q" placeholder="A query to place in the embedding space…" value="${esc(ragState.query)}"></div>
          <label class="slider-lab">k <input type="range" id="space-k" min="1" max="10" value="4"><b id="space-k-v">4</b></label>
          <label class="sel-lab">filter <select id="space-cat"><option value="">no filter</option>${Object.keys(CAT_COLORS).map((c) => `<option value="${c}">category = ${c}</option>`).join("")}</select></label>
          <div class="seg" id="space-mode"><button data-m="pre" class="active">Pre</button><button data-m="in">In</button><button data-m="post">Post</button></div>
          <label class="slider-lab">accuracy <input type="range" id="space-acc" min="50" max="100" step="5" value="90"><b id="space-acc-v">90</b></label>
          <div class="seg" id="space-dim"><button data-d="2d" class="active">2D</button><button data-d="3d">3D</button></div>
          <button class="btn btn-accent" id="space-run">${I.play} Map it</button>
        </div>
        <div class="space-grid">
          <div class="space-canvas-wrap"><canvas id="space-canvas"></canvas><div class="space-tip" id="space-tip" hidden></div>
            <div class="space-legend">${Object.entries(CAT_COLORS).map(([c, col]) => `<span><i style="background:${col}"></i>${c}</span>`).join("")}<span><i class="q"></i>your query</span><span><i class="ring"></i>retrieved</span><span><i class="x">×</i>dropped by post-filter</span></div>
          </div>
          <div class="space-side">
            <div id="space-compare"><div class="hint">Pick a category filter to compare when Oracle applies it: before the vector search (pre), during the HNSW walk (in), or after ranking (post).</div></div>
            <div id="space-table"></div>
            <details class="sql-box"><summary>SQL for this filter strategy</summary><pre class="rag-sql" id="space-sql">—</pre></details>
          </div>
        </div>
      </div>
    </section>

    <section class="panel hnsw-panel" id="hnsw-panel"></section>`, f.accent);

  const input = $("#rag-input");
  autosize(input, 220);
  $("#rag-tech").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $$("#rag-tech button").forEach((x) => x.classList.toggle("active", x === b));
    ragState.technique = b.dataset.t;
    setText("#rag-desc", RAG_TECH[ragState.technique].desc);
    setText("#viz-tech", RAG_TECH[ragState.technique].name);
    if (!ragState.lastQuery) return;
    // Same question, new technique: answer, sources and viz together. Mid-stream, draw the viz now and re-answer after.
    if (state.abort) { ragState.rerun = true; explainTechnique(ragState.lastQuery); } else runRAG();
  });
  $("#rag-k").addEventListener("input", (e) => { ragState.k = +e.target.value; setText("#rag-k-v", ragState.k); });
  $("#rag-rerank").addEventListener("change", (e) => { ragState.rerank = e.target.checked; if (!ragState.lastQuery) return; if (state.abort) ragState.rerun = true; else runRAG(); });
  $$("[data-rag-sample]").forEach((b) => b.addEventListener("click", () => { input.value = RAG_SAMPLES[+b.dataset.ragSample]; autosize(input, 220); input.focus(); }));
  $("#rag-ask").addEventListener("click", runRAG);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runRAG(); } });
  input.addEventListener("input", () => autosize(input, 220));
  $("#viz-replay").addEventListener("click", () => { const v = $("#viz"); if (v) { v.classList.remove("play"); void v.offsetWidth; v.classList.add("play"); } });
  $("#pol-refresh").addEventListener("click", loadPolicy);
  loadPolicy();
  wireSpace();
  wireHNSW();
}

async function runRAG() {
  const q = $("#rag-input").value.trim();
  if (!q || state.abort) return;
  ragState.query = ragState.lastQuery = q;
  const ans = $("#rag-answer"), src = $("#rag-sources"), ask = $("#rag-ask");
  ans.innerHTML = '<span class="caret"></span>';
  src.innerHTML = `<div class="empty"><span class="spinner"></span> retrieving…</div>`;
  ask.disabled = true;
  setHTML("#viz-rerank", "");
  explainTechnique(q);
  const spaceQ = $("#space-q"); if (spaceQ && !spaceQ.value.trim()) { spaceQ.value = q; }
  let acc = "";
  state.abort = new AbortController();
  try {
    let moves = null;
    await streamSSE("/api/rag/answer", { query: q, technique: ragState.technique, k: ragState.k, rerank: ragState.rerank }, (ev) => {
      if (ev.type === "status") { setText("#rag-src-note", ev.text); }
      else if (ev.type === "rerank") { moves = Object.fromEntries(ev.rows.map((r) => [r.doc_id, r])); setHTML("#viz-rerank", vizRerank(ev, ragState.k)); }
      else if (ev.type === "sources") {
        setText("#rag-src-note", `${ev.technique} · top-${ev.hits.length}`);
        src.innerHTML = ev.hits.length ? ev.hits.map((h, i) => sourceCard(h, i, moves)).join("") : `<div class="empty">No section matched with this technique.</div>`;
      } else if (ev.type === "delta") { acc += ev.text; ans.innerHTML = renderRich(acc) + '<span class="caret"></span>'; }
      else if (ev.type === "done") { ans.innerHTML = renderRich(acc) || `<div class="empty">No answer.</div>`; }
    }, state.abort.signal);
  } catch (e) { ans.innerHTML = `<div class="banner warn">${I.alert}<div>${esc(e.message)}</div></div>`; }
  finally {
    state.abort = null; ask.disabled = false;
    if (ragState.rerun && $("#rag-answer")) { ragState.rerun = false; runRAG(); }
  }
}

function sourceCard(h, i, moves) {
  const mv = moves && moves[h.doc_id], shift = mv ? mv.before - mv.after : 0;
  return `<div class="source" style="animation-delay:${i * 50}ms;--cc:${catColor(h.category)}">
    <div class="source-top"><span class="source-idx">${i + 1}</span><span class="source-title">${esc(h.title)}</span><span class="vbadge ${h.version > 1 ? "new" : ""}">v${h.version}</span><span class="source-cat">${esc(h.category)}</span><span class="source-score">${(+h.score).toFixed(3)}</span>${mv ? `<span class="rr-move ${shift > 0 ? "up" : shift < 0 ? "down" : ""}" title="first-stage rank ${mv.before} → reranked ${mv.after} · score ${mv.score}">${shift > 0 ? `↑ ${shift}` : shift < 0 ? `↓ ${-shift}` : "·"} from #${mv.before}</span>` : ""}</div>
    <div class="source-body">${esc(h.content)}</div></div>`;
}

// ── the side-pane visualizations ─────────────────────────────────────────
async function explainTechnique(q) {
  const viz = $("#viz"); if (!viz) return;
  viz.innerHTML = `<div class="empty"><span class="spinner"></span> tracing ${esc(ragState.technique)} retrieval…</div>`;
  try {
    const t = ragState.technique;
    const data = await postJSON("/api/rag/explain", { query: q, technique: t, k: ragState.k });
    if (t === "vector") data.space = await postJSON("/api/rag/space", { query: q, k: ragState.k });
    if (!$("#viz")) return;
    setText("#rag-sql", data.sql || "—");
    viz.innerHTML = { keyword: vizKeyword, vector: vizVector, hybrid: vizHybrid, graph: vizGraph }[t](data, q);
    if (t === "vector") mountNearest3D(data.space, data.k);
    viz.classList.remove("play"); void viz.offsetWidth; viz.classList.add("play");
  } catch (e) { viz.innerHTML = `<div class="banner warn">${I.alert}<div>${esc(e.message)}</div></div>`; }
}

function vstep(n, title, body) {
  return `<div class="vstep" style="--d:${n}"><div class="vstep-n">${n}</div><div class="vstep-body"><div class="vstep-title">${title}</div>${body}</div></div>`;
}

function vizKeyword(d, q) {
  const tokens = (q.toLowerCase().match(/[a-z0-9]+/g) || []);
  const kept = new Set(d.terms);
  const termColors = ["#22d3ee", "#f472b6", "#a3e635", "#fb923c", "#c084fc", "#facc15", "#60a5fa", "#34d399"];
  const tcol = Object.fromEntries(d.terms.map((t, i) => [t, termColors[i % termColors.length]]));
  // Bipartite inverted-index graph: terms on the left, every section on the right.
  const docs = d.documents;
  const W = 420, rowH = 19, H = Math.max(docs.length * rowH + 20, d.terms.length * 40 + 20);
  const top = new Set(d.results.map((r) => r.doc_id));
  const yDoc = (i) => 14 + i * rowH;
  const yTerm = (i) => H / 2 - (d.terms.length - 1) * 20 + i * 40;
  const docIndex = Object.fromEntries(docs.map((doc, i) => [doc.doc_id, i]));
  const maxScore = Math.max(1, ...d.postings.flatMap((p) => p.docs.map((x) => x.score)));
  const edges = d.postings.flatMap((p, ti) => p.docs.map((x) => {
    const y1 = yTerm(ti), y2 = yDoc(docIndex[x.doc_id]);
    return `<path class="kw-edge" d="M120 ${y1} C 210 ${y1}, 230 ${y2}, 268 ${y2}" stroke="${tcol[p.term]}" stroke-width="${1 + (x.score / maxScore) * 4}"><title>${esc(p.term)} → ${esc(x.doc_id)} · SCORE ${x.score}</title></path>`;
  })).join("");
  const termNodes = d.terms.map((t, i) => `<g class="kw-term"><rect x="8" y="${yTerm(i) - 12}" width="112" height="24" rx="12" fill="${tcol[t]}22" stroke="${tcol[t]}"/><text x="64" y="${yTerm(i) + 4}" text-anchor="middle" fill="${tcol[t]}">${esc(t)}</text></g>`).join("");
  const docNodes = docs.map((doc, i) => `<g class="kw-doc ${top.has(doc.doc_id) ? "hit" : ""}"><circle cx="272" cy="${yDoc(i)}" r="4.5" fill="${catColor(doc.category)}"/><text x="282" y="${yDoc(i) + 4}">${esc(doc.doc_id)}</text></g>`).join("");
  const postings = d.postings.map((p) => `<div class="posting"><span class="pterm" style="--tc:${tcol[p.term]}">${esc(p.term)}</span><span class="parrow">→</span>${p.docs.length ? p.docs.map((x) => `<span class="pdoc">${esc(x.doc_id)} <b>${x.score}</b></span>`).join("") : '<span class="hint">no section contains this term</span>'}</div>`).join("");
  const maxR = Math.max(1, ...d.results.map((r) => r.score));
  const ranked = d.results.length ? d.results.map((r, i) => `<div class="rbar"><span class="rk">${i + 1}</span><span class="rn">${esc(r.doc_id)}</span><span class="rb"><i style="width:${(r.score / maxR) * 100}%;background:${catColor(r.category)}"></i></span><span class="rv">${r.score}</span></div>`).join("") : '<div class="hint">No section contains any term: keyword search returns nothing, even though the meaning may be in the policy. That is the gap vector search fills.</div>';
  return vstep(1, "Tokenize the question", `<div class="tokens">${tokens.map((t) => `<span class="tok ${kept.has(t) ? "kept" : "stop"}" style="${kept.has(t) ? `--tc:${tcol[t]}` : ""}">${esc(t)}</span>`).join("")}</div><div class="hint">Stopwords and very short words are dropped; the rest become the Oracle Text query <span class="mono">${esc(d.text_query)}</span>.</div>`)
    + vstep(2, "Look each term up in the inverted index", `<svg class="kw-svg" viewBox="0 0 ${W} ${H}" style="height:${Math.min(H, 360)}px">${edges}${termNodes}${docNodes}</svg>${postings}<div class="hint">The index stores, for every word, the rows that contain it. No row is scanned; each line is a posting with its relevance SCORE.</div>`)
    + vstep(3, "ACCUM adds the scores, highest first", ranked);
}

function scatter2D(space, k, opts = {}) {
  const W = opts.w || 420, H = opts.h || 300, pad = 26;
  const X = (x) => pad + ((x + 1) / 2) * (W - 2 * pad), Y = (y) => H - pad - ((y + 1) / 2) * (H - 2 * pad);
  const retrieved = new Set(space.retrieved);
  const qx = X(space.query.x), qy = Y(space.query.y);
  const lines = space.points.filter((p) => retrieved.has(p.doc_id)).map((p) => {
    const px = X(p.x), py = Y(p.y);
    return `<line class="sp-line" x1="${qx}" y1="${qy}" x2="${px}" y2="${py}"/><text class="sp-dist" x="${(qx + px) / 2}" y="${(qy + py) / 2 - 3}">${p.similarity.toFixed(2)}</text>`;
  }).join("");
  const dots = space.points.map((p) => `<g class="sp-pt ${retrieved.has(p.doc_id) ? "hit" : ""}"><circle cx="${X(p.x)}" cy="${Y(p.y)}" r="${retrieved.has(p.doc_id) ? 6 : 4.5}" fill="${catColor(p.category)}"><title>${esc(p.title)} · cos ${p.similarity} · rank ${p.rank}</title></circle>${retrieved.has(p.doc_id) ? `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="10" class="sp-ring"/><text x="${X(p.x) + 11}" y="${Y(p.y) + 4}" class="sp-lab">${esc(p.doc_id)}</text>` : ""}</g>`).join("");
  return `<svg class="sp-svg" viewBox="0 0 ${W} ${H}"><rect x="0" y="0" width="${W}" height="${H}" class="sp-bg"/>${lines}${dots}<g class="sp-q"><path d="M${qx} ${qy - 9} L${qx + 3} ${qy - 3} L${qx + 9} ${qy - 2} L${qx + 4} ${qy + 2} L${qx + 6} ${qy + 9} L${qx} ${qy + 5} L${qx - 6} ${qy + 9} L${qx - 4} ${qy + 2} L${qx - 9} ${qy - 2} L${qx - 3} ${qy - 3} Z"/></g></svg>`;
}

function vizVector(d) {
  const rows = d.ranked.map((r) => `<div class="rbar ${r.in_top_k ? "in" : "out"}"><span class="rk">${r.rank}</span><span class="rn">${esc(r.doc_id)}</span><span class="rb"><i style="width:${Math.max(2, r.similarity * 100)}%;background:${catColor(r.category)}"></i></span><span class="rv">${r.similarity.toFixed(3)}</span></div>${r.rank === d.k ? `<div class="kcut">top-k cut · k = ${d.k}</div>` : ""}`).join("");
  return vstep(1, "Embed the question", `<div class="hint">FastEmbed turns the question into 768 numbers with the same model used for the policy, so both live in one space.</div>`)
    + vstep(2, "Find the nearest sections", `<div class="n3d-wrap"><canvas id="n3d-canvas"></canvas><div class="space-tip" id="n3d-tip" hidden></div>
        <div class="n3d-ctl"><button class="btn btn-ghost mini" id="n3d-spin" title="Spin">${I.refresh} spin</button><button class="btn btn-ghost mini" id="n3d-reset" title="Reset the view">reset</button></div></div>
      <div class="hint">All 17 sections in 3-D (PCA of the 768-d embeddings; colour = category). <b>Drag to rotate</b>, hover a point for its similarity. Lines join the question ★ to the top-k; their labels are the true cosine similarity in 768-D. The HNSW index finds these neighbours without scanning every row.</div>`)
    + vstep(3, "Rank every section by cosine similarity", `<div class="rbars">${rows}</div>`);
}

function vizHybrid(d) {
  const W = 420, rowH = 22, n = Math.max(d.vector_list.length, d.keyword_list.length, d.fused.length);
  const H = n * rowH + 34;
  const y = (i) => 30 + i * rowH;
  const fusedIndex = Object.fromEntries(d.fused.map((f, i) => [f.doc_id, i]));
  const left = d.vector_list.map((id, i) => `<text x="8" y="${y(i) + 4}" class="hy-t">${i + 1}. ${esc(id)}</text>`).join("");
  const right = d.keyword_list.map((id, i) => `<text x="${W - 8}" y="${y(i) + 4}" text-anchor="end" class="hy-t kw">${esc(id)} .${i + 1}</text>`).join("");
  const mid = d.fused.map((f, i) => `<g class="hy-f ${f.in_top_k ? "top" : ""}"><rect x="${W / 2 - 62}" y="${y(i) - 9}" width="124" height="18" rx="9"/><text x="${W / 2}" y="${y(i) + 4}" text-anchor="middle">${esc(f.doc_id)}</text></g>`).join("");
  const links = d.vector_list.map((id, i) => `<path class="hy-l v" d="M110 ${y(i)} C 140 ${y(i)}, 130 ${y(fusedIndex[id])}, ${W / 2 - 62} ${y(fusedIndex[id])}"/>`).join("")
    + d.keyword_list.map((id, i) => `<path class="hy-l k" d="M${W - 110} ${y(i)} C ${W - 140} ${y(i)}, ${W - 130} ${y(fusedIndex[id])}, ${W / 2 + 62} ${y(fusedIndex[id])}"/>`).join("");
  const max = Math.max(...d.fused.map((f) => f.rrf_score));
  const bars = d.fused.map((f, i) => `<div class="rbar ${f.in_top_k ? "in" : "out"}"><span class="rk">${i + 1}</span><span class="rn">${esc(f.doc_id)}</span><span class="rb dual"><i class="v" style="width:${(f.from_vector / max) * 100}%"></i><i class="k" style="width:${(f.from_keyword / max) * 100}%"></i></span><span class="rv">${f.rrf_score.toFixed(4)}</span></div>`).join("");
  return vstep(1, "Two independent searches", `<div class="hint">Vector ranking on the left, keyword ranking (terms: ${d.terms.map((t) => `<span class="mono">${esc(t)}</span>`).join(", ") || "none"}) on the right. Each list only knows ranks, not comparable scores.</div>`)
    + vstep(2, "Fuse by rank", `<svg class="hy-svg" viewBox="0 0 ${W} ${H}"><text x="8" y="14" class="hy-h">vector rank</text><text x="${W / 2}" y="14" text-anchor="middle" class="hy-h">fused</text><text x="${W - 8}" y="14" text-anchor="end" class="hy-h">keyword rank</text>${links}${left}${right}${mid}</svg>`)
    + vstep(3, `RRF score = 1/(${d.rrf_k} + rank<sub>vector</sub>) + 1/(${d.rrf_k} + rank<sub>keyword</sub>)`, `<div class="rbars">${bars}</div><div class="legend-inline"><span><i class="v"></i>from the vector list</span><span><i class="k"></i>from the keyword list</span></div>`);
}

function vizGraph(d) {
  // Every section sits on one ring, grouped by category; edges are chords between them.
  const W = 500, H = 400, cx = W / 2, cy = H / 2, R = 128;
  const all = {};
  (window.__policyDocs || []).forEach((doc) => { all[doc.doc_id] = { doc_id: doc.doc_id, category: doc.category }; });
  d.seeds.forEach((s) => { all[s.doc_id] = { ...all[s.doc_id], ...s }; });
  d.nodes.forEach((n) => { all[n.doc_id] = { ...all[n.doc_id], ...n }; });
  const order = d.categories.concat(Object.values(all).map((n) => n.category).filter((c) => !d.categories.includes(c)));
  const ids = Object.values(all).sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category) || a.doc_id.localeCompare(b.doc_id)).map((n) => n.doc_id);
  const pos = {};
  ids.forEach((id, i) => { const a = (i / ids.length) * Math.PI * 2 - Math.PI / 2; pos[id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R, a }; });
  const seedIds = new Set(d.seeds.map((s) => s.doc_id));
  const top = new Set(d.nodes.filter((n) => n.in_top_k).map((n) => n.doc_id));
  const step = (Math.PI * 2) / ids.length;
  const arcs = order.map((c) => {
    const mine = ids.filter((id) => all[id].category === c); if (!mine.length) return "";
    const a0 = pos[mine[0]].a - step * 0.42, a1 = pos[mine[mine.length - 1]].a + step * 0.42, r = R - 16;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    return `<path class="g-arc" d="M${cx + Math.cos(a0) * r} ${cy + Math.sin(a0) * r} A ${r} ${r} 0 ${large} 1 ${cx + Math.cos(a1) * r} ${cy + Math.sin(a1) * r}" stroke="${catColor(c)}"><title>${esc(c)}</title></path>`;
  }).join("");
  const edges = d.edges.filter((e) => pos[e.source] && pos[e.target]).map((e) => {
    const a = pos[e.source], b = pos[e.target], mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    return `<path class="g-edge ${e.type}" d="M${a.x} ${a.y} Q ${cx + (mx - cx) * 0.25} ${cy + (my - cy) * 0.25} ${b.x} ${b.y}"><title>${esc(e.source)} → ${esc(e.target)} · ${e.type} ${e.weight}</title></path>`;
  }).join("");
  const nodes = ids.map((id) => {
    const n = all[id], p = pos[id], c = Math.cos(p.a);
    const cls = seedIds.has(id) ? "seed" : top.has(id) ? "top" : n.reached_by ? "reached" : "idle";
    const lx = cx + c * (R + 13), ly = cy + Math.sin(p.a) * (R + 13) + 3.5;
    const anchor = c > 0.15 ? "start" : c < -0.15 ? "end" : "middle";
    return `<g class="g-node ${cls} ${top.has(id) ? "intop" : ""}"><circle cx="${p.x}" cy="${p.y}" r="${seedIds.has(id) ? 7.5 : 5.5}" fill="${catColor(n.category)}"><title>${esc(id)}${n.graph_score != null ? " · score " + n.graph_score : ""}${n.reached_by ? " · via " + n.reached_by : ""}</title></circle>${top.has(id) ? `<circle cx="${p.x}" cy="${p.y}" r="11.5" class="g-ring"/>` : ""}<text x="${lx}" y="${ly}" text-anchor="${anchor}">${esc(id)}</text></g>`;
  }).join("");
  const cats = order.filter((c) => ids.some((id) => all[id].category === c)).map((c) => `<span><i class="catdot" style="background:${catColor(c)}"></i>${esc(c)}</span>`).join("");
  const table = d.nodes.slice(0, 8).map((n, i) => `<div class="rbar ${n.in_top_k ? "in" : "out"}"><span class="rk">${i + 1}</span><span class="rn">${esc(n.doc_id)}</span><span class="rvia">${n.reached_by === "seed" ? "seed" : `${esc(n.reached_by)} ← ${esc(n.via)}`}</span><span class="rv">${n.graph_score.toFixed(3)}</span></div>`).join("");
  return vstep(1, "Seed with vector search", `<div class="seeds">${d.seeds.map((s) => `<span class="pdoc seedchip">${esc(s.doc_id)} <b>${s.seed_score.toFixed(2)}</b></span>`).join("")}</div>`)
    + vstep(2, "Walk the property graph from each seed", `<svg class="g-svg" viewBox="0 0 ${W} ${H}">${arcs}${edges}${nodes}</svg><div class="legend-inline"><span><i class="seed"></i>seed (larger dot)</span><span><i class="sim"></i>SIMILAR_TO edge</span><span><i class="cat"></i>same category edge</span><span><i class="ring"></i>final top-k</span></div><div class="legend-inline">${cats}</div>`)
    + vstep(3, "Score = seed score × edge strength (keep the best path)", `<div class="rbars">${table}</div>`);
}

// ── policy memory panel ────────────────────────────────────────────────
async function loadPolicy() {
  const box = $("#policy-box"); if (!box) return;
  try {
    const d = await getJSON("/api/rag/policy");
    window.__policyDocs = d.sections;
    const byCat = {};
    d.sections.forEach((s) => { (byCat[s.category] = byCat[s.category] || []).push(s); });
    box.innerHTML = `
      <div class="bulletins">${d.bulletins.map((b) => `<button class="btn ${b.applied ? "btn-ghost" : "btn-accent"} bulletin" data-b="${b.id}" ${b.applied ? "disabled" : ""}>${b.applied ? I.check : I.play} ${esc(b.label)}${b.applied ? " · applied" : ""}</button>`).join("")}</div>
      <div class="hint" style="margin:8px 0 12px">A bulletin archives the current row into POLICY_DOC_VERSIONS, re-embeds the new text and updates POLICY_DOCS in place (version + 1). Ask again to see the answer change.</div>
      <div class="pol-list">${Object.entries(byCat).map(([c, list]) => `<div class="pol-cat"><div class="pol-cat-h" style="color:${catColor(c)}">${esc(c)}</div>${list.map((s) => `<details class="pol-sec"><summary><span>${esc(s.title)}</span><span class="vbadge ${s.version > 1 ? "new" : ""}">v${s.version}</span></summary><div class="pol-body">${esc(s.content)}${s.rules ? `<pre class="pol-rules">${esc(JSON.stringify(s.rules))}</pre>` : ""}</div></details>`).join("")}</div>`).join("")}</div>
      ${d.history.length ? `<div class="pol-hist"><div class="pol-cat-h">${I.history} Archived versions</div>${d.history.map((h) => `<div class="hist-row"><span class="mono">${esc(h.doc_id)} v${h.version}</span><span class="hint">${esc(h.valid_to)}</span><div class="hint">${esc(h.reason || "")}</div></div>`).join("")}</div>` : ""}
      <details class="pol-edit"><summary>${I.memory} Write your own update</summary>
        <select id="pe-doc">${d.sections.map((s) => `<option value="${s.doc_id}">${esc(s.title)} (v${s.version})</option>`).join("")}</select>
        <textarea id="pe-text" rows="4"></textarea><input type="text" id="pe-reason" placeholder="Why it changed">
        <button class="btn btn-accent" id="pe-save">${I.check} Save as a new version</button><span class="hint" id="pe-msg"></span>
      </details>`;
    $$(".bulletin", box).forEach((b) => b.addEventListener("click", async () => {
      b.disabled = true; b.innerHTML = '<span class="spinner"></span> updating…';
      try { const r = await postJSON("/api/rag/policy/bulletin", { bulletin_id: b.dataset.b }); b.innerHTML = `${I.check} ${esc(r.doc_id)} is now v${r.version}`; }
      catch (e) { b.innerHTML = esc(e.message); }
      await loadPolicy();
      if (ragState.lastQuery) explainTechnique(ragState.lastQuery);
    }));
    const doc = $("#pe-doc"), text = $("#pe-text");
    const fill = () => { const s = d.sections.find((x) => x.doc_id === doc.value); text.value = s ? s.content : ""; };
    fill(); doc.addEventListener("change", fill);
    $("#pe-save").addEventListener("click", async () => {
      try { const r = await postJSON("/api/rag/policy/update", { doc_id: doc.value, content: text.value, reason: $("#pe-reason").value }); setText("#pe-msg", `${r.doc_id} is now v${r.version}`); await loadPolicy(); }
      catch (e) { setText("#pe-msg", e.message); }
    });
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

// ── latent space viewer ─────────────────────────────────────────────────
function wireSpace() {
  const mode = $("#space-mode"), dim = $("#space-dim");
  let selectedMode = "pre";
  mode.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; $$("button", mode).forEach((x) => x.classList.toggle("active", x === b)); selectedMode = b.dataset.m; if (ragState.space) runSpace(); });
  dim.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; $$("button", dim).forEach((x) => x.classList.toggle("active", x === b)); ragState.spaceMode = b.dataset.d; drawSpace(); });
  $("#space-k").addEventListener("input", (e) => setText("#space-k-v", e.target.value));
  $("#space-acc").addEventListener("input", (e) => setText("#space-acc-v", e.target.value));
  $("#space-cat").addEventListener("change", () => { if (ragState.space) runSpace(); });
  $("#space-run").addEventListener("click", runSpace);
  $("#space-q").addEventListener("keydown", (e) => { if (e.key === "Enter") runSpace(); });
  async function runSpace() {
    const q = $("#space-q").value.trim() || $("#rag-input").value.trim();
    if (!q) { $("#space-q").focus(); return; }
    $("#space-q").value = q;
    const body = { query: q, k: +$("#space-k").value, category: $("#space-cat").value || null, mode: selectedMode, accuracy: +$("#space-acc").value };
    try {
      ragState.space = await postJSON("/api/rag/space", body);
      if (!$("#space-canvas")) return;
      drawSpace(); renderSpaceSide();
    } catch (e) { setHTML("#space-compare", `<div class="banner warn">${I.alert}<div>${esc(e.message)}</div></div>`); }
  }
  const canvas = $("#space-canvas");
  let drag = null;
  canvas.addEventListener("pointerdown", (e) => { if (ragState.spaceMode !== "3d") return; drag = { x: e.clientX, y: e.clientY, a: ragState.rot.a, b: ragState.rot.b }; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", (e) => {
    if (drag) { ragState.rot.a = drag.a + (e.clientX - drag.x) * 0.01; ragState.rot.b = Math.max(-1.4, Math.min(1.4, drag.b + (e.clientY - drag.y) * 0.01)); drawSpace(); return; }
    spaceHover(e);
  });
  canvas.addEventListener("pointerup", () => { drag = null; });
  canvas.addEventListener("pointerleave", () => { const t = $("#space-tip"); if (t) t.hidden = true; });
  const onResize = () => drawSpace();
  window.addEventListener("resize", onResize);
  document.addEventListener("themechange", onResize);
  document.addEventListener("routechange", () => window.removeEventListener("resize", onResize), { once: true });
  drawSpace();
}

function projectPoint(p) {
  if (ragState.spaceMode !== "3d") return { x: p.x, y: p.y, z: 0, s: 1 };
  const { a, b } = ragState.rot;
  const x1 = p.x * Math.cos(a) - p.z * Math.sin(a), z1 = p.x * Math.sin(a) + p.z * Math.cos(a);
  const y1 = p.y * Math.cos(b) - z1 * Math.sin(b), z2 = p.y * Math.sin(b) + z1 * Math.cos(b);
  const s = 2.6 / (2.6 + z2);
  return { x: x1 * s, y: y1 * s, z: z2, s };
}

function drawSpace() {
  const canvas = $("#space-canvas"); if (!canvas) return;
  const rect = canvas.parentElement.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const W = Math.max(320, rect.width), H = Math.max(360, Math.min(560, W * 0.62));
  canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.width = W + "px"; canvas.style.height = H + "px";
  const g = canvas.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = getComputedStyle(document.documentElement);
  const text = css.getPropertyValue("--text").trim() || "#e9eaee", text3 = css.getPropertyValue("--text-3").trim() || "#6c7080", line = css.getPropertyValue("--line-2").trim() || "#333";
  g.fillStyle = document.documentElement.getAttribute("data-theme") === "light" ? "#f7f6f2" : "#05070d";
  g.fillRect(0, 0, W, H);
  const pad = 40, sx = (x) => W / 2 + x * (W / 2 - pad), sy = (y) => H / 2 - y * (H / 2 - pad);
  // axes and grid
  g.strokeStyle = line; g.lineWidth = 1; g.setLineDash([3, 5]);
  for (let i = -1; i <= 1; i += 0.5) { g.beginPath(); g.moveTo(sx(-1), sy(i)); g.lineTo(sx(1), sy(i)); g.stroke(); g.beginPath(); g.moveTo(sx(i), sy(-1)); g.lineTo(sx(i), sy(1)); g.stroke(); }
  g.setLineDash([]);
  const sp = ragState.space;
  if (!sp) {
    g.fillStyle = text3; g.font = "13px IBM Plex Mono, monospace"; g.textAlign = "center";
    g.fillText("Map a query to see where it lands among the 17 policy sections.", W / 2, H / 2);
    canvas.__pts = []; return;
  }
  setText("#space-var", `PC1 ${(sp.explained_variance[0] * 100).toFixed(0)}% · PC2 ${(sp.explained_variance[1] * 100).toFixed(0)}% · PC3 ${(sp.explained_variance[2] * 100).toFixed(0)}% of variance`);
  const retrieved = new Set(sp.retrieved), dropped = new Set(sp.dropped_by_post_filter);
  const q = projectPoint(sp.query);
  const pts = sp.points.map((p) => ({ ...p, pr: projectPoint(p) })).sort((a, b) => b.pr.z - a.pr.z);
  // query → retrieved lines, labelled with the true 768-d cosine similarity
  pts.filter((p) => retrieved.has(p.doc_id)).forEach((p) => {
    g.strokeStyle = "rgba(250, 204, 21, 0.75)"; g.lineWidth = 1.6; g.beginPath(); g.moveTo(sx(q.x), sy(q.y)); g.lineTo(sx(p.pr.x), sy(p.pr.y)); g.stroke();
    g.fillStyle = "#facc15"; g.font = "11px IBM Plex Mono, monospace"; g.textAlign = "center";
    g.fillText(p.similarity.toFixed(3), (sx(q.x) + sx(p.pr.x)) / 2, (sy(q.y) + sy(p.pr.y)) / 2 - 4);
  });
  canvas.__pts = [];
  pts.forEach((p) => {
    const x = sx(p.pr.x), y = sy(p.pr.y), r = (retrieved.has(p.doc_id) ? 7 : 5.5) * p.pr.s;
    g.globalAlpha = p.eligible ? 1 : 0.22;
    g.fillStyle = catColor(p.category); g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
    if (retrieved.has(p.doc_id)) { g.strokeStyle = "#facc15"; g.lineWidth = 2; g.beginPath(); g.arc(x, y, r + 5, 0, Math.PI * 2); g.stroke(); }
    if (dropped.has(p.doc_id)) { g.strokeStyle = "#fb7185"; g.lineWidth = 2.5; g.beginPath(); g.moveTo(x - 8, y - 8); g.lineTo(x + 8, y + 8); g.moveTo(x + 8, y - 8); g.lineTo(x - 8, y + 8); g.stroke(); }
    if (retrieved.has(p.doc_id) || dropped.has(p.doc_id) || p.rank <= 6) {
      g.fillStyle = p.eligible ? text : text3; g.font = `${retrieved.has(p.doc_id) ? "600 " : ""}11.5px IBM Plex Mono, monospace`; g.textAlign = "left";
      g.fillText(p.doc_id, x + r + 7, y + 4);
    }
    g.globalAlpha = 1;
    canvas.__pts.push({ x, y, r: r + 4, p });
  });
  // the query star
  const qx = sx(q.x), qy = sy(q.y);
  g.fillStyle = "#fde047"; g.strokeStyle = "#000"; g.lineWidth = 1.2; g.beginPath();
  for (let i = 0; i < 10; i++) { const rr = i % 2 ? 4.5 : 11, a = -Math.PI / 2 + (i * Math.PI) / 5; g.lineTo(qx + Math.cos(a) * rr, qy + Math.sin(a) * rr); }
  g.closePath(); g.fill(); g.stroke();
  g.fillStyle = "#fde047"; g.font = "600 12px IBM Plex Mono, monospace"; g.textAlign = "left"; g.fillText("your query", qx + 14, qy - 10);
  g.fillStyle = text3; g.font = "11px IBM Plex Mono, monospace"; g.textAlign = "right";
  g.fillText(ragState.spaceMode === "3d" ? "drag to rotate · PCA of 768-d embeddings" : "PC1 →  ·  PC2 ↑  ·  PCA of 768-d embeddings", W - 12, H - 12);
}

function spaceHover(e) {
  const canvas = $("#space-canvas"), tip = $("#space-tip"); if (!canvas || !canvas.__pts) return;
  const r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
  const hit = canvas.__pts.slice().reverse().find((c) => Math.hypot(c.x - x, c.y - y) <= c.r + 3);
  if (!hit) { tip.hidden = true; return; }
  const p = hit.p;
  tip.hidden = false; tip.style.left = Math.min(x + 14, r.width - 230) + "px"; tip.style.top = (y + 12) + "px";
  tip.innerHTML = `<b>${esc(p.title)}</b><br><span style="color:${catColor(p.category)}">${esc(p.category)}</span> · v${p.version}<br>cosine ${p.similarity.toFixed(4)} · distance ${p.distance.toFixed(4)}<br>rank ${p.rank} of 17${p.eligible ? "" : " · <i>filtered out</i>"}`;
}

function renderSpaceSide() {
  const sp = ragState.space; if (!sp) return;
  const retrieved = new Set(sp.retrieved);
  if (sp.comparison) {
    const modes = { pre: "Pre-filter: filter, then rank", in: "In-filter: check during the HNSW walk", post: "Post-filter: rank all, then filter" };
    setHTML("#space-compare", `<div class="cmp-title">category = <b style="color:${catColor(sp.category)}">${esc(sp.category)}</b> · k = ${sp.k}</div>
      ${Object.entries(sp.comparison).map(([m, ids]) => `<div class="cmp-row ${m === sp.mode ? "sel" : ""} ${ids.length < sp.k ? "short" : ""}"><span class="cmp-m">${m.toUpperCase()}</span><span class="cmp-d">${modes[m]}</span><span class="cmp-n">${ids.length}/${sp.k}</span><div class="cmp-ids">${ids.map((id) => `<span class="pdoc">${esc(id)}</span>`).join("") || '<span class="hint">no rows — the global top-k were all in other categories</span>'}</div></div>`).join("")}
      ${sp.mode === "post" ? `<div class="hint">Global top-${sp.k}: ${sp.global_top_k.map(esc).join(", ")}. Post-filter keeps only those in <b>${esc(sp.category)}</b> — the crossed-out points were ranked, then thrown away.</div>` : `<div class="hint">Pre- and in-filter fill k from inside the category, so they return the same rows; they differ in how Oracle gets there.</div>`}`);
  } else {
    setHTML("#space-compare", `<div class="hint">No filter: the top-${sp.k} are the nearest sections in the full 768-dimensional space. Add a category filter to compare pre, in and post.</div>`);
  }
  const rows = sp.points.slice().sort((a, b) => a.rank - b.rank).map((p) => `<tr class="${retrieved.has(p.doc_id) ? "hit" : ""} ${p.eligible ? "" : "dim"}"><td class="num">${p.rank}</td><td><i class="catdot" style="background:${catColor(p.category)}"></i>${esc(p.doc_id)}</td><td class="num">${p.similarity.toFixed(3)}</td><td class="num">${p.distance.toFixed(3)}</td><td>${retrieved.has(p.doc_id) ? "✓" : sp.dropped_by_post_filter.includes(p.doc_id) ? '<span style="color:var(--r5)">dropped</span>' : ""}</td></tr>`).join("");
  setHTML("#space-table", `<table class="data-table compact"><thead><tr><th class="num">#</th><th>section</th><th class="num">cos</th><th class="num">dist</th><th>top-k</th></tr></thead><tbody>${rows}</tbody></table>`);
  setText("#space-sql", sp.sql || "—");
}

// ── step 2 of the vector viz: the nearest sections, in interactive 3-D ──────────────
function mountNearest3D(space, k) {
  const cv = $("#n3d-canvas"); if (!cv || !space) return;
  const st = { a: 0.7, b: 0.32, spin: true, drag: null, hover: null };
  const top = new Set(space.retrieved), pts = space.points, q = space.query;
  const project = (p, W, H) => {
    const x1 = p.x * Math.cos(st.a) - p.z * Math.sin(st.a), z1 = p.x * Math.sin(st.a) + p.z * Math.cos(st.a);
    const y1 = p.y * Math.cos(st.b) - z1 * Math.sin(st.b), z2 = p.y * Math.sin(st.b) + z1 * Math.cos(st.b);
    const s = 2.8 / (2.8 + z2), R = Math.min(W, H) * 0.36;
    return { x: W / 2 + x1 * s * R, y: H / 2 - y1 * s * R, z: z2, s };
  };
  let screen = [];
  const draw = () => {
    if (!cv.isConnected) return false;
    const W = cv.parentElement.clientWidth, H = Math.round(W * 0.78), dpr = window.devicePixelRatio || 1;
    if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + "px"; }
    const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const light = document.documentElement.getAttribute("data-theme") === "light";
    g.fillStyle = light ? "#f7f6f2" : "#03050a"; g.fillRect(0, 0, W, H);
    // a floor grid and the three axes, for depth
    g.lineWidth = 1;
    for (let i = -4; i <= 4; i++) {
      const t = i / 4;
      for (const [a, b] of [[{ x: t, y: -1, z: -1 }, { x: t, y: -1, z: 1 }], [{ x: -1, y: -1, z: t }, { x: 1, y: -1, z: t }]]) {
        const A = project(a, W, H), B = project(b, W, H);
        g.strokeStyle = light ? "rgba(15,23,42,.07)" : "rgba(148,163,184,.08)"; g.beginPath(); g.moveTo(A.x, A.y); g.lineTo(B.x, B.y); g.stroke();
      }
    }
    const O = project({ x: -1, y: -1, z: -1 }, W, H);
    [["PC1", { x: -0.55, y: -1, z: -1 }, "#22d3ee"], ["PC2", { x: -1, y: -0.55, z: -1 }, "#a3e635"], ["PC3", { x: -1, y: -1, z: -0.55 }, "#f472b6"]].forEach(([name, p, c]) => {
      const P = project(p, W, H); g.strokeStyle = c; g.lineWidth = 1.6; g.beginPath(); g.moveTo(O.x, O.y); g.lineTo(P.x, P.y); g.stroke();
      g.fillStyle = c; g.font = "600 10px ui-monospace, Menlo, monospace"; g.fillText(name, P.x + 4, P.y - 3);
    });
    const Q = project(q, W, H);
    screen = pts.map((p) => ({ p, ...project(p, W, H) })).sort((a, b) => b.z - a.z);
    // lines to the top-k first, so points sit on top of them
    for (const s of screen) if (top.has(s.p.doc_id)) { g.strokeStyle = "rgba(250,204,21,.75)"; g.lineWidth = 1.4; g.beginPath(); g.moveTo(Q.x, Q.y); g.lineTo(s.x, s.y); g.stroke(); }
    const labels = [];
    const drawQuery = () => { const r = 9 * Q.s; g.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r; g.lineTo(Q.x + Math.cos(a) * rr, Q.y + Math.sin(a) * rr); } g.closePath(); g.fillStyle = "#fde047"; g.fill(); g.strokeStyle = "#000"; g.lineWidth = 1; g.stroke(); };
    let queryDrawn = false;
    for (const s of screen) {
      if (!queryDrawn && s.z < Q.z) { drawQuery(); queryDrawn = true; }
      const hit = top.has(s.p.doc_id), r = (hit ? 7 : 5) * s.s, hov = st.hover === s.p.doc_id;
      g.globalAlpha = hit || hov ? 1 : 0.55 + 0.45 * Math.max(0, Math.min(1, (1.4 - s.z) / 2.4));
      g.fillStyle = CAT_COLORS[s.p.category] || "#94a3b8"; g.beginPath(); g.arc(s.x, s.y, r, 0, Math.PI * 2); g.fill();
      g.globalAlpha = 1; g.strokeStyle = "rgba(0,0,0,.7)"; g.lineWidth = 0.8; g.stroke();
      if (hit || hov) { g.strokeStyle = hov ? "#fff" : "#facc15"; g.lineWidth = 2; g.beginPath(); g.arc(s.x, s.y, r + 4, 0, Math.PI * 2); g.stroke(); }
      if (hit || hov) labels.push({ x: s.x + r + 6, y: s.y + 4, text: s.p.doc_id, sim: s.p.similarity.toFixed(2) });
    }
    if (!queryDrawn) drawQuery();
    // labels: nudge each one below any it would overlap
    g.font = "600 11px ui-monospace, Menlo, monospace";
    labels.sort((a, b) => a.y - b.y);
    const placed = [];
    for (const l of labels) {
      const w = g.measureText(`${l.text}  ${l.sim}`).width + 8;
      while (placed.some((p) => Math.abs(p.y - l.y) < 14 && l.x < p.x + p.w && p.x < l.x + w)) l.y += 14;
      placed.push({ ...l, w });
      g.fillStyle = light ? "rgba(255,255,255,.85)" : "rgba(3,5,10,.75)"; g.fillRect(l.x - 3, l.y - 11, w, 15);
      g.fillStyle = light ? "#0f172a" : "#e2e8f0"; g.fillText(l.text, l.x, l.y);
      g.fillStyle = "#facc15"; g.fillText(l.sim, l.x + g.measureText(l.text + "  ").width, l.y);
    }
    return true;
  };
  const loop = () => { if (!st.spin || !draw()) return; st.a += 0.004; requestAnimationFrame(loop); };
  cv.addEventListener("pointerdown", (e) => { st.spin = false; st.drag = { x: e.clientX, y: e.clientY, a: st.a, b: st.b }; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", (e) => {
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (st.drag) { st.a = st.drag.a + (e.clientX - st.drag.x) * 0.01; st.b = Math.max(-1.45, Math.min(1.45, st.drag.b + (e.clientY - st.drag.y) * 0.01)); draw(); return; }
    let best = null, bd = 12;
    for (const s of screen) { const d = Math.hypot(s.x - mx, s.y - my); if (d < bd) { bd = d; best = s; } }
    const tip = $("#n3d-tip");
    st.hover = best ? best.p.doc_id : null;
    if (!st.spin) draw();
    if (!best) { tip.hidden = true; return; }
    tip.hidden = false; tip.style.left = Math.min(mx + 14, r.width - 220) + "px"; tip.style.top = my + 12 + "px";
    tip.innerHTML = `<b>${esc(best.p.title)}</b><br>${esc(best.p.category)} · rank ${best.p.rank}<br>cosine similarity <b>${best.p.similarity.toFixed(3)}</b>${top.has(best.p.doc_id) ? " · in the top-k" : ""}`;
  });
  cv.addEventListener("pointerup", () => { st.drag = null; });
  cv.addEventListener("pointerleave", () => { st.hover = null; const t = $("#n3d-tip"); if (t) t.hidden = true; if (!st.spin) draw(); });
  cv.addEventListener("dblclick", () => { st.a = 0.7; st.b = 0.32; draw(); });
  $("#n3d-spin").addEventListener("click", () => { st.spin = !st.spin; if (st.spin) loop(); });
  $("#n3d-reset").addEventListener("click", () => { st.a = 0.7; st.b = 0.32; draw(); });
  draw(); loop();
}

// ── stage 2: what the reranker did to the candidates ─────────────────────────────
function vizRerank(ev, k) {
  const rows = [...ev.rows].sort((a, b) => a.before - b.before);
  const H = rows.length * 24 + 30, W = 440, y = (r) => 26 + (r - 1) * 24;
  const links = rows.map((r) => `<path class="rr-l ${r.after <= k ? "in" : ""} ${r.before > r.after ? "up" : r.before < r.after ? "down" : ""}" d="M150 ${y(r.before)} C 220 ${y(r.before)}, 220 ${y(r.after)}, 290 ${y(r.after)}"/>`).join("");
  const left = rows.map((r) => `<text x="142" y="${y(r.before) + 4}" text-anchor="end" class="rr-t ${r.before <= k ? "in" : ""}">${r.before}. ${esc(r.doc_id)}</text>`).join("");
  const right = [...ev.rows].map((r) => `<text x="298" y="${y(r.after) + 4}" class="rr-t ${r.after <= k ? "in" : ""}">${r.after}. ${esc(r.doc_id)}</text><text x="${W - 4}" y="${y(r.after) + 4}" text-anchor="end" class="rr-s">${r.score.toFixed(2)}</text>`).join("");
  const cut = `<line x1="0" x2="${W}" y1="${y(k) + 12}" y2="${y(k) + 12}" class="rr-cut"/><text x="${W - 4}" y="${y(k) + 24}" text-anchor="end" class="rr-cutl">top-k cut · k = ${k}</text>`;
  return vstep(4, `Stage 2 · rerank ${rows.length} candidates with ${esc(ev.model.replace("-int8", ""))} · ${ev.ms} ms`, `
    <svg class="rr-svg" viewBox="0 0 ${W} ${H}"><text x="142" y="12" text-anchor="end" class="hy-h">${esc(ev.technique)} order</text><text x="298" y="12" class="hy-h">reranked</text><text x="${W - 4}" y="12" text-anchor="end" class="hy-h">score</text>${cut}${links}${left}${right}</svg>
    <div class="hint">A cross-encoder reads the question and each candidate <i>together</i> and scores the pair. It can only re-order what stage 1 returned: if the right section was not among the ${rows.length} candidates, no reranker can bring it back.</div>`);
}
