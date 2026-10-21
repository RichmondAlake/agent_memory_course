/* ======================================================================
   Form Factor 4 — the tool-using agent, with session memory in Oracle.
   Sessions (left) are the Agent SDK transcripts mirrored by the
   OracleSessionStore: resume one after a refresh, fork a turn as a
   what-if, or branch from any earlier reply. The case file (right) is
   the application memory the agent reads and writes through its tools.
   The session chat helpers here are shared with the autonomous agent.
   ====================================================================== */

const SESSION_KEYS = { agent: "aiml-agent-session", builder: "aiml-builder-session" };
const agState = { session: null, samples: [], applicant: null };

// ── shared session-chat helpers (FF4 and FF5) ───────────────────────────
function savedSession(kind) { try { return localStorage.getItem(SESSION_KEYS[kind]) || null; } catch (_) { return null; } }
function saveSession(kind, id) { try { id ? localStorage.setItem(SESSION_KEYS[kind], id) : localStorage.removeItem(SESSION_KEYS[kind]); } catch (_) {} }

function sessionList(kind, sessions, current) {
  if (!sessions.length) return `<div class="empty">No sessions yet. Start a conversation; it is mirrored to Oracle as it runs.</div>`;
  return sessions.map((s) => `<button class="sess ${s.session_id === current ? "active" : ""}" data-sid="${esc(s.session_id)}">
      <span class="sess-title">${esc(s.title || "untitled")}</span>
      <span class="sess-meta"><span class="mono">${esc(s.session_id.slice(0, 8))}</span>${s.tag ? `<span class="sess-tag">${esc(s.tag)}</span>` : ""}<span>${s.entries} entries</span><span>${fmtWhen(s.last_modified)}</span></span>
    </button>`).join("");
}

// Turn a stored transcript (text / tool_use / tool_result items) into chat HTML.
function transcriptHTML(items, opts = {}) {
  const out = [];
  let lastAssistant = null;
  items.forEach((m, i) => {
    if (m.kind === "text" && m.role === "user") {
      out.push(`<div class="msg user"><div class="avatar user">YOU</div><div class="bubble">${renderRich(m.text)}</div></div>`);
    } else if (m.kind === "text") {
      lastAssistant = m.uuid;
      const next = items[i + 1];
      const endsTurn = !next || (next.role === "user" && next.kind === "text");
      out.push(`<div class="msg bot"><div class="avatar bot">${I.bot}</div><div class="bubble">${renderRich(m.text)}${opts.images ? opts.images(m.text) : ""}${endsTurn && opts.branch ? `<button class="branch-btn" data-uuid="${esc(m.uuid)}" title="Start a new session that keeps the conversation up to this reply">${I.branch} Branch from here</button>` : ""}</div></div>`);
    } else if (m.kind === "tool_use") {
      out.push(`<div class="tool-chip" data-i="${i}"><details><summary>${I.tool}<span class="tname">${esc(toolLabel(m.name))}</span><span class="tool-args">${esc(argsPreview(m.input, 120))}</span></summary><pre class="ev-pre">${esc(JSON.stringify(m.input, null, 2))}</pre><div class="tool-res"></div></details></div>`);
    } else if (m.kind === "tool_result") {
      out.push(`<div class="tool-result-stored" hidden>${esc((m.text || "").slice(0, 2500))}</div>`);
    }
  });
  return out.join("") || `<div class="empty">This session has no messages yet.</div>`;
}
function attachStoredResults(box) {
  // pair each stored tool result with the tool call before it
  $$(".tool-result-stored", box).forEach((r) => {
    let prev = r.previousElementSibling;
    while (prev && !prev.classList.contains("tool-chip")) prev = prev.previousElementSibling;
    if (prev) { const slot = prev.querySelector(".tool-res"); if (slot && !slot.innerHTML) slot.innerHTML = `<div class="ev-result-head">result</div><pre class="ev-pre">${r.innerHTML}</pre>`; }
    r.remove();
  });
}

// Live events from /run or /chat appended to a chat box.
function liveRenderer(box, opts = {}) {
  let bubble = null;
  const chips = {};
  return (ev) => {
    if (box.querySelector(".empty")) box.innerHTML = "";
    if (ev.type === "text") {
      bubble = document.createElement("div");
      bubble.className = "msg bot";
      bubble.innerHTML = `<div class="avatar bot">${I.bot}</div><div class="bubble">${renderRich(ev.text)}${opts.images ? opts.images(ev.text) : ""}</div>`;
      box.appendChild(bubble);
    } else if (ev.type === "tool_use") {
      const chip = document.createElement("div");
      chip.className = "tool-chip live";
      chip.innerHTML = `<details><summary>${I.tool}<span class="tname">${esc(toolLabel(ev.name))}</span><span class="tool-args">${esc(argsPreview(ev.input, 120))}</span><span class="spinner"></span></summary><pre class="ev-pre">${esc(JSON.stringify(ev.input, null, 2))}</pre><div class="tool-res"></div></details>`;
      chips[ev.id] = chip; box.appendChild(chip);
    } else if (ev.type === "tool_result") {
      const chip = chips[ev.id];
      if (chip) {
        chip.querySelector(".spinner")?.remove();
        chip.classList.toggle("errored", !!ev.is_error);
        chip.querySelector(".tool-res").innerHTML = `<div class="ev-result-head">${ev.is_error ? "error" : "result"}</div><pre class="ev-pre">${esc((ev.text || "").slice(0, 2500))}</pre>`;
      }
    } else if (ev.type === "hook") {
      const h = document.createElement("div");
      h.className = "hook-chip " + ev.decision;
      h.innerHTML = `${ev.decision === "deny" ? I.cross : I.check}<span>hook · <b>${esc(ev.tool)}</b> ${ev.decision === "deny" ? "denied" : "allowed"}</span><span class="mono">${esc(ev.path || "")}</span>`;
      if (ev.decision === "deny" || ev.tool === "Write" || ev.tool === "Edit") box.appendChild(h);
    } else if (ev.type === "files" && opts.files) {
      opts.files(ev, box);
    } else if (ev.type === "result") {
      const r = document.createElement("div");
      r.className = "turn-meta";
      r.innerHTML = `${ev.subtype === "success" ? I.check : I.alert} ${esc(ev.subtype)} · ${ev.num_turns} turns · ${(ev.duration_ms / 1000).toFixed(1)}s · $${(+ev.cost_usd || 0).toFixed(4)} · session <span class="mono">${esc((ev.session_id || "").slice(0, 8))}…</span>`;
      box.appendChild(r);
    } else if (ev.type === "error") {
      const e = document.createElement("div");
      e.className = "banner warn"; e.innerHTML = `${I.alert}<div>${esc(ev.message)}</div>`; box.appendChild(e);
    }
    box.scrollTop = box.scrollHeight;
  };
}

// ── view: agent (FF4) ───────────────────────────────────────────────────
function viewAgent() {
  const f = FF_BY_ID.agent;
  const unavailable = state.health && !state.health.agent_available;
  agState.session = savedSession("agent");
  setStage(`${ffHeader(f)}${needsDB()}${unavailable ? agentBanner() : ""}
    <div class="agent3">
      <aside class="panel side-panel">
        <div class="panel-head"><span class="panel-title">${I.history} Sessions · in Oracle ${memBadge("session", true)}</span><button class="btn btn-ghost" id="ag-sess-refresh">${I.refresh}</button></div>
        <div class="panel-body">
          <button class="btn btn-accent wide-btn" id="ag-new">${I.chat} New conversation</button>
          <div class="hint" style="margin:10px 0">Each conversation is an Agent SDK session, mirrored into <span class="mono">AGENT_SESSION_ENTRIES</span> as it runs. Refresh the page and pick it up again.</div>
          <div class="sess-list" id="ag-sessions"><div class="empty">Loading sessions…</div></div>
        </div>
      </aside>
      <section class="panel chat-col">
        <div class="panel-head"><span class="panel-title">${I.agent} Conversation</span><span class="hint mono" id="ag-current"></span></div>
        <div class="panel-body chat-col-body">
          <div class="chat-scroll tall" id="ag-chat"><div class="empty">Ask as an applicant or a loan officer. The agent decides which lender tools to call.</div></div>
          <div class="chips" id="ag-samples" style="margin:10px 0"></div>
          <div class="composer">
            <textarea id="ag-input" rows="2" placeholder="Message the underwriting agent…"></textarea>
            <div class="composer-side">
              <label class="toggle-lab" title="Send this turn into a new session that starts from a copy of this one; the original stays unchanged"><input type="checkbox" id="ag-fork"> fork as a what-if</label>
              <button class="btn btn-accent" id="ag-send" ${unavailable ? "disabled" : ""}>${I.send} Send</button>
            </div>
          </div>
        </div>
      </section>
      <aside class="panel side-panel">
        <div class="panel-head"><span class="panel-title">${I.memory} Memory it touched</span></div>
        <div class="panel-body">
          <div class="mem-box" id="ag-session-box"></div>
          <div class="mem-box" id="ag-case"><div class="hint">The applicant's file — applications, decisions, notes — appears here when the agent looks it up or changes it.</div></div>
          <div class="hint" style="margin-top:12px">Tools: <span class="mono">search_policies</span> (reads POLICY_DOCS) · <span class="mono">get_case_history</span> (reads LOAN_*, CASE_NOTES) · <span class="mono">reassess_application</span> (Clef; appends a decision) · <span class="mono">add_case_note</span> (writes CASE_NOTES).</div>
        </div>
      </aside>
    </div>`, f.accent);

  getJSON("/api/agent/samples").then((d) => {
    agState.samples = d.samples;
    setHTML("#ag-samples", d.samples.map((s, i) => `<button class="chip seed-chip" data-i="${i}">${esc(s.label)}</button>`).join(""));
    $$("#ag-samples .chip").forEach((b) => b.addEventListener("click", () => { const s = agState.samples[+b.dataset.i]; $("#ag-input").value = s.prompt; autosize($("#ag-input"), 200); }));
  }).catch(() => {});
  $("#ag-new").addEventListener("click", () => { agState.session = null; saveSession("agent", null); setHTML("#ag-chat", '<div class="empty">New conversation. The first message starts a new session.</div>'); renderAgentSessionBox(); loadAgentSessions(); });
  $("#ag-sess-refresh").addEventListener("click", loadAgentSessions);
  $("#ag-send").addEventListener("click", sendAgent);
  $("#ag-input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendAgent(); } });
  $("#ag-input").addEventListener("input", (e) => autosize(e.target, 200));
  loadAgentSessions();
  if (agState.session) openAgentSession(agState.session); else renderAgentSessionBox();
}

async function loadAgentSessions() {
  try {
    const d = await getJSON("/api/agent/sessions");
    setHTML("#ag-sessions", sessionList("agent", d.sessions, agState.session));
    $$("#ag-sessions .sess").forEach((b) => b.addEventListener("click", () => openAgentSession(b.dataset.sid)));
  } catch (e) { setHTML("#ag-sessions", `<div class="empty">${esc(e.message)}</div>`); }
}

async function openAgentSession(id, note) {
  agState.session = id; saveSession("agent", id);
  const box = $("#ag-chat"); if (!box) return;
  box.innerHTML = '<div class="empty"><span class="spinner"></span> loading the session from Oracle…</div>';
  try {
    const d = await getJSON(`/api/agent/sessions/${encodeURIComponent(id)}`);
    box.innerHTML = `<div class="sys-note">${note || `${I.history} Session <span class="mono">${esc(id.slice(0, 8))}…</span> read back from Oracle: ${d.messages.length} messages. Send a message to resume it with full context.`}</div>` + transcriptHTML(d.messages, { branch: true });
    attachStoredResults(box);
    $$(".branch-btn", box).forEach((b) => b.addEventListener("click", () => branchAgent(b.dataset.uuid)));
    box.scrollTop = box.scrollHeight;
    const applicant = d.messages.filter((m) => m.kind === "tool_use" && m.input && m.input.applicant).map((m) => m.input.applicant).pop();
    if (applicant) loadCase(applicant);
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  renderAgentSessionBox(); loadAgentSessions();
}

function renderAgentSessionBox(extra = "") {
  setHTML("#ag-session-box", agState.session
    ? `<div class="mem-h">Session ${memBadge("session", true)}</div><div class="mono">${esc(agState.session)}</div><div class="hint">Resumed with <span class="mono">resume=${esc(agState.session.slice(0, 8))}…</span> on the next message. Stored rows: <span id="ag-entries">…</span></div>${extra}`
    : `<div class="mem-h">Session ${memBadge("session", true)}</div><div class="hint">None yet — the first message creates one.</div>${extra}`);
  if (agState.session) getJSON("/api/agent/sessions").then((d) => { const s = d.sessions.find((x) => x.session_id === agState.session); setText("#ag-entries", s ? `${s.entries} entries` : "not stored yet"); }).catch(() => {});
}

async function branchAgent(uuid) {
  if (!agState.session) return;
  try {
    const r = await postJSON("/api/agent/branch", { session_id: agState.session, message_uuid: uuid });
    await openAgentSession(r.session_id, `${I.branch} New session <span class="mono">${esc(r.session_id.slice(0, 8))}…</span> branched from <span class="mono">${esc(r.branched_from.slice(0, 8))}…</span>; the conversation below ends at the reply you picked. Ask something different.`);
  } catch (e) { alertInline("#ag-chat", e.message); }
}

function alertInline(sel, msg) { const b = $(sel); if (b) b.insertAdjacentHTML("beforeend", `<div class="banner warn">${I.alert}<div>${esc(msg)}</div></div>`); }

async function sendAgent() {
  const input = $("#ag-input"), prompt = input.value.trim();
  if (!prompt || state.abort) return;
  const fork = $("#ag-fork").checked && !!agState.session;
  const box = $("#ag-chat");
  if (box.querySelector(".empty")) box.innerHTML = "";
  if (fork) box.insertAdjacentHTML("beforeend", `<div class="sys-note">${I.branch} Forking: this turn runs in a new session copied from <span class="mono">${esc(agState.session.slice(0, 8))}…</span>; the original is left as it was.</div>`);
  box.insertAdjacentHTML("beforeend", `<div class="msg user"><div class="avatar user">YOU</div><div class="bubble">${renderRich(prompt)}</div></div>`);
  input.value = ""; autosize(input, 200);
  $("#ag-send").disabled = true; setText("#ag-current", "running…");
  const render = liveRenderer(box);
  const from = agState.session;
  state.abort = new AbortController();
  try {
    await streamSSE("/api/agent/run", { prompt, session_id: agState.session, fork }, (ev) => {
      render(ev);
      if (ev.type === "session") { agState.session = ev.session_id; saveSession("agent", ev.session_id); }
      if (ev.type === "tool_use" && ev.input && ev.input.applicant) agState.applicant = ev.input.applicant;
      if (ev.type === "tool_result" && agState.applicant) loadCase(agState.applicant);
      if (ev.type === "result") agState.session = ev.session_id;
    }, state.abort.signal);
  } catch (e) { render({ type: "error", message: e.message }); }
  finally {
    state.abort = null; setText("#ag-current", agState.session ? `session ${agState.session.slice(0, 8)}…` : "");
    const b = $("#ag-send"); if (b) b.disabled = false;
    $("#ag-fork") && ($("#ag-fork").checked = false);
    renderAgentSessionBox(fork && from ? `<div class="hint">Forked from <span class="mono">${esc(from.slice(0, 8))}…</span>, which is unchanged — pick it in the list to see.</div>` : "");
    loadAgentSessions();
    if (agState.applicant) loadCase(agState.applicant);
  }
}

async function loadCase(applicant) {
  try {
    const d = await getJSON(`/api/agent/case/${encodeURIComponent(applicant)}`);
    if (!d.files.length) { setHTML("#ag-case", `<div class="mem-h">Case file · ${esc(applicant)} ${memBadge("episodic", true)}</div><div class="hint">No application on file. Run one on the workflow page first.</div>`); return; }
    setHTML("#ag-case", d.files.map((f) => `<div class="mem-h">Case file · ${esc(f.applicant)} ${memBadge("episodic", true)}</div>
      <div class="hint mono">${esc(f.application_id.slice(0, 8))}… · debts ${money(f.current_facts.monthly_debts)} · income ${money(f.current_facts.gross_monthly_income)}</div>
      <div class="case-list">${f.decisions.map((x) => `<div class="case-dec"><span class="outcome ${x.outcome}">${esc(x.outcome)}</span><span class="mono">#${x.decision_id}</span><span class="hint">${esc(x.decided_at)}</span><div class="hint">${esc((x.decided_by || "").split(" · ")[0])}${x.ratios ? ` · DTI ${pct(x.ratios.dti)}` : ""}${(x.reasons || []).length ? ` · ${esc(x.reasons[0])}` : ""}</div></div>`).join("")}</div>
      ${f.notes.length ? `<div class="mem-h" style="margin-top:8px">Notes</div>${f.notes.map((n) => `<div class="case-note"><b>${esc(n.author)}</b> <span class="hint">${esc(n.written_at)}</span><div>${esc(n.note)}</div></div>`).join("")}` : ""}`).join(""));
  } catch (_) {}
}
