/* ======================================================================
   Context window — what each agent sent to the model on every call of a
   measured turn, section by section, in the order the model reads it:
   instructions, tool schemas, then the messages. The bar under each call
   is the request at scale; its hatched part is the prefix OpenAI served
   from its prompt cache. Loaded before app.js; uses its helpers ($, $$,
   esc, getJSON, setStage, healthBanner, state, I) at call time.
   ====================================================================== */

const CW_COLOUR = {
  system: "#8d8a82", tools: "#5b8def", memory: "#e7a033", context: "#d0603a",
  history: "#4fa3c7", query: "#e05d7b", tool_io: "#8fbf3a",
};
const CW_OPEN = new Set(["memory", "context", "query", "tool_io"]);   // expanded by default
const cw = { turns: [], record: null, call: { scratch: 0, memorizz: 0 } };
const cwTok = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString());

function viewContext(turnNo) {
  setStage(`
    <header class="ff-head">
      <div class="ff-numeral cw-numeral">${I.window}</div>
      <div class="ff-head-body">
        <div class="ff-kicker">Measure · what each agent sent to the model</div>
        <h1 class="ff-title">Context window</h1>
        <p class="ff-desc">Every model call of every measured turn, for both agents, section by section in the order the model reads it: instructions, tool schemas, then the messages. Scratch shows the request it built from your <code>SCRATCH_*</code> tables; MemoRizz shows the context snapshot it stored for each call. The hatched part of each bar is the prefix OpenAI served from its prompt cache.</p>
      </div>
    </header>
    <div id="page-banner">${healthBanner()}</div>
    <div class="panel cw-controls">
      <div class="panel-body">
        <button class="btn" id="cw-prev" type="button" aria-label="Previous turn">←</button>
        <label class="cw-pick"><span class="sr-only">Turn</span><select id="cw-turn" aria-label="Turn"></select></label>
        <button class="btn" id="cw-next" type="button" aria-label="Next turn">→</button>
      </div>
      <div class="cw-question" id="cw-question"></div>
    </div>
    <div class="tk-legend cw-legend" id="cw-legend"></div>
    <div class="duo cw-duo" id="cw-duo"></div>
    <p class="muted tk-note">Token counts on sections are tiktoken estimates; the input, cached and output counts above each bar are OpenAI's own. The bar scales the sections to OpenAI's input count. OpenAI caches a prefix in steps of 1,024 tokens, so a section after the first change since the previous call is sent at full price. A turn can have several calls: the steps of the tool loop, and calls a scratch memory layer makes itself (entity extraction).</p>`, "var(--r1)");
  $("#cw-turn").onchange = (e) => { location.hash = `#/context/${e.target.value}`; };
  $("#cw-prev").onclick = () => cwStep(-1);
  $("#cw-next").onclick = () => cwStep(1);
  cwLoad(turnNo);
}

function cwStep(delta) {
  const index = cw.turns.findIndex((t) => t.turn === cw.record?.turn) + delta;
  if (index >= 0 && index < cw.turns.length) location.hash = `#/context/${cw.turns[index].turn}`;
}

async function cwLoad(turnNo) {
  try {
    cw.turns = (await getJSON("/api/context")).turns;
    if (!state.route.startsWith("context")) return;
    if (!cw.turns.length) {
      $("#cw-duo").innerHTML = `<div class="reply-empty cw-empty">No turns yet. Send a message on a Part page, or run the memory workload on the Tokenomics page: each turn's context windows appear here.</div>`;
      $("#cw-turn").innerHTML = "<option>No turns yet</option>";
      $("#cw-prev").disabled = $("#cw-next").disabled = true;
      return;
    }
    const chosen = cw.turns.find((t) => t.turn === turnNo) || cw.turns[cw.turns.length - 1];
    $("#cw-turn").innerHTML = cw.turns.map((t) => `<option value="${t.turn}" ${t.turn === chosen.turn ? "selected" : ""}>${esc(`Turn ${t.turn} · Part ${t.part} · ${t.thread} · ${t.question.length > 70 ? t.question.slice(0, 69) + "…" : t.question}`)}</option>`).join("");
    const index = cw.turns.indexOf(chosen);
    $("#cw-prev").disabled = index === 0;
    $("#cw-next").disabled = index === cw.turns.length - 1;
    cw.record = await getJSON(`/api/context/${chosen.turn}`);
    if (!state.route.startsWith("context")) return;
    cw.call = { scratch: 0, memorizz: 0 };
    cwRender();
  } catch (error) {
    if ($("#page-banner")) $("#page-banner").innerHTML = healthBanner(error.message);
  }
}

function cwRender() {
  const r = cw.record;
  $("#cw-question").innerHTML = `<span class="cw-meta">Turn ${r.turn} · Part ${r.part} · thread ${esc(r.thread)}${r.test ? ` · <span class="tk-test-tag" data-test="${esc(r.test)}">${esc(r.test)}</span>` : ""}</span><b>${esc(r.question)}</b>`;
  $("#cw-legend").innerHTML = Object.entries(r.kinds).map(([kind, label]) => `<span style="--c:${CW_COLOUR[kind]}">${esc(label)}</span>`).join("") +
    `<span class="cw-cached-key">Served from the prompt cache</span>`;
  $("#cw-duo").innerHTML = ["scratch", "memorizz"].map((side) => `
    <section class="side ${side}" aria-label="${esc(r[side].title)}">
      <div class="side-head"><i></i><b>${esc(r[side].title)}</b> · ${r[side].calls.length} model call${r[side].calls.length === 1 ? "" : "s"}</div>
      <div class="cw-agent" id="cw-${side}"></div>
    </section>`).join("");
  ["scratch", "memorizz"].forEach(cwSide);
}

function cwSide(side) {
  const data = cw.record[side], el = $(`#cw-${side}`);
  if (!data.calls.length) { el.innerHTML = `<div class="reply-empty">${esc(data.note || "No model call.")}</div>`; return; }
  const active = Math.min(cw.call[side], data.calls.length - 1);
  const tabs = data.calls.length > 1 ? `<div class="cw-calls" role="tablist">${data.calls.map((c, k) => `<button class="chip ${k === active ? "active" : ""}" role="tab" aria-selected="${k === active}" data-call="${k}">${c.n} · ${esc(c.stage)}</button>`).join("")}</div>` : "";
  el.innerHTML = tabs + cwCall(data.calls[active]);
  $$("[data-call]", el).forEach((b) => b.addEventListener("click", () => { cw.call[side] = Number(b.dataset.call); cwSide(side); }));
}

function cwCall(c) {
  const input = c.input_tokens || c.estimated_tokens || 1, cached = c.cached_tokens || 0, est = c.estimated_tokens || 1;
  let at = 0;
  const placed = c.sections.map((s) => { const begin = (at / est) * input; at += s.tokens; return { ...s, begin, end: (at / est) * input }; });
  const share = Math.round((cached / input) * 100);
  const metrics = [metric("input tokens", cwTok(c.input_tokens)), metric("prompt-cached", `${cwTok(cached)} · ${share}%`, cached ? "hit" : ""),
    metric("output", cwTok(c.output_tokens)), metric("stage", c.stage)].join("");
  const bar = `<div class="cw-bar" role="img" aria-label="${esc(`${c.sections.length} sections, ${cwTok(c.input_tokens)} input tokens, ${cwTok(cached)} served from the prompt cache`)}">
      ${placed.map((s) => `<span style="width:${Math.max(0.4, ((s.end - s.begin) / input) * 100)}%;background:${CW_COLOUR[s.kind]}" data-tip="${esc(`<b>${esc(s.label)}</b><br>${s.tokens.toLocaleString()} tokens (estimate)`)}"></span>`).join("")}
      ${cached ? `<i class="cw-cached" style="width:${Math.min(100, (cached / input) * 100)}%"></i>` : ""}
    </div>`;
  const items = placed.map((s) => {
    const where = s.end <= cached ? "cached" : s.begin < cached ? "partly cached" : "";
    return `<li class="cw-section" style="--c:${CW_COLOUR[s.kind]}"><details ${CW_OPEN.has(s.kind) ? "open" : ""}>
      <summary><span class="cw-kind">${esc(cw.record.kinds[s.kind] || s.kind)}</span><b>${esc(s.label)}</b><span class="cw-tok">${s.tokens.toLocaleString()} tok</span>${where ? `<span class="cw-state">${where}</span>` : ""}</summary>
      ${cwBody(s)}</details></li>`;
  }).join("");
  return `<div class="metrics cw-metrics">${metrics}</div>${bar}<ol class="cw-sections">${items}</ol>`;
}

function cwBody(s) {
  if (s.kind === "history" && s.messages)
    return `<div class="cw-history">${s.messages.map((m) => `<div class="cw-msg ${esc(m.role)}"><span class="cw-role">${esc(m.role)}</span><pre class="cw-pre">${esc(m.text)}</pre></div>`).join("")}</div>`;
  if (s.kind === "tools" && s.items)
    return `<div class="cw-tools">${s.items.map((name) => `<code>${esc(name)}</code>`).join("")}</div><details class="cw-json"><summary>The schemas, as sent</summary><pre class="cw-pre">${esc(s.text)}</pre></details>`;
  return `<pre class="cw-pre">${esc(s.text) || "<i>empty</i>"}</pre>`;
}
