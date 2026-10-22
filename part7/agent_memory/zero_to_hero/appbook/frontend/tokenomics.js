/* ======================================================================
   Tokenomics — latency, cost and token consumption of every measured turn,
   scratch Memo against MemoRizz Memo, with a naive baseline in the memory
   workload. Inline SVG charts (lines and stacked bars) with one shared
   tooltip and a legend on every card; click a chart to enlarge it with a
   table of the plotted values. Loaded before app.js; uses its helpers
   ($, $$, esc, getJSON, postJSON, streamSSE, setStage, state) at call time.
   ====================================================================== */

// Series and segment colours (the two Memos match their columns on the Part pages).
const TK = {
  agents: { scratch: "#25b3a3", memorizz: "#9b6cff", naive: "#e8607a" },
  phases: { model: "#5b8def", memory: "#e7a033", tools: "#8fbf3a", other: "#8d8a82" },
  kinds: { input: "#5b8def", cached: "#a9c4f5", output: "#e7a033" },
};
const TK_LABEL = { scratch: "Scratch", memorizz: "MemoRizz", naive: "Naive" };
const TK_TAG = { scratch: "S", memorizz: "M", naive: "N" };
const TK_ORDER = ["scratch", "memorizz", "naive"];
const tk = { data: null, modal: null, running: false, stopping: false, watch: null, abort: null, progress: "" };
// Progress goes to the page when it is open; the text is kept for when it opens again.
const tkProgress = (text) => { tk.progress = text; const el = $("#tk-progress"); if (el) el.textContent = text; };
// The naive baseline answers in the memory workload only, so it appears once it has turns.
const tkAgents = () => TK_ORDER.filter((a) => a !== "naive" || (tk.data?.turns || []).some((r) => r.agent === a));

// ---- shared tooltip ----
const tkTip = document.createElement("div");
tkTip.className = "tk-tip";
tkTip.hidden = true;
document.body.append(tkTip);
document.addEventListener("mousemove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  if (!t) { tkTip.hidden = true; return; }
  tkTip.innerHTML = t.dataset.tip;
  tkTip.hidden = false;
  tkTip.style.left = Math.min(e.clientX + 14, innerWidth - tkTip.offsetWidth - 8) + "px";
  tkTip.style.top = e.clientY + 14 + "px";
});

// ---- chart geometry (viewBox units); the modal re-renders larger instead of stretching ----
let W = 300, H = 150, L = 40, R = 8, T = 10, B = 30;
const yOf = (v, max) => T + (H - T - B) * (1 - v / max);
const sec = (ms) => (ms / 1000).toFixed(2) + "s";
const usd = (v) => (v === 0 ? "$0" : v < 0.01 ? "$" + v.toFixed(4) : "$" + v.toFixed(3));
const kTok = (v) => (v >= 1000 ? (v / 1000).toFixed(v >= 10000 ? 0 : 1) + "k" : String(Math.round(v)));

function tkFrame(max, fmt, runs) {
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  for (let k = 0; k <= 2; k++) {
    const y = T + ((H - T - B) * k) / 2;
    s += `<line x1="${L}" y1="${y}" x2="${W - R}" y2="${y}" class="grid"/><text x="${L - 5}" y="${y + 3}" text-anchor="end">${fmt(max * (1 - k / 2))}</text>`;
  }
  const step = (W - L - R) / Math.max(runs.length, 1), every = Math.ceil(runs.length / 12);
  runs.forEach((run, k) => {
    const x = L + step * (k + 0.5);
    if (k % every === 0) s += `<text x="${x}" y="${H - B + 12}" text-anchor="middle">${run.turn}</text>`;
    if (k === 0 || run.part !== runs[k - 1].part) s += `<text x="${x}" y="${H - B + 23}" text-anchor="middle" class="tick-part">P${run.part}</text>`;
  });
  return [s, step];
}

function tkRuns() {
  const turns = tk.data?.turns || [];
  return [...new Map(turns.map((r) => [r.run_id, r])).values()];
}
const tkGet = (run, agent) => (tk.data?.turns || []).find((r) => r.run_id === run.run_id && r.agent === agent);

// One bar per agent per turn (scratch, MemoRizz, naive from left to right), each a stack of segments.
function tkStacked(runs, step, max, segmentsOf, tipOf) {
  let s = "";
  const agents = tkAgents(), n = agents.length, gap = 1;
  const bw = Math.max(1.2, Math.min(W * 0.047, (step - 4) / n - gap));
  runs.forEach((run, k) => agents.forEach((agent, j) => {
    const r = tkGet(run, agent);
    if (!r) return;
    const x = L + step * (k + 0.5) - (n * bw + (n - 1) * gap) / 2 + j * (bw + gap);
    let y0 = H - B, total = 0;
    segmentsOf(r).forEach(([value, colour]) => {
      total += value;
      const h = ((H - T - B) * value) / max;
      if (h < 0.5) return;
      s += `<rect x="${x}" y="${y0 - h}" width="${bw}" height="${Math.max(h - 0.6, 0.5)}" fill="${colour}"/>`;
      y0 -= h;
    });
    s += `<rect x="${x}" y="${T}" width="${bw}" height="${H - T - B}" fill="transparent" data-tip="${esc(tipOf(r, k))}"/>`;
    if (bw >= 3.5) s += `<text x="${x + bw / 2}" y="${(total > 0 ? y0 : H - B) - 3}" text-anchor="middle" class="bar-tag">${total > 0 ? TK_TAG[agent] : "0"}</text>`;
  }));
  return s;
}

// Line charts: one full-height hover column per turn with a crosshair, so close points never hide each other.
function tkColumns(runs, step, tipOf) {
  return runs.map((run, k) => {
    const x = L + step * k;
    return `<g class="col"><line class="xhair" x1="${x + step / 2}" x2="${x + step / 2}" y1="${T}" y2="${H - B}"/><rect x="${x}" y="${T}" width="${step}" height="${H - T - B}" fill="transparent" data-tip="${esc(tipOf(run, k))}"/></g>`;
  }).join("");
}
// One line per agent through points {k, v}; dashed lines carry a second measure in the same colour.
function tkLine(points, step, max, colour, { dashed = false, dots = true, offset = 0 } = {}) {
  const p = points.map((q) => [L + step * (q.k + 0.5) + offset, yOf(q.v, max)]);
  let s = p.length > 1 ? `<polyline fill="none" stroke="${colour}" stroke-width="${dashed ? 1.4 : 2}" ${dashed ? 'stroke-dasharray="4 3" opacity="0.8"' : ""} stroke-linejoin="round" points="${p.map((q) => q.join(",")).join(" ")}"/>` : "";
  if (dots) {
    const r = Math.max(1.6, Math.min(4, step / 5));
    p.forEach(([x, y]) => { s += `<circle cx="${x}" cy="${y}" r="${r}" fill="${colour}" style="stroke:var(--panel)" stroke-width="1.2"/>`; });
  }
  return s;
}
const scored = (r) => r && r.accuracy && r.accuracy.score !== null && r.accuracy.score !== undefined;
const tkKey = (a) => `<br><span class="tk-key" style="--c:${TK.agents[a]}"></span>${TK_LABEL[a]}: `;

const tkHeader = (r, k) => `<b>${TK_LABEL[r.agent]} · turn ${r.turn} · Part ${r.part}</b>` + (r.test ? ` · ${esc(r.test)}` : "");
const tkTurnHeader = (run) => `<b>Turn ${run.turn} · Part ${run.part}</b>` + (run.test ? ` · ${esc(run.test)}` : "");
const tkQuestion = (r) => `<br><span class="tk-q">${esc(r.question.length > 120 ? r.question.slice(0, 120) + "…" : r.question)}</span>`;

function tkCharts(nested) {
  const runs = tkRuns();
  const empty = (id, message) => { const el = $("#tk-" + id); if (el) el.innerHTML = `<div class="placeholder">${message || "Run the memory workload or send messages on any Part page"}</div>`; };
  if (!$("#tk-latency")) return;
  tkLegends();
  if (!runs.length) { ["accuracy", "latency", "cost", "tokens"].forEach((id) => empty(id)); tkSummary(); tkTests(); tkTable(); return; }
  const turns = tk.data.turns, agents = tkAgents();
  const spread = (j) => (j - (agents.length - 1) / 2) * 1.5;      // keeps equal values of two agents apart

  // Accuracy: running % correct over the golden questions graded by the LLM judge, per agent.
  {
    const pts = Object.fromEntries(agents.map((a) => [a, []]));
    for (const agent of agents) {
      let n = 0, ok = 0;
      runs.forEach((run, k) => {
        const r = tkGet(run, agent);
        if (scored(r)) { n++; ok += r.accuracy.score; pts[agent].push({ k, v: (ok / n) * 100, r, n, ok }); }
      });
    }
    if (!agents.some((a) => pts[a].length)) empty("accuracy", "No answers graded yet");
    else {
      let [s, step] = tkFrame(100, (v) => v.toFixed(0) + "%", runs);
      agents.forEach((agent, j) => { s += tkLine(pts[agent], step, 100, TK.agents[agent], { offset: spread(j) }); });
      s += tkColumns(runs, step, (run, k) => tkTurnHeader(run) + agents.map((a) => {
        const q = pts[a].find((p) => p.k === k), r = tkGet(run, a);
        return tkKey(a) + (q
          ? `${q.r.accuracy.verdict} · running ${q.ok}/${q.n} = ${q.v.toFixed(0)}%` + (q.r.accuracy.missing?.length ? ` · missing: ${esc(q.r.accuracy.missing.join("; "))}` : "")
          : (r?.accuracy?.verdict || "—"));
      }).join("") + tkQuestion(run));
      $("#tk-accuracy").innerHTML = s + "</svg>";
    }
  }

  // Latency: per turn, one bar per agent stacked by phase.
  {
    const parts = (r) => [[r.latency.model_ms, TK.phases.model], [r.latency.memory_ms, TK.phases.memory], [r.latency.tools_ms, TK.phases.tools], [r.latency.other_ms, TK.phases.other]];
    const max = Math.max(...turns.map((r) => r.latency.total_ms), 1) * 1.1;
    let [s, step] = tkFrame(max / 1000, (v) => v.toFixed(v < 10 ? 1 : 0) + "s", runs);
    s += tkStacked(runs, step, max, parts, (r, k) => tkHeader(r, k) + ` · ${sec(r.latency.total_ms)}<br>model ${sec(r.latency.model_ms)} · memory ${sec(r.latency.memory_ms)} · tools ${sec(r.latency.tools_ms)} · other ${sec(r.latency.other_ms)}` + (r.cache_hit ? "<br>⚡ answered from the semantic cache" : "") + tkQuestion(r));
    $("#tk-latency").innerHTML = s + "</svg>";
  }

  // Cost: what each agent has spent so far, turn after turn (one line per agent).
  {
    const pts = Object.fromEntries(agents.map((a) => [a, []])), spent = Object.fromEntries(agents.map((a) => [a, 0]));
    runs.forEach((run, k) => agents.forEach((a) => {
      const r = tkGet(run, a);
      if (!r) return;
      spent[a] += r.cost_usd || 0;
      pts[a].push({ k, v: spent[a], r });
    }));
    const max = Math.max(...agents.map((a) => spent[a]), 0.000001) * 1.12;
    let [s, step] = tkFrame(max, usd, runs);
    agents.forEach((agent, j) => { s += tkLine(pts[agent], step, max, TK.agents[agent], { offset: spread(j) }); });
    s += tkColumns(runs, step, (run, k) => tkTurnHeader(run) + agents.map((a) => {
      const q = pts[a].find((p) => p.k === k);
      return tkKey(a) + (q
        ? `$${(q.r.cost_usd ?? 0).toFixed(6)} this turn · $${q.v.toFixed(5)} so far` + (q.r.cache_hit ? " · ⚡ semantic cache hit" : "")
        : "—");
    }).join("") + tkQuestion(run));
    $("#tk-cost").innerHTML = s + "</svg>";
  }

  // Context size: input tokens sent to the model each turn (all its model calls), solid; the prompt-cached part, dashed.
  {
    const pts = Object.fromEntries(agents.map((a) => [a, []])), cached = Object.fromEntries(agents.map((a) => [a, []]));
    runs.forEach((run, k) => agents.forEach((a) => {
      const r = tkGet(run, a);
      if (!r) return;
      pts[a].push({ k, v: r.usage.input_tokens, r });
      cached[a].push({ k, v: r.usage.cached_input_tokens, r });
    }));
    const max = Math.max(...turns.map((r) => r.usage.input_tokens), 1) * 1.12;
    let [s, step] = tkFrame(max, kTok, runs);
    agents.forEach((agent, j) => {
      if (cached[agent].some((q) => q.v)) s += tkLine(cached[agent], step, max, TK.agents[agent], { dashed: true, dots: false, offset: spread(j) });
      s += tkLine(pts[agent], step, max, TK.agents[agent], { offset: spread(j) });
    });
    s += tkColumns(runs, step, (run, k) => tkTurnHeader(run) + agents.map((a) => {
      const r = tkGet(run, a);
      return tkKey(a) + (r
        ? `${r.usage.input_tokens.toLocaleString()} input (${r.usage.cached_input_tokens.toLocaleString()} prompt-cached) · ${r.usage.output_tokens.toLocaleString()} output · ${r.usage.model_calls} model call${r.usage.model_calls === 1 ? "" : "s"}`
        : "—");
    }).join("") + tkQuestion(run));
    $("#tk-tokens").innerHTML = s + "</svg>";
  }
  if (tk.modal && !nested) tkOpenChart(tk.modal);
  tkSummary();
  tkTests();
  tkTable();
}

// ---- tables ----
function tkRowsTable(rows) {
  if (!rows.length) return '<p class="muted">No measurements yet.</p>';
  const keys = [...new Set(rows.flatMap(Object.keys))];
  const cell = (v) => (v && typeof v === "object" && "html" in v ? v.html : esc(v ?? ""));     // {html}: trusted markup
  return `<div class="tk-table-wrap"><table class="tk-table"><thead><tr>${keys.map((k) => `<th>${esc(k)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${keys.map((k) => `<td>${cell(r[k])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const TK_ROW = {
  accuracy: (r) => ({ test: r.test || "", verdict: r.accuracy?.verdict || "unscored", missing: (r.accuracy?.missing || []).join("; "), judge_reason: r.accuracy?.reason || "" }),
  latency: (r) => ({ total_s: (r.latency.total_ms / 1000).toFixed(2), model_s: (r.latency.model_ms / 1000).toFixed(2), memory_s: (r.latency.memory_ms / 1000).toFixed(2), tools_s: (r.latency.tools_ms / 1000).toFixed(2), other_s: (r.latency.other_ms / 1000).toFixed(2) }),
  cost: (r, spent) => ({ cost_usd: r.cost_usd, spent_so_far_usd: spent.toFixed(6), total_tokens: r.usage.total_tokens, model_calls: r.usage.model_calls, cache_hit: r.cache_hit ? "yes" : "" }),
  tokens: (r) => ({ input: r.usage.input_tokens, prompt_cached: r.usage.cached_input_tokens, output: r.usage.output_tokens, model_calls: r.usage.model_calls }),
};
function tkTable() {
  const el = $("#tk-turns");
  if (!el) return;
  const turns = tk.data?.turns || [];
  el.innerHTML = tkRowsTable(turns.map((r) => ({
    turn: r.turn, part: r.part, thread: r.thread, test: r.test || "", agent: TK_LABEL[r.agent], question: r.question,
    latency_s: (r.latency.total_ms / 1000).toFixed(2), tokens: r.usage.total_tokens,
    cached_input: r.usage.cached_input_tokens, output: r.usage.output_tokens, cost_usd: r.cost_usd,
    model_calls: r.usage.model_calls, tools: r.tool_calls.join(", "), cache: r.cache_hit ? "hit" : "",
    judge: r.accuracy?.verdict || "unscored",
    context: r.agent === "naive" ? "" : { html: `<a href="#/context/${Number(r.turn)}">context window</a>` },
  })));
}
function tkSummary() {
  const el = $("#tk-summary");
  if (!el) return;
  const s = tk.data?.summary, agents = tkAgents();
  if (!s || !agents.some((a) => s[a]?.turns)) { el.innerHTML = ""; return; }
  const row = (label, f) => `<tr><th>${label}</th>${agents.map((a) => `<td>${f(s[a])}</td>`).join("")}</tr>`;
  el.innerHTML = `<h3>Session summary <small>${tkRuns().length} measured turns</small></h3>
    <div class="tk-table-wrap"><table class="tk-table tk-summary-table"><thead><tr><th></th>${agents.map((a) => `<th><span class="tk-dot" style="--c:${TK.agents[a]}"></span>${TK_LABEL[a]}</th>`).join("")}</tr></thead><tbody>
    ${row(`Accuracy (LLM judge, graded turns)`, (x) => x.accuracy === null ? "—" : `${Math.round(x.accuracy * 100)}% · ${x.correct} of ${x.scored}`)}
    ${row("Total tokens", (x) => x.total_tokens.toLocaleString())}
    ${row("Input tokens (prompt-cached share)", (x) => `${x.input_tokens.toLocaleString()} (${Math.round(x.cached_share * 100)}%)`)}
    ${row("Output tokens", (x) => x.output_tokens.toLocaleString())}
    ${row("Total cost", (x) => "$" + x.total_cost_usd.toFixed(4))}
    ${row("Average latency", (x) => x.avg_latency_s.toFixed(2) + " s")}
    ${row("Slowest turn", (x) => x.max_latency_s.toFixed(2) + " s")}
    ${row("Model calls", (x) => x.model_calls)}
    ${row("Tool calls", (x) => x.tool_calls)}
    ${row("Answers served from the semantic cache", (x) => x.cache_hits)}
    ${row(`Judge cost (${esc(tk.data?.judge_model || "judge")}, not in the agents' cost)`, (x) => "$" + x.judge_cost_usd.toFixed(4))}
    </tbody></table></div>`;
}

// Accuracy by memory test: one row per kind of probe, a bar per agent.
function tkTests() {
  const el = $("#tk-tests");
  if (!el) return;
  const s = tk.data?.summary, tests = tk.data?.tests || {}, agents = tkAgents();
  const names = s ? [...new Set(agents.flatMap((a) => Object.keys(s[a]?.by_test || {})))] : [];
  if (!names.length) { el.innerHTML = ""; return; }
  const order = Object.keys(tests);
  names.sort((a, b) => (order.indexOf(a) + 99 * (order.indexOf(a) < 0)) - (order.indexOf(b) + 99 * (order.indexOf(b) < 0)));
  const bar = (agent, cell) => {
    if (!cell) return `<div class="tk-test-bar"><span class="tk-test-track"></span><span class="tk-test-val">—</span></div>`;
    const pct = Math.round((cell.correct / cell.scored) * 100);
    return `<div class="tk-test-bar" data-tip="${esc(`<b>${TK_LABEL[agent]}</b> · ${cell.correct} of ${cell.scored} correct`)}"><span class="tk-test-track"><span style="width:${pct}%;background:${TK.agents[agent]}"></span></span><span class="tk-test-val">${pct}% · ${cell.correct}/${cell.scored}</span></div>`;
  };
  el.innerHTML = `<h3>Accuracy by memory test <small>LLM judge · each probe tests one way memory can fail</small></h3>${tkAgentLegend()}
    <div class="tk-tests" style="--agents:${agents.length}">${names.map((name) => `<div class="tk-test-row"><div class="tk-test-name"><b>${esc(name)}</b><span>${esc(tests[name] || "")}</span></div>${agents.map((a) => bar(a, s[a].by_test?.[name])).join("")}</div>`).join("")}</div>`;
}

// ---- enlarge a chart ----
const tkModal = document.createElement("div");
tkModal.className = "tk-modal";
tkModal.hidden = true;
tkModal.setAttribute("role", "dialog");
tkModal.setAttribute("aria-modal", "true");
tkModal.innerHTML = '<div class="tk-modal-panel"><button class="tk-modal-close" aria-label="Close">×</button><div class="tk-modal-body"></div></div>';
document.body.append(tkModal);
function tkOpenChart(id) {
  const card = $("#tk-" + id)?.closest("article");
  if (!card) return;
  tk.modal = id;
  const spent = {};
  const rows = (tk.data?.turns || []).map((r) => {
    spent[r.agent] = (spent[r.agent] || 0) + (r.cost_usd || 0);
    return { turn: r.turn, part: r.part, agent: TK_LABEL[r.agent], question: r.question, ...TK_ROW[id](r, spent[r.agent]) };
  });
  const legend = card.querySelector(".tk-legend").outerHTML;
  [W, H, L, B] = [960, 400, 64, 44];
  tkCharts(true);
  const big = $("#tk-" + id).innerHTML;
  [W, H, L, B] = [300, 150, 40, 30];
  tkCharts(true);
  tkModal.querySelector(".tk-modal-body").innerHTML = `<h2>${card.querySelector("h3").innerHTML}</h2>${legend}<div class="tk-modal-chart">${big}</div><details><summary>Table view · ${rows.length} results</summary>${tkRowsTable(rows)}</details>`;
  if (tkModal.hidden) { tkModal.hidden = false; tkModal.querySelector(".tk-modal-close").focus(); }
}
function tkCloseChart() { tkModal.hidden = true; tk.modal = null; }
tkModal.querySelector(".tk-modal-close").onclick = tkCloseChart;
tkModal.onclick = (e) => { if (e.target === tkModal) tkCloseChart(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !tkModal.hidden) tkCloseChart(); });

// ---- the page ----
const tkAgentLegend = () => `<div class="tk-legend">${tkAgents().map((a) => `<span style="--c:${TK.agents[a]}" class="tk-agent">${TK_LABEL[a]} (${TK_TAG[a]})</span>`).join("")}</div>`;
const tkSegmentLegend = (entries) => `<div class="tk-legend tk-segments">${entries.map(([label, colour, cls]) => `<span style="--c:${colour}"${cls ? ` class="${cls}"` : ""}>${label}</span>`).join("")}</div>`;
// Card legends that list the agents follow the agents present (the naive baseline joins with the workload).
function tkLegends() {
  const agents = tkAgents().map((a) => [TK_LABEL[a], TK.agents[a]]);
  $$("[data-tk-legend]").forEach((el) => {
    const extra = el.dataset.tkLegend === "tokens" ? [["prompt-cached part", "var(--text-3)", "tk-dashed"]] : [];
    el.outerHTML = tkSegmentLegend([...agents, ...extra]).replace('class="tk-legend', `data-tk-legend="${el.dataset.tkLegend}" class="tk-legend`);
  });
  const heading = $(".tk-heading");
  if (heading) heading.innerHTML = tkAgentLegend();
}

function viewTokenomics() {
  setStage(`
    <header class="ff-head">
      <div class="ff-numeral">$</div>
      <div class="ff-head-body">
        <div class="ff-kicker">Measure the difference · scratch Memo vs MemoRizz Memo vs a naive agent</div>
        <h1 class="ff-title">Tokenomics</h1>
        <p class="ff-desc">Every message sent to both Memos on a Part page, and every turn of the memory workload, is measured the same way on every side: answer accuracy graded by an LLM judge; latency split into model, memory, tool and other time; input, prompt-cached and output tokens over every model call of the turn; and cost at OpenAI list prices from MemoRizz's rate card. The memory workload adds a third agent, a <b>naive</b> baseline with no memory engineering: it appends every message of the thread to the request, and nothing else.</p>
      </div>
    </header>
    <div id="page-banner">${healthBanner()}</div>
    <div class="panel tk-controls">
      <div class="panel-body">
        <button class="btn btn-accent" id="tk-run" type="button">${I.play} Run the memory workload</button>
        <button class="btn" id="tk-stop" type="button" hidden>${I.stop} Stop run</button>
        <button class="btn" id="tk-clear" type="button">${I.refresh} Clear measurements</button>
        <span class="tk-progress" id="tk-progress" aria-live="polite"></span>
      </div>
      <details class="tk-workload"><summary>What the workload asks: 30 turns at the full stack, in a fresh memory scope, with the judge's references</summary><p class="muted" id="tk-workload-intro"></p><ol id="tk-workload-list"></ol></details>
      <div class="tk-stacks" id="tk-stacks"></div>
    </div>
    <section class="tk-section">
      <div class="tk-heading">${tkAgentLegend()}</div>
      <div class="tk-charts">
        <article tabindex="0" title="Click to enlarge"><h3>Answer accuracy <small>Running % correct · graded turns · LLM judge</small></h3><div id="tk-accuracy" class="tk-chart"></div><div data-tk-legend="agents"></div></article>
        <article tabindex="0" title="Click to enlarge"><h3>Latency per turn <small>Seconds · one bar per agent: scratch, MemoRizz, naive</small></h3><div id="tk-latency" class="tk-chart"></div>${tkSegmentLegend([["Model", TK.phases.model], ["Memory", TK.phases.memory], ["Tools", TK.phases.tools], ["Other", TK.phases.other]])}</article>
        <article tabindex="0" title="Click to enlarge"><h3>Cumulative inference cost <small>${state.health?.provider === "ollama" ? "USD · open models on this machine through Ollama: no API cost" : "USD spent so far · OpenAI list prices · every model call"}</small></h3><div id="tk-cost" class="tk-chart"></div><div data-tk-legend="agents"></div></article>
        <article tabindex="0" title="Click to enlarge"><h3>Context size per turn <small>Input tokens sent to the model · all model calls of the turn</small></h3><div id="tk-tokens" class="tk-chart"></div><div data-tk-legend="tokens"></div></article>
      </div>
      <p class="muted tk-note">Turn numbers run left to right; the Part under a turn shows how far the Memos were built when it ran. Memory time is reads and writes outside model calls (SQL, embeddings, the Jev router); MemoRizz reports it from its memory-retrieval traces. The naive agent answers in the memory workload only: its context grows with every turn because it resends the whole thread, while the two Memos send what their memory selects. A turn with no cost, such as a MemoRizz semantic-cache hit, leaves its line flat. Accuracy counts turns with a reference only: a separate LLM judge (MEMO_JUDGE_MODEL) compares each answer with the facts it must contain, from the setup (persona, runbook, tools, the rebuild skill) or from what Ada said earlier; its tokens and cost are reported apart from the agents'. The workload's one compaction (a summary call per Memo after turn 20) is not a turn and is not charted; the naive agent never compacts. Embedding tokens are excluded on every side. List prices are not an invoice.</p>
      <div id="tk-tests-wrap" class="tk-tests-wrap"><div id="tk-tests"></div></div>
      <div id="tk-summary"></div>
      <details class="tk-turn-details"><summary>Turn-by-turn table</summary><div id="tk-turns"></div></details>
    </section>`, "var(--r6)");
  $$(".tk-charts article").forEach((card) => {
    const id = card.querySelector(".tk-chart").id.replace("tk-", "");
    const open = () => { if (tkRuns().length) tkOpenChart(id); };
    card.onclick = open;
    card.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } };
  });
  $("#tk-run").onclick = tkRunWorkload;
  $("#tk-stop").onclick = tkStopWorkload;
  $("#tk-clear").onclick = async () => { if (tk.running || tk.data?.running) return; tk.data = await postJSON("/api/tokenomics/clear", {}); tkCharts(); $("#tk-progress").textContent = "Measurements cleared; memory is unchanged."; };
  if (tk.running && tk.progress) $("#tk-progress").textContent = tk.progress;
  tkCharts();
  tkLoad();
}

async function tkLoad() {
  try {
    tk.data = await getJSON("/api/tokenomics");
    if (state.route !== "tokenomics") return;
    tkWorkload();
    tkCharts();
    tkControls();
    if (tk.data.running && !tk.running) tkFollow();
  } catch (error) {
    if ($("#page-banner")) $("#page-banner").innerHTML = healthBanner(error.message);
  }
}

// Run and Stop follow the server: a workload started in another tab shows as running here too, and can be stopped.
function tkControls() {
  const busy = tk.running || !!tk.data?.running, run = $("#tk-run"), stop = $("#tk-stop");
  if (!run || !stop) return;
  run.disabled = busy;
  run.innerHTML = busy ? `<span class="spinner"></span> Running…` : `${I.play} Run the memory workload`;
  stop.hidden = !busy;
  if (!busy) tk.stopping = false;
  stop.disabled = tk.stopping;
  stop.innerHTML = tk.stopping ? `<span class="spinner"></span> Stopping…` : `${I.stop} Stop run`;
}

async function tkStopWorkload() {
  if (tk.stopping) return;
  tk.stopping = true;
  tkControls();
  tkProgress("Stopping after the turn in progress; every turn measured so far stays on the charts…");
  try {
    await postJSON("/api/tokenomics/stop", {});
    tkPollStatus();
  } catch (error) {
    tk.stopping = false;
    tkControls();
    tkProgress(error.message);
  }
}

// Follow a workload this tab did not start: refresh the charts until it ends.
function tkFollow() {
  if (tk.watch) return;
  $("#tk-progress").textContent = "A workload started in another tab is running; the charts follow it.";
  tk.watch = setInterval(async () => {
    if (state.route !== "tokenomics" || tk.running) { clearInterval(tk.watch); tk.watch = null; return; }
    try { tk.data = await getJSON("/api/tokenomics"); } catch (_) { return; }
    tkCharts();
    tkControls();
    if (!tk.data.running) {
      clearInterval(tk.watch);
      tk.watch = null;
      $("#tk-progress").textContent = `The workload has ended: ${tkRuns().length} measured turns.`;
    }
  }, 4000);
}

function tkWorkload() {
  const items = tk.data?.workload || [], after = tk.data?.compact_after, main = items[0]?.thread;
  $("#tk-workload-intro").textContent = `Turns where Ada tells Memo something are unscored; every other turn is graded against its reference, for all three agents. Threads: "${main}"` +
    ([...new Set(items.map((q) => q.thread))].filter((t) => t !== main).map((t) => `, then "${t}" (a new thread)`).join("")) +
    (after ? `. After turn ${after}, both Memos compact "${main}" into a summary; the naive agent keeps resending all of it.` : ".");
  $("#tk-workload-list").innerHTML = items.map((q, k) =>
    `<li><span class="tk-test-tag" data-test="${esc(q.test)}">${esc(q.test)}</span>${q.thread !== main ? `<span class="tk-thread-tag">${esc(q.thread)}</span>` : ""}${esc(q.question)}<br><span class="tk-ref">${q.reference ? "Reference: " + esc(q.reference) : "Unscored: Memo is told this"}</span>${k + 1 === after ? `<div class="tk-compact-mark">Both Memos summarise thread "${esc(main)}" here, keeping its 4 newest messages.</div>` : ""}</li>`).join("");
  const st = tk.data?.stacks;
  $("#tk-stacks").innerHTML = st ? `<div><b>Scratch layers (Part ${st.part})</b> ${st.scratch.map((x) => `<code>${esc(x)}</code>`).join(" ")}</div><div><b>MemoRizz memory (Part ${st.part})</b> ${st.memorizz.map((x) => `<code>${esc(x)}</code>`).join(" ")}</div>` +
    (st.naive ? `<div><b>Naive agent</b> ${st.naive.map((x) => `<code>${esc(x)}</code>`).join(" ")}</div>` : "") : "";
}

// The run keeps going when you leave the page: its stream has its own abort controller (changing page
// cancels only chat streams), and every other page shows the run notification below.
async function tkRunWorkload() {
  if (tk.running || tk.data?.running) return;
  tk.running = true;
  tkControls();
  let stopped = null;
  cancelStream();
  tk.abort = new AbortController();
  const onPage = () => state.route === "tokenomics";
  setTimeout(tkPollStatus, 800);
  try {
    await streamSSE("/api/tokenomics/workload", {}, (event) => {
      if (event.type === "setup" && !tk.stopping) tkProgress(`Setting up Part ${event.part}…`);
      if (event.type === "progress" && !tk.stopping) tkProgress(event.note ? `${event.note}…` : `Turn ${event.index} of ${event.total} · ${event.test}${event.thread && event.thread !== "tokenomics" ? ` · thread ${event.thread}` : ""}: ${event.question}`);
      if (event.type === "turn" && onPage()) getJSON("/api/tokenomics").then((data) => { tk.data = data; if (onPage()) tkCharts(); }).catch(() => {});
      if (event.type === "stopped") stopped = event;
      if (event.type === "done") {
        tk.data = event;
        if (onPage()) { tkWorkload(); tkCharts(); }
        tkProgress(stopped
          ? `Stopped after turn ${stopped.after} of ${stopped.total}: the turns measured so far stay on the charts.`
          : "Workload complete: every turn above is measured.");
      }
      if (event.type === "error") tkProgress(event.message);
    }, tk.abort.signal);
  } catch (error) {
    if (error.name !== "AbortError") tkProgress(error.message);
  } finally {
    tk.running = false;
    if (tk.data) tk.data.running = false;
    tkControls();
    tkPollStatus();
  }
}

// ---- the run notification: other pages show how far a running workload is, and how it ended ----
const tkToast = document.createElement("div");
tkToast.className = "run-toast";
tkToast.hidden = true;
tkToast.setAttribute("role", "status");
tkToast.setAttribute("aria-live", "polite");
document.body.append(tkToast);
const tkStatus = { data: null, timer: null, seen: null };

async function tkPollStatus() {
  clearTimeout(tkStatus.timer);
  try { tkStatus.data = await getJSON("/api/tokenomics/status"); } catch (_) { return; }
  tkRenderToast();
  if (tkStatus.data.running) tkStatus.timer = setTimeout(tkPollStatus, 2500);
}

function tkRenderToast() {
  const s = tkStatus.data;
  const ended = s && !s.running && s.state !== "idle" ? `${s.state}-${s.finished_at}` : null;
  if (state.route === "tokenomics" && ended) tkStatus.seen = ended;      // the page itself shows how it ended
  if (!s || s.state === "idle" || state.route === "tokenomics" || (ended && ended === tkStatus.seen)) { tkToast.hidden = true; return; }
  const total = s.total || 30, done = s.completed || 0;
  const line = s.state === "stopping" ? `Stopping after turn ${s.index} of ${total}…`
    : s.state === "running" ? (s.note ? `${esc(s.note)}…` : `Turn ${s.index} of ${total}${s.test ? ` · ${esc(s.test)}` : ""}`)
    : s.state === "stopped" ? `Stopped after turn ${done} of ${total}; the measured turns stay on the charts.`
    : s.state === "failed" ? `Stopped by an error: ${esc(s.note || "")}`
    : `Complete: ${total} turns measured for scratch, MemoRizz and naive.`;
  tkToast.dataset.state = s.state;
  tkToast.innerHTML = `
    <div class="run-toast-head">${s.running ? '<span class="spinner"></span>' : s.state === "complete" ? I.check : I.stop}<b>Memory workload</b>
      ${s.running ? `<span class="run-toast-count">${done}/${total}</span>` : '<button class="run-toast-x" type="button" aria-label="Dismiss">×</button>'}</div>
    <div class="run-toast-line">${line}</div>
    ${s.running && s.question && !s.note ? `<div class="run-toast-q" title="${esc(s.question)}">${esc(s.question)}</div>` : ""}
    <div class="run-toast-bar"><i style="width:${Math.round((done / total) * 100)}%"></i></div>
    <div class="run-toast-actions"><a class="btn" href="#/tokenomics">Open Tokenomics</a>
      ${s.running ? `<button class="btn" type="button" data-stop ${s.state === "stopping" ? "disabled" : ""}>${I.stop} Stop run</button>` : ""}</div>`;
  tkToast.hidden = false;
  tkToast.querySelector(".run-toast-x")?.addEventListener("click", () => { tkStatus.seen = ended; tkToast.hidden = true; });
  tkToast.querySelector("[data-stop]")?.addEventListener("click", async (e) => {
    e.currentTarget.disabled = true;
    tk.stopping = tk.running;
    await postJSON("/api/tokenomics/stop", {}).catch(() => {});
    tkPollStatus();
  });
}
