/* ======================================================================
   HNSW lab (RAG page) — build and search an HNSW graph in the browser.
   The same algorithm as the notebook's TinyHNSW, instrumented: every
   level draw, greedy hop, beam, link and prune is an event the player
   animates on a stack of layers. Two data sets: the policy's sentences
   (real 768-d embeddings, cosine) and synthetic 2-D points, where the
   distances are the ones you see and the graph is big enough for the
   savings to show.
   ====================================================================== */

const HL = {
  data: null, policy: null, index: null, events: [], cursor: 0, next: 0, timer: null, playing: false,
  highlight: null, query: null, search: null, layout: null, params: { dataset: "policy", n: 400, m: 4, efc: 32, efs: 8, k: 3, seed: 7, speed: 6, heur: true },
};

function rng(seed) { // mulberry32: reproducible levels and points
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

class MinHeap { // [priority, value] pairs
  constructor() { this.a = []; }
  get size() { return this.a.length; }
  peek() { return this.a[0]; }
  push(x) { const a = this.a; a.push(x); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (a[p][0] <= a[i][0]) break; [a[p], a[i]] = [a[i], a[p]]; i = p; } }
  pop() { const a = this.a, top = a[0], last = a.pop(); if (a.length) { a[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let s = i; if (l < a.length && a[l][0] < a[s][0]) s = l; if (r < a.length && a[r][0] < a[s][0]) s = r; if (s === i) break; [a[s], a[i]] = [a[i], a[s]]; i = s; } } return top; }
}

class LabHNSW {
  constructor(metric, { m, efc, seed, heuristic = true }) {
    this.metric = metric; this.heuristic = heuristic; this.m = m; this.m0 = 2 * m; this.efc = efc;
    this.mL = m > 1 ? 1 / Math.log(m) : 1; this.rand = rng(seed);
    this.vectors = []; this.levels = []; this.links = []; this.entry = null; this.calls = 0; this.buildCalls = 0;
  }
  dist(q, n) { this.calls++; return this.metric(q, this.vectors[n]); }
  select(cands, M) {
    // cands: [distance to the base vector, node], closest first.
    // closest: keep the M nearest. heuristic (HNSW paper, hnswlib): keep a candidate only if it is closer
    // to the base than to every neighbour already kept, so links point in different directions.
    if (!this.heuristic) return cands.slice(0, M).map(([, n]) => n);
    const out = [];
    for (const [d, c] of cands) {
      if (out.length >= M) break;
      if (out.every((r) => this.dist(this.vectors[c], r) > d)) out.push(c);
    }
    return out;
  }
  searchLayer(q, entries, ef, layer, order) {
    const visited = new Set(entries), cand = new MinHeap(), best = new MinHeap(); // best holds [-d, node]
    for (const e of entries) { const d = this.dist(q, e); cand.push([d, e]); best.push([-d, e]); if (order) order.push(e); }
    while (best.size > ef) best.pop();
    while (cand.size) {
      const [d, c] = cand.pop();
      if (d > -best.peek()[0]) break;
      for (const n of this.links[c][layer]) {
        if (visited.has(n)) continue;
        visited.add(n); if (order) order.push(n);
        const dn = this.dist(q, n);
        if (best.size < ef || dn < -best.peek()[0]) { cand.push([dn, n]); best.push([-dn, n]); if (best.size > ef) best.pop(); }
      }
    }
    return { found: best.a.map(([nd, n]) => [-nd, n]).sort((x, y) => x[0] - y[0]), visited: [...visited] };
  }
  insert(v, log) {
    const before = this.calls;
    try { this._insert(v, log); } finally { this.buildCalls += this.calls - before; }
  }
  _insert(v, log) {
    const node = this.vectors.length; this.vectors.push(v);
    const level = Math.floor(-Math.log(1 - this.rand()) * this.mL);
    this.levels.push(level); this.links.push(Array.from({ length: level + 1 }, () => new Set()));
    log.push({ t: "new", node, level });
    if (this.entry === null) { this.entry = node; log.push({ t: "entry", node, first: true }); return; }
    const top = this.levels[this.entry]; let ep = [this.entry];
    for (let layer = top; layer > level; layer--) {
      const r = this.searchLayer(v, ep, 1, layer);
      log.push({ t: "descend", node, layer, from: ep[0], to: r.found[0][1], visited: r.visited });
      ep = [r.found[0][1]];
    }
    for (let layer = Math.min(level, top); layer >= 0; layer--) {
      const r = this.searchLayer(v, ep, this.efc, layer), cap = layer === 0 ? this.m0 : this.m;
      const chosen = this.select(r.found, this.m);
      log.push({ t: "beam", node, layer, visited: r.visited, found: r.found.map(([, n]) => n) });
      for (const n of chosen) { this.links[node][layer].add(n); this.links[n][layer].add(node); }
      log.push({ t: "link", node, layer, to: chosen });
      for (const n of chosen) {
        if (this.links[n][layer].size <= cap) continue;
        const ranked = [...this.links[n][layer]].map((x) => [this.dist(this.vectors[n], x), x]).sort((a, b) => a[0] - b[0]);
        const keep = this.select(ranked, cap);
        const dropped = [...this.links[n][layer]].filter((x) => !keep.includes(x));
        this.links[n][layer] = new Set(keep);
        log.push({ t: "prune", node: n, layer, dropped, cap });
      }
      ep = r.found.map(([, n]) => n);
    }
    if (level > top) { this.entry = node; log.push({ t: "entry", node }); }
  }
  search(q, k, efs, log) {
    let ep = this.entry; const hops = [];
    for (let layer = this.levels[this.entry]; layer > 0; layer--) {
      const r = this.searchLayer(q, [ep], 1, layer); const to = r.found[0][1];
      hops.push({ layer, from: ep, to, visited: r.visited }); if (log) log.push({ t: "hop", layer, from: ep, to, visited: r.visited }); ep = to;
    }
    const order = [], r = this.searchLayer(q, [ep], Math.max(efs, k), 0, order);
    const top = r.found.slice(0, k).map(([, n]) => n);
    if (log) { for (let i = 1; i <= order.length; i++) log.push({ t: "visit", layer: 0, visited: order.slice(0, i), start: ep }); log.push({ t: "found", top, visited: order, start: ep }); }
    return { top, hops, visited: order, start: ep };
  }
}

const cosine = (a, b) => { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return 1 - s; };
const euclid = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function syntheticPoints(n, seed) {
  const r = rng(seed * 7919 + n), cats = Object.keys(CAT_COLORS);
  const centers = cats.map(() => [0.12 + r() * 0.76, 0.12 + r() * 0.76]);
  const gauss = () => Math.sqrt(-2 * Math.log(1 - r())) * Math.cos(2 * Math.PI * r());
  return Array.from({ length: n }, (_, i) => {
    const c = i % cats.length, x = Math.min(0.99, Math.max(0.01, centers[c][0] + gauss() * 0.075)), y = Math.min(0.99, Math.max(0.01, centers[c][1] + gauss() * 0.075));
    return { id: i, category: cats[c], text: `point #${i} (${cats[c]} cluster)`, x, y, v: [x, y] };
  });
}

// ── data and build ────────────────────────────────────────────────────────
async function hnswData() {
  if (HL.params.dataset === "points") return { items: syntheticPoints(HL.params.n, HL.params.seed), metric: euclid };
  if (!HL.policy) {
    const d = await getJSON("/api/rag/hnsw/corpus");
    HL.policy = d.items.map((it, i) => ({ ...it, v: Float32Array.from(d.vectors[i]) }));
  }
  return { items: HL.policy, metric: cosine };
}

function newIndex() {
  const p = HL.params;
  return new LabHNSW(HL.data.metric, { m: p.m, efc: p.efc, seed: p.seed, heuristic: p.heur });
}

async function rebuild(animate) {
  stopHnsw();
  try { HL.data = await hnswData(); } catch (e) { setHTML("#hl-narr", `<span class="hint">${esc(e.message)}</span>`); return; }
  HL.index = newIndex(); HL.events = []; HL.cursor = 0; HL.next = 0; HL.highlight = null; HL.search = null;
  if (HL.params.dataset === "points" && HL.query && HL.query.points !== true) HL.query = null;
  if (HL.params.dataset === "policy" && HL.query && HL.query.points) HL.query = null;
  if (animate) { setHTML("#hl-narr", "Press play: each vector is ingested in turn, one event at a time."); drawHnsw(); renderHnswStats(); playHnsw(); return; }
  const log = [];
  for (const it of HL.data.items) HL.index.insert(it.v, log);
  HL.next = HL.data.items.length;
  setHTML("#hl-narr", `Built: ${HL.data.items.length} vectors ingested with m = ${HL.params.m}, efConstruction = ${HL.params.efc}. ${HL.query ? "" : "Ask a question or click the bottom layer to search."}`);
  if (HL.query) runHnswSearch(false); else { drawHnsw(); renderHnswStats(); }
  hnswSweep();
}

// ── the player: one event per tick ────────────────────────────────────────
function stepHnsw() {
  if (HL.cursor >= HL.events.length) {
    if (HL.next >= HL.data.items.length) { stopHnsw(); HL.highlight = null; drawHnsw(); renderHnswStats(); hnswSweep(); setHTML("#hl-narr", `Ingestion finished: ${HL.data.items.length} vectors. Ask a question or click the bottom layer to search.`); return false; }
    HL.events = []; HL.cursor = 0;
    HL.index.insert(HL.data.items[HL.next].v, HL.events); HL.next++;
  }
  const ev = HL.events[HL.cursor++];
  HL.highlight = ev; narrate(ev); drawHnsw(); renderHnswStats();
  return true;
}
function playHnsw() {
  if (!HL.index) return;
  HL.playing = true; $("#hl-play").innerHTML = I.pause;
  const tick = () => { if (!HL.playing) return; if (stepHnsw()) HL.timer = setTimeout(tick, 1000 / HL.params.speed); };
  tick();
}
function stopHnsw() { HL.playing = false; clearTimeout(HL.timer); const b = $("#hl-play"); if (b) b.innerHTML = I.play; }
function finishHnsw() {
  stopHnsw();
  if (!HL.index) return;
  while (HL.next < HL.data.items.length) { HL.index.insert(HL.data.items[HL.next].v, []); HL.next++; }
  HL.events = []; HL.cursor = 0; HL.highlight = null;
  setHTML("#hl-narr", `Built: ${HL.data.items.length} vectors.`); drawHnsw(); renderHnswStats(); hnswSweep();
}

function label(n) {
  const it = HL.data.items[n]; if (!it) return `#${n}`;
  return HL.params.dataset === "policy" ? `#${n} <span class="hl-quote">“${esc(it.text.length > 70 ? it.text.slice(0, 68) + "…" : it.text)}”</span>` : `#${n}`;
}
function narrate(ev) {
  const p = HL.params; let html = "";
  if (ev.t === "new") html = `<b>Insert ${label(ev.node)}</b> · drew <b>level ${ev.level}</b>. With m = ${p.m}, about 1 node in ${p.m} reaches layer 1, 1 in ${p.m * p.m} layer 2.`;
  else if (ev.t === "entry") html = ev.first ? `${label(ev.node)} is the first vector: it is the entry point.` : `${label(ev.node)} is the first node on layer ${HL.index.levels[ev.node]}: it becomes the <b>entry point</b>.`;
  else if (ev.t === "descend") html = `Layer ${ev.layer}: greedy hop ${ev.from === ev.to ? `stays at #${ev.from}` : `from #${ev.from} to #${ev.to}`}, the closest node to the new vector on this layer.`;
  else if (ev.t === "beam") html = `Layer ${ev.layer}: a beam of efConstruction = ${p.efc} visited <b>${ev.visited.length}</b> node${ev.visited.length === 1 ? "" : "s"} looking for the new vector's neighbours.`;
  else if (ev.t === "link") html = `Layer ${ev.layer}: ${label(ev.node)} links to ${ev.to.map((n) => `#${n}`).join(", ")}${p.heur ? ` (the heuristic keeps ${ev.to.length} of up to ${p.m}: a candidate is skipped when an already-linked neighbour is closer to it than the new vector is)` : `, its ${ev.to.length} closest`}.`;
  else if (ev.t === "prune") html = `Layer ${ev.layer}: #${ev.node} now has more than ${ev.cap} links (${ev.layer === 0 ? "2m on layer 0" : "m"}), so it ${p.heur ? "re-selects a diverse set" : "keeps its closest"} and drops ${ev.dropped.map((n) => `#${n}`).join(", ")}.`;
  else if (ev.t === "hop") html = `Search, layer ${ev.layer}: greedy hop ${ev.from === ev.to ? `stays at #${ev.from}` : `#${ev.from} → #${ev.to}`}.`;
  else if (ev.t === "visit") html = `Search, layer 0: the beam of efSearch = ${p.efs} has visited ${ev.visited.length} node${ev.visited.length === 1 ? "" : "s"}.`;
  else if (ev.t === "found") html = `Search done: the ${ev.top.length} closest found after visiting ${ev.visited.length} of ${HL.index.vectors.length} vectors.`;
  setHTML("#hl-narr", html);
}

// ── search ───────────────────────────────────────────────────────────────
async function hnswAsk(text) {
  if (!text.trim() || HL.params.dataset !== "policy") return;
  setHTML("#hl-narr", '<span class="spinner"></span> embedding the question…');
  try { const q = await postJSON("/api/rag/hnsw/query", { query: text }); HL.query = { text, v: Float32Array.from(q.vector), x: q.x, y: q.y }; }
  catch (e) { setHTML("#hl-narr", esc(e.message)); return; }
  if (HL.next < HL.data.items.length) finishHnsw();
  runHnswSearch(true);
}
function exactTop(q, k) {
  return HL.data.items.map((it, i) => [HL.data.metric(q, it.v), i]).sort((a, b) => a[0] - b[0]).slice(0, k).map(([, i]) => i);
}
function runHnswSearch(animate) {
  if (!HL.query || !HL.index || !HL.index.vectors.length || HL.next < HL.data.items.length) return;
  stopHnsw();
  const p = HL.params; HL.index.calls = 0;
  const log = animate ? [] : null, res = HL.index.search(HL.query.v, p.k, p.efs, log);
  const exact = exactTop(HL.query.v, p.k);
  HL.search = { ...res, calls: HL.index.calls, exact, recall: res.top.filter((n) => exact.includes(n)).length / p.k };
  if (!animate) { HL.highlight = { t: "found", top: res.top, visited: res.visited, start: res.start }; drawHnsw(); renderHnswStats(); narrate(HL.highlight); return; }
  let i = 0; HL.playing = true; $("#hl-play").innerHTML = I.pause;
  const tick = () => {
    if (!HL.playing || i >= log.length) { stopHnsw(); renderHnswStats(); return; }
    HL.highlight = log[i++]; narrate(HL.highlight); drawHnsw(); HL.timer = setTimeout(tick, Math.max(40, 600 / HL.params.speed));
  };
  tick();
}

// ── drawing: a stack of layers in perspective ──────────────────────────────
function drawHnsw() {
  const cv = $("#hl-canvas"); if (!cv || !HL.index) return;
  const idx = HL.index, items = HL.data.items, n = idx.vectors.length;
  const layers = Math.max(1, (n ? Math.max(...idx.levels) : 0) + 1);
  const W = cv.parentElement.clientWidth, ph = layers > 4 ? 150 : 200, gap = layers > 1 ? Math.min(170, Math.max(64, 560 / (layers - 1))) : 0;
  const H = Math.round(48 + ph + gap * (layers - 1)), dpr = window.devicePixelRatio || 1;
  cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + "px";
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const light = document.documentElement.getAttribute("data-theme") === "light";
  g.fillStyle = light ? "#f7f6f2" : "#03050a"; g.fillRect(0, 0, W, H);
  const left = 70, skew = Math.min(150, W * 0.13), pw = W - left - skew - 24;
  const topOf = (L) => H - 24 - ph - L * gap;
  const P = (i, L, pt) => { const it = pt || items[i]; return [left + it.x * pw + (1 - it.y) * skew, topOf(L) + it.y * ph]; };
  HL.layout = { left, skew, pw, ph, topOf, layers };
  const hl = HL.highlight || {}, small = n > 200;
  const visited = new Set(hl.visited || []), top = new Set(hl.top || []), fresh = new Set(hl.t === "link" ? hl.to : []), dropped = new Set(hl.t === "prune" ? hl.dropped : []);
  for (let L = 0; L < layers; L++) {
    const t = topOf(L), on = [];
    for (let i = 0; i < n; i++) if (idx.levels[i] >= L) on.push(i);
    g.beginPath(); g.moveTo(left + skew, t); g.lineTo(left + skew + pw, t); g.lineTo(left + pw, t + ph); g.lineTo(left, t + ph); g.closePath();
    const active = hl.layer === L;
    g.fillStyle = light ? (active ? "rgba(34,211,238,.10)" : "rgba(15,23,42,.04)") : (active ? "rgba(34,211,238,.09)" : "rgba(148,163,184,.045)"); g.fill();
    g.strokeStyle = active ? "rgba(34,211,238,.7)" : light ? "rgba(15,23,42,.18)" : "rgba(148,163,184,.25)"; g.lineWidth = 1; g.stroke();
    g.fillStyle = light ? "#334155" : "#cbd5e1"; g.font = "600 11px ui-monospace, Menlo, monospace";
    g.fillText(`layer ${L}`, 10, t + ph / 2 - 4); g.fillStyle = light ? "#64748b" : "#64748b"; g.font = "10px ui-monospace, Menlo, monospace"; g.fillText(`${on.length} node${on.length === 1 ? "" : "s"}`, 10, t + ph / 2 + 10);
    // links
    g.lineWidth = small ? 0.5 : 0.9;
    for (const i of on) for (const j of idx.links[i][L]) {
      if (j < i && idx.links[j][L] && idx.links[j][L].has(i)) continue;
      const [x1, y1] = P(i, L), [x2, y2] = P(j, L);
      const isNew = hl.t === "link" && hl.layer === L && hl.node === i && fresh.has(j);
      g.strokeStyle = isNew ? "#34d399" : light ? "rgba(71,85,105,.32)" : `rgba(148,163,184,${small ? 0.16 : 0.32})`;
      g.lineWidth = isNew ? 2.2 : small ? 0.5 : 0.9;
      g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke();
    }
    if (hl.t === "prune" && hl.layer === L) {
      g.setLineDash([4, 4]); g.strokeStyle = "#fb7185"; g.lineWidth = 2;
      for (const j of dropped) { const [x1, y1] = P(hl.node, L), [x2, y2] = P(j, L); g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2, y2); g.stroke(); }
      g.setLineDash([]);
    }
    // nodes
    for (const i of on) {
      const [x, y] = P(i, L), r = small ? (L === 0 ? 2.2 : 3.2) : L === 0 ? 4.2 : 5.2;
      g.fillStyle = CAT_COLORS[items[i].category] || "#94a3b8"; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill();
      if (visited.has(i) && (hl.layer === L || ((hl.t === "found" || hl.t === "visit") && L === 0))) { g.strokeStyle = "#fbbf24"; g.lineWidth = 1.3; g.beginPath(); g.arc(x, y, r + 3, 0, Math.PI * 2); g.stroke(); }
      if (top.has(i) && L === 0) { g.strokeStyle = "#fde047"; g.lineWidth = 2.4; g.beginPath(); g.arc(x, y, r + 6, 0, Math.PI * 2); g.stroke(); }
    }
    // entry point
    if (idx.entry !== null && idx.levels[idx.entry] === L) {
      const [x, y] = P(idx.entry, L); g.strokeStyle = light ? "#0f172a" : "#fff"; g.lineWidth = 2; g.beginPath(); g.arc(x, y, 9, 0, Math.PI * 2); g.stroke();
      g.fillStyle = light ? "#0f172a" : "#fff"; g.font = "600 10px ui-monospace, Menlo, monospace"; g.fillText("entry", x + 12, y - 8);
    }
    // the query, on every layer
    if (HL.query) { const [x, y] = P(null, L, HL.query); star(g, x, y, 7, "#fde047"); }
  }
  // the node being inserted, through all its layers
  if (hl.node !== undefined && ["new", "descend", "beam", "link", "entry"].includes(hl.t)) {
    const i = hl.node;
    for (let L = 0; L <= idx.levels[i]; L++) { const [x, y] = P(i, L); g.strokeStyle = "#22d3ee"; g.lineWidth = 2.2; g.beginPath(); g.arc(x, y, 8, 0, Math.PI * 2); g.stroke(); }
    if (idx.levels[i] > 0) { const [x0, y0] = P(i, 0), [x1, y1] = P(i, idx.levels[i]); g.setLineDash([3, 4]); g.strokeStyle = "rgba(34,211,238,.7)"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); g.setLineDash([]); }
  }
  // greedy hops: the insert's descent, or the search route
  const hops = hl.t === "descend" ? [hl] : HL.search && ["hop", "visit", "found"].includes(hl.t) ? HL.search.hops.filter((h) => hl.t !== "hop" || h.layer >= hl.layer) : [];
  for (const h of hops) {
    const [x1, y1] = P(h.from, h.layer), [x2, y2] = P(h.to, h.layer);
    if (h.from !== h.to) arrow(g, x1, y1, x2, y2, "#fde047");
    if (h.layer > 0 && (hl.t !== "hop" || h.layer > hl.layer)) { const [xa, ya] = P(h.to, h.layer - 1); g.setLineDash([2, 4]); g.strokeStyle = "rgba(253,224,71,.6)"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(x2, y2); g.lineTo(xa, ya); g.stroke(); g.setLineDash([]); }
  }
}
function star(g, x, y, r, color) {
  g.beginPath();
  for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  g.closePath(); g.fillStyle = color; g.fill(); g.strokeStyle = "#000"; g.lineWidth = 0.8; g.stroke();
}
function arrow(g, x1, y1, x2, y2, color) {
  const a = Math.atan2(y2 - y1, x2 - x1);
  g.strokeStyle = color; g.fillStyle = color; g.lineWidth = 2.2;
  g.beginPath(); g.moveTo(x1, y1); g.lineTo(x2 - Math.cos(a) * 6, y2 - Math.sin(a) * 6); g.stroke();
  g.beginPath(); g.moveTo(x2, y2); g.lineTo(x2 - Math.cos(a - 0.4) * 10, y2 - Math.sin(a - 0.4) * 10); g.lineTo(x2 - Math.cos(a + 0.4) * 10, y2 - Math.sin(a + 0.4) * 10); g.closePath(); g.fill();
}

// ── numbers beside the picture ─────────────────────────────────────────────
function renderHnswStats() {
  const idx = HL.index; if (!idx) return;
  const p = HL.params, n = idx.vectors.length, layers = n ? Math.max(...idx.levels) + 1 : 0;
  const per = Array.from({ length: layers }, (_, L) => idx.levels.filter((l) => l >= L).length).reverse();
  const links = n ? idx.links.reduce((s, l) => s + l.reduce((t, set) => t + set.size, 0), 0) : 0;
  const deg0 = n ? (idx.links.reduce((s, l) => s + l[0].size, 0) / n).toFixed(1) : "0";
  const dim = p.dataset === "policy" ? (HL.policy && HL.policy[0] ? HL.policy[0].v.length : 768) : 2;
  const s = HL.search;
  setHTML("#hl-stats", `
    <div class="hl-kv"><span>vectors ingested</span><b>${n} / ${HL.data ? HL.data.items.length : 0}</b></div>
    <div class="hl-kv"><span>layers (top → 0)</span><b>${per.join(" · ") || "—"}</b></div>
    <div class="hl-kv"><span>links, avg per node on layer 0</span><b>${links} · ${deg0} (cap ${2 * p.m})</b></div>
    <div class="hl-kv"><span>distances computed to build</span><b>${idx.buildCalls.toLocaleString()}</b></div>
    <div class="hl-kv"><span>graph size vs vectors</span><b>${(links * 4 / 1024).toFixed(1)} KB · ${(n * dim * 4 / 1024).toFixed(0)} KB</b></div>
    ${s ? `<div class="hl-res"><div class="mem-h">Search · top ${p.k}, efSearch ${p.efs}</div>
      <div class="hl-kv"><span>recall@${p.k} vs an exact scan</span><b class="${s.recall === 1 ? "ok" : "warn"}">${Math.round(s.recall * 100)}%</b></div>
      <div class="hl-kv"><span>distances computed</span><b>${s.calls} of ${n} (${Math.round((s.calls / Math.max(1, n)) * 100)}%)</b></div>
      ${s.top.map((t, i) => `<div class="hl-hit ${s.exact.includes(t) ? "" : "miss"}"><span>${i + 1}</span>${p.dataset === "policy" ? esc(HL.data.items[t].text) : `point #${t}`}${s.exact.includes(t) ? "" : ' <em>not in the exact top</em>'}</div>`).join("")}</div>` : ""}`);
  setText("#hl-sql", `CREATE VECTOR INDEX policy_vec_idx ON policy_docs(embedding)\n  ORGANIZATION INMEMORY NEIGHBOR GRAPH\n  DISTANCE COSINE WITH TARGET ACCURACY 90      -- Oracle turns this into efSearch per query\n  PARAMETERS (TYPE HNSW, NEIGHBORS ${p.m}, EFCONSTRUCTION ${p.efc});`);
}

function hnswSweep() {
  const idx = HL.index; if (!idx || !idx.vectors.length || HL.next < HL.data.items.length) return;
  const p = HL.params, r = rng(p.seed + 99), n = idx.vectors.length, dim = idx.vectors[0].length;
  const queries = Array.from({ length: 30 }, () => {
    if (p.dataset === "points") return [r(), r()];
    const base = idx.vectors[Math.floor(r() * n)], v = Float32Array.from(base, (x) => x + (r() - 0.5) * 0.06);
    const norm = Math.hypot(...v); return v.map((x) => x / norm);
  });
  const exact = queries.map((q) => exactTop(q, p.k));
  const efs = [1, 2, 4, 8, 16, 32, 64, 128].filter((e) => e >= 1);
  const pts = efs.map((e) => {
    let rec = 0, calls = 0;
    queries.forEach((q, i) => { idx.calls = 0; const res = idx.search(q, p.k, e); calls += idx.calls; rec += res.top.filter((t) => exact[i].includes(t)).length / p.k; });
    return { e, recall: rec / queries.length, share: calls / queries.length / n };
  });
  idx.calls = 0;
  const W = 330, H = 170, l = 34, b = 26, X = (i) => l + (i / (efs.length - 1)) * (W - l - 10), Y = (v) => H - b - v * (H - b - 10);
  const line = (key, cls) => `<path class="hl-line ${cls}" d="${pts.map((pt, i) => `${i ? "L" : "M"}${X(i)} ${Y(Math.min(1, pt[key]))}`).join(" ")}"/>` + pts.map((pt, i) => `<circle class="hl-dot ${cls}" cx="${X(i)}" cy="${Y(Math.min(1, pt[key]))}" r="3"><title>efSearch ${pt.e}: ${key === "recall" ? `recall ${(pt.recall * 100).toFixed(0)}%` : `${(pt.share * 100).toFixed(0)}% of vectors`}</title></circle>`).join("");
  const cur = efs.reduce((best, e, i) => (Math.abs(e - p.efs) < Math.abs(efs[best] - p.efs) ? i : best), 0);
  setHTML("#hl-sweep", `<svg viewBox="0 0 ${W} ${H}" class="hl-chart">
    ${[0, 0.5, 1].map((v) => `<line x1="${l}" x2="${W - 10}" y1="${Y(v)}" y2="${Y(v)}" class="hl-grid"/><text x="${l - 6}" y="${Y(v) + 3}" text-anchor="end" class="hl-ax">${v * 100}%</text>`).join("")}
    <line x1="${X(cur)}" x2="${X(cur)}" y1="10" y2="${H - b}" class="hl-cur"/>
    ${line("recall", "rec")}${line("share", "cost")}
    ${efs.map((e, i) => `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" class="hl-ax">${e}</text>`).join("")}
  </svg><div class="legend-inline"><span><i class="hl-k rec"></i>recall@${p.k}</span><span><i class="hl-k cost"></i>share of vectors compared</span><span class="hint">x: efSearch · 30 queries · ${n} vectors, ${dim}-d</span></div>`);
}

// ── panel ─────────────────────────────────────────────────────────────────
function hnswPanelHTML() {
  const p = HL.params;
  const slider = (id, lab, min, max, val, step = 1) => `<label class="slider-lab" title="${lab}">${lab} <input type="range" id="hl-${id}" min="${min}" max="${max}" step="${step}" value="${val}"><b id="hl-${id}-v">${val}</b></label>`;
  return `
    <div class="panel-head"><span class="panel-title">${I.flow} HNSW lab · how the vector index is built and searched ${memBadge("semantic", true)}</span><span class="hint mono">the notebook's TinyHNSW, in your browser, plus the neighbour heuristic real indexes use</span></div>
    <div class="panel-body">
      <div class="space-controls">
        <div class="seg" id="hl-dataset"><button data-d="policy" class="${p.dataset === "policy" ? "active" : ""}">Policy sentences · 768-d</button><button data-d="points" class="${p.dataset === "points" ? "active" : ""}">2-D points</button></div>
        <span id="hl-n-wrap" ${p.dataset === "points" ? "" : "hidden"}>${slider("n", "points", 50, 1500, p.n, 50)}</span>
        ${slider("m", "m · NEIGHBORS", 2, 32, p.m)}${slider("efc", "efConstruction", 1, 200, p.efc)}${slider("efs", "efSearch", 1, 128, p.efs)}${slider("k", "k", 1, 10, p.k)}
        <div class="seg" id="hl-heur" title="How a node chooses which candidates to link to"><button data-h="1" class="${p.heur ? "active" : ""}">diverse links (heuristic)</button><button data-h="0" class="${p.heur ? "" : "active"}">m closest</button></div>
        <button class="btn btn-ghost" id="hl-seed" title="Draw new random levels">${I.refresh} new levels</button>
      </div>
      <div class="hl-bar">
        <span class="scen-ctl" style="margin-left:0"><button class="btn btn-accent" id="hl-ingest">${I.play} Ingest step by step</button><button class="btn btn-ghost" id="hl-play" title="Play / pause">${I.play}</button><button class="btn btn-ghost" id="hl-step" title="Next event">${I.step}</button><button class="btn btn-ghost" id="hl-finish" title="Finish building">Build all</button></span>
        ${slider("speed", "speed", 1, 30, p.speed)}
        <div class="field hl-ask" id="hl-ask-wrap"><input type="text" id="hl-q" placeholder="Search the index: ask a question…" value="Will an algorithm decide my loan on its own?"><button class="btn btn-accent" id="hl-search">${I.send} Search</button></div>
        <span class="hint" id="hl-click-hint" ${p.dataset === "points" ? "" : "hidden"}>click layer 0 to place a query</span>
      </div>
      <div class="hl-narr" id="hl-narr">Loading the policy sentences…</div>
      <div class="hl-grid2">
        <div class="hl-canvas-wrap"><canvas id="hl-canvas"></canvas><div class="space-tip" id="hl-tip" hidden></div>
          <div class="legend-inline hl-legend"><span><i class="hl-k new"></i>vector being inserted</span><span><i class="hl-k link"></i>new link</span><span><i class="hl-k prune"></i>pruned link</span><span><i class="ring"></i>visited by the beam</span><span><i class="hl-k top"></i>result</span><span>★ query</span><span>◯ entry point</span></div>
        </div>
        <div class="hl-side">
          <div id="hl-stats"></div>
          <div class="mem-h" style="margin-top:12px">efSearch: recall against cost</div>
          <div id="hl-sweep"></div>
          <details class="sql-box" open><summary>The same knobs in Oracle</summary><pre class="rag-sql" id="hl-sql"></pre></details>
        </div>
      </div>
    </div>`;
}

function wireHNSW() {
  const panel = $("#hnsw-panel"); if (!panel) return;
  panel.innerHTML = hnswPanelHTML();
  const p = HL.params;
  const bind = (id, key, after) => $(`#hl-${id}`).addEventListener("input", (e) => { p[key] = +e.target.value; setText(`#hl-${id}-v`, p[key]); after && after(); });
  const rebuildSoon = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => rebuild(false), 180); }; })();
  bind("n", "n", rebuildSoon); bind("m", "m", rebuildSoon); bind("efc", "efc", rebuildSoon);
  bind("efs", "efs", () => { runHnswSearch(false); hnswSweep(); }); bind("k", "k", () => { runHnswSearch(false); hnswSweep(); });
  bind("speed", "speed");
  $$("#hl-dataset button").forEach((b) => b.addEventListener("click", () => {
    $$("#hl-dataset button").forEach((x) => x.classList.toggle("active", x === b)); p.dataset = b.dataset.d; HL.query = null;
    $("#hl-n-wrap").hidden = p.dataset !== "points"; $("#hl-click-hint").hidden = p.dataset !== "points"; $("#hl-ask-wrap").hidden = p.dataset !== "policy";
    rebuild(false);
  }));
  $("#hl-seed").addEventListener("click", () => { p.seed = Math.floor(Math.random() * 1e6); rebuild(false); });
  $$("#hl-heur button").forEach((b) => b.addEventListener("click", () => { $$("#hl-heur button").forEach((x) => x.classList.toggle("active", x === b)); p.heur = b.dataset.h === "1"; rebuild(false); }));
  $("#hl-ingest").addEventListener("click", () => rebuild(true));
  $("#hl-play").addEventListener("click", () => { if (HL.playing) stopHnsw(); else if (HL.next < (HL.data ? HL.data.items.length : 0) || HL.cursor < HL.events.length) playHnsw(); else runHnswSearch(true); });
  $("#hl-step").addEventListener("click", () => { stopHnsw(); if (HL.index) stepHnsw(); });
  $("#hl-finish").addEventListener("click", finishHnsw);
  $("#hl-search").addEventListener("click", () => hnswAsk($("#hl-q").value));
  $("#hl-q").addEventListener("keydown", (e) => { if (e.key === "Enter") hnswAsk(e.target.value); });
  const cv = $("#hl-canvas");
  cv.addEventListener("click", (e) => {
    if (p.dataset !== "points" || !HL.layout) return;
    const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, Lo = HL.layout, t0 = Lo.topOf(0);
    const qy = (y - t0) / Lo.ph; if (qy < 0 || qy > 1) return;
    const qx = (x - Lo.left - (1 - qy) * Lo.skew) / Lo.pw; if (qx < 0 || qx > 1) return;
    if (HL.next < HL.data.items.length) finishHnsw();
    HL.query = { points: true, v: [qx, qy], x: qx, y: qy }; runHnswSearch(true);
  });
  cv.addEventListener("mousemove", (e) => {
    const tip = $("#hl-tip"); if (!HL.layout || !HL.index) return;
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, Lo = HL.layout, items = HL.data.items;
    let best = null, bd = 9;
    for (let i = 0; i < HL.index.vectors.length; i++) for (let L = 0; L <= HL.index.levels[i]; L++) {
      const sx = Lo.left + items[i].x * Lo.pw + (1 - items[i].y) * Lo.skew, sy = Lo.topOf(L) + items[i].y * Lo.ph, d = Math.hypot(sx - mx, sy - my);
      if (d < bd) { bd = d; best = [i, L]; }
    }
    if (!best) { tip.hidden = true; return; }
    const [i, L] = best, it = items[i];
    tip.hidden = false; tip.style.left = Math.min(mx + 14, r.width - 240) + "px"; tip.style.top = my + 14 + "px";
    tip.innerHTML = `<b>#${i}</b> · ${esc(it.category)} · level ${HL.index.levels[i]}<br>${p.dataset === "policy" ? esc(it.text) : ""}<br><span class="hint">layer ${L}: ${HL.index.links[i][L].size} links</span>`;
  });
  cv.addEventListener("mouseleave", () => { $("#hl-tip").hidden = true; });
  window.addEventListener("resize", () => { if ($("#hl-canvas")) drawHnsw(); });
  rebuild(false).then(() => { if (p.dataset === "policy") hnswAsk($("#hl-q").value); });
}
