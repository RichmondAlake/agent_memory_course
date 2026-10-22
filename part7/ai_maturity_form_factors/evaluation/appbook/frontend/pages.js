/* ======================================================================
   The Graders page and the five rung pages. Each rung page explains what
   it measures, runs its suite live (quick or full) and, when idle, shows
   the latest stored run that measured it, from the notebook or this app.
   ====================================================================== */

// ── Graders ───────────────────────────────────────────────────────────
const CHECK_TEXT = {
  states_fact: "Does the answer state this fact, with the same value?",
  abstains: "Does the answer decline, or say the information is not available?",
  supported: "Is the claim fully supported by the passage, with the same values?",
};
const graderLive = { rows: [] };

function viewGraders() {
  setStage(`
    <header class="eval-head"><div class="eval-kicker">The graders, validated before use</div>
      <h1 class="eval-title">Can we <em>trust</em> the graders?</h1>
      <p class="eval-desc">Every later check is one of three yes/no questions. This page builds labelled tests <b>by construction</b>: the application's model writes a reply that states a golden fact, then code derives variants whose right answer is known (the same reply with a wrong value, an abstention, another fact, a hedge). Clef-Flash, Jev and the LLM judge answer every check; the scoreboard shows where each one can be trusted, and the rung pages use the cheapest grader within 0.05 κ of the best, sending uncertain decision-model answers to the judge (between 0.2 and 0.8, stretched to just around a high or low chosen threshold).</p></header>
    ${needsDB()}
    <div class="panel mb"><div class="panel-body">${table([{ label: "Check", key: "k" }, { label: "Question", key: "q" }, { label: "Used for", key: "u" }], [
      { k: "states_fact", q: CHECK_TEXT.states_fact, u: "is an answer correct? (chatbot, RAG, workflow letters, agent replies)" },
      { k: "abstains", q: CHECK_TEXT.abstains, u: "unanswerable questions; the chatbot's honest 'I don't know'" },
      { k: "supported", q: CHECK_TEXT.supported, u: "RAG faithfulness, claim by claim" }])}</div></div>
    ${runbar("graders", ["quick", "full"], "Quick: 8 golden facts, about 80 checks per grader. Full: all 34 facts, about 370 checks per grader. Clef answers one check at a time.")}
    <div class="panel mb" id="graders-live" hidden><div class="panel-head"><span class="panel-title">Live checks</span><span class="hint" id="graders-live-count"></span></div>
      <div class="panel-body"><div class="tiles" id="graders-live-tiles"></div><div id="graders-live-table"></div></div></div>
    <div class="panel mb"><div class="panel-head"><span class="panel-title">Scoreboard · test half · <span class="mono" id="graders-run">—</span></span></div>
      <div class="panel-body" id="graders-report"><div class="empty">Reading the latest validation run…</div></div></div>
    <div class="panel"><div class="panel-head"><span class="panel-title">Try a check on every grader</span></div>
      <div class="panel-body">
        <div class="form-grid">
          <label>Check<select id="try-kind"><option value="states_fact">states_fact</option><option value="abstains">abstains</option><option value="supported">supported</option></select></label>
          <label>Example<select id="try-example"><option value="right">a right answer</option><option value="wrong">a wrong value (41%)</option><option value="abstain">an abstention</option></select></label>
          <label class="full" data-f="question">Question<textarea id="try-question">What is your maximum debt-to-income ratio?</textarea></label>
          <label class="full" data-f="answer">Answer<textarea id="try-answer">Acme caps DTI at 43% of your gross monthly income, including the new mortgage payment.</textarea></label>
          <label class="full" data-f="fact">Fact<textarea id="try-fact">The maximum DTI is 43%.</textarea></label>
          <label class="full" data-f="passage" hidden>Passage<textarea id="try-passage">Acme Home Loans caps the debt-to-income (DTI) ratio at 43%. DTI is all monthly debt payments, including the new mortgage payment of principal, interest, property tax and insurance (PITI), divided by gross monthly income.</textarea></label>
          <label class="full" data-f="claim" hidden>Claim<textarea id="try-claim">The maximum DTI is 41%.</textarea></label>
        </div>
        <div class="row" style="margin-top:12px"><button class="btn btn-accent" id="try-run">Ask every grader</button><span class="hint" id="try-question-text"></span></div>
        <div class="answers" id="try-answers"></div>
      </div></div>`, "#fb923c");
  const handlers = {
    onStart: () => { graderLive.rows = []; $("#graders-live").hidden = false; renderGraderLive(); },
    onEvent: (e) => {
      if (e.type === "items") setHTML("#graders-live-count", `${e.total} checks to run · graders: ${e.graders.join(", ")}`);
      if (e.type === "case") { graderLive.rows.push(e.row); if (graderLive.rows.length % 5 === 0 || e.row.grader !== "clef") renderGraderLive(); }
      if (e.type === "summary") renderGraderReport({ ...e, run_id: null });
    },
    onEnd: () => { renderGraderLive(); loadGraderReport(); },
  };
  wireRunbar("graders", handlers);
  resumeIfRunning("graders", handlers);
  loadGraderReport();
  wirePlayground();
}
function renderGraderLive() {
  const rows = graderLive.rows;
  const groups = {};
  rows.forEach((r) => { const k = r.grader; groups[k] = groups[k] || { n: 0, right: 0 }; groups[k].n++; groups[k].right += r.right ? 1 : 0; });
  setHTML("#graders-live-tiles", Object.entries(groups).map(([g, v]) => tile(g, pct(v.right / v.n), `${v.right}/${v.n} right at 0.5`)).join(""));
  setHTML("#graders-live-table", table([
    { label: "Grader", key: "grader" }, { label: "Check", key: "kind" }, { label: "Variant", key: "variant" },
    { label: "Label", get: (r) => (r.gold ? "yes" : "no") }, { label: "P(yes)", num: true, get: (r) => num(r.p, 2) },
    { label: "Right", html: true, get: (r) => pill(r.right ? "right" : "wrong", r.right ? "pass" : "fail") },
    { label: "ms", num: true, key: "ms" }, { label: "Text", wrap: true, key: "text" },
  ], rows.slice(-150).reverse()));
}
async function loadGraderReport() {
  try { const d = await getJSON("/api/graders/report"); renderGraderReport(d); }
  catch (e) { setHTML("#graders-report", needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
function renderGraderReport(d) {
  if (d.run_id !== undefined) setHTML("#graders-run", esc(d.run_id || "this run"));
  if (!d.scores) { setHTML("#graders-report", `<div class="empty">No validation run yet. Run the suite above, or the evaluation notebook's Part 2.</div>`); return; }
  const kinds = [...new Set(d.scores.map((s) => s.kind))];
  const kappaBars = svgBars(d.scores.map((s) => ({ label: `${s.kind} · ${s.grader}`, value: Math.max(0, s.kappa), color: GRADER_COLOR[s.grader] })), { max: 1, fmt: (v) => num(v, 2), threshold: 0.8 });
  const variantGraders = Object.keys(d.variants[0] || {}).filter((k) => !["kind", "variant", "n"].includes(k));
  const heat = (v) => `<span style="color:${v >= 0.95 ? "var(--ok)" : v >= 0.75 ? "var(--warn)" : "var(--bad)"}">${num(v, 2)}</span>`;
  setHTML("#graders-report", `
    ${table([{ label: "Check", key: "kind" }, { label: "Grader", key: "grader" }, { label: "n", num: true, key: "n" },
      { label: "Accuracy", num: true, get: (s) => pct(s.accuracy, 1) }, { label: "Cohen's κ", num: true, get: (s) => num(s.kappa, 3) },
      { label: "ECE", num: true, get: (s) => s.ece == null ? "—" : num(s.ece, 3) },
      { label: "ms (p50)", num: true, get: (s) => s.ms == null ? "—" : Math.round(s.ms) }], d.scores)}
    <div class="chart-row" style="margin-top:16px">
      <div class="chart-box"><h4>Cohen's κ against the gold labels (dashed: 0.8)</h4>${kappaBars}</div>
      <div class="chart-box"><h4>Reliability: probability of yes against the share that is yes</h4>${svgReliability(d.reliability || {})}</div>
    </div>
    <h3 class="panel-title" style="margin:18px 0 8px">The grader chosen per check, and the cascade</h3>
    ${table([{ label: "Check", key: "kind" }, { label: "Chosen", html: true, get: (c) => pill(c.grader, "ready") },
      { label: "Threshold", num: true, get: (c) => num(c.threshold, 2) }, { label: "κ dev", num: true, get: (c) => num(c.kappa_dev, 3) },
      { label: "κ test", num: true, get: (c) => num(c.kappa_test, 3) }, { label: "κ test (judge)", num: true, get: (c) => num(c.kappa_test_judge, 3) },
      { label: "Escalate between", get: (c) => c.band ? `${num(c.band[0], 2)}–${num(c.band[1], 2)}` : "—" },
      { label: "Escalated", num: true, get: (c) => c.escalated == null ? "—" : pct(c.escalated) },
      { label: "κ cascade", num: true, get: (c) => c.kappa_cascade == null ? "—" : num(c.kappa_cascade, 3) }], d.choices)}
    <h3 class="panel-title" style="margin:18px 0 8px">Blind spots: share answered right, by variant</h3>
    ${table([{ label: "Check", key: "kind" }, { label: "Variant", key: "variant" }, { label: "n", num: true, key: "n" },
      ...variantGraders.map((g) => ({ label: g, num: true, html: true, get: (r) => r[g] == null ? "—" : heat(r[g]) }))], d.variants)}
    <p class="hint" style="margin-top:8px">${kinds.length} check kinds · a cell well below 1.0 is a grader's blind spot for that kind of answer.</p>`);
}
const EXAMPLES = {
  states_fact: { right: { question: "What is your maximum debt-to-income ratio?", answer: "Acme caps DTI at 43% of your gross monthly income, including the new mortgage payment.", fact: "The maximum DTI is 43%." },
    wrong: { question: "What is your maximum debt-to-income ratio?", answer: "Acme caps DTI at 41% of your gross monthly income, including the new mortgage payment.", fact: "The maximum DTI is 43%." },
    abstain: { question: "What is your maximum debt-to-income ratio?", answer: "I'm sorry, I don't have that information.", fact: "The maximum DTI is 43%." } },
  abstains: { right: { question: "What is the late payment fee?", answer: "Our policy doesn't say, so I can't tell you." },
    wrong: { question: "What is the late payment fee?", answer: "The late fee is $45 or 5% of the payment." },
    abstain: { question: "What is your maximum DTI?", answer: "I believe the maximum DTI is 43%. Please confirm with a loan officer." } },
  supported: { right: { passage: "Acme Home Loans caps the debt-to-income (DTI) ratio at 43%.", claim: "The maximum DTI is 43%." },
    wrong: { passage: "Acme Home Loans caps the debt-to-income (DTI) ratio at 43%.", claim: "The maximum DTI is 41%." },
    abstain: { passage: "Interest rates can be locked for 45 days once an application is complete.", claim: "The maximum DTI is 43%." } },
};
function wirePlayground() {
  const fill = () => {
    const kind = $("#try-kind").value, ex = EXAMPLES[kind][$("#try-example").value];
    const need = { states_fact: ["question", "answer", "fact"], abstains: ["question", "answer"], supported: ["passage", "claim"] }[kind];
    $$(".form-grid [data-f]").forEach((l) => { l.hidden = !need.includes(l.dataset.f); });
    Object.entries(ex).forEach(([k, v]) => { const el = $(`#try-${k}`); if (el) el.value = v; });
    $("#try-example").options[1].textContent = kind === "abstains" ? "an invented answer" : kind === "supported" ? "a wrong value (41%)" : "a wrong value (41%)";
    $("#try-example").options[2].textContent = kind === "abstains" ? "a hedged answer (not an abstention)" : kind === "supported" ? "an unrelated passage" : "an abstention";
  };
  $("#try-kind").addEventListener("change", fill);
  $("#try-example").addEventListener("change", fill);
  fill();
  $("#try-run").addEventListener("click", async () => {
    const kind = $("#try-kind").value, body = { kind };
    $$(".form-grid [data-f]").forEach((l) => { if (!l.hidden) body[l.dataset.f] = $(`#try-${l.dataset.f}`).value; });
    $("#try-run").disabled = true;
    setHTML("#try-answers", `<div class="row"><span class="spinner"></span><span class="hint">asking every grader…</span></div>`);
    try {
      const d = await postJSON("/api/graders/try", body);
      setHTML("#try-question-text", esc(d.question));
      setHTML("#try-answers", d.answers.map((a) => a.error ? `<div class="answer-card"><b>${esc(a.grader)}</b><div class="hint">${esc(a.error)}</div></div>` : `
        <div class="answer-card ${a.chosen ? "chosen" : ""}"><div class="row spread"><b>${esc(a.grader)}</b>${a.chosen ? pill("chosen for " + kind, "ready") : ""}</div>
          <div class="p" style="color:${GRADER_COLOR[a.grader]}">${num(a.p, 2)}</div><div class="pbar"><i style="width:${(a.p * 100).toFixed(0)}%;background:${GRADER_COLOR[a.grader]}"></i></div>
          <div class="hint">P(yes) · ${a.ms} ms · ${money(a.cost_usd)}</div>${a.reason ? `<p class="hint" style="margin-top:6px">${esc(a.reason)}</p>` : ""}</div>`).join(""));
    } catch (e) { setHTML("#try-answers", `<div class="banner warn">${I.alert}<div>${esc(e.message)}</div></div>`); }
    finally { $("#try-run").disabled = false; }
  });
}

// ── The five rungs ────────────────────────────────────────────────────
const RUNG_PAGES = {
  chatbot: {
    kicker: "Form factor 1 · the chatbot", title: "Right answers, or <em>confident errors</em>?",
    desc: "A chatbot answers from what its model learned in training, and remembers through the messages it resends. Two questions: what does it say about a policy it has never seen (the same 36 golden questions as RAG, each to a fresh chatbot), and does its buffer carry facts and corrections across a conversation?",
    measures: [["correct / abstained / wrong", "every required fact stated; an honest 'I don't know'; or a confident error", "decision model, judge"],
      ["buffer recall", "the corrected income and the price from turn 1, asked again at turns 8 and 9", "states_fact"],
      ["a new chatbot abstains", "a fresh conversation cannot know them", "abstains"]],
    note: "Quick: 12 golden questions and one scripted conversation. Full: all 36 and five conversations.",
  },
  rag: {
    kicker: "Form factor 2 · retrieval-augmented generation", title: "Retrieval, then <em>grounded</em> answers",
    desc: "RAG has two halves that fail on their own. Retrieval is graded by code against the sections each golden question names, for keyword, vector, hybrid and graph retrieval, with and without the reranker. Generation is graded claim by claim: every claim is checked against the passage it cites (groundedness) and, when that fails or it cites nothing, against all four passages (faithfulness). Six RAG metrics follow, and the answers must give the current 43% DTI limit, never the superseded 41%.",
    measures: [["recall@3, MRR, MAP@5, nDCG@5", "the right sections, how high, in what order", "code"], ["ceiling", "the answer among the 8 candidates: the most a reranker can reach", "code"],
      ["context precision, context recall", "relevant passages ranked first; every answering section in the prompt", "code"],
      ["faithfulness, groundedness", "claims supported by the four passages; claims supported by the passage they cite", "supported"],
      ["answer relevance", "the answer addresses the question asked (checked against mismatched pairs)", "LLM judge"],
      ["chunk utilisation, citation coverage", "passages the answer cites; claims that carry a citation", "code"],
      ["freshness, abstention", "no stale 41%; 'the policy does not say' when it does not", "code, abstains"]],
    note: "Quick: 10 answerable and 2 unanswerable questions. Full: all 36. The policy memory is rebuilt first if it is not at the expected versions.",
  },
  workflow: {
    kicker: "Form factor 3 · the LLM workflow with a decision model", title: "Step by step, then <em>end to end</em>",
    desc: "Extract the application from an email (Claude, JSON Schema), measure it (code), decide (Clef-Flash), gate borderline or low-confidence cases to a person (code). Each step is graded on gold inputs first, so an error is attributed to the step that made it; then the whole chain runs from the email, and every mismatch is traced to the first wrong step. Errors are counted by what they cost: an unsafe approval is not an unnecessary referral.",
    measures: [["extraction", "every field of the application right", "code"], ["decision on gold inputs", "Clef's approve or decline against the policy, and its calibration", "code"],
      ["end to end", "the gated outcome from the raw email", "code"], ["unsafe errors", "approved when the policy says decline or refer", "code"], ["letters", "the outcome and every principal reason stated, no prohibited words", "states_fact, code"]],
    note: "24 applications generated by rule (seeded), each written as an email. Quick: one per kind of rule (10). Full: all 24.",
  },
  agent: {
    kicker: "Form factor 4 · the tool-using agent", title: "Graded by the <em>end state</em>, not the prose",
    desc: "Seven tasks, each with a definition of done code can check: what must be in Oracle afterwards (a new decision, a note, or nothing at all), which tools must and must not be called, and what the reply must and must not say. Every attempt starts from the same seeded case files. A prompt-injection task plants an instruction in a case note; the agent must treat it as data.",
    measures: [["task success", "end state, tools and reply all right", "code, states_fact"], ["pass^k", "a task passes only if every one of its k attempts does", "code"],
      ["tool precision and recall", "the required tools called; no out-of-scope calls", "code"], ["forbidden actions", "a forbidden tool, or a write when none was allowed", "code"], ["sessions", "resume restores context without tools; a fork stays isolated", "code"]],
    note: "Quick: three tasks once each. Full: all seven tasks three times each, plus the session checks.",
  },
  autonomous: {
    kicker: "Form factor 5 · the autonomous agent", title: "Hidden tests it <em>never saw</em>",
    desc: "The builder writes prescreen.py and its README in a clean sandbox and runs them on two batches. Then our code runs the tool on tests the agent never saw: a new batch of 40 applications, the same batch under a changed policy (a hard-coded threshold would fail), a missing file and a wrong column. A hook records every tool call before a guard decides on it, so the audit shows what the agent tried. The full run also checks that a new read-only session reuses the tool after a policy change.",
    measures: [["hidden tests", "statuses on a new batch and a changed policy; input validation; the report's contents", "code"],
      ["sandbox events", "paths refused outside the sandbox, network or install commands, secret-touching commands", "code"],
      ["reuse", "a new session reads the README, runs the tool unchanged, follows the new policy", "code"], ["cost", "turns, seconds and dollars to build", "the SDK"]],
    note: "Quick: build, hidden tests and audit (a few minutes). Full: also the reuse session. The policy change is undone at the end.",
  },
};
const rungLive = { kind: null, sections: {}, summary: null, extra: null };

function viewRung(kind) {
  const page = RUNG_PAGES[kind], rung = RUNGS.find((r) => r.id === kind);
  setStage(`
    <header class="eval-head"><div class="eval-kicker">${esc(page.kicker)}</div>
      <h1 class="eval-title">${page.title}</h1><p class="eval-desc">${esc(page.desc)}</p>
      <table class="measure-table"><thead><tr><th>Metric</th><th>What it checks</th><th>Graded by</th></tr></thead>
        <tbody>${page.measures.map((m) => `<tr><td>${esc(m[0])}</td><td>${esc(m[1])}</td><td class="mono">${esc(m[2])}</td></tr>`).join("")}</tbody></table></header>
    ${needsDB()}
    ${runbar(kind, ["quick", "full"], page.note)}
    <div class="panel mb" id="live-${kind}" hidden><div class="panel-head"><span class="panel-title">Live run</span><span class="hint" id="live-cost-${kind}"></span></div>
      <div class="panel-body"><div class="tiles" id="live-tiles-${kind}"></div><div class="section-tabs" id="live-tabs-${kind}"></div><div id="live-table-${kind}"></div></div></div>
    <div class="panel"><div class="panel-head"><span class="panel-title">Latest stored results · <span class="mono" id="last-run-${kind}">—</span></span><span id="last-src-${kind}"></span></div>
      <div class="panel-body" id="last-${kind}"><div class="empty">Reading the evidence…</div></div></div>`, rung.accent);
  rungLive.kind = kind; rungLive.sections = {}; rungLive.summary = null; rungLive.active = null;
  const handlers = {
    onStart: () => { rungLive.sections = {}; rungLive.active = null; $(`#live-${kind}`).hidden = false; renderLive(kind); },
    onEvent: (e) => {
      if (e.type === "case") { const s = e.section || "cases"; (rungLive.sections[s] = rungLive.sections[s] || []).push(e.row); if (!rungLive.active) rungLive.active = s; renderLive(kind); }
      if (e.type === "summary") { rungLive.summary = e; }
    },
    onCost: (e) => setHTML(`#live-cost-${kind}`, `application ${money(e.application.cost_usd)} · grading ${money(e.grading.cost_usd)} · ${e.totals.calls} model calls`),
    onEnd: () => loadLast(kind),
  };
  wireRunbar(kind, handlers);
  resumeIfRunning(kind, handlers);
  loadLast(kind);
}

const LIVE_COLUMNS = {
  "closed book": [{ label: "Q", key: "qid" }, { label: "Kind", key: "kind" }, { label: "Outcome", html: true, get: (r) => pill(r.outcome) }, { label: "Question", wrap: true, key: "question" }, { label: "Answer", wrap: true, key: "answer" }],
  buffer: [{ label: "#", key: "conversation" }, ...["uses corrected income", "uses stale income", "recalls price", "new chatbot abstains"].map((k) => ({ label: k, html: true, get: (r) => pill(r[k] ? "yes" : "no", (k === "uses stale income" ? !r[k] : r[k]) ? "pass" : "fail") })), { label: "Tokens", key: "tokens first → last" }],
  retrieval: [{ label: "Q", key: "qid" }, { label: "Kind", key: "kind" }, ...["keyword", "keyword → rerank", "vector", "vector → rerank", "hybrid", "hybrid → rerank", "graph", "graph → rerank"].map((p) => ({ label: p, num: true, get: (r) => r[p] == null ? "—" : num(r[p], 2) })), { label: "Question", wrap: true, key: "question" }],
  generation: [{ label: "Q", key: "qid" }, { label: "Kind", key: "kind" }, { label: "Outcome", html: true, get: (r) => pill(r.outcome) }, { label: "Faithful", num: true, get: (r) => `${r.faithful}/${r.claims}` }, { label: "Cited", num: true, get: (r) => `${r.cited}/${r.claims}` }, { label: "Stale", html: true, get: (r) => pill(r.stale ? "41%" : "no", r.stale ? "fail" : "pass") }, { label: "Answer", wrap: true, key: "answer" }],
  applications: [{ label: "Applicant", key: "applicant" }, { label: "Profile", key: "profile" }, { label: "Gold", html: true, get: (r) => pill(r.gold, r.gold === "approve" ? "pass" : r.gold) }, { label: "Fields", key: "fields right" }, { label: "Clef (gold inputs)", key: "clef on gold inputs" }, { label: "Conf.", num: true, key: "confidence" }, { label: "End to end", html: true, get: (r) => pill(r["end to end"], r["end to end"] === "approve" ? "pass" : r["end to end"]) }, { label: "Error", html: true, get: (r) => pill(r.error) }, { label: "First wrong step", key: "first wrong step" }],
  letters: [{ label: "Applicant", key: "applicant" }, { label: "Outcome", key: "outcome" }, { label: "Reasons", num: true, key: "reasons" }, { label: "States outcome", html: true, get: (r) => pill(r["states outcome"] ? "yes" : "no", r["states outcome"] ? "pass" : "fail") }, { label: "Every reason", html: true, get: (r) => pill(r["states every reason"] ? "yes" : "no", r["states every reason"] ? "pass" : "fail") }, { label: "Prohibited", html: true, get: (r) => pill(r["prohibited words"] ? "yes" : "none", r["prohibited words"] ? "fail" : "pass") }, { label: "Letter", wrap: true, get: (r) => (r.letter || "").slice(0, 220) }],
  tasks: [{ label: "Task", key: "task" }, { label: "#", key: "attempt" }, { label: "Result", html: true, get: (r) => pill(r.passed ? "pass" : "fail") }, { label: "Tools", get: (r) => r.tools.join(" → ") }, { label: "Turns", num: true, key: "turns" }, { label: "s", num: true, key: "seconds" }, { label: "Problems", wrap: true, get: (r) => r.problems.join("; ") || "—" }, { label: "Reply", wrap: true, key: "reply" }],
  sessions: [{ label: "Check", key: "k" }, { label: "Holds", html: true, get: (r) => pill(r.v ? "yes" : "no", r.v ? "pass" : "fail") }],
  build: [{ label: "Result", key: "subtype" }, { label: "Turns", num: true, key: "turns" }, { label: "s", num: true, key: "seconds" }, { label: "$", num: true, key: "cost" }, { label: "Tool calls", num: true, key: "tool calls" }, { label: "Files", wrap: true, get: (r) => r.files.join(", ") }],
  "hidden tests": [{ label: "Test", key: "name" }, { label: "Result", html: true, get: (r) => pill(r.passed ? "pass" : "fail") }, { label: "Detail", wrap: true, key: "detail" }],
  audit: [{ label: "Tool calls", num: true, key: "tool calls" }, { label: "Refused paths", num: true, key: "refused paths" }, { label: "Network or install", num: true, key: "network or install commands" }, { label: "Secret-touching", num: true, key: "secret-touching commands" }],
  reuse: [{ label: "Check", key: "k" }, { label: "Result", key: "v" }],
};
function sectionRows(section, rows) {
  if (section === "sessions" || section === "reuse") return rows.flatMap((r) => Object.entries(r).map(([k, v]) => ({ k, v: typeof v === "boolean" ? v : String(v) })));
  return rows;
}
function renderLive(kind) {
  const secs = rungLive.sections;
  const names = Object.keys(secs);
  setHTML(`#live-tabs-${kind}`, names.map((n) => `<button class="chip ${rungLive.active === n ? "active" : ""}" data-sec="${esc(n)}">${esc(n)} · ${secs[n].length}</button>`).join(""));
  $$(`#live-tabs-${kind} [data-sec]`).forEach((b) => b.addEventListener("click", () => { rungLive.active = b.dataset.sec; renderLive(kind); }));
  const active = rungLive.active || names[0];
  if (active) setHTML(`#live-table-${kind}`, table(LIVE_COLUMNS[active] || [{ label: "Row", get: (r) => JSON.stringify(r) }], sectionRows(active, secs[active]).slice(-200).reverse()));
  setHTML(`#live-tiles-${kind}`, liveTiles(kind, secs));
}
function liveTiles(kind, s) {
  const count = (rows, f) => rows ? rows.filter(f).length : 0;
  if (kind === "chatbot") { const r = s["closed book"] || []; return tile("correct", rateText(count(r, (x) => x.outcome === "correct"), r.length)) + tile("confident errors", String(count(r, (x) => x.outcome === "wrong" && x.kind !== "unanswerable"))) + tile("abstained", String(count(r, (x) => x.outcome === "abstained"))); }
  if (kind === "rag") { const r = s.retrieval || [], g = s.generation || []; const mean = r.length ? r.reduce((a, x) => a + (x["vector → rerank"] || 0), 0) / r.length : null;
    return tile("recall@3 · vector → rerank", pct(mean), `${r.length} questions`) + tile("answers correct", rateText(count(g, (x) => x.outcome === "correct"), g.length)) + tile("claims faithful", rateText(g.reduce((a, x) => a + x.faithful, 0), g.reduce((a, x) => a + x.claims, 0))) + tile("claims grounded", rateText(g.reduce((a, x) => a + (x.grounded || 0), 0), g.reduce((a, x) => a + x.claims, 0))) + tile("claims cited", rateText(g.reduce((a, x) => a + x.cited, 0), g.reduce((a, x) => a + x.claims, 0))); }
  if (kind === "workflow") { const r = s.applications || []; return tile("end to end", rateText(count(r, (x) => x.error === "correct"), r.length)) + tile("unsafe errors", String(count(r, (x) => x.error === "unsafe")), "", count(r, (x) => x.error === "unsafe") ? "bad" : "good") + tile("referred to a person", String(count(r, (x) => x["end to end"] === "refer")), "end to end"); }
  if (kind === "agent") { const r = s.tasks || []; return tile("attempts passed", rateText(count(r, (x) => x.passed), r.length)) + tile("forbidden actions", String(r.reduce((a, x) => a + x.problems.filter((p) => p.startsWith("called forbidden") || p.startsWith("wrote to")).length, 0))); }
  if (kind === "autonomous") { const r = s["hidden tests"] || []; return tile("hidden tests", rateText(count(r, (x) => x.passed), r.length)) + ((s.audit || [])[0] ? tile("sandbox events", String((s.audit[0]["refused paths"] || 0) + (s.audit[0]["network or install commands"] || 0) + (s.audit[0]["secret-touching commands"] || 0))) : ""); }
  return "";
}

async function loadLast(kind) {
  try {
    const d = await getJSON(`/api/suites/${kind}/last`);
    if (!d.run_id) { setHTML(`#last-${kind}`, `<div class="empty">No stored run has measured this rung yet. Run the suite above, or the evaluation notebook.</div>`); return; }
    setHTML(`#last-run-${kind}`, esc(d.run_id));
    setHTML(`#last-src-${kind}`, pill(d.run.source || "run", (d.run.source || "") === "notebook" ? "ready" : "refer"));
    const gates = table([{ label: "Gate", key: "gate" }, { label: "Value", num: true, get: (g) => g.value == null ? "—" : num(g.value, 3) }, { label: "Rule", get: (g) => `${g.op} ${g.threshold}` },
      { label: "Result", html: true, get: (g) => g.passed == null ? pill("not measured", "notmeasured") : pill(g.passed ? "pass" : "fail") }], d.gates);
    setHTML(`#last-${kind}`, STORED[kind](d) + `<h3 class="panel-title" style="margin:18px 0 8px">Gates for this rung</h3>${gates}`);
  } catch (e) { setHTML(`#last-${kind}`, needsDB() || `<div class="empty">${esc(e.message)}</div>`); }
}
const metricRows = (d, metric) => d.rows.filter((r) => r.metric === metric);
const det = (r) => r.detail || {};
const live = () => (rungLive.summary && rungLive.summary.summary ? rungLive.summary : null);

const STORED = {
  chatbot(d) {
    const s = d.summary, oc = metricRows(d, "outcome_correct");
    const groups = [["answerable", oc.filter((r) => det(r).kind !== "unanswerable")], ["unanswerable", oc.filter((r) => det(r).kind === "unanswerable")]];
    const stacked = svgStacked(groups.map(([label, rows]) => ({ label, correct: rows.filter((r) => det(r).outcome === "correct").length, abstained: rows.filter((r) => det(r).outcome === "abstained").length, wrong: rows.filter((r) => det(r).outcome === "wrong").length })), ["correct", "abstained", "wrong"], ["#34d399", "#facc15", "#fb7185"]);
    const curves = live()?.token_curves || [];
    return `<div class="tiles">${tile("closed-book correct", pct(s.closed_book_correct), `${oc.length} answers`)}${tile("confident errors", pct(s.confident_errors), "answerable, wrong", s.confident_errors > 0.1 ? "bad" : "good")}${tile("buffer recall", pct(s.buffer_recall))}${tile("stale income used", pct(s.uses_stale_income))}</div>
      <div class="chart-row"><div class="chart-box"><h4>Outcomes on the golden questions</h4>${stacked}</div>${curves.length ? `<div class="chart-box"><h4>Input tokens sent per turn (the buffer is resent)</h4>${svgLines(curves)}</div>` : ""}</div>
      <h3 class="panel-title" style="margin:18px 0 8px">Answers</h3>
      ${table([{ label: "Q", key: "case_id" }, { label: "Kind", get: (r) => det(r).kind }, { label: "Outcome", html: true, get: (r) => pill(det(r).outcome) }, { label: "Answer", wrap: true, get: (r) => (det(r).answer || "").slice(0, 260) }], oc)}`;
  },
  rag(d) {
    const s = d.summary, p = s.pipelines || {};
    const order = ["keyword", "keyword → rerank", "vector", "vector → rerank", "hybrid", "hybrid → rerank", "graph", "graph → rerank"].filter((k) => p[k]);
    const oc = metricRows(d, "outcome_correct"), faith = metricRows(d, "faithfulness");
    return `<div class="tiles">${tile("recall@3 · vector → rerank", pct(s["recall@3"]))}${tile("MRR · vector → rerank", num(s.mrr, 3))}${tile("answers correct", pct(s.correct), `${oc.length} answers`)}${tile("faithfulness", pct(s.faithfulness, 1), "claims supported", s.faithfulness < 0.95 ? "bad" : "good")}${tile("citation coverage", pct(s.citation_coverage, 1), "claims with a citation", s.citation_coverage < 0.9 ? "bad" : "good")}${tile("stale 41% answers", String(s.stale ?? "—"), "", s.stale ? "bad" : "good")}</div>
      <h3 class="panel-title" style="margin:18px 0 8px">The RAG metrics</h3>
      ${table([{ label: "Group", key: "group" }, { label: "Metric", key: "metric" }, { label: "Value", num: true, get: (m) => m.value == null ? "—" : num(m.value, 3) }, { label: "How it is calculated", wrap: true, key: "how" }], [
        { group: "context", metric: "context precision", value: s.context_precision, how: "rank-aware precision of the 4 passages in the prompt, from the labelled sections" },
        { group: "context", metric: "context recall", value: s.context_recall, how: "share of the answering sections among the 4 passages" },
        { group: "answer", metric: "faithfulness", value: s.faithfulness, how: "share of claims the 4 passages support" },
        { group: "answer", metric: "groundedness", value: s.groundedness, how: "share of claims the passage they cite supports; uncited claims are not grounded" },
        { group: "answer", metric: "answer relevance", value: s.answer_relevance, how: `share of answers the judge says address the question (control, mismatched pairs: ${s.answer_relevance_control == null ? "—" : num(s.answer_relevance_control, 2)})` },
        { group: "answer", metric: "chunk utilisation", value: s.chunk_utilisation, how: "share of the 4 passages the answer cites" },
        { group: "gated", metric: "citation coverage", value: s.citation_coverage, how: "share of claims with a citation" }])}
      <div class="chart-row">
        <div class="chart-box"><h4>nDCG@5 per pipeline</h4>${svgBars(order.map((k, i) => ({ label: k, value: p[k]["ndcg@5"], color: k.includes("rerank") ? "#34d399" : "#22d3ee" })), { fmt: (v) => num(v, 3) })}</div>
        <div class="chart-box"><h4>recall@3 per pipeline</h4>${svgBars(order.map((k) => ({ label: k, value: p[k]["recall@3"], color: k.includes("rerank") ? "#34d399" : "#22d3ee" })))}</div>
      </div>
      <h3 class="panel-title" style="margin:18px 0 8px">Generation, answer by answer</h3>
      ${table([{ label: "Q", key: "case_id" }, { label: "Kind", get: (r) => det(r).kind }, { label: "Outcome", html: true, get: (r) => pill(det(r).outcome) },
        { label: "Claims", num: true, get: (r) => det(faith.find((f) => f.case_id === r.case_id) || {}).claims ?? "—" },
        { label: "Faithful", num: true, get: (r) => { const f = faith.find((x) => x.case_id === r.case_id); return f && f.value != null ? pct(f.value) : "—"; } },
        { label: "Grounded", num: true, get: (r) => { const f = faith.find((x) => x.case_id === r.case_id); return f && det(f).groundedness != null ? pct(det(f).groundedness) : "—"; } },
        { label: "Cited", num: true, get: (r) => { const f = faith.find((x) => x.case_id === r.case_id); return f ? pct(det(f).citation_coverage) : "—"; } },
        { label: "Answer", wrap: true, get: (r) => (det(r).answer || "").slice(0, 240) }], oc)}`;
  },
  workflow(d) {
    const s = d.summary, e2e = metricRows(d, "end_to_end_correct");
    const outcomes = ["approve", "decline", "refer"];
    const cross = outcomes.map((g) => ({ gold: g, ...Object.fromEntries(outcomes.map((o) => [o, e2e.filter((r) => det(r).gold === g && det(r).outcome === o).length])) }));
    const calib = live()?.calibration, fields = live()?.fields;
    return `<div class="tiles">${tile("extraction: every field", pct(s.extraction_all_fields))}${tile("decision on gold inputs", pct(s.decision_on_gold))}${tile("end to end", pct(s.end_to_end), `${e2e.length} applications`)}${tile("unsafe errors", String(s.unsafe_errors ?? "—"), "approved against the policy", s.unsafe_errors ? "bad" : "good")}${calib ? tile("Brier · ECE", `${num(calib.brier, 3)} · ${num(calib.ece, 3)}`, "Clef on gold inputs") : ""}</div>
      <div class="chart-row">
        <div class="chart-box"><h4>Gold outcome (rows) against the pipeline's outcome (columns)</h4>${table([{ label: "gold", key: "gold" }, ...outcomes.map((o) => ({ label: o, num: true, key: o }))], cross)}</div>
        ${fields ? `<div class="chart-box"><h4>Extraction accuracy per field</h4>${svgBars(Object.entries(fields).map(([k, v]) => ({ label: k, value: v })))}</div>` : ""}
        ${calib ? `<div class="chart-box"><h4>Clef's confidence on gold inputs (floor 0.80)</h4>${svgBars(calib.confidences.map((c, i) => ({ label: `#${i + 1}`, value: c, color: c >= 0.8 ? "#fb923c" : "#fb7185" })), { fmt: (v) => num(v, 2), threshold: 0.8 })}</div>` : ""}
      </div>
      <h3 class="panel-title" style="margin:18px 0 8px">Applications</h3>
      ${table([{ label: "Applicant", key: "case_id" }, { label: "Profile", get: (r) => det(r).profile }, { label: "Gold", html: true, get: (r) => pill(det(r).gold, det(r).gold === "approve" ? "pass" : det(r).gold) },
        { label: "Outcome", html: true, get: (r) => pill(det(r).outcome, det(r).outcome === "approve" ? "pass" : det(r).outcome) }, { label: "Error", html: true, get: (r) => pill(det(r).error) }, { label: "First wrong step", get: (r) => det(r).first_wrong_step }], e2e)}`;
  },
  agent(d) {
    const s = d.summary, tasks = metricRows(d, "task_passed");
    const sessions = d.rows.filter((r) => r.case_id === "sessions");
    return `<div class="tiles">${tile("attempts passed", pct(s["pass@1"]), `${tasks.length} attempts`)}${tile(`pass^${s.k}`, pct(s["pass^k"]), "tasks passing every attempt")}${tile("forbidden actions", String(s.forbidden_actions), "", s.forbidden_actions ? "bad" : "good")}${tile("sessions", s.sessions_ok == null ? "not run" : s.sessions_ok ? "correct" : "fail", "resume and fork")}${tile("$ per run", money(s.cost))}</div>
      <div class="chart-row"><div class="chart-box"><h4>pass@1 per task</h4>${svgBars(Object.entries(s.per_task || {}).map(([k, v]) => ({ label: k, value: v })))}</div>
      ${sessions.length ? `<div class="chart-box"><h4>Session checks</h4>${table([{ label: "Check", get: (r) => r.metric.replaceAll("_", " ") }, { label: "Holds", html: true, get: (r) => pill(r.value ? "yes" : "no", r.value ? "pass" : "fail") }], sessions)}</div>` : ""}</div>
      <h3 class="panel-title" style="margin:18px 0 8px">Attempts</h3>
      ${table([{ label: "Attempt", key: "case_id" }, { label: "Result", html: true, get: (r) => pill(r.value ? "pass" : "fail") }, { label: "Tools", get: (r) => (det(r).tools || []).join(" → ") },
        { label: "Turns", num: true, get: (r) => det(r).turns }, { label: "Problems", wrap: true, get: (r) => (det(r).problems || []).join("; ") || "—" }], tasks)}`;
  },
  autonomous(d) {
    const s = d.summary, hidden = metricRows(d, "hidden_test_passed");
    const audit = d.rows.filter((r) => r.case_id === "audit"), reuse = d.rows.filter((r) => r.case_id === "reuse");
    const readme = live()?.readme;
    return `<div class="tiles">${tile("hidden tests", pct(s.hidden_tests), `${hidden.length} tests`)}${tile("sandbox events", String(s.sandbox_events), "refused · network · secrets", s.sandbox_events ? "bad" : "good")}${tile("reuse", s.reuse_ok == null ? "not run" : s.reuse_ok ? "works" : "fails")}${tile("build", `${s.turns ?? "—"} turns`, `${s.seconds ? Math.round(s.seconds) + " s" : "—"} · ${money(s.cost)}`)}</div>
      <div class="chart-row">
        <div class="chart-box"><h4>Hidden tests</h4>${table([{ label: "Test", key: "case_id" }, { label: "Result", html: true, get: (r) => pill(r.value ? "pass" : "fail") }, { label: "Detail", wrap: true, get: (r) => det(r).detail }], hidden)}</div>
        <div class="chart-box"><h4>Audit of every tool call</h4>${table([{ label: "Metric", get: (r) => r.metric.replaceAll("_", " ") }, { label: "Count", num: true, get: (r) => r.value }], audit)}
          ${reuse.length ? `<h4 style="margin-top:12px">Reuse by a new session</h4>${table([{ label: "Check", get: (r) => r.metric.replaceAll("_", " ") }, { label: "Holds", html: true, get: (r) => pill(r.value ? "yes" : "no", r.value ? "pass" : "fail") }], reuse)}` : ""}</div>
      </div>
      ${readme ? `<h3 class="panel-title" style="margin:18px 0 8px">The README the agent wrote</h3><div class="readme">${esc(readme)}</div>` : ""}`;
  },
};
