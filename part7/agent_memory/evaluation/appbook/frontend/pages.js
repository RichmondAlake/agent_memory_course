/* ======================================================================
   The Graders page and the five suite pages. Each suite page explains
   what it measures, runs its suite live (quick or full) and, when idle,
   shows the latest stored run that measured it, notebook or appbook.
   ====================================================================== */

function head(kicker, title, desc) {
  return `<header class="eval-head"><div class="eval-kicker">${esc(kicker)}</div><h1 class="eval-title">${title}</h1><p class="eval-desc">${desc}</p></header>${needsDB()}`;
}
function measures(rows) {
  return `<div class="panel mb"><div class="panel-body"><table class="measure-table"><thead><tr><th>Metric</th><th>Definition</th><th>Grader</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join("")}</tbody></table></div></div>`;
}
function livePanel(kind, title = "Live") {
  return `<div class="panel mb" id="live-${kind}" hidden><div class="panel-head"><span class="panel-title">${esc(title)}</span><span class="hint" id="live-${kind}-count"></span></div>
    <div class="panel-body"><div class="tiles" id="live-${kind}-tiles"></div><div id="live-${kind}-body"></div><div class="log-lines" id="live-${kind}-log"></div></div></div>`;
}
function lastPanel(kind) {
  return `<div class="panel"><div class="panel-head"><span class="panel-title">Latest stored run · <span class="mono" id="last-${kind}-run">—</span></span><button class="btn btn-ghost" id="last-${kind}-refresh">${I.refresh}</button></div>
    <div class="panel-body" id="last-${kind}"><div class="empty">Reading the evidence…</div></div></div>`;
}
function keptLine(e) {
  if (e.type === "kept") return `kept for the MemoRizz UI (Traces, filtered by agent): <b>${esc(e.agent)}</b> · <span class="mono">${esc(e.memory_id)}</span> · set MEMO_CLEANUP=1 to delete a run's rows`;
  return `cleanup (MEMO_CLEANUP=1): ${esc(JSON.stringify(e.deleted || e.error))}`;
}
function logLine(kind, html) { const el = $(`#live-${kind}-log`); if (el) { el.insertAdjacentHTML("afterbegin", `<div>${html}</div>`); } }
function gatesTable(gates) {
  if (!gates || !gates.length) return "";
  return `<h3 class="panel-title" style="margin:16px 0 8px">Gates for this suite</h3>` + table([
    { label: "Memo", html: true, get: (g) => chip(g.system) }, { label: "Gate", key: "gate" },
    { label: "Value", num: true, get: (g) => (Math.abs(g.value) <= 1 && !Number.isInteger(g.value) ? num(g.value, 3) : g.value) },
    { label: "Rule", get: (g) => `${g.op} ${g.threshold}` }, { label: "Result", html: true, get: (g) => pill(g.passed ? "pass" : "fail") }], gates);
}
async function loadLast(kind, render) {
  try {
    const d = await getJSON(`/api/suites/${kind}/last`);
    setHTML(`#last-${kind}-run`, esc(d.run_id || "none"));
    if (!d.run_id) { setHTML(`#last-${kind}`, `<div class="empty">No stored run of this suite yet: run it above, or run the evaluation notebook.</div>`); return; }
    setHTML(`#last-${kind}`, render(d) + gatesTable(d.gates));
  } catch (e) { setHTML(`#last-${kind}`, needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
function systemTable(systems, extra = []) {
  return table([{ label: "Agent", html: true, get: (r) => chip(r.system) }, { label: "Accuracy", get: (r) => ciText(r.accuracy) },
    ...extra, { label: "Input tokens / answer", num: true, get: (r) => r.input_tokens == null ? "—" : Math.round(r.input_tokens).toLocaleString() },
    { label: "Cached", num: true, get: (r) => pct(r.cached_share) }, { label: "p50 s", num: true, get: (r) => num(r.p50_s, 1) },
    { label: "p95 s", num: true, get: (r) => num(r.p95_s, 1) }, { label: "$ / answer", num: true, get: (r) => money(r.cost_per_answer) }],
    Object.entries(systems || {}).map(([system, s]) => ({ system, ...s })));
}

// ── Graders ───────────────────────────────────────────────────────────
const CHECK_TEXT = {
  states_fact: "Does the answer state this fact, with the same value?",
  uses_old_value: "Does the answer give this outdated value as if it were still current?",
  abstains: "Does the answer decline, or say it does not know or does not have the information?",
};
const graderLive = { rows: [] };
function viewGraders() {
  setStage(`${head("The graders, validated before use", "Can we <em>trust</em> the graders?",
    "Every later check is one of three yes/no questions. The validation set is built <b>by construction</b>: 24 facts about Ada's team, each answered five ways (a paraphrase, \"it used to be X, now Y\", the old value, a wrong value, a refusal), so every answer's three labels are known. Clef-Flash, Jev and the LLM judge answer every check. Thresholds are chosen on half the facts and tested on the other half; the suites then use, per check, the cheapest grader within 0.05 κ of the best on the dev half, and send any decision-model probability inside its escalation band to the judge.")}
    <div class="panel mb"><div class="panel-body">${table([{ label: "Check", key: "k" }, { label: "Question", key: "q" }, { label: "Used for", key: "u" }], [
      { k: "states_fact", q: CHECK_TEXT.states_fact, u: "LongMemEval (second grader), write recall and false memories, update answers" },
      { k: "uses_old_value", q: CHECK_TEXT.uses_old_value, u: "updates: omission vs correct" },
      { k: "abstains", q: CHECK_TEXT.abstains, u: "LongMemEval's unanswerable questions" }])}</div></div>
    ${runbar("graders", "Quick: 8 facts, 40 answers, about 120 checks per grader. Full: 24 facts, 120 answers, 360 checks per grader.")}
    ${livePanel("graders", "Live checks")}
    ${lastPanel("graders")}
    <div class="panel" style="margin-top:18px"><div class="panel-head"><span class="panel-title">Try a check on every grader</span><span class="hint" id="try-policy"></span></div>
      <div class="panel-body">
        <div class="form-grid">
          <label>Check<select id="try-check"><option value="states_fact">states_fact</option><option value="uses_old_value">uses_old_value</option><option value="abstains">abstains</option></select></label>
          <label>Example<select id="try-example"><option value="update">used to be X, now Y</option><option value="old">the old value</option><option value="refuse">a refusal</option></select></label>
          <label class="full">Question<textarea id="try-question">Where does Ada live?</textarea></label>
          <label class="full">Answer<textarea id="try-answer">It used to be Porto, but she moved: now she lives in Lisbon.</textarea></label>
          <label class="full" data-f="fact">Fact<textarea id="try-fact">Ada lives in Lisbon.</textarea></label>
          <label class="full" data-f="old" hidden>Outdated value<textarea id="try-old">Porto</textarea></label>
        </div>
        <div class="row" style="margin-top:12px"><button class="btn btn-accent" id="try-run">Ask every grader</button><span class="hint" id="try-question-text"></span></div>
        <div class="answers" id="try-answers"></div>
      </div></div>`, "#fb923c");
  const handlers = {
    onStart: () => { graderLive.rows = []; $("#live-graders").hidden = false; renderGraderLive(); },
    onEvent: (e) => {
      if (e.type === "items") setHTML("#live-graders-count", `${e.total} checks · ${e.answers} answers · graders: ${e.graders.join(", ")}`);
      if (e.type === "case") { graderLive.rows.push(e.row); if (graderLive.rows.length % 6 === 0) renderGraderLive(); }
      if (e.type === "summary") renderGraderReport({ analysis: e.analysis, policy: e.policy });
    },
    onEnd: () => { renderGraderLive(); loadGraderReport(); },
  };
  wireRunbar("graders", handlers);
  resumeIfRunning("graders", handlers);
  $("#last-graders-refresh").addEventListener("click", loadGraderReport);
  loadGraderReport();
  wirePlayground();
}
function renderGraderLive() {
  const groups = {};
  graderLive.rows.forEach((r) => { groups[r.grader] = groups[r.grader] || { n: 0, right: 0 }; groups[r.grader].n++; groups[r.grader].right += r.right ? 1 : 0; });
  setHTML("#live-graders-tiles", Object.entries(groups).map(([g, v]) => tile(g, pct(v.right / v.n), `${v.right}/${v.n} right at 0.5`)).join(""));
  setHTML("#live-graders-body", table([{ label: "Grader", key: "grader" }, { label: "Check", key: "check" }, { label: "Variant", key: "variant" },
    { label: "Label", get: (r) => (r.label ? "yes" : "no") }, { label: "P(yes)", num: true, get: (r) => num(r.p, 2) },
    { label: "Right", html: true, get: (r) => pill(r.right ? "right" : "wrong", r.right ? "pass" : "fail") }, { label: "ms", num: true, key: "ms" },
    { label: "Answer", wrap: true, key: "answer" }], graderLive.rows.slice(-120).reverse()));
}
async function loadGraderReport() {
  try {
    const d = await getJSON("/api/suites/graders/last");
    setHTML("#last-graders-run", esc(d.run_id || "none"));
    if (!d.run_id) { setHTML("#last-graders", `<div class="empty">No validation run yet: run the suite above, or the evaluation notebook's Part 2.</div>`); return; }
    renderGraderReport(d);
  } catch (e) { setHTML("#last-graders", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
function renderGraderReport(d) {
  const a = d.analysis || {};
  if (!a.scores) return;
  const kappaBars = svgBars(a.scores.map((s) => ({ label: `${s.check} · ${s.grader}`, value: Math.max(0, s.kappa ?? 0), color: GRADER_COLOR[s.grader] })), { max: 1, fmt: (v) => num(v, 2), threshold: 0.8, left: 190 });
  const check = $("#rel-check")?.value || "uses_old_value";
  const graders = a.graders.filter((g) => g !== "judge");
  setHTML("#last-graders", `
    ${table([{ label: "Check", key: "check" }, { label: "Grader", html: true, get: (s) => `<span style="color:${GRADER_COLOR[s.grader]}">${esc(s.grader)}</span>` }, { label: "n", num: true, key: "n" },
      { label: "Accuracy at 0.5", num: true, get: (s) => pct(s.accuracy, 1) }, { label: "κ vs gold", num: true, get: (s) => num(s.kappa, 2) },
      { label: "ECE", num: true, get: (s) => s.ece == null ? "—" : num(s.ece, 3) }, { label: "Brier", num: true, get: (s) => s.brier == null ? "—" : num(s.brier, 3) },
      { label: "ms (p50)", num: true, get: (s) => s.ms == null ? "—" : Math.round(s.ms) }], a.scores)}
    <div class="chart-row" style="margin-top:16px">
      <div class="chart-box"><h4>Cohen's κ against the labels (dashed: 0.8)</h4>${kappaBars}</div>
      <div class="chart-box"><h4>Reliability · <select id="rel-check">${Object.keys(CHECK_TEXT).map((c) => `<option ${c === check ? "selected" : ""}>${c}</option>`).join("")}</select></h4>${svgReliability((a.reliability || {})[check] || {})}</div>
    </div>
    <h3 class="panel-title" style="margin:18px 0 8px">Trust or escalate: each decision model's cascade on the held-out facts</h3>
    <p class="hint" style="margin:-2px 0 10px">A probability strictly inside the band goes to the LLM judge. The band is (min(0.2, threshold − 0.05), max(0.8, threshold + 0.05)), fixed before the run. ✓ marks the grader chosen on the dev facts: the cheapest (Clef-Flash, Jev, the judge) within 0.05 κ of the best.</p>
    ${table([{ label: "Check", key: "check" }, { label: "Decision model", html: true, get: (c) => `${esc(c.grader)}${(a.choices || []).some((x) => x.check === c.check && x.grader === c.grader) ? " ✓" : ""}` },
      { label: "Threshold (dev)", num: true, get: (c) => num(c.threshold, 2) }, { label: "κ on dev", num: true, get: (c) => num(c.kappa_dev, 2) },
      { label: "Escalation band", get: (c) => c.band ? `${num(c.band[0], 2)} < P < ${num(c.band[1], 2)}` : "—" },
      { label: "κ at 0.5", num: true, get: (c) => num(c.kappa_05, 2) }, { label: "κ at threshold", num: true, get: (c) => num(c.kappa_test, 2) },
      { label: "Escalated", num: true, get: (c) => pct(c.escalated) }, { label: "κ cascade", num: true, get: (c) => num(c.kappa_cascade, 2) },
      { label: "κ judge", num: true, get: (c) => num(c.kappa_judge, 2) }], a.cascades || [])}
    <p class="hint" style="margin-top:8px">The suites grade with: ${(a.choices || []).map((c) => `<b>${esc(c.check)}</b> → ${esc(c.uses)}`).join(" · ")}</p>
    <h3 class="panel-title" style="margin:18px 0 8px">Blind spots: share right at 0.5, by variant</h3>
    ${table([{ label: "Check", key: "check" }, { label: "Variant", key: "variant" },
      ...a.graders.map((g) => ({ label: g, num: true, html: true, get: (r) => r[g] == null ? "—" : `<span style="color:${r[g] >= 0.95 ? "var(--ok)" : r[g] >= 0.75 ? "var(--warn)" : "var(--bad)"}">${pct(r[g])}</span>` }))], a.variants || [])}`);
  const sel = $("#rel-check");
  if (sel) sel.addEventListener("change", () => renderGraderReport(d));
  void graders;
}
const TRY = {
  update: { question: "Where does Ada live?", answer: "It used to be Porto, but she moved: now she lives in Lisbon.", fact: "Ada lives in Lisbon.", old: "Porto" },
  old: { question: "Where does Ada live?", answer: "From what you told me, Porto.", fact: "Ada lives in Lisbon.", old: "Porto" },
  refuse: { question: "Where does Ada live?", answer: "I don't have that information.", fact: "Ada lives in Lisbon.", old: "Porto" },
};
function wirePlayground() {
  const fill = () => {
    const check = $("#try-check").value, ex = TRY[$("#try-example").value];
    $$(".form-grid [data-f]").forEach((l) => { l.hidden = !((check === "states_fact" && l.dataset.f === "fact") || (check === "uses_old_value" && l.dataset.f === "old")); });
    Object.entries(ex).forEach(([k, v]) => { const el = $(`#try-${k}`); if (el) el.value = v; });
    $("#try-question-text").textContent = CHECK_TEXT[check];
  };
  $("#try-check").addEventListener("change", fill);
  $("#try-example").addEventListener("change", fill);
  fill();
  getJSON("/api/graders/policy").then((d) => setHTML("#try-policy", Object.entries(d.policy).map(([k, v]) => `${esc(k)} → ${esc(v.grader)}`).join(" · "))).catch(() => {});
  $("#try-run").addEventListener("click", async () => {
    const check = $("#try-check").value;
    const body = { check, question: $("#try-question").value, answer: $("#try-answer").value,
                   fact: check === "states_fact" ? $("#try-fact").value : null, old: check === "uses_old_value" ? $("#try-old").value : null };
    setHTML("#try-answers", `<div class="empty">Asking ${esc((state.health?.graders || []).join(", "))}…</div>`);
    try {
      const d = await postJSON("/api/graders/try", body);
      setHTML("#try-answers", d.answers.map((a) => a.error ? `<div class="answer-card"><b>${esc(a.grader)}</b><div class="hint">${esc(a.error)}</div></div>` :
        `<div class="answer-card ${a.chosen ? "chosen" : ""}"><div class="row" style="justify-content:space-between"><b style="color:${GRADER_COLOR[a.grader]}">${esc(a.grader)}</b>${a.chosen ? pill("used by the suites", "ready") : ""}</div>
          <div class="p">${pct(a.p)}</div><div class="pbar"><i style="width:${(a.p || 0) * 100}%;background:${GRADER_COLOR[a.grader]}"></i></div>
          <div class="hint">${a.ms} ms · ${money(a.cost_usd)}${a.chosen && a.grader !== "judge" ? (a.escalates ? " · inside the band: the suites ask the judge" : " · outside the band: the suites keep this verdict") : ""}</div>${a.reason ? `<div class="hint" style="margin-top:6px">${esc(a.reason)}</div>` : ""}</div>`).join(""));
    } catch (e) { setHTML("#try-answers", `<div class="empty">${esc(e.message)}</div>`); }
  });
}

// ── LongMemEval ───────────────────────────────────────────────────────
const lmeLive = { answers: [] };
function viewLongMemEval() {
  setStage(`${head("Benchmark · LongMemEval-S (cleaned) · MIT · @98d7416", "Recall over <em>long</em> chat histories",
    "Each question has its own history of past sessions with dates and one or more evidence sessions. The sample takes n answerable questions per type (single-session user, assistant and preference, multi-session, temporal reasoning, knowledge update) plus unanswerable ones, with seed 7; each history is trimmed to its evidence sessions plus distractors up to 20,000 tokens. Every agent ingests every history under its own user id, answers with today's date, and is graded with LongMemEval's own prompt per question type. Scores compare the three agents with each other; they are not comparable with published full-history results.")}
    ${measures([["accuracy per ability", "LongMemEval's judge prompt for the question type says the answer is correct", "LLM judge (typed yes/no)"],
      ["session recall@10 (any / all)", "an evidence session (every evidence session) among the 10 the Memo retrieved", "code"],
      ["tokens · latency · $", "input tokens (and the cached share), p50 and p95 seconds, dollars per answer", "measured"]])}
    ${runbar("longmemeval", "Quick: 1 per type + 1 unanswerable (7 questions, about 4 minutes). Full: 5 per type + 6 unanswerable (36 questions, the notebook's sample, about 15 minutes).",
      `<label class="hint">per type <select id="lme-per-type"><option value="">auto</option>${[1, 2, 3, 4, 5].map((n) => `<option>${n}</option>`).join("")}</select></label>`)}
    ${livePanel("longmemeval", "Live answers")}
    ${lastPanel("longmemeval")}`, "#22d3ee");
  const handlers = {
    onStart: () => { lmeLive.answers = []; $("#live-longmemeval").hidden = false; setHTML("#live-longmemeval-body", ""); setHTML("#live-longmemeval-log", ""); },
    onEvent: (e) => {
      if (e.type === "items") setHTML("#live-longmemeval-count", `${e.total} questions`);
      if (e.type === "ingested") logLine("longmemeval", `ingested ${esc(e.id)}`);
      if (e.type === "answer") { lmeLive.answers.push(e); renderLmeLive(); }
      if (e.type === "summary") loadLast("longmemeval", renderLmeLast);
      if (e.type === "cost") logLine("longmemeval", `cost of this run: ${money(e.total)}`);
      if (e.type === "cleanup" || e.type === "kept") logLine("longmemeval", keptLine(e));
    },
  };
  wireRunbar("longmemeval", handlers, () => { const v = $("#lme-per-type").value; return v ? { per_type: Number(v) } : {}; });
  resumeIfRunning("longmemeval", handlers);
  $("#last-longmemeval-refresh").addEventListener("click", () => loadLast("longmemeval", renderLmeLast));
  loadLast("longmemeval", renderLmeLast);
}
function renderLmeLive() {
  const by = {};
  lmeLive.answers.forEach((a) => { by[a.system] = by[a.system] || { k: 0, n: 0 }; by[a.system].n++; by[a.system].k += a.correct ? 1 : 0; });
  setHTML("#live-longmemeval-tiles", SYSTEMS.filter((s) => by[s]).map((s) => tile(s, pct(by[s].k / by[s].n), `${by[s].k}/${by[s].n} correct`)).join(""));
  setHTML("#live-longmemeval-body", table([{ label: "Agent", html: true, get: (r) => chip(r.system) }, { label: "Type", key: "category" },
    { label: "Question", wrap: true, key: "question" }, { label: "Reference", wrap: true, key: "reference" }, { label: "Answer", wrap: true, key: "text" },
    { label: "Judge", html: true, get: (r) => pill(r.correct ? "correct" : "wrong") }, { label: "Tokens", num: true, key: "tokens" },
    { label: "s", num: true, key: "seconds" }], lmeLive.answers.slice().reverse()));
}
function renderLmeLast(d) {
  const s = d.summary || {}, systems = s.systems || {};
  const cats = [...new Set(Object.values(systems).flatMap((x) => Object.keys(x.by_category || {})))];
  const groups = cats.map((c) => ({ label: c, values: Object.fromEntries(Object.entries(systems).map(([n, x]) => [n, (x.by_category || {})[c] || {}])) }));
  groups.push({ label: "all", values: Object.fromEntries(Object.entries(systems).map(([n, x]) => [n, x.accuracy || {}])) });
  const rows = (d.rows || []).filter((r) => r.system !== "cache");
  return `${systemTable(systems, [{ label: "Recall@10 any / all", get: (r) => r.recall_any == null ? "—" : `${num(r.recall_any, 2)} / ${num(r.recall_all, 2)}` }])}
    <div class="chart-row" style="margin-top:14px"><div class="chart-box"><h4>Accuracy per ability, with 95% Wilson intervals</h4>${svgGrouped(groups, SYSTEMS.filter((n) => systems[n]))}</div></div>
    <p class="hint" style="margin-top:8px">McNemar on the same questions: ${Object.entries(s.mcnemar || {}).map(([k, v]) => `${esc(k)}: ${v.only_a} · ${v.only_b} · p = ${num(v.p, 2)}`).join(" · ") || "—"}</p>
    <h3 class="panel-title" style="margin:16px 0 8px">Every answer (${rows.length})</h3>
    ${table([{ label: "Agent", html: true, get: (r) => chip(r.system) }, { label: "Type", key: "category" }, { label: "Question id", key: "item_id" },
      { label: "Answer", wrap: true, get: (r) => (r.detail || {}).answer }, { label: "Judge", html: true, get: (r) => pill(r.correct ? "correct" : "wrong") },
      { label: "Reason", wrap: true, get: (r) => (r.detail || {}).reason }, { label: "Tokens", num: true, key: "input_tokens" }], rows)}`;
}

// ── FactConsolidation ─────────────────────────────────────────────────
const fcLive = { answers: [] };
function viewFactConsolidation() {
  setStage(`${head("Benchmark · MemoryAgentBench FactConsolidation (single-hop, 6k) · MIT · @7ea0669", "When later facts <em>overwrite</em> earlier ones",
    "455 numbered facts arrive as turns, eight per message, and some later facts contradict earlier ones. Each agent's own write path runs: the naive agent appends, the scratch Memo extracts every fact and supersedes the old value, MemoRizz stores the conversation. Then each answers questions about the current values; a stale answer gives an overwritten value.")}
    <div class="callout"><b>MemoRizz runs with entity memory on, as designed.</b> MemoRizz 0.17.4 failed here: an entity whose JSON passed about 8 KB could not be saved (ORA-03146), and the broken connections then hung the agent waiting for the pool. 0.17.8 fixes both, and this app requires it. Facts still arrive eight per message, because MemoRizz shows the model at most 600 characters of each recalled message.</div>
    ${measures([["accuracy", "the answer contains the gold (newest) value: MemoryAgentBench's substring match", "code"],
      ["stale answers", "the answer contains an overwritten value and not the gold one", "code"],
      ["write path", "seconds and model cost to hear every fact", "measured"]])}
    ${runbar("factconsolidation", "Quick: the first 160 facts (20 messages) and 10 questions they answer (about 4 minutes). Full: all 455 facts (57 messages) and 40 questions (about 10 minutes).")}
    ${livePanel("factconsolidation", "Live")}
    ${lastPanel("factconsolidation")}`, "#34d399");
  const handlers = {
    onStart: () => { fcLive.answers = []; $("#live-factconsolidation").hidden = false; setHTML("#live-factconsolidation-body", ""); setHTML("#live-factconsolidation-log", ""); },
    onEvent: (e) => {
      if (e.type === "start") setHTML("#live-factconsolidation-count", `${e.facts} facts · ${e.messages} messages · ${e.questions} questions`);
      if (e.type === "told") logLine("factconsolidation", `${chip(e.system)} heard ${e.done}/${e.total} messages`);
      if (e.type === "written") logLine("factconsolidation", `scratch facts: ${e.scratch_facts} rows, ${e.scratch_current} current · write seconds ${esc(JSON.stringify(Object.fromEntries(Object.entries(e.write_seconds).map(([k, v]) => [k, Math.round(v)]))))}`);
      if (e.type === "answer") { fcLive.answers.push(e); renderFcLive(); }
      if (e.type === "cleanup" || e.type === "kept") logLine("factconsolidation", keptLine(e));
      if (e.type === "summary") loadLast("factconsolidation", renderFcLast);
      if (e.type === "cost") logLine("factconsolidation", `cost of this run: ${money(e.total)}`);
    },
  };
  wireRunbar("factconsolidation", handlers);
  resumeIfRunning("factconsolidation", handlers);
  $("#last-factconsolidation-refresh").addEventListener("click", () => loadLast("factconsolidation", renderFcLast));
  loadLast("factconsolidation", renderFcLast);
}
function renderFcLive() {
  const by = {};
  fcLive.answers.forEach((a) => { by[a.system] = by[a.system] || { k: 0, n: 0, stale: 0 }; by[a.system].n++; by[a.system].k += a.correct ? 1 : 0; by[a.system].stale += a.stale ? 1 : 0; });
  setHTML("#live-factconsolidation-tiles", SYSTEMS.filter((s) => by[s]).map((s) => tile(s, pct(by[s].k / by[s].n), `${by[s].k}/${by[s].n} correct · ${by[s].stale} stale`)).join(""));
  setHTML("#live-factconsolidation-body", table([{ label: "Agent", html: true, get: (r) => chip(r.system) }, { label: "Question", wrap: true, key: "question" },
    { label: "Gold", key: "gold" }, { label: "Overwritten", get: (r) => (r.stale_values || []).join(", ") || "—" }, { label: "Answer", wrap: true, key: "text" },
    { label: "Result", html: true, get: (r) => pill(r.correct ? "correct" : r.stale ? "stale" : "wrong", r.correct ? "pass" : "fail") }], fcLive.answers.slice().reverse()));
}
function renderFcLast(d) {
  const rows = d.rows || [];
  return `${systemTable((d.summary || {}).systems, [{ label: "Stale", num: true, get: (r) => r.stale ?? "—" }])}
    <h3 class="panel-title" style="margin:16px 0 8px">Wrong and stale answers</h3>
    ${table([{ label: "Agent", html: true, get: (r) => chip(r.system) }, { label: "Question", wrap: true, key: "item_id" },
      { label: "Gold", get: (r) => ((r.detail || {}).gold || [])[0] }, { label: "Answer", wrap: true, get: (r) => (r.detail || {}).answer },
      { label: "Stale", html: true, get: (r) => (r.detail || {}).stale ? pill("stale", "fail") : "" }], rows.filter((r) => !r.correct), { empty: "Every answer was right." })}`;
}

// ── Memory operations ─────────────────────────────────────────────────
function viewOperations() {
  setStage(`${head("Memory operations · generated by rule", "Open the <em>stores</em>",
    "Both Memos hear the same ten turns: seven facts, three distractors (a hypothetical, someone else's plan, small talk) and three updates; then a canary for another user (Ben) and one in Ada's sealed thread. The suite reads each store back, asks the update questions, probes for the canaries from the wrong scope, and forgets Ada's city in two stages: from the fact store only, then from every copy.")}
    ${measures([["write recall · false-memory resistance", "gold facts present in the store · distractors absent (HaluMem's write stage)", "states_fact (Graders policy)"],
      ["updates", "correct when the answer gives the new value and not the old one; omission when the old one; hallucination otherwise", "states_fact + uses_old_value"],
      ["leaks", "a canary appears in an answer from another user or outside the sealed thread", "code (substring)"],
      ["forgetting", "the city is gone from answers in a new thread, and an unrelated fact is still answered", "code"]])}
    ${runbar("operations", "One size: twelve turns per Memo, then the checks (about 3 minutes).")}
    ${livePanel("operations", "Live")}
    ${lastPanel("operations")}`, "#facc15");
  const handlers = {
    onStart: () => { $("#live-operations").hidden = false; setHTML("#live-operations-body", ""); setHTML("#live-operations-log", ""); },
    onEvent: (e) => {
      if (e.type === "told") logLine("operations", `${chip(e.system)} heard (${esc(e.kind)}): ${esc(e.text)}`);
      if (e.type === "stores") setHTML("#live-operations-body", storesHTML(e.stores));
      if (e.type === "probe") logLine("operations", `${chip(e.system)} ${esc(e.probe)} · ${e.leaked ? pill("LEAK", "fail") : e.expected ? pill(e.found ? "found in scope" : "not found in scope", e.found ? "pass" : "warn") : pill("no leak", "pass")} · ${esc(e.answer)}`);
      if (e.type === "graded") logLine("operations", `${esc(e.step)} · ${esc(e.check)}: ${e.grader === "judge" ? `${e.verdicts} by the judge alone` : `${e.escalated} of ${e.verdicts} ${esc(e.grader)} verdicts escalated to the judge`}`);
      if (e.type === "forget") logLine("operations", `${chip(e.system)} forget ${esc(e.stage)} · forgotten ${e.forgotten ? "yes" : "no"} · retained ${e.retained ? "yes" : "no"}`);
      if (e.type === "cleanup" || e.type === "kept") logLine("operations", keptLine(e));
      if (e.type === "summary") loadLast("operations", renderOpsLast);
    },
  };
  wireRunbar("operations", handlers);
  resumeIfRunning("operations", handlers);
  $("#last-operations-refresh").addEventListener("click", () => loadLast("operations", renderOpsLast));
  loadLast("operations", renderOpsLast);
}
function storesHTML(stores) {
  return `<div class="chart-row">${Object.entries(stores).map(([name, lines]) => `<div class="chart-box"><h4>${esc(name)} · ${lines.length} current facts for Ada</h4><div class="readme">${esc(lines.join("\n") || "(empty)")}</div></div>`).join("")}</div>`;
}
function renderOpsLast(d) {
  const rows = d.rows || [], per = (d.summary || {}).systems || {};
  const stores = Object.fromEntries(rows.filter((r) => r.category === "store").map((r) => [r.system, (r.detail || {}).lines || []]));
  return `${table([{ label: "Memo", html: true, get: (r) => chip(r.system) }, { label: "Write recall", num: true, get: (r) => pct(r.write_recall) },
      { label: "False-memory resistance", num: true, get: (r) => pct(r.false_memory_resistance) }, { label: "Updates correct", num: true, get: (r) => pct(r.updates_correct) },
      { label: "Leaks", num: true, get: (r) => `${r.leaks} / ${Math.max(0, r.probes - 2)}` },
      { label: "Forgetting reaches every copy", get: (r) => r.forgetting_every_copy == null ? "—" : r.forgetting_every_copy ? "yes" : "no" }],
      Object.entries(per).map(([system, s]) => ({ system, ...s })))}
    ${Object.keys(stores).length ? `<h3 class="panel-title" style="margin:16px 0 8px">What each Memo stored</h3>${storesHTML(stores)}` : ""}
    <h3 class="panel-title" style="margin:16px 0 8px">Isolation probes, updates and forgetting</h3>
    ${table([{ label: "Memo", html: true, get: (r) => chip(r.system) }, { label: "Test", key: "item_id" }, { label: "Kind", key: "category" },
      { label: "Result", html: true, get: (r) => pill(r.correct ? "pass" : "fail") },
      { label: "Answer / detail", wrap: true, get: (r) => { const x = r.detail || {}; return x.answer || x.where || x.result || JSON.stringify(x).slice(0, 160); } },
      { label: "Graded by", get: (r) => (r.detail || {}).graded_by || "" }],
      rows.filter((r) => ["isolation", "update", "forgetting", "write recall", "false memory"].includes(r.category)))}`;
}
