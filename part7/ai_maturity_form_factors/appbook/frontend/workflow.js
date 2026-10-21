/* ======================================================================
   Form Factor 3 — the underwriting workflow with the Clef decision model.
   One application, or several in parallel lanes. Each lane shows the
   fixed pipeline, the decision tree (criteria → Clef → gate → outcome),
   and the hand-off to a human underwriter when the gate refers.
   ====================================================================== */

const WF_STEPS = [
  { id: "extract", label: "Extract", who: "Claude · JSON schema" },
  { id: "measure", label: "Measure", who: "Python", par: true },
  { id: "ground", label: "Ground", who: "Oracle · policy", par: true },
  { id: "decide", label: "Decide", who: "Clef-Flash" },
  { id: "gate", label: "Gate", who: "Python · policy rule" },
  { id: "explain", label: "Explain", who: "Claude" },
  { id: "review", label: "Review", who: "Claude · compliance" },
  { id: "record", label: "Record", who: "Oracle · memory" },
];
const wfState = { samples: [], lanes: {}, t0: 0, timer: null };

function viewWorkflow() {
  const f = FF_BY_ID.workflow;
  setStage(`${ffHeader(f)}${needsDB()}
    <div class="wf-top">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.file} One application</span><span class="hint mono">emailed, in the applicant's own words</span></div>
        <div class="panel-body">
          <div class="chips" id="wf-samples"></div>
          <textarea id="wf-email" rows="6" placeholder="Paste an application email…" style="margin-top:12px"></textarea>
          <div class="row spread" style="margin-top:10px"><span class="hint">Pipeline: extract → measure ‖ ground → decide → gate → explain → review → record</span><button class="btn btn-accent" id="wf-run">${I.play} Run the workflow</button></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><span class="panel-title">${I.flow} Parallel scenario · a broker batch</span><span class="hint mono">lanes run concurrently</span></div>
        <div class="panel-body">
          <div class="batch-picks" id="wf-batch"></div>
          <div class="hint" style="margin:10px 0">Each application is its own lane, launched at the same moment. The Claude steps overlap freely; the Clef decision model runs one request at a time on the GPU, so lanes <b>queue</b> for it — watch the timeline.</div>
          <button class="btn btn-accent" id="wf-batch-run">${I.play} Run the batch in parallel</button>
        </div>
      </div>
    </div>
    <div id="wf-runs"></div>
    <div class="panel" style="margin-top:22px">
      <div class="panel-head"><span class="panel-title">${I.memory} Decision memory · LOAN_DECISIONS ${memBadge("episodic", true)}</span><button class="btn btn-ghost" id="wf-dec-refresh">${I.refresh}</button></div>
      <div class="panel-body"><div id="wf-decisions"><div class="empty">Recorded decisions appear here, newest first.</div></div></div>
    </div>`, f.accent);

  getJSON("/api/workflow/samples").then((d) => {
    wfState.samples = d.samples;
    setHTML("#wf-samples", d.samples.map((s) => `<button class="chip seed-chip" data-s="${s.id}">${esc(s.applicant)} · ${esc(s.label)}</button>`).join(""));
    setHTML("#wf-batch", d.samples.map((s, i) => `<label class="pick"><input type="checkbox" value="${s.id}" ${i < 4 ? "checked" : ""}><span><b>${esc(s.applicant)}</b><small>${esc(s.label)}</small></span></label>`).join(""));
    $$("#wf-samples .chip").forEach((b) => b.addEventListener("click", () => { $("#wf-email").value = d.samples.find((s) => s.id === b.dataset.s).email; autosize($("#wf-email"), 260); }));
    if (!$("#wf-email").value) { $("#wf-email").value = d.samples[0].email; autosize($("#wf-email"), 260); }
  }).catch(() => {});
  $("#wf-run").addEventListener("click", () => {
    const email = $("#wf-email").value.trim(); if (!email) return;
    runWorkflow("/api/workflow/run", { email }, false);
  });
  $("#wf-batch-run").addEventListener("click", () => {
    const samples = $$("#wf-batch input:checked").map((x) => x.value);
    if (!samples.length) return;
    runWorkflow("/api/workflow/batch", { samples }, true);
  });
  $("#wf-dec-refresh").addEventListener("click", loadDecisions);
  loadDecisions();
}

async function runWorkflow(url, body, batch) {
  if (state.abort) return;
  const runs = $("#wf-runs");
  wfState.lanes = {}; wfState.t0 = performance.now();
  runs.innerHTML = batch ? `
    <div class="panel batch-panel"><div class="panel-head"><span class="panel-title">${I.flow} Parallel lanes</span><span class="hint mono" id="wf-clock">0.0 s</span></div>
      <div class="panel-body"><div class="clef-queue" id="clef-queue"></div><div class="gantt" id="gantt"></div><div id="lanes"></div></div></div>` : `<div id="lanes"></div>`;
  $("#wf-run").disabled = $("#wf-batch-run").disabled = true;
  clearInterval(wfState.timer);
  wfState.timer = setInterval(() => { setText("#wf-clock", ((performance.now() - wfState.t0) / 1000).toFixed(1) + " s"); if (batch) renderGantt(); }, 200);
  state.abort = new AbortController();
  try {
    await streamSSE(url, body, (ev) => onWorkflowEvent(ev, batch), state.abort.signal);
  } catch (e) {
    $("#lanes")?.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>${esc(e.message)}</div></div>`);
  } finally {
    state.abort = null; clearInterval(wfState.timer);
    const r = $("#wf-run"), b = $("#wf-batch-run"); if (r) r.disabled = false; if (b) b.disabled = false;
    if (batch) renderGantt();
    loadDecisions();
  }
}

function laneOf(id) {
  if (!wfState.lanes[id]) wfState.lanes[id] = { id, steps: {}, spans: {}, applicant: id, data: {} };
  return wfState.lanes[id];
}

function onWorkflowEvent(ev, batch) {
  if (ev.type === "start") {
    ev.lanes.forEach((l) => { const lane = laneOf(l.lane); lane.applicant = l.applicant === "single" ? "Application" : l.applicant; });
    setHTML("#lanes", ev.lanes.map((l) => laneShell(laneOf(l.lane), batch)).join(""));
    return;
  }
  if (ev.type === "all_done") return;
  const lane = laneOf(ev.lane);
  const now = (performance.now() - wfState.t0) / 1000;
  if (ev.type === "step") {
    lane.steps[ev.step] = ev.status;
    const span = lane.spans[ev.step] || (lane.spans[ev.step] = {});
    if (ev.status === "queued" || ev.status === "loading") { span.queued = span.queued ?? now; }
    if (ev.status === "running" || ev.status === "queued" || ev.status === "loading") span.start = span.start ?? now;
    if (ev.status === "running" && span.queued != null && span.runStart == null) span.runStart = now;
    if (ev.status === "done") { span.end = now; if (span.queued != null && span.runStart == null) span.runStart = Math.max(span.queued, now - ((ev.data && ev.data.latency_ms) || 0) / 1000); }
    if (ev.data) lane.data[ev.step] = ev.data;
    if (ev.step === "extract" && ev.status === "done") lane.applicant = ev.data.application.applicant;
    renderLane(lane, batch);
    if (batch) renderQueue();
  } else if (ev.type === "lane_done") {
    lane.summary = ev; renderLane(lane, batch); if (batch) renderQueue();
  } else if (ev.type === "handoff") {
    lane.handoff = ev; renderLane(lane, batch);
  } else if (ev.type === "error") {
    lane.error = ev.message; renderLane(lane, batch);
  }
}

function laneShell(lane, batch) {
  return `<div class="lane ${batch ? "compact" : "open"}" id="lane-${lane.id}"><div class="lane-head"></div><div class="lane-pipe"></div><div class="lane-detail"></div></div>`;
}

function stepClass(lane, id) { return lane.steps[id] || "pending"; }

function renderLane(lane, batch) {
  const el = $(`#lane-${CSS.escape(lane.id)}`); if (!el) return;
  const s = lane.summary;
  const outcome = s ? s.outcome : lane.data.gate ? lane.data.gate.outcome : null;
  el.querySelector(".lane-head").innerHTML = `<span class="lane-name">${esc(lane.applicant)}</span>
    ${outcome ? `<span class="outcome ${outcome}">${outcome}</span>` : lane.error ? '<span class="outcome decline">error</span>' : `<span class="hint mono">${esc(Object.entries(lane.steps).filter(([, v]) => v !== "done").map(([k, v]) => `${k} ${v}`).join(" · ") || "starting")}</span>`}
    ${s ? `<span class="hint mono">${s.seconds}s · decision #${s.decision_id}</span>` : ""}
    ${batch ? `<button class="btn btn-ghost lane-toggle">${el.classList.contains("open") ? "Hide" : "Details"}</button>` : ""}`;
  const pipe = WF_STEPS.map((st) => {
    const c = stepClass(lane, st.id);
    return `<div class="pstep ${c} ${st.par ? "par" : ""}" title="${esc(st.who)}"><span class="pdot">${c === "done" ? I.check : c === "running" || c === "loading" ? '<span class="spinner"></span>' : c === "queued" ? "⏳" : ""}</span><span class="plab">${st.label}</span><span class="pwho">${c === "queued" ? "waiting for Clef" : c === "loading" ? "loading Clef" : esc(st.who)}</span></div>`;
  });
  el.querySelector(".lane-pipe").innerHTML = `${pipe[0]}<span class="parr">→</span><div class="pgroup">${pipe[1]}${pipe[2]}<span class="pgroup-tag">in parallel</span></div><span class="parr">→</span>${pipe.slice(3).join('<span class="parr">→</span>')}`;
  const toggle = el.querySelector(".lane-toggle");
  if (toggle) toggle.onclick = () => { el.classList.toggle("open"); renderLane(lane, batch); };
  if (!el.classList.contains("open")) { el.querySelector(".lane-detail").innerHTML = ""; return; }
  el.querySelector(".lane-detail").innerHTML = laneDetail(lane);
  wireHandoff(el, lane);
}

function laneDetail(lane) {
  const d = lane.data, parts = [];
  if (lane.error) parts.push(`<div class="banner warn">${I.alert}<div>${esc(lane.error)}</div></div>`);
  if (d.extract) {
    const a = d.extract.application;
    parts.push(`<div class="dcard"><div class="dcard-h">① Extract · structured output</div><div class="kvgrid">
      ${kv("income / month", money(a.gross_monthly_income))}${kv("debts / month", money(a.monthly_debts))}${kv("loan", money(a.loan_amount))}${kv("property", money(a.property_value))}
      ${kv("use", a.property_use)}${kv("credit score", a.credit_score)}${kv("employment", a.employment_months + " mo")}${kv("reserves", money(a.liquid_reserves))}</div>
      <div class="hint">documents: ${a.documents_provided.map(esc).join(", ") || "none"}${a.notes ? ` · notes: ${esc(a.notes)}` : ""}</div></div>`);
  }
  if (d.measure || d.ground) {
    const m = d.measure;
    parts.push(`<div class="dpair"><div class="dcard"><div class="dcard-h">② Measure · Python, limits from policy memory ${memBadge("semantic", true)}</div>${m ? `
      ${ratioBar("DTI", m.ratios.dti, m.limits.max_dti, true)}${ratioBar("LTV", m.ratios.ltv, m.limits.max_ltv, true)}
      <div class="kvgrid">${kv("PITI / month", money(m.ratios.monthly_payment_piti))}${kv("reserves", m.ratios.reserve_months + " mo (min " + m.limits.min_reserve_months + ")")}</div>` : '<span class="spinner"></span>'}</div>
      <div class="dcard"><div class="dcard-h">③ Ground · current policy versions ${memBadge("semantic", true)}</div>${d.ground ? `<div class="chips">${d.ground.sections.map((s) => `<span class="pdoc">${esc(s.doc_id)} <b class="${s.version > 1 ? "vnew" : ""}">v${s.version}</b></span>`).join("")}</div><div class="hint">Read from POLICY_DOCS at run time — a bulletin applied on the RAG page changes the next decision.</div>` : '<span class="spinner"></span>'}</div></div>`);
  }
  if (d.decide) {
    const ans = d.decide.answers;
    parts.push(`<div class="dcard"><div class="dcard-h">④ Decide · Clef-Flash, one forward pass · ${d.decide.latency_ms} ms · ${d.decide.usage.input_tokens} tokens in, ${d.decide.usage.output_tokens} out</div>
      <div class="probs">${probRow("decision: approve", ans.decision.probabilities.approve, ans.decision.choice === "approve")}${probRow("decision: decline", ans.decision.probabilities.decline, ans.decision.choice === "decline")}
      ${Object.keys(ans).filter((k) => k !== "decision").map((k) => probRow(k, ans[k].noul, ans[k].noul >= 0.5, true)).join("")}</div>
      <details class="sql-box"><summary>The SystemOne request (state + questions)</summary><pre class="rag-sql">${esc(JSON.stringify(d.decide.request, null, 2))}</pre></details></div>`);
  }
  if (d.gate) parts.push(`<div class="dcard"><div class="dcard-h">⑤ Gate → the path this application took</div>${treeSVG(d.gate.tree)}${d.gate.review_reasons.length ? `<div class="hint">Referred because ${d.gate.review_reasons.map(esc).join("; ")}.</div>` : ""}</div>`);
  if (d.explain || d.review) parts.push(`<div class="dcard"><div class="dcard-h">⑥ Explain · ⑦ Review</div>${d.explain && d.explain.letter ? `<div class="letter">${renderRich(d.explain.letter)}</div>` : '<span class="spinner"></span>'}${d.review && d.review.approved !== undefined ? `<div class="hint">compliance review ${d.review.attempt}: ${d.review.approved ? '<span class="tag ok">approved</span>' : `<span class="tag no">revise</span> ${esc(d.review.feedback)}`}</div>` : ""}</div>`);
  if (d.record && d.record.application_id) parts.push(`<div class="dcard"><div class="dcard-h">⑧ Record ${memBadge("episodic", true)}</div><div class="hint">LOAN_APPLICATIONS <span class="mono">${esc(d.record.application_id.slice(0, 8))}…</span> and LOAN_DECISIONS <span class="mono">#${d.record.decision_id}</span>, with the policy versions used. Open the Data Explorer below to see the rows.</div></div>`);
  if (lane.handoff) parts.push(`<div class="dcard handoff-card"><div class="dcard-h">${I.alert} Human underwriter · the gate referred this application</div>
    <div class="hint">${lane.handoff.reasons.map(esc).join("; ")}</div>
    <textarea class="hf-note" rows="2" placeholder="Underwriter's note (stored as a case note)"></textarea>
    <div class="row" style="gap:8px;margin-top:8px"><button class="btn btn-accent hf-approve">${I.check} Approve</button><button class="btn hf-decline">${I.cross} Decline</button><span class="hint hf-msg"></span></div></div>`);
  return parts.join("");
}

function wireHandoff(el, lane) {
  const box = el.querySelector(".handoff-card"); if (!box || !lane.handoff) return;
  const go = async (outcome) => {
    $$("button", box).forEach((b) => (b.disabled = true));
    try {
      const r = await postJSON("/api/workflow/underwriter", { application_id: lane.handoff.application_id, outcome, note: box.querySelector(".hf-note").value });
      box.querySelector(".hf-msg").textContent = `recorded decision #${r.decision_id} (${outcome}) and a case note`;
      loadDecisions();
    } catch (e) { box.querySelector(".hf-msg").textContent = e.message; }
  };
  box.querySelector(".hf-approve").onclick = () => go("approve");
  box.querySelector(".hf-decline").onclick = () => go("decline");
}

function kv(k, v) { return `<div class="kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`; }
function ratioBar(name, value, limit, upper) {
  const max = Math.max(limit * 1.3, value * 1.05);
  const over = upper ? value > limit : value < limit;
  return `<div class="ratio"><span class="rname">${name}</span><span class="rtrack"><i class="${over ? "over" : ""}" style="width:${(value / max) * 100}%"></i><b style="left:${(limit / max) * 100}%" title="limit"></b></span><span class="rval ${over ? "over" : ""}">${pct(value)}</span><span class="rlim">limit ${pct(limit, 0)}</span></div>`;
}
function probRow(name, p, chosen, crit) {
  return `<div class="prob ${chosen ? "yes" : "no"} ${crit ? "crit" : ""}"><span class="pname">${esc(name)}</span><span class="ptrack"><i style="width:${p * 100}%"></i></span><span class="pval">${p.toFixed(3)}</span></div>`;
}

function treeSVG(t) {
  const W = 980, H = 300, crit = t.criteria;
  const cy = (i) => 30 + i * 44;
  const model = { x: 360, y: 140 }, gx = 560, gy = (i) => 80 + i * 60, outs = { approve: 70, decline: 150, refer: 230 }, ox = 860;
  const modelColor = t.model.choice === "approve" ? "#34d399" : "#fb7185";
  const critNodes = crit.map((c, i) => `<g class="t-crit ${c.passed ? "pass" : "fail"}"><rect x="10" y="${cy(i) - 17}" width="210" height="34" rx="9"/><text x="22" y="${cy(i) - 2}" class="t-l">${esc(c.label)}</text><text x="22" y="${cy(i) + 11}" class="t-s">${esc(c.evidence)}</text><text x="208" y="${cy(i) + 4}" text-anchor="end" class="t-p">${c.probability.toFixed(2)}</text></g>
    <path class="t-edge ${c.passed ? "pass" : "fail"}" d="M220 ${cy(i)} C 280 ${cy(i)}, 290 ${model.y}, ${model.x - 70} ${model.y}"/>`).join("");
  const modelNode = `<g class="t-model"><rect x="${model.x - 70}" y="${model.y - 32}" width="140" height="64" rx="12" style="stroke:${modelColor}"/><text x="${model.x}" y="${model.y - 10}" text-anchor="middle" class="t-l">Clef chooses</text><text x="${model.x}" y="${model.y + 10}" text-anchor="middle" class="t-big" fill="${modelColor}">${esc(t.model.choice)}</text><text x="${model.x}" y="${model.y + 25}" text-anchor="middle" class="t-s">confidence ${t.model.confidence.toFixed(2)}</text></g>`;
  const gates = t.gates.map((g, i) => `<path class="t-edge ${g.passed ? "pass" : "fail"}" d="M${model.x + 70} ${model.y} C ${model.x + 120} ${model.y}, ${gx - 70} ${gy(i)}, ${gx - 10} ${gy(i)}"/>
    <g class="t-gate ${g.passed ? "pass" : "fail"}"><rect x="${gx - 10}" y="${gy(i) - 20}" width="190" height="40" rx="9"/><text x="${gx}" y="${gy(i) - 4}" class="t-l">${esc(g.label)}</text><text x="${gx}" y="${gy(i) + 11}" class="t-s">${esc(g.value)} · ${g.passed ? "pass" : "fails → refer"}</text></g>`).join("");
  const taken = t.outcome;
  const outNodes = Object.entries(outs).map(([o, y]) => `<g class="t-out ${o} ${o === taken ? "taken" : ""}"><rect x="${ox - 10}" y="${y - 20}" width="120" height="40" rx="20"/><text x="${ox + 50}" y="${y + 5}" text-anchor="middle">${o}</text></g>`).join("");
  const from = t.all_gates_passed ? gy(1) : gy(t.gates.findIndex((g) => !g.passed));
  const path = `<path class="t-edge taken" d="M${gx + 180} ${from} C ${gx + 240} ${from}, ${ox - 70} ${outs[taken]}, ${ox - 10} ${outs[taken]}"/>`;
  return `<svg class="tree-svg" viewBox="0 0 ${W} ${H}">${critNodes}${modelNode}${gates}${path}${outNodes}
    <text x="10" y="${H - 6}" class="t-s">criteria (P true) → the decision model's choice → the code-owned gate → the outcome that was recorded</text></svg>`;
}

function renderQueue() {
  const q = $("#clef-queue"); if (!q) return;
  const lanes = Object.values(wfState.lanes);
  const deciding = lanes.filter((l) => l.steps.decide === "running");
  const waiting = lanes.filter((l) => l.steps.decide === "queued" || l.steps.decide === "loading");
  const done = lanes.filter((l) => l.steps.decide === "done");
  q.innerHTML = `<span class="cq-title">Clef-Flash · one GPU</span>
    <span class="cq-slot">${deciding.length ? deciding.map((l) => `<b>${esc(l.applicant)}</b>`).join(", ") : '<span class="hint">idle</span>'}</span>
    <span class="cq-wait">${waiting.length ? `queued: ${waiting.map((l) => esc(l.applicant)).join(" → ")}` : ""}</span>
    <span class="hint">decided ${done.length}/${lanes.length}</span>`;
}

function renderGantt() {
  const g = $("#gantt"); if (!g) return;
  const lanes = Object.values(wfState.lanes);
  const now = (performance.now() - wfState.t0) / 1000;
  const total = Math.max(now, ...lanes.flatMap((l) => Object.values(l.spans).map((s) => s.end || 0)), 1);
  const colors = { extract: "#c084fc", measure: "#a3e635", ground: "#34d399", decide: "#fb923c", gate: "#fbbf24", explain: "#c084fc", review: "#f472b6", record: "#facc15" };
  g.innerHTML = `<div class="gantt-axis"><span>0 s</span><span>${(total / 2).toFixed(0)} s</span><span>${total.toFixed(0)} s</span></div>` + lanes.map((l) => `<div class="gantt-row"><span class="gantt-name">${esc(l.applicant)}</span><span class="gantt-track">${Object.entries(l.spans).map(([step, s]) => {
    if (s.start == null) return "";
    const end = s.end ?? now;
    const qEnd = step === "decide" && s.queued != null ? (s.runStart ?? (l.steps.decide === "done" ? end : now)) : null;
    const queued = qEnd != null && qEnd > s.queued ? `<i class="gq" style="left:${(s.queued / total) * 100}%;width:${((qEnd - s.queued) / total) * 100}%" title="decide · waiting for the decision model"></i>` : "";
    const start = qEnd != null ? qEnd : s.start;
    return `${queued}<i class="gs" style="left:${(start / total) * 100}%;width:${Math.max(0.4, ((end - start) / total) * 100)}%;background:${colors[step]}" title="${step} · ${(end - start).toFixed(1)}s"></i>`;
  }).join("")}</span></div>`).join("") + `<div class="legend-inline">${Object.entries(colors).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join("")}<span><i class="gq-key"></i>waiting for Clef</span></div>`;
}

async function loadDecisions() {
  const box = $("#wf-decisions"); if (!box) return;
  try {
    const d = await getJSON("/api/workflow/decisions");
    box.innerHTML = d.decisions.length ? `<table class="data-table"><thead><tr><th class="num">#</th><th>applicant</th><th>outcome</th><th>Clef chose</th><th class="num">confidence</th><th class="num">DTI</th><th class="num">dti_limit v</th><th>decided by</th><th>when</th></tr></thead><tbody>
      ${d.decisions.map((r) => `<tr><td class="num">${r.decision_id}</td><td>${esc(r.applicant)}</td><td><span class="outcome ${r.outcome}">${esc(r.outcome)}</span></td><td>${esc(r.model_choice || "—")}</td><td class="num">${r.confidence != null ? r.confidence.toFixed(2) : "—"}</td><td class="num">${r.dti != null ? pct(r.dti) : "—"}</td><td class="num">${r.dti_policy_version ?? "—"}</td><td class="mono small">${esc(r.decided_by || "")}</td><td class="mono small">${esc(r.decided_at)}</td></tr>`).join("")}</tbody></table>` : `<div class="empty">No decisions yet. Run an application above.</div>`;
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
