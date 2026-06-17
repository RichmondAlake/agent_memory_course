/* ======================================================================
   AI Application Evaluation — single-page app (vanilla JS).
   Hash router, theme toggle, SSE-over-fetch streaming client, and one
   live evaluation view per form factor. Companion to the Maturity Ladder.
   ====================================================================== */

// ── icons ────────────────────────────────────────────────────────────
const I = {
  gauge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 13l4-3"/><path d="M3.5 18a9 9 0 1 1 17 0"/><circle cx="12" cy="13" r="1.4" fill="currentColor"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20l1-4.5A8 8 0 1 1 21 12Z"/></svg>',
  rag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="7" ry="2.7"/><path d="M5 5.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/><path d="M5 11.5v6c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-6"/></svg>',
  flow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="6" rx="1.5"/><rect x="14" y="9" width="7" height="6" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/><path d="M10 6h2.5a1.5 1.5 0 0 1 1.5 1.5V9M10 18h2.5a1.5 1.5 0 0 0 1.5-1.5V15"/></svg>',
  agent: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="7" width="14" height="12" rx="2.5"/><path d="M12 7V4M9 3.5h6M9 12h.01M15 12h.01M9.5 16h5"/></svg>',
  build: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m8 8-4 4 4 4M16 8l4 4-4 4"/><path d="m13.5 5-3 14"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13.5A8 8 0 1 1 10.5 4 6.3 6.3 0 0 0 20 13.5Z"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M7 5.5v13l11-6.5z" fill="currentColor"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9 17.5 20 6.5"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  tool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-9 9a2.1 2.1 0 0 1-3-3l9-9a3.5 3.5 0 0 1-1.6-1.6Z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/></svg>',
  menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></svg>',
  flag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4M5 4h11l-2 4 2 4H5"/></svg>',
};

// ── form factors (evaluation framing) ────────────────────────────────
const FF = [
  { id: "chatbot", rung: 1, nav: "Chatbot", icon: I.chat, accent: "var(--r1)",
    title: "Evaluating the Chatbot", kicker: "Form Factor 01",
    lead: "A bare chatbot's signature failures are hallucinating on data it was never given, and losing the thread across turns. So we measure exactly those — not generic 'quality'.",
    fails: "Hallucinates on unknown data · forgets earlier turns",
    how: "Abstention (reference-free judge + heuristic) · multi-turn memory (judge)" },
  { id: "rag", rung: 2, nav: "RAG", icon: I.rag, accent: "var(--r2)",
    title: "Evaluating RAG", kicker: "Form Factor 02",
    lead: "RAG has two stages that fail independently. Grade the evidence (retrieval) before the answer (generation) — then settle 'which retriever wins' on a real benchmark.",
    fails: "Wrong document retrieved · ungrounded answer",
    how: "recall@k / MRR (heuristic) · correctness & groundedness (judge) · BEIR precision/recall/NDCG" },
  { id: "workflow", rung: 3, nav: "Workflow", icon: I.flow, accent: "var(--r3)",
    title: "Evaluating the Workflow", kicker: "Form Factor 03",
    lead: "A workflow is a chain of typed steps. Evaluate each with the cheapest evaluator it allows: exact-match where there's a label, an LLM-judge where the output is free text.",
    fails: "Misroutes a ticket · weak or ungrounded reply",
    how: "category/urgency exact-match (heuristic) · reply helpfulness & groundedness (judge)" },
  { id: "agent", rung: 4, nav: "Agent", icon: I.agent, accent: "var(--r4)",
    title: "Evaluating the Agent", kicker: "Form Factor 04",
    lead: "An agent chooses its own path, so a correct-looking answer can hide a bad trajectory. We score it through LangSmith's three lenses — final response, trajectory, and single step.",
    fails: "Wrong tool · skips search · over-escalates",
    how: "final response (judge) · trajectory subsequence + exact tool set · first-tool + no-wrong-action" },
  { id: "builder", rung: 5, nav: "Autonomous Agent", icon: I.build, accent: "var(--r5)",
    title: "Evaluating the Autonomous Agent", kicker: "Form Factor 05",
    lead: "The top rung produces effects, not prose. So we evaluate the outcome: run the code it wrote against ground truth we compute ourselves — including on a batch it never saw.",
    fails: "Code looks right, produces wrong numbers · doesn't generalize",
    how: "runs clean + functional correctness (execute it!) · code quality (judge)" },
];
const FF_BY_ID = Object.fromEntries(FF.map((f) => [f.id, f]));

// metrics shown as fractional numbers rather than ✓/✗
const FRACTIONAL = new Set(["mrr", "recall@3", "trajectory_subseq",
  "precision@10", "recall@10", "NDCG@10"]);

// ── tiny utils ───────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtMetric = (k, v) => FRACTIONAL.has(k) ? v.toFixed(3) : Math.round(v * 100) + "%";
const prettyKey = (k) => k.replace(/_/g, " ").replace(/@/g, "@");

async function getJSON(url) { const r = await fetch(url); return r.json(); }

// SSE-over-fetch: POST a JSON body, parse the text/event-stream response.
async function streamSSE(url, body, onEvent, signal) {
  const res = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}), signal,
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

// ── app state ────────────────────────────────────────────────────────
const state = { health: null, suites: null, abort: null, currentRoute: "" };

function cancelStream() {
  if (state.abort) { try { state.abort.abort(); } catch (_) {} state.abort = null; }
}

// ── injected component styles (keep the shared stylesheet untouched) ──
function injectStyles() {
  const css = `
  .wrap{max-width:1080px;margin:0 auto;padding:30px 30px 90px}
  .page-head{display:flex;flex-direction:column;gap:6px;margin-bottom:6px}
  .kicker{font-family:var(--font-mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:600}
  .page-title{font-family:var(--font-serif);font-size:40px;line-height:1.05;margin:2px 0 0}
  .lead{color:var(--text-2);font-size:15px;max-width:70ch;margin:10px 0 0}
  .meta-row{display:flex;flex-wrap:wrap;gap:18px;margin:16px 0 6px;font-size:12.5px}
  .meta-row b{color:var(--text);font-weight:600}
  .meta-row span{color:var(--text-3)}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow);margin-top:18px}
  .card-h{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
  .card-t{font-size:16px;font-weight:600;margin:0;display:flex;align-items:center;gap:9px}
  .chip{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.04em;padding:3px 8px;border-radius:999px;border:1px solid var(--line-2);color:var(--text-2);white-space:nowrap}
  .chip.lens{color:var(--accent);border-color:color-mix(in oklab,var(--accent) 45%,transparent)}
  .blurb{color:var(--text-2);font-size:13.5px;margin:10px 0 0;max-width:74ch}
  .metric-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
  .btn{display:inline-flex;align-items:center;gap:8px;font-family:var(--font-sans);font-size:13.5px;font-weight:600;color:#fff;background:var(--accent);border:none;border-radius:var(--radius-sm);padding:9px 15px;cursor:pointer;transition:transform .1s var(--ease),filter .15s}
  .btn:hover{filter:brightness(1.08)}.btn:active{transform:translateY(1px)}
  .btn[disabled]{opacity:.55;cursor:default;filter:none}
  .btn svg{width:15px;height:15px}
  .progress{height:5px;border-radius:99px;background:var(--panel-3);overflow:hidden;margin-top:14px}
  .progress>i{display:block;height:100%;width:0;background:var(--accent);transition:width .3s var(--ease)}
  .cards-grid{display:flex;flex-wrap:wrap;gap:12px;margin-top:16px}
  .scorecard{flex:1 1 130px;min-width:120px;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:13px 14px}
  .scorecard .v{font-family:var(--font-serif);font-size:30px;line-height:1;color:var(--accent)}
  .scorecard .k{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.04em;color:var(--text-3);margin-top:7px;text-transform:lowercase}
  table.results{width:100%;border-collapse:collapse;margin-top:16px;font-size:12.5px}
  table.results th{text-align:left;font-family:var(--font-mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-3);padding:6px 9px;border-bottom:1px solid var(--line-2)}
  table.results td{padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--text-2)}
  table.results td.lbl{color:var(--text);max-width:300px}
  table.results td.prev{color:var(--text-3);font-size:11.5px}
  .pf{display:inline-flex;width:18px;height:18px;align-items:center;justify-content:center;border-radius:6px}
  .pf svg{width:13px;height:13px}
  .pf.ok{color:#1f8f5f;background:color-mix(in oklab,#25b3a3 18%,transparent)}
  .pf.no{color:#d2462f;background:color-mix(in oklab,#ef5a44 18%,transparent)}
  .pf.flag{color:var(--accent);background:color-mix(in oklab,var(--accent) 16%,transparent)}
  .pf.dim{color:var(--text-3);font-family:var(--font-mono);font-size:15px;line-height:18px}
  .run-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .model-sel{font-family:var(--font-mono);font-size:11.5px;color:var(--text);background:var(--panel-2);
    border:1px solid var(--line-2);border-radius:var(--radius-sm);padding:7px 9px;cursor:pointer;max-width:230px}
  .ranwith{font-family:var(--font-mono);font-size:11px;color:var(--text-3);margin-top:10px}
  .ranwith b{color:var(--text-2);font-weight:600}
  td.prev{max-width:340px}
  .cellout{color:var(--text-3);font-size:11.5px;line-height:1.5;cursor:pointer}
  .cellout.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .cellout:not(.clamp){white-space:pre-wrap}
  .chart{margin-top:16px;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:12px 14px}
  .chart-t{font-family:var(--font-mono);font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--text-3);margin-bottom:6px}
  .chart svg{width:100%;height:auto;display:block}
  .num{font-family:var(--font-mono);color:var(--text)}
  .pending{color:var(--text-3)}
  .scenario{background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:14px 16px;margin-top:12px}
  .scenario.active{box-shadow:var(--glow);border-color:transparent}
  .scenario .prompt{font-size:13.5px;color:var(--text);margin:0 0 8px}
  .traj{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
  .tool-chip{font-family:var(--font-mono);font-size:11px;padding:3px 9px;border-radius:999px;background:var(--panel-3);border:1px solid var(--line-2);color:var(--text);display:inline-flex;align-items:center;gap:6px}
  .tool-chip svg{width:12px;height:12px;color:var(--accent)}
  .arrow{color:var(--text-3)}
  .resp{font-size:12.5px;color:var(--text-2);margin-top:8px;white-space:pre-wrap;border-left:2px solid var(--line-2);padding-left:10px}
  .why{font-size:11.5px;color:var(--text-3);margin-top:6px;font-style:italic}
  .log{font-family:var(--font-mono);font-size:11.5px;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:12px;max-height:300px;overflow:auto;white-space:pre-wrap;margin-top:12px;color:var(--text-2)}
  .log .t{color:var(--accent)}
  pre.code{font-family:var(--font-mono);font-size:11.5px;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:12px;overflow:auto;max-height:340px;color:var(--text-2);margin-top:12px}
  .note{font-size:12.5px;color:var(--text-2);background:var(--panel-2);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:var(--radius-sm);padding:11px 14px;margin-top:16px}
  .ff-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:18px}
  .ff-card{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px 18px;box-shadow:var(--shadow);transition:transform .12s var(--ease),box-shadow .15s}
  .ff-card:hover{transform:translateY(-2px);box-shadow:var(--glow)}
  .ff-card .top{display:flex;align-items:center;gap:10px}
  .ff-card .node{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;color:#fff;background:var(--accent);font-family:var(--font-mono);font-weight:600;font-size:14px}
  .ff-card .ic{width:18px;height:18px;color:var(--accent);margin-left:auto}
  .ff-card h3{font-size:15px;margin:11px 0 0}
  .ff-card p{font-size:12.5px;color:var(--text-2);margin:7px 0 0}
  .ff-card .how{font-size:11.5px;color:var(--text-3);margin-top:9px;font-family:var(--font-mono)}
  .land-table{width:100%;border-collapse:collapse;margin-top:14px;font-size:12.5px}
  .land-table th,.land-table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
  .land-table th{font-family:var(--font-mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-3)}
  .land-table td:first-child{color:var(--text);font-weight:600;white-space:nowrap}
  .gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:16px}
  .gallery figure{margin:0;background:var(--panel-2);border:1px solid var(--line);border-radius:var(--radius-sm);overflow:hidden}
  .gallery img{width:100%;display:block;background:#fff}
  .gallery figcaption{font-size:11.5px;color:var(--text-3);padding:7px 10px}
  .metric-chip{cursor:pointer;transition:border-color .12s,color .12s}
  .metric-chip:hover{border-color:var(--accent);color:var(--accent)}
  .scorecard .k.metric-chip{display:inline-block;border:1px dashed var(--line-2);padding:2px 6px;border-radius:6px}
  .pop-scrim{position:fixed;inset:0;z-index:60;background:transparent}
  .popover{position:fixed;z-index:61;width:330px;max-width:calc(100vw - 24px);background:var(--panel);
    border:1px solid var(--line-2);border-radius:var(--radius);box-shadow:var(--glow);padding:15px 16px;
    animation:popin .12s var(--ease)}
  @keyframes popin{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
  .popover .ph{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .popover .pt{font-size:14.5px;font-weight:600}
  .popover .fam{font-family:var(--font-mono);font-size:9.5px;letter-spacing:.05em;text-transform:uppercase;
    padding:2px 7px;border-radius:999px;border:1px solid var(--line-2);color:var(--text-2)}
  .popover .pdef{font-size:12.5px;color:var(--text-2);margin:9px 0 0;line-height:1.5}
  .popover .pfam-blurb{font-size:11px;color:var(--text-3);margin-top:6px}
  .popover .want{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;margin-top:10px}
  .popover .want.high{color:#1f9d63}.popover .want.low{color:#d2462f}.popover .want.detector{color:var(--accent)}
  .popover .formula{font-family:var(--font-mono);font-size:11px;color:var(--text);background:var(--panel-2);
    border:1px solid var(--line);border-radius:7px;padding:7px 9px;margin-top:10px;overflow-x:auto}
  .popover .vizbox{margin-top:12px;background:var(--panel-2);border:1px solid var(--line);border-radius:9px;
    padding:10px;display:flex;justify-content:center}
  .popover .vizbox svg{width:100%;height:64px;max-width:280px}
  `;
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
}

// ── theme ────────────────────────────────────────────────────────────
const themeOf = () => document.documentElement.getAttribute("data-theme") || "dark";
const themeIcon = () => (themeOf() === "dark" ? I.moon : I.sun);
const themeLabel = () => (themeOf() === "dark" ? "Dark" : "Light");
function toggleTheme() {
  const t = themeOf() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("aieval-theme", t); } catch (_) {}
  const tl = $("#theme-label"), ti = $("#theme-toggle span span");
  if (tl) tl.textContent = themeLabel();
  if (ti) ti.innerHTML = themeIcon();
}

// ── sidebar + status ─────────────────────────────────────────────────
function statusInner() {
  const h = state.health;
  if (!h) return `<div class="status-row"><span class="dot pulse"></span><span class="muted">Connecting…</span></div>`;
  const rb = h.retrieval || {};
  const backend = rb.backend === "oracle" ? "Oracle AI DB" : rb.backend === "memory" ? "In-memory" : "warming…";
  const rdot = rb.ready ? "ok" : "warn pulse";
  const adot = h.agent_available ? "ok" : "off";
  const lsLabel = h.langsmith_ok ? "on" : h.langsmith_key_set ? "key set · unauthorized" : "local-only";
  const ldot = h.langsmith_ok ? "ok" : h.langsmith_key_set ? "warn" : "off";
  return `
    <div class="status-row"><span class="dot ${rdot}"></span><span>Retrieval · <b>${esc(backend)}</b></span></div>
    <div class="status-row"><span class="dot ${adot}"></span><span>Agent SDK · <b>${h.agent_available ? "ready" : "off"}</b></span></div>
    <div class="status-row"><span class="dot ${ldot}"></span><span>LangSmith · <b>${esc(lsLabel)}</b></span></div>
    <div class="status-row"><span class="dot ${h.api_key_set ? "ok" : "off"}"></span><span>Model · <b>${esc(h.model || "—")}</b></span></div>`;
}

function renderSidebar(activeId) {
  const items = [
    `<a class="nav-item nav-home ${activeId === "home" ? "active" : ""}" href="#/" style="--c:var(--text-2);animation-delay:0ms">
       <span class="nav-node">${I.home}</span><span class="nav-label">Overview</span></a>`,
    ...FF.map((f, i) => `
      <a class="nav-item ${activeId === f.id ? "active" : ""}" href="#/${f.id}" style="--c:${f.accent};animation-delay:${(i + 1) * 55}ms">
        <span class="nav-node">${f.rung}</span><span class="nav-label">${f.nav}</span>
        <span class="nav-rung">${f.icon}</span></a>`),
  ].join("");
  $("#sidebar").innerHTML = `
    <div class="brand">
      <span class="brand-glyph">${I.gauge}</span>
      <span class="brand-text"><b>AI Evaluation</b><span>Measuring every rung</span></span>
    </div>
    <div class="rail-label">The Ladder, Measured</div>
    <nav class="ladder-rail">${items}</nav>
    <div class="sidebar-foot">
      <div class="status-card" id="status-card">${statusInner()}</div>
      <button class="theme-toggle" id="theme-toggle">
        <span style="display:flex;align-items:center;gap:8px"><span>${themeIcon()}</span> <span id="theme-label">${themeLabel()}</span></span>
        <span class="toggle-track"></span>
      </button>
    </div>`;
  $("#theme-toggle").addEventListener("click", toggleTheme);
}

function refreshStatus() { const c = $("#status-card"); if (c) c.innerHTML = statusInner(); }

// ── score rendering helpers ──────────────────────────────────────────
// A metric's intent decides how to read a score: ↑ higher better, ↓ lower better (a risk),
// or a detector (firing = flagged, not "fail"). Drives the icon AND the color.
function wantOf(key) {
  const m = state.catalog && state.catalog.metrics && state.catalog.metrics[key];
  return (m && m.want) || "high";
}
const GREEN = "#3aa76d", AMBER = "#d99a2b", RED = "#d2462f";
function goodColor(key, v) {
  const w = wantOf(key);
  if (w === "detector") return "var(--accent)";       // neutral — firing is informative, not bad
  if (w === "low") return v <= 0.05 ? GREEN : v <= 0.5 ? AMBER : RED;   // risk: 0 is good
  return v >= 0.66 ? GREEN : v >= 0.33 ? AMBER : RED;  // quality: 1 is good
}

// Per-example cell — colored by the metric's intent so "0 PII leaked" reads as ✓, not ✗.
function cell(key, v) {
  if (v === undefined || v === null) return `<span class="pending">…</span>`;
  if (FRACTIONAL.has(key)) return `<span class="num">${v.toFixed(3)}</span>`;
  const w = wantOf(key), on = v >= 0.999;
  if (w === "low")  // risk metric: 1 = risk present (bad), 0 = clean (good)
    return on ? `<span class="pf no" title="risk present">${I.alert}</span>`
              : `<span class="pf ok" title="clean — no risk">${I.check}</span>`;
  if (w === "detector")  // a detector: 1 = flagged this input, 0 = did not flag (neither is "fail")
    return on ? `<span class="pf flag" title="flagged">${I.flag}</span>`
              : `<span class="pf dim" title="not flagged">·</span>`;
  return on ? `<span class="pf ok">${I.check}</span>` : `<span class="pf no">${I.x}</span>`;  // quality
}
function scorecards(metrics, agg) {
  return `<div class="cards-grid">` + metrics.map((m) => {
    const has = agg && agg[m] !== undefined;
    const col = has ? goodColor(m, agg[m]) : "var(--text-3)";
    return `<div class="scorecard"><div class="v" style="color:${col}">${has ? fmtMetric(m, agg[m]) : "—"}</div>` +
      `<div class="k metric-chip" data-metric="${esc(m)}">${esc(prettyKey(m))}</div></div>`;
  }).join("") + `</div>`;
}

// ── lightweight inline-SVG bar chart of a run's results ───────────────
function chartBars(items, { ymax = 1.0, title = "" } = {}) {
  if (!items.length) return "";
  const W = 600, H = 188, padL = 30, padB = 38, padT = 14, top = H - padB;
  const innerW = W - padL - 16, bw = Math.min(64, innerW / items.length - 16);
  const step = innerW / items.length;
  const grid = [0, 0.25, 0.5, 0.75, 1.0].map((g) => {
    const y = padT + (1 - g) * (top - padT);
    return `<line x1="${padL}" y1="${y}" x2="${W - 16}" y2="${y}" stroke="var(--line)"/>` +
      `<text x="${padL - 5}" y="${y + 3}" font-size="8.5" text-anchor="end" fill="var(--text-3)" font-family="monospace">${g.toFixed(2)}</text>`;
  }).join("");
  const bars = items.map((it, i) => {
    const x = padL + i * step + (step - bw) / 2;
    const h = Math.max(1, (Math.min(it.value, ymax) / ymax) * (top - padT));
    const y = top - h;
    const lab = String(it.label).split(/\s+/);
    const labels = lab.length > 1
      ? `<text x="${x + bw / 2}" y="${top + 13}" font-size="8.5" text-anchor="middle" fill="var(--text-3)">${esc(lab[0])}</text><text x="${x + bw / 2}" y="${top + 24}" font-size="8.5" text-anchor="middle" fill="var(--text-3)">${esc(lab.slice(1).join(" "))}</text>`
      : `<text x="${x + bw / 2}" y="${top + 14}" font-size="8.5" text-anchor="middle" fill="var(--text-3)">${esc(it.label)}</text>`;
    return `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="3" fill="${it.color}"/>` +
      `<text x="${x + bw / 2}" y="${y - 4}" font-size="10" text-anchor="middle" fill="var(--text)" font-family="monospace">${it.disp}</text>${labels}`;
  }).join("");
  return `<div class="chart">${title ? `<div class="chart-t">${esc(title)}</div>` : ""}<svg viewBox="0 0 ${W} ${H}">${grid}${bars}</svg></div>`;
}
function aggChart(metrics, agg, title) {
  const items = metrics.filter((m) => agg[m] !== undefined).map((m) => ({
    label: prettyKey(m), value: agg[m], disp: fmtMetric(m, agg[m]), color: goodColor(m, agg[m]),
  }));
  return chartBars(items, { title });
}

// A clickable metric chip (click → definition popover).
const mchip = (m) => `<span class="chip metric-chip" data-metric="${esc(m)}">${esc(prettyKey(m))}</span>`;
const mchips = (metrics) => (metrics || []).map(mchip).join("");

// ── metric definition popover ─────────────────────────────────────────
const A = "var(--accent)";
function vizFor(family) {
  const dim = "var(--text-3)", line = "var(--line-2)";
  switch (family) {
    case "ir": // ranked list with a relevant hit inside top-k
      return `<svg viewBox="0 0 240 64"><rect x="4" y="6" width="150" height="14" rx="3" fill="${A}"/>
        <rect x="4" y="24" width="120" height="14" rx="3" fill="${dim}" opacity=".5"/>
        <rect x="4" y="42" width="135" height="14" rx="3" fill="${dim}" opacity=".5"/>
        <rect x="2" y="3" width="170" height="38" rx="5" fill="none" stroke="${A}" stroke-dasharray="4 3"/>
        <text x="176" y="26" font-size="10" fill="${A}" font-family="monospace">top-k</text>
        <text x="158" y="17" font-size="10" fill="${A}" font-family="monospace">✓ relevant</text></svg>`;
    case "llm-judge": case "template": // input → judge → {score}
      return `<svg viewBox="0 0 240 64"><rect x="6" y="18" width="58" height="28" rx="4" fill="none" stroke="${line}"/>
        <text x="35" y="36" font-size="9" fill="${dim}" text-anchor="middle" font-family="monospace">output</text>
        <path d="M68 32h26" stroke="${dim}" stroke-width="1.5" marker-end="url(#a)"/>
        <circle cx="120" cy="32" r="18" fill="none" stroke="${A}" stroke-width="1.6"/>
        <path d="M112 30h16M120 24v4M114 38h12" stroke="${A}" stroke-width="1.5" fill="none"/>
        <text x="120" y="58" font-size="8.5" fill="${A}" text-anchor="middle" font-family="monospace">judge</text>
        <path d="M146 32h26" stroke="${dim}" stroke-width="1.5" marker-end="url(#a)"/>
        <rect x="176" y="18" width="60" height="28" rx="4" fill="none" stroke="${A}"/>
        <text x="206" y="36" font-size="9" fill="${A}" text-anchor="middle" font-family="monospace">{0…1}</text>
        <defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0l6 3-6 3z" fill="${dim}"/></marker></defs></svg>`;
    case "exact":
      return `<svg viewBox="0 0 240 64"><rect x="20" y="22" width="70" height="22" rx="4" fill="none" stroke="${A}"/>
        <text x="55" y="37" font-size="10" fill="${A}" text-anchor="middle" font-family="monospace">pred</text>
        <text x="118" y="38" font-size="16" fill="${dim}" text-anchor="middle">=</text>
        <rect x="146" y="22" width="70" height="22" rx="4" fill="none" stroke="${dim}"/>
        <text x="181" y="37" font-size="10" fill="${dim}" text-anchor="middle" font-family="monospace">gold</text>
        <path d="M150 12l4 4 8-9" stroke="#1f9d63" stroke-width="2.2" fill="none"/></svg>`;
    case "trajectory":
      return `<svg viewBox="0 0 240 64">${[0, 1, 2].map((i) => `<rect x="${10 + i * 78}" y="22" width="58" height="22" rx="11" fill="none" stroke="${i < 2 ? A : line}"/><text x="${39 + i * 78}" y="37" font-size="8.5" fill="${i < 2 ? A : dim}" text-anchor="middle" font-family="monospace">tool ${i + 1}</text>`).join("")}
        <path d="M68 33h16M146 33h16" stroke="${dim}" stroke-width="1.5" marker-end="url(#b)"/>
        <defs><marker id="b" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0l6 3-6 3z" fill="${dim}"/></marker></defs></svg>`;
    case "outcome":
      return `<svg viewBox="0 0 240 64"><rect x="20" y="10" width="200" height="44" rx="5" fill="none" stroke="${line}"/>
        <text x="30" y="30" font-size="10" fill="${dim}" font-family="monospace">$ python triage.py</text>
        <text x="30" y="46" font-size="10" fill="#1f9d63" font-family="monospace">exit 0 · counts ✓</text></svg>`;
    default: // heuristic
      return `<svg viewBox="0 0 240 64"><rect x="14" y="24" width="150" height="16" rx="3" fill="${dim}" opacity=".4"/>
        <rect x="58" y="24" width="44" height="16" rx="3" fill="${A}" opacity=".55"/>
        <circle cx="150" cy="44" r="11" fill="none" stroke="${A}" stroke-width="2"/><path d="M158 52l9 9" stroke="${A}" stroke-width="2.4"/></svg>`;
  }
}

function closePopover() { document.querySelectorAll(".pop-scrim,.popover").forEach((e) => e.remove()); }

function openPopover(key, anchor) {
  closePopover();
  const cat = state.catalog;
  const m = cat && cat.metrics && cat.metrics[key];
  if (!m) return;
  const fam = (cat.families && cat.families[m.family]) || { label: m.family, blurb: "" };
  const wantTxt = { high: "↑ higher is better", low: "↓ lower is better (a risk)", detector: "◎ detector — should fire on the bad input" }[m.want] || "";
  const scrim = document.createElement("div"); scrim.className = "pop-scrim";
  const pop = document.createElement("div"); pop.className = "popover";
  pop.innerHTML = `
    <div class="ph"><span class="pt">${esc(prettyKey(key))}</span><span class="fam">${esc(fam.label)}</span></div>
    <div class="pfam-blurb">${esc(fam.blurb)}</div>
    <div class="pdef">${esc(m.def)}</div>
    ${m.want ? `<div class="want ${m.want}">${esc(wantTxt)}</div>` : ""}
    ${m.formula ? `<div class="formula">${esc(m.formula)}</div>` : ""}
    <div class="vizbox">${vizFor(m.family)}</div>`;
  scrim.addEventListener("click", closePopover);
  document.body.appendChild(scrim); document.body.appendChild(pop);
  // position near the clicked chip, clamped to the viewport
  const r = anchor.getBoundingClientRect();
  const pw = pop.offsetWidth, ph = pop.offsetHeight;
  let left = Math.min(r.left, window.innerWidth - pw - 12);
  let top = r.bottom + 8;
  if (top + ph > window.innerHeight - 12) top = Math.max(12, r.top - ph - 8);
  pop.style.left = Math.max(12, left) + "px"; pop.style.top = top + "px";
}

// ── generic suite runner (FF1–FF3) ───────────────────────────────────
function suiteCard(suite) {
  const metrics = suite.metrics;
  return `
  <div class="card" data-suite="${suite.id}">
    <div class="card-h">
      <div>
        <h3 class="card-t">${esc(suite.title)}</h3>
        <div class="metric-chips"><span class="chip lens">${esc(suite.lens)}</span>
          <span class="chip">${suite.n} examples</span>
          ${mchips(metrics)}</div>
      </div>
      <div class="run-row">${modelSelect()}<button class="btn run" data-suite="${suite.id}">${I.play}<span>Run evaluation</span></button></div>
    </div>
    <p class="blurb">${esc(suite.blurb)}</p>
    <div class="progress" hidden><i></i></div>
    <div class="ranwith" hidden></div>
    <div class="cards-mount">${scorecards(metrics, null)}</div>
    <div class="chart-mount"></div>
    <div class="table-mount"></div>
  </div>`;
}

// A <select> of model options (system-under-test model — e.g. swap in a weaker Haiku).
function modelSelect() {
  const opts = (state.suites && state.suites.models && state.suites.models.options) || [];
  if (!opts.length) return "";
  return `<select class="model-sel" title="model under test (the judge stays on the default)">` +
    opts.map((o) => `<option value="${esc(o.id)}">${esc(o.label)}</option>`).join("") + `</select>`;
}

async function runSuite(suiteId, card, metrics) {
  const btn = $(".run", card);
  const model = ($(".model-sel", card) || {}).value || undefined;
  btn.disabled = true; btn.querySelector("span").textContent = "Running…";
  const bar = $(".progress", card); bar.hidden = false; bar.firstElementChild.style.width = "0%";
  const tableMount = $(".table-mount", card);
  $(".chart-mount", card).innerHTML = "";
  tableMount.innerHTML = `
    <table class="results"><thead><tr><th>example</th>${metrics.map((m) => `<th>${esc(prettyKey(m))}</th>`).join("")}<th>output</th></tr></thead><tbody></tbody></table>`;
  const tbody = $("tbody", tableMount);
  cancelStream(); state.abort = new AbortController();
  try {
    await streamSSE(`/api/eval/${suiteId}`, { model }, (ev) => {
      if (ev.type === "start" && ev.model) {
        const rw = $(".ranwith", card); rw.hidden = false;
        rw.innerHTML = `model under test: <b>${esc(ev.model)}</b> · judge: <b>${esc((state.health && state.health.model) || "default")}</b>`;
      } else if (ev.type === "example") {
        bar.firstElementChild.style.width = Math.round((ev.done / ev.total) * 100) + "%";
        const tr = document.createElement("tr");
        tr.innerHTML = `<td class="lbl">${esc(ev.label)}</td>` +
          metrics.map((m) => `<td>${cell(m, ev.scores[m])}</td>`).join("") +
          `<td class="prev"><div class="cellout clamp">${esc(ev.preview || "")}</div></td>`;
        tbody.appendChild(tr);
      } else if (ev.type === "summary") {
        $(".cards-mount", card).innerHTML = scorecards(metrics, ev.aggregate);
        $(".chart-mount", card).innerHTML = aggChart(metrics, ev.aggregate, "Results — mean score per metric");
      }
    }, state.abort.signal);
  } catch (e) {
    tableMount.insertAdjacentHTML("beforeend", `<div class="note">Run failed: ${esc(e.message)}</div>`);
  }
  bar.firstElementChild.style.width = "100%";
  btn.disabled = false; btn.querySelector("span").textContent = "Re-run";
}

// ── BEIR benchmark panel (FF2) ───────────────────────────────────────
function beirDatasetSelect() {
  const ds = (state.suites && state.suites.beir && state.suites.beir.datasets) || [{ id: "scifact", label: "scifact" }];
  return `<select class="model-sel" id="beir-dataset" title="which BEIR benchmark to bake off">` +
    ds.map((d) => `<option value="${esc(d.id)}">${esc(d.label)}</option>`).join("") + `</select>`;
}
function beirPanel() {
  const metrics = ["precision@10", "recall@10", "NDCG@10"];
  return `
  <div class="card" id="beir-card">
    <div class="card-h">
      <div><h3 class="card-t">${I.spark} Retrieval Bake-off — BEIR</h3>
        <div class="metric-chips"><span class="chip lens">benchmark · qrels</span>
          <span class="chip">${(state.suites?.beir?.n_queries) || 50} queries</span>
          ${mchips(metrics)}</div></div>
      <div class="run-row">${beirDatasetSelect()}<button class="btn" id="beir-run">${I.play}<span>Run bake-off</span></button></div>
    </div>
    <p class="blurb">The toy set above saturates (vector recall@3 hits 1.0). To crown a real winner you need many docs, many queries, and expert relevance labels. Score keyword / vector / hybrid on a real BEIR benchmark — each loaded from a precomputed seed (skips the slow embed). Try <b>scifact</b> (science, ~1 relevant doc/query → precision capped low) and <b>fiqa</b> (finance, ~2.6 relevant/query → precision runs higher): the winner — and the metric profile — can differ by domain.</p>
    <div class="progress" hidden><i></i></div>
    <div id="beir-status" class="why"></div>
    <div id="beir-table"></div>
    <div id="beir-chart"></div>
  </div>`;
}

function beirChart(rows, k, ds = "scifact") {
  const techs = ["keyword", "vector", "hybrid"];
  const cols = [`precision@${k}`, `recall@${k}`, `NDCG@${k}`];
  const colors = { [cols[0]]: "#4C72B0", [cols[1]]: "#DD8452", [cols[2]]: "#55A868" };
  const W = 600, H = 216, padL = 30, padB = 50, padT = 16, top = H - padB;
  const grid = [0, 0.25, 0.5, 0.75, 1].map((g) => { const y = padT + (1 - g) * (top - padT);
    return `<line x1="${padL}" y1="${y}" x2="${W - 12}" y2="${y}" stroke="var(--line)"/><text x="${padL - 5}" y="${y + 3}" font-size="8" text-anchor="end" fill="var(--text-3)" font-family="monospace">${g.toFixed(2)}</text>`; }).join("");
  const gw = (W - padL - 16) / techs.length, bw = Math.min(28, (gw - 22) / cols.length);
  let bars = "";
  techs.forEach((t, gi) => {
    const gx = padL + gi * gw + 12;
    cols.forEach((c, ci) => {
      const v = rows[t] ? rows[t][c] : 0, h = Math.max(1, v * (top - padT)), x = gx + ci * (bw + 5), y = top - h;
      bars += `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="2" fill="${colors[c]}"/><text x="${x + bw / 2}" y="${y - 3}" font-size="7.5" text-anchor="middle" fill="var(--text-2)" font-family="monospace">${v.toFixed(2)}</text>`;
    });
    bars += `<text x="${gx + (cols.length * (bw + 5)) / 2 - 2}" y="${top + 15}" font-size="10" text-anchor="middle" fill="var(--text)">${t}</text>`;
  });
  const legend = cols.map((c, i) => `<rect x="${padL + i * 150}" y="${H - 14}" width="9" height="9" rx="2" fill="${colors[c]}"/><text x="${padL + i * 150 + 13}" y="${H - 6}" font-size="8.5" fill="var(--text-3)" font-family="monospace">${esc(c)}</text>`).join("");
  return `<div class="chart"><div class="chart-t">BEIR ${esc(ds)} — keyword vs vector vs hybrid</div><svg viewBox="0 0 ${W} ${H}">${grid}${bars}${legend}</svg></div>`;
}

async function runBeir() {
  const card = $("#beir-card"), btn = $("#beir-run");
  const dataset = ($("#beir-dataset") || {}).value || "scifact";
  btn.disabled = true; btn.querySelector("span").textContent = "Running…";
  const bar = $(".progress", card); bar.hidden = false; bar.firstElementChild.style.width = "10%";
  const techniques = ["keyword", "vector", "hybrid"];
  const rows = {};
  const render = (k = 10) => {
    const cols = [`precision@${k}`, `recall@${k}`, `NDCG@${k}`];
    $("#beir-table").innerHTML = `<table class="results"><thead><tr><th>technique</th>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>` +
      techniques.map((t) => `<tr><td class="lbl">${t}</td>${cols.map((c) => `<td>${rows[t] ? `<span class="num">${rows[t][c].toFixed(3)}</span>` : '<span class="pending">…</span>'}</td>`).join("")}</tr>`).join("") + `</tbody></table>`;
  };
  render();
  cancelStream(); state.abort = new AbortController();
  try {
    await streamSSE("/api/eval/beir", { k: 10, dataset }, (ev) => {
      if (ev.type === "status") $("#beir-status").textContent = ev.message;
      else if (ev.type === "technique") { rows[ev.name] = ev.metrics; bar.firstElementChild.style.width = (Object.keys(rows).length / 3 * 90 + 10) + "%"; render(); }
      else if (ev.type === "summary") { render(ev.k); $("#beir-chart").innerHTML = beirChart(rows, ev.k, ev.dataset || dataset); $("#beir-table").insertAdjacentHTML("beforeend", `<div class="note"><b>Read it in context:</b> vector & hybrid usually lead on recall@10 and NDCG@10 — semantics matter for paraphrased queries. <b>precision@10</b> depends on how many relevant docs a query has: ~0.1 ceiling on <b>scifact</b> (~1 relevant), noticeably higher on <b>fiqa</b> (~2.6 relevant). Always read the metrics against the dataset.</div>`); }
      else if (ev.type === "error") $("#beir-table").innerHTML = `<div class="note">Bake-off failed: ${esc(ev.message)}</div>`;
    }, state.abort.signal);
  } catch (e) { $("#beir-table").innerHTML = `<div class="note">Bake-off failed: ${esc(e.message)}</div>`; }
  bar.firstElementChild.style.width = "100%";
  btn.disabled = false; btn.querySelector("span").textContent = "Re-run bake-off";
}

// ── agent (FF4) ──────────────────────────────────────────────────────
function agentView(f) {
  const meta = state.suites?.agent || { scenarios: [], metrics: [] };
  return `
  ${pageHead(f)}
  <div class="card">
    <div class="card-h">
      <div><h3 class="card-t">${I.agent} Three lenses, run live</h3>
        <div class="metric-chips">${mchips(meta.metrics)}</div></div>
      <button class="btn" id="agent-run">${I.play}<span>Run agent evaluation</span></button>
    </div>
    <p class="blurb">Each scenario runs the real <code>claude-agent-sdk</code> agent with two tools. We capture its <b>trajectory</b> of tool calls (the runtime hides the built-in discovery call) and score the <b>final response</b>, the <b>trajectory</b>, and <b>single-step</b> decisions.</p>
    <div class="progress" hidden><i></i></div>
    <div class="cards-mount">${scorecards(meta.metrics, null)}</div>
    <div class="chart-mount"></div>
    <div id="agent-scenarios">${meta.scenarios.map((s) => scenarioCard(s)).join("")}</div>
  </div>`;
}
function scenarioCard(s) {
  return `<div class="scenario" id="sc-${s.id}">
    <p class="prompt"><b>${esc(s.id)}</b> — ${esc(s.prompt)}</p>
    <div class="metric-chips"><span class="chip">expected: ${s.expected.join(" → ") || "none"}</span>${s.forbidden.length ? `<span class="chip">must not: ${s.forbidden.join(", ")}</span>` : ""}</div>
    <div class="traj" data-traj="${s.id}"></div>
    <div class="sc-scores"></div></div>`;
}
async function runAgent() {
  const btn = $("#agent-run"); btn.disabled = true; btn.querySelector("span").textContent = "Running agents…";
  const card = btn.closest(".card"), bar = $(".progress", card); bar.hidden = false; bar.firstElementChild.style.width = "5%";
  let metrics = state.suites.agent.metrics, total = 1, done = 0;
  cancelStream(); state.abort = new AbortController();
  try {
    await streamSSE("/api/eval/agent", {}, (ev) => {
      if (ev.type === "start") { metrics = ev.metrics; total = ev.total; }
      else if (ev.type === "scenario_start") { const el = $(`#sc-${ev.id}`); if (el) el.classList.add("active"); $(`[data-traj="${ev.id}"]`).innerHTML = `<span class="why">running…</span>`; }
      else if (ev.type === "tool_use") {
        const t = $(`[data-traj="${ev.id}"]`); if (t.querySelector(".why")) t.innerHTML = "";
        if (t.children.length) t.insertAdjacentHTML("beforeend", `<span class="arrow">→</span>`);
        t.insertAdjacentHTML("beforeend", `<span class="tool-chip">${I.tool}${esc(ev.tool)}</span>`);
      } else if (ev.type === "scenario_scores") {
        done++; bar.firstElementChild.style.width = Math.round(done / total * 100) + "%";
        const el = $(`#sc-${ev.id}`); el.classList.remove("active");
        $(".sc-scores", el).innerHTML =
          `<table class="results"><tbody><tr>${metrics.map((m) => `<td><span class="why">${esc(prettyKey(m))}</span> ${cell(m, ev.scores[m])}</td>`).join("")}</tr></tbody></table>
           <div class="resp">${esc(ev.response)}</div>${ev.comment ? `<div class="why">judge: ${esc(ev.comment)}</div>` : ""}`;
      } else if (ev.type === "summary") { $(".cards-mount", card).innerHTML = scorecards(metrics, ev.aggregate); $(".chart-mount", card).innerHTML = aggChart(metrics, ev.aggregate, "Agent evaluation — mean score per metric"); }
      else if (ev.type === "error") { $("#agent-scenarios").insertAdjacentHTML("afterbegin", `<div class="note">${esc(ev.message)}</div>`); }
    }, state.abort.signal);
  } catch (e) { card.insertAdjacentHTML("beforeend", `<div class="note">Run failed: ${esc(e.message)}</div>`); }
  bar.firstElementChild.style.width = "100%";
  btn.disabled = false; btn.querySelector("span").textContent = "Re-run agent evaluation";
}

// ── builder (FF5) ────────────────────────────────────────────────────
function builderView(f) {
  const metrics = state.suites?.builder?.metrics || [];
  return `
  ${pageHead(f)}
  <div class="card">
    <div class="card-h">
      <div><h3 class="card-t">${I.build} Outcome evaluation — run the artifact</h3>
        <div class="metric-chips">${mchips(metrics)}</div></div>
      <button class="btn" id="builder-run">${I.play}<span>Build &amp; evaluate</span></button>
    </div>
    <p class="blurb">The builder agent writes a <code>triage.py</code> CLI and runs it on two ticket batches. We then <b>execute its tool ourselves</b> on each batch — including one it never saw — and compare the report to a breakdown we compute independently. The strongest evaluator here isn't a judge; it's running the code.</p>
    <div class="progress" hidden><i></i></div>
    <div class="cards-mount">${scorecards(metrics, null)}</div>
    <div class="chart-mount"></div>
    <div id="builder-log" class="log" hidden></div>
    <div id="builder-art"></div>
    <div id="builder-rows"></div>
  </div>`;
}
async function runBuilder() {
  const btn = $("#builder-run"); btn.disabled = true; btn.querySelector("span").textContent = "Building…";
  const card = btn.closest(".card"), bar = $(".progress", card); bar.hidden = false; bar.firstElementChild.style.width = "4%";
  const log = $("#builder-log"); log.hidden = false; log.innerHTML = "";
  let metrics = state.suites.builder.metrics;
  const addLog = (html) => { log.insertAdjacentHTML("beforeend", html + "\n"); log.scrollTop = log.scrollHeight; };
  cancelStream(); state.abort = new AbortController();
  try {
    await streamSSE("/api/eval/builder", {}, (ev) => {
      if (ev.type === "start") { addLog(`<span class="t">sandbox</span> ${esc(ev.sandbox)}`); bar.firstElementChild.style.width = "12%"; }
      else if (ev.type === "tool_use") { addLog(`<span class="t">🔧 ${esc(ev.tool)}</span> ${esc(JSON.stringify(ev.input).slice(0, 120))}`); bar.firstElementChild.style.width = "45%"; }
      else if (ev.type === "text") { addLog(esc(ev.text.slice(0, 300))); }
      else if (ev.type === "evaluating") { addLog(`<span class="t">evaluating…</span> running triage.py on both batches`); bar.firstElementChild.style.width = "80%"; }
      else if (ev.type === "artifact") { $("#builder-art").innerHTML = `<pre class="code">${esc(ev.content)}</pre>`; }
      else if (ev.type === "row") {
        const rowsEl = $("#builder-rows");
        if (!rowsEl.querySelector("table")) rowsEl.innerHTML = `<table class="results"><thead><tr><th>batch</th>${metrics.map((m) => `<th>${esc(prettyKey(m))}</th>`).join("")}<th>check</th></tr></thead><tbody></tbody></table>`;
        $("tbody", rowsEl).insertAdjacentHTML("beforeend", `<tr><td class="lbl">${esc(ev.label)}</td>${metrics.map((m) => `<td>${cell(m, ev.scores[m])}</td>`).join("")}<td class="prev">${esc(ev.comment)}</td></tr>`);
      } else if (ev.type === "summary") {
        $(".cards-mount", card).innerHTML = scorecards(metrics, ev.aggregate);
        $(".chart-mount", card).innerHTML = aggChart(metrics, ev.aggregate, "Outcome evaluation — mean score per metric");
        if (ev.code_quality_reason) $("#builder-rows").insertAdjacentHTML("beforeend", `<div class="why">code-quality judge: ${esc(ev.code_quality_reason)}</div>`);
      } else if (ev.type === "build_error" || ev.type === "error") { addLog(`<span class="t">error</span> ${esc(ev.message)}`); }
    }, state.abort.signal);
  } catch (e) { card.insertAdjacentHTML("beforeend", `<div class="note">Run failed: ${esc(e.message)}</div>`); }
  bar.firstElementChild.style.width = "100%";
  btn.disabled = false; btn.querySelector("span").textContent = "Re-build & evaluate";
}

// ── page scaffolding ─────────────────────────────────────────────────
function pageHead(f) {
  return `<div class="page-head">
    <span class="kicker">${esc(f.kicker)} — Evaluation</span>
    <h1 class="page-title">${esc(f.title)}</h1>
    <p class="lead">${esc(f.lead)}</p>
    <div class="meta-row"><span>Fails by:</span> <b>${esc(f.fails)}</b></div>
    <div class="meta-row"><span>Measured with:</span> <b>${esc(f.how)}</b></div>
  </div>`;
}

async function renderGallery(page) {
  try {
    const data = await getJSON("/api/images");
    const imgs = (data.pages || {})[page] || [];
    if (!imgs.length) return "";
    return `<div class="gallery">` + imgs.map((im) => `<figure><img loading="lazy" src="${esc(im.src)}" alt="${esc(im.caption)}"><figcaption>${esc(im.caption)}</figcaption></figure>`).join("") + `</div>`;
  } catch (_) { return ""; }
}

function suiteSection(ff) {
  const list = (state.suites?.suites?.[ff]) || [];
  return list.map((s) => suiteCard(s)).join("");
}

async function renderView() {
  const stage = $("#stage");
  const route = (location.hash || "#/").replace(/^#\//, "") || "home";
  state.currentRoute = route;
  renderSidebar(route === "home" ? "home" : route);
  cancelStream();

  if (route === "home") {
    stage.innerHTML = `<div class="wrap">
      <div class="page-head">
        <span class="kicker">AI Application Evaluation</span>
        <h1 class="page-title">You can't improve what you can't measure.</h1>
        <p class="lead">A companion to the AI Maturity Ladder: instead of <i>building</i> the five form factors, this app <b>evaluates</b> them — each with the metric that fits how it fails. Every score is computed live against the real systems (Oracle-backed retrieval, Claude as model <i>and</i> judge, the agent SDK), and packaged the LangSmith way: <b>dataset → target → evaluators → experiment</b>.</p>
      </div>
      <div class="note">Pick a rung from the left to run its evaluation. Scores compute locally; with a <code>LANGSMITH_API_KEY</code> set, the same datasets, targets, and evaluators also upload as versioned experiments — status is shown bottom-left.</div>
      <table class="land-table"><thead><tr><th>Form factor</th><th>What can go wrong</th><th>How we evaluate it</th></tr></thead><tbody>
        ${FF.map((f) => `<tr><td>${f.nav}</td><td>${esc(f.fails)}</td><td>${esc(f.how)}</td></tr>`).join("")}
      </tbody></table>
      <div class="ff-grid">${FF.map((f) => `
        <a class="ff-card" href="#/${f.id}" style="--accent:${f.accent}">
          <div class="top"><span class="node">${f.rung}</span><span class="ic">${f.icon}</span></div>
          <h3>${esc(f.title)}</h3><p>${esc(f.lead)}</p><div class="how">${esc(f.how)}</div></a>`).join("")}</div>
    </div>`;
    return;
  }

  const f = FF_BY_ID[route];
  if (!f) { location.hash = "#/"; return; }
  stage.style.setProperty("--accent", f.accent);
  document.documentElement.style.setProperty("--accent", f.accent);

  if (route === "agent") { stage.innerHTML = `<div class="wrap">${agentView(f)}</div>`; $("#agent-run").addEventListener("click", runAgent); return; }
  if (route === "builder") { stage.innerHTML = `<div class="wrap">${builderView(f)}</div>`; $("#builder-run").addEventListener("click", runBuilder); return; }

  // chatbot / rag / workflow → suite cards (+ BEIR for rag)
  const beir = route === "rag" ? beirPanel() : "";
  stage.innerHTML = `<div class="wrap">${pageHead(f)}${suiteSection(route)}${beir}</div>`;
  stage.querySelectorAll(".card .run").forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".card");
      const sid = btn.dataset.suite;
      const suite = (state.suites.suites[route] || []).find((s) => s.id === sid);
      runSuite(sid, card, suite.metrics);
    });
  });
  if (route === "rag") $("#beir-run").addEventListener("click", runBeir);
}

// ── boot ─────────────────────────────────────────────────────────────
async function boot() {
  injectStyles();
  renderSidebar("home");
  try { state.health = await getJSON("/api/health"); } catch (_) {}
  try { state.suites = await getJSON("/api/suites"); state.catalog = state.suites && state.suites.catalog; } catch (_) {}
  refreshStatus();
  await renderView();
  window.addEventListener("hashchange", () => { closePopover(); renderView(); });
  // Click any metric chip / scorecard label to see its definition.
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".metric-chip");
    if (chip && chip.dataset.metric) { e.preventDefault(); e.stopPropagation(); openPopover(chip.dataset.metric, chip); return; }
    const out = e.target.closest(".cellout");        // click an output cell to expand/collapse it
    if (out) out.classList.toggle("clamp");
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePopover(); });
  window.addEventListener("resize", closePopover);
  setInterval(async () => { try { state.health = await getJSON("/api/health"); refreshStatus(); } catch (_) {} }, 8000);
}
boot();
