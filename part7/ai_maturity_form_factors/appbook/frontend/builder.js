/* ======================================================================
   Form Factor 5 — the autonomous agent as a chat, with a sandbox.
   Left: sessions in Oracle (resume / branch after a refresh), the sandbox
   files (procedural memory, charts and images) and automations.
   Centre: the chat. Right: the live process on the architecture.
   Below: the full reference architecture with scenario simulations.
   ====================================================================== */

// ── the architecture model (shared by the live pane and the reference view) ──
const ARCH_NODES = [
  { id: "user", label: "You", sub: "chat in browser", short: "You", x: 20, y: 250, w: 120, h: 56, kind: "user",
    detail: "You ask in plain language: build a tool, chart a batch, schedule an automation. Replies, tool calls, hook decisions and images stream back over Server-Sent Events.", code: "frontend/builder.js" },
  { id: "api", label: "FastAPI", sub: "builder/chat · SSE", short: "FastAPI", x: 190, y: 250, w: 150, h: 56, kind: "app",
    detail: "Turns one chat turn into an Agent SDK query: the system prompt, the allowed tools, the hooks, the OS sandbox and the session store. It watches the sandbox and reports changed files after every tool result.", code: "backend/routers/builder.py · chat()" },
  { id: "sdk", label: "Claude Agent SDK", sub: "agent loop · claude CLI", short: "Agent SDK", x: 400, y: 236, w: 190, h: 84, kind: "tool",
    detail: "Runs the loop: send the conversation to Claude, run the tools it asks for, send the results back, repeat until done. It writes the session transcript as it goes and mirrors each batch to the SessionStore.", code: "claude_agent_sdk.query(prompt, options)" },
  { id: "claude", label: "Claude Haiku 5.5", sub: "plans every step", short: "Claude", x: 410, y: 40, w: 170, h: 60, kind: "llm",
    detail: "Decides the next step from the whole session: which file to read, what code to write, which command to run, when to call save_automation, and what to tell you.", code: "model = claude-haiku-5-5" },
  { id: "hook", label: "PreToolUse hook", sub: "path guard · allow/deny", short: "Hook", x: 660, y: 150, w: 170, h: 56, kind: "gate",
    detail: "Runs before every Read, Write, Edit, Glob and Grep. Any path outside the sandbox folder is denied, and the reason goes back to Claude, which corrects itself. Hooks run even with bypassPermissions.", code: "backend/routers/builder.py · _guard()" },
  { id: "ossb", label: "OS sandbox", sub: "Seatbelt · bubblewrap", short: "OS sandbox", x: 660, y: 300, w: 170, h: 56, kind: "risk",
    detail: "Every Bash command runs inside the operating system's sandbox: writes outside the folder fail with 'operation not permitted', and allowUnsandboxedCommands=False removes the escape hatch.", code: "sandbox={'enabled': True, 'allowUnsandboxedCommands': False}" },
  { id: "python", label: "python", sub: "pandas · matplotlib", short: "python", x: 880, y: 300, w: 150, h: 56, kind: "code",
    detail: "The scripts the agent writes run here, inside the OS sandbox. Charts are saved as PNG files with plt.savefig and appear in the chat once they exist in the folder.", code: "PATH starts with this app's Python" },
  { id: "files", label: "Sandbox folder", sub: "tools · CSV · PNG", short: "Sandbox", x: 880, y: 150, w: 150, h: 56, kind: "mem",
    detail: "The only place the agent can write. Tools and their READMEs persist between sessions — procedural memory a later session finds and reuses. policy.json is exported from Oracle.", code: "backend/sandbox/" },
  { id: "ops", label: "ops MCP server", sub: "policy · automations", short: "ops MCP", x: 400, y: 430, w: 190, h: 56, kind: "tool",
    detail: "In-process MCP tools beside the file and shell tools: refresh policy.json from Oracle, save a script as an automation, list or run automations.", code: "backend/routers/builder.py · _ops_tools()" },
  { id: "sched", label: "Scheduler", sub: "ticks every 15 s", short: "Scheduler", x: 660, y: 450, w: 170, h: 56, kind: "gate",
    detail: "Saved automations snapshot the sandbox and re-run `python <script>.py` on demand or on a schedule (once, every N minutes, daily). Each run records its exit code and output.", code: "backend/core/automations.py" },
  { id: "policy", label: "Oracle · POLICY_DOCS", sub: "rules · versions", short: "POLICY_DOCS", x: 860, y: 450, w: 180, h: 56, kind: "db",
    detail: "Acme's lending policy — the semantic memory from Form Factor 2. export_policy writes its current rules and versions to policy.json, so tools never hard-code a threshold.", code: "backend/core/underwriting.py · current_policy()" },
  { id: "store", label: "Oracle · SessionStore", sub: "AGENT_SESSION_ENTRIES", short: "SessionStore", x: 180, y: 430, w: 190, h: 56, kind: "db",
    detail: "OracleSessionStore mirrors every transcript batch (append) and rebuilds a session on resume (load). That is why you can refresh the page, pick a session and continue — or branch from an earlier reply.", code: "backend/core/sessions.py · OracleSessionStore" },
];
const ARCH_EDGES = [
  ["user", "api"], ["api", "user"], ["api", "sdk"], ["sdk", "api"], ["sdk", "claude"], ["claude", "sdk"], ["sdk", "hook"], ["hook", "files"],
  ["sdk", "ossb"], ["ossb", "python"], ["python", "files"], ["sdk", "ops"], ["ops", "sched"], ["ops", "policy"], ["policy", "files"],
  ["sdk", "store"], ["store", "sdk"], ["files", "api"], ["sched", "python"],
];
const ARCH_BY_ID = Object.fromEntries(ARCH_NODES.map((n) => [n.id, n]));

function edgePath(a, b) {
  const A = ARCH_BY_ID[a], B = ARCH_BY_ID[b];
  const ax = A.x + A.w / 2, ay = A.y + A.h / 2, bx = B.x + B.w / 2, by = B.y + B.h / 2;
  const back = ARCH_EDGES.some(([x, y]) => x === b && y === a);
  const off = back ? (a < b ? -9 : 9) : 0;
  const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy) || 1, nx = -dy / len * off, ny = dx / len * off;
  const clip = (x, y, n, tx, ty) => { // start/end on the box border
    const hw = n.w / 2, hh = n.h / 2, vx = tx - x, vy = ty - y;
    const s = Math.min(Math.abs(vx) > 0 ? hw / Math.abs(vx) : 1e9, Math.abs(vy) > 0 ? hh / Math.abs(vy) : 1e9);
    return [x + vx * s, y + vy * s];
  };
  const [sx, sy] = clip(ax, ay, A, bx, by), [ex, ey] = clip(bx, by, B, ax, ay);
  return `M${sx + nx} ${sy + ny} L${ex + nx} ${ey + ny}`;
}

function archSVG(idPrefix, big) {
  const W = 1050, H = 520;
  const edges = ARCH_EDGES.map(([a, b]) => `<path id="${idPrefix}-e-${a}-${b}" class="ae" d="${edgePath(a, b)}" marker-end="url(#${idPrefix}-arrow)"/>`).join("");
  const nodes = ARCH_NODES.map((n) => `<g class="an ${n.kind}" id="${idPrefix}-n-${n.id}" data-node="${n.id}" tabindex="0"><rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="11"/><text x="${n.x + n.w / 2}" y="${n.y + n.h / 2 + (big ? -3 : 7)}" text-anchor="middle" class="an-l">${esc(big ? n.label : n.short)}</text>${big ? `<text x="${n.x + n.w / 2}" y="${n.y + n.h / 2 + 14}" text-anchor="middle" class="an-s">${esc(n.sub)}</text>` : ""}<text class="an-x" x="${n.x + n.w - 14}" y="${n.y + 18}">✕</text></g>`).join("");
  const zones = big ? `<rect class="az" x="645" y="130" width="400" height="245" rx="16"/><text class="az-l" x="655" y="124">sandbox boundary · hook + OS sandbox</text>
    <rect class="az db" x="168" y="416" width="214" height="84" rx="16"/><rect class="az db" x="848" y="436" width="196" height="84" rx="16"/><text class="az-l" x="178" y="410">Oracle AI Database</text>` : "";
  return `<svg class="arch-svg ${big ? "big" : ""}" viewBox="0 0 ${W} ${H}" id="${idPrefix}-svg"><defs><marker id="${idPrefix}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" class="am"/></marker></defs>${zones}${edges}${nodes}<g id="${idPrefix}-packets"></g></svg>`;
}

function pulseNode(prefix, id, cls = "hot", ms = 1100) {
  const n = document.getElementById(`${prefix}-n-${id}`); if (!n) return;
  n.classList.add(cls); clearTimeout(n.__t); n.__t = setTimeout(() => n.classList.remove(cls), ms);
}
function sendPacket(prefix, a, b, color, ms = 700) {
  return new Promise((resolve) => {
    const path = document.getElementById(`${prefix}-e-${a}-${b}`), layer = document.getElementById(`${prefix}-packets`);
    if (!path || !layer) return resolve();
    path.classList.add("live"); setTimeout(() => path.classList.remove("live"), ms + 500);
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("r", "6"); dot.setAttribute("class", "packet"); if (color) dot.style.fill = color;
    layer.appendChild(dot);
    const len = path.getTotalLength(), t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms), p = path.getPointAtLength(len * k);
      dot.setAttribute("cx", p.x); dot.setAttribute("cy", p.y);
      if (k < 1) requestAnimationFrame(tick); else { dot.remove(); resolve(); }
    };
    requestAnimationFrame(tick);
  });
}
async function flow(prefix, hops, color) {
  for (const [a, b] of hops) { pulseNode(prefix, a); await sendPacket(prefix, a, b, color); pulseNode(prefix, b); }
}

document.addEventListener("sandboxchange", () => { if ($("#bd-files")) loadFiles(); });

// ── live mapping from real events to the architecture ───────────────────
const bdState = { session: null, files: [], live: [], playing: null, step: 0, scenario: null };
function liveEvent(ev) {
  const P = "live";
  const log = (icon, text, cls = "") => {
    bdState.live.unshift({ icon, text, cls, t: new Date() });
    bdState.live = bdState.live.slice(0, 40);
    setHTML("#live-log", bdState.live.map((e) => `<div class="ll ${e.cls}"><span class="ll-i">${e.icon}</span><span>${e.text}</span><time>${e.t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>`).join(""));
  };
  if (ev.type === "session") { flow(P, [["api", "sdk"], ["sdk", "store"]], "#34d399"); log("◆", `session <span class="mono">${esc(ev.session_id.slice(0, 8))}…</span> · mirrored to Oracle`); }
  else if (ev.type === "tool_use") {
    const n = ev.name;
    flow(P, [["claude", "sdk"]], "#c084fc");
    if (["Read", "Write", "Edit", "Glob", "Grep"].includes(n)) { flow(P, [["sdk", "hook"]], "#fbbf24"); log("✎", `<b>${esc(n)}</b> <span class="mono">${esc(String(ev.input.file_path || ev.input.path || ev.input.pattern || "").split("/").pop())}</span>`); }
    else if (n === "Bash") { flow(P, [["sdk", "ossb"], ...(/\bpython/.test(ev.input.command || "") ? [["ossb", "python"]] : [])], "#fb7185"); log("$", `<b>Bash</b> <span class="mono">${esc((ev.input.command || "").slice(0, 70))}</span>`); }
    else if (n.startsWith("mcp__ops__")) {
      const t = toolLabel(n);
      flow(P, [["sdk", "ops"], ...(t === "save_automation" || t === "run_automation" ? [["ops", "sched"]] : t === "export_policy" ? [["ops", "policy"], ["policy", "files"]] : [])], "#60a5fa");
      log("⚙", `<b>${esc(t)}</b>`);
    }
  } else if (ev.type === "hook") {
    if (ev.decision === "deny") { pulseNode(P, "hook", "deny", 2200); log("✕", `hook <b>denied</b> ${esc(ev.tool)} · <span class="mono">${esc(ev.path)}</span>`, "deny"); }
    else if (ev.tool !== "Bash") flow(P, [["hook", "files"]], "#34d399");
  } else if (ev.type === "tool_result") { flow(P, [["sdk", "claude"]], "#22d3ee"); }
  else if (ev.type === "files") {
    const imgs = ev.changed.filter((f) => f.kind === "image");
    pulseNode(P, "files");
    if (imgs.length) flow(P, [["files", "api"], ["api", "user"]], "#facc15");
    log("▣", `files changed: ${ev.changed.map((f) => `<span class="mono">${esc(f.path)}</span>`).join(", ")}`);
  } else if (ev.type === "text") { flow(P, [["sdk", "api"], ["api", "user"]], "#c084fc"); }
  else if (ev.type === "result") { flow(P, [["sdk", "store"]], "#34d399"); log("✓", `turn done · ${ev.num_turns} turns · $${(+ev.cost_usd || 0).toFixed(4)} · transcript mirrored`); }
  else if (ev.type === "error") { log("!", esc(ev.message), "deny"); }
}

// ── scenario simulations (no API calls) ──────────────────────────────────
const SCENARIOS = {
  build: { title: "Build a reusable tool", steps: [
    { hops: [["user", "api"], ["api", "sdk"]], text: "You ask for a pre-screen tool. FastAPI starts an Agent SDK query with the sandbox, the hook and the session store." },
    { hops: [["sdk", "store"]], text: "The SDK opens a session and mirrors its first transcript entries to Oracle (append)." },
    { hops: [["sdk", "claude"], ["claude", "sdk"]], text: "Claude plans: list the folder and read README.md first, in case a tool already exists." },
    { hops: [["sdk", "hook"], ["hook", "files"]], text: "Read README.md → the PreToolUse hook checks the path: inside the sandbox, allowed." },
    { hops: [["sdk", "hook"], ["hook", "files"]], text: "Write prescreen.py → allowed. Thresholds are read from policy.json, never hard-coded." },
    { hops: [["sdk", "ossb"], ["ossb", "python"], ["python", "files"]], text: "Bash runs python prescreen.py on batch 1 inside the OS sandbox; report_batch1.json lands in the folder." },
    { hops: [["files", "api"], ["sdk", "claude"], ["claude", "sdk"], ["sdk", "api"], ["api", "user"]], text: "Claude reads the result and summarises: who passes, who is referred, who fails, and why." },
    { hops: [["sdk", "store"]], text: "The final batch is mirrored. The tool and README stay on disk: procedural memory for later sessions." },
  ] },
  chart: { title: "Chart → image in the chat", steps: [
    { hops: [["user", "api"], ["api", "sdk"], ["sdk", "claude"]], text: "You ask for a DTI chart of batch 1 against the policy limit." },
    { hops: [["claude", "sdk"], ["sdk", "hook"], ["hook", "files"]], text: "Claude writes chart.py — the hook allows it." },
    { hops: [["sdk", "ossb"], ["ossb", "python"]], text: "python runs inside the OS sandbox with matplotlib on the headless Agg backend." },
    { hops: [["python", "files"]], text: "plt.savefig writes dti_batch1.png into the sandbox — the image exists first in the sandbox." },
    { hops: [["files", "api"], ["api", "user"]], text: "FastAPI sees the new PNG after the tool result and streams it to the chat, where it renders inline." },
  ] },
  escape: { title: "Escape attempt blocked", steps: [
    { hops: [["user", "api"], ["api", "sdk"], ["sdk", "claude"]], text: "You ask the agent to read ../../config.py, outside its folder." },
    { hops: [["claude", "sdk"], ["sdk", "hook"]], text: "Claude calls Read with that path. The PreToolUse hook resolves it…", deny: true },
    { hops: [["sdk", "claude"]], text: "…outside the sandbox: denied. The denial reason goes back to Claude as the tool result." },
    { hops: [["claude", "sdk"], ["sdk", "api"], ["api", "user"]], text: "Claude explains it cannot read files outside its folder. Bash would fail too: the OS sandbox blocks it." },
  ] },
  resume: { title: "Resume after a refresh", steps: [
    { hops: [["user", "api"]], text: "You refresh the page, open the session list and pick yesterday's conversation." },
    { hops: [["api", "store"], ["store", "api"], ["api", "user"]], text: "The transcript is read back from AGENT_SESSION_ENTRIES and shown in the chat." },
    { hops: [["user", "api"], ["api", "sdk"]], text: "You send a follow-up. The SDK is started with resume=<session id> and the Oracle store." },
    { hops: [["sdk", "store"], ["store", "sdk"]], text: "Before the CLI starts, the SDK calls load(): the whole conversation comes back from Oracle." },
    { hops: [["sdk", "claude"], ["claude", "sdk"], ["sdk", "api"], ["api", "user"]], text: "Claude answers with full context — no tool calls needed to remember what it built." },
  ] },
  schedule: { title: "Schedule an automation", steps: [
    { hops: [["user", "api"], ["api", "sdk"], ["sdk", "claude"]], text: "You ask for batch 3 to be pre-screened every 30 minutes." },
    { hops: [["claude", "sdk"], ["sdk", "hook"], ["hook", "files"]], text: "Claude reads README.md and reuses prescreen.py instead of writing a new tool." },
    { hops: [["sdk", "ops"], ["ops", "sched"]], text: "It calls save_automation: the sandbox is snapshotted and the command registered, every 30 minutes." },
    { hops: [["sched", "python"], ["python", "files"]], text: "Later, the scheduler fires on its own and runs the command; the report and exit code are recorded." },
  ] },
  policy: { title: "The policy changes", steps: [
    { hops: [["user", "api"], ["api", "sdk"], ["sdk", "claude"]], text: "A bulletin raised the minimum credit score to 660 in POLICY_DOCS (RAG page). You ask to re-screen batch 3." },
    { hops: [["claude", "sdk"], ["sdk", "ops"], ["ops", "policy"], ["policy", "files"]], text: "export_policy reads the current rules and versions from Oracle and rewrites policy.json." },
    { hops: [["sdk", "ossb"], ["ossb", "python"], ["python", "files"]], text: "The same prescreen.py runs unchanged; two applicants now fail on credit score." },
    { hops: [["files", "api"], ["api", "user"]], text: "Semantic memory changed the rules; procedural memory did the work. No code was edited." },
  ] },
};

function viewBuilder() {
  const f = FF_BY_ID.builder;
  const unavailable = state.health && !state.health.agent_available;
  bdState.session = savedSession("builder");
  setStage(`${ffHeader(f)}${needsDB()}
    ${unavailable ? agentBanner() : `<div class="banner warn">${I.alert}<div>This agent writes and runs code with permissions bypassed. A PreToolUse hook keeps its file tools inside <span class="mono">backend/sandbox</span> and the OS sandbox confines its shell commands. Run it locally all the same.</div></div>`}
    <div class="builder3">
      <aside class="panel side-panel">
        <div class="panel-head"><span class="panel-title">${I.history} Sessions · in Oracle ${memBadge("session", true)}</span><button class="btn btn-ghost" id="bd-sess-refresh">${I.refresh}</button></div>
        <div class="panel-body">
          <button class="btn btn-accent wide-btn" id="bd-new">${I.chat} New conversation</button>
          <div class="sess-list" id="bd-sessions" style="margin-top:10px"><div class="empty">Loading…</div></div>
          <div class="side-h"><span>${I.file} Sandbox ${memBadge("procedural", true)}</span><button class="btn btn-ghost mini" id="bd-files-refresh">${I.refresh}</button></div>
          <div class="file-tree" id="bd-files"></div>
          <button class="btn btn-ghost wide-btn" id="bd-reset" title="Empty the sandbox and reseed the batches">${I.history} Reset sandbox</button>
          <div class="side-h">${I.play} Automations <button class="btn btn-ghost mini" id="au-refresh">${I.refresh}</button></div>
          <div class="automations" id="au-list"></div>
        </div>
      </aside>
      <section class="panel chat-col">
        <div class="panel-head"><span class="panel-title">${I.build} Chat with the autonomous agent</span><span class="hint mono" id="bd-current"></span></div>
        <div class="panel-body chat-col-body">
          <div class="chat-scroll tall" id="bd-chat"><div class="empty">Ask it to build a tool, chart a batch, draw an image or set up an automation. It works in the sandbox and shows you what it made.</div></div>
          <div class="chips" id="bd-samples" style="margin:10px 0"></div>
          <div class="composer">
            <textarea id="bd-input" rows="2" placeholder="Message the autonomous agent…"></textarea>
            <div class="composer-side"><button class="btn btn-accent" id="bd-send" ${unavailable ? "disabled" : ""}>${I.send} Send</button></div>
          </div>
        </div>
      </section>
      <aside class="panel arch-panel">
        <div class="panel-head"><span class="panel-title">${I.flow} Live process</span><span class="hint mono">each real event, on the architecture</span></div>
        <div class="panel-body">
          ${archSVG("live", false)}
          <div class="live-log" id="live-log"><div class="hint">Send a message: every tool call, hook decision, file and session write lights up here.</div></div>
        </div>
      </aside>
    </div>

    <section class="panel" style="margin-top:22px">
      <div class="panel-head"><span class="panel-title">${I.window} Reference architecture · run a scenario</span><span class="hint mono">simulation · no model calls</span></div>
      <div class="panel-body">
        <div class="scen-bar">${Object.entries(SCENARIOS).map(([k, s]) => `<button class="chip scen" data-sc="${k}">${esc(s.title)}</button>`).join("")}
          <span class="scen-ctl"><button class="btn btn-ghost" id="sc-play" title="Play">${I.play}</button><button class="btn btn-ghost" id="sc-step" title="Next step">${I.step}</button><button class="btn btn-ghost" id="sc-reset" title="Reset">${I.refresh}</button></span></div>
        <div class="arch-ref">
          <div class="arch-big">${archSVG("ref", true)}</div>
          <div class="arch-side">
            <div class="scen-narr" id="sc-narr"><div class="hint">Pick a scenario and press play, or step through it. Click any component to read what it does and where it lives in the code.</div></div>
            <div class="comp-detail" id="comp-detail"></div>
          </div>
        </div>
      </div>
    </section>
    <div class="drawer" id="file-drawer" hidden><div class="drawer-head"><span class="mono" id="drawer-title"></span><button class="btn btn-ghost" id="drawer-close">${I.cross}</button></div><div class="drawer-body" id="drawer-body"></div></div>`, f.accent);

  getJSON("/api/builder/samples").then((d) => {
    setHTML("#bd-samples", d.samples.map((s, i) => `<button class="chip seed-chip" data-i="${i}">${esc(s.label)}</button>`).join(""));
    $$("#bd-samples .chip").forEach((b) => b.addEventListener("click", () => { $("#bd-input").value = d.samples[+b.dataset.i].prompt; autosize($("#bd-input"), 200); }));
  }).catch(() => {});
  $("#bd-new").addEventListener("click", () => { bdState.session = null; saveSession("builder", null); setHTML("#bd-chat", '<div class="empty">New conversation. The sandbox keeps its files — tools from earlier sessions are still there to reuse.</div>'); loadBuilderSessions(); setText("#bd-current", ""); });
  $("#bd-sess-refresh").addEventListener("click", loadBuilderSessions);
  $("#bd-files-refresh").addEventListener("click", loadFiles);
  $("#au-refresh").addEventListener("click", loadAutomations);
  let armed = false;
  $("#bd-reset").addEventListener("click", async (e) => {
    const b = e.currentTarget;
    if (!armed) { armed = true; b.innerHTML = `${I.alert} Click again: delete built tools`; setTimeout(() => { armed = false; if (b.isConnected) b.innerHTML = `${I.history} Reset sandbox`; }, 4000); return; }
    armed = false; b.disabled = true;
    try { await postJSON("/api/builder/reset"); } catch (_) {}
    b.disabled = false; b.innerHTML = `${I.history} Reset sandbox`; loadFiles();
  });
  $("#bd-send").addEventListener("click", sendBuilder);
  $("#bd-input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendBuilder(); } });
  $("#bd-input").addEventListener("input", (e) => autosize(e.target, 200));
  $("#drawer-close").addEventListener("click", () => { $("#file-drawer").hidden = true; });
  wireScenarios();
  $$("#live-svg .an").forEach((n) => n.addEventListener("click", () => showComponent(n.dataset.node)));
  loadBuilderSessions(); loadFiles(); loadAutomations();
  if (bdState.session) openBuilderSession(bdState.session);
}

async function loadBuilderSessions() {
  try {
    const d = await getJSON("/api/builder/sessions");
    setHTML("#bd-sessions", sessionList("builder", d.sessions, bdState.session));
    $$("#bd-sessions .sess").forEach((b) => b.addEventListener("click", () => openBuilderSession(b.dataset.sid)));
  } catch (e) { setHTML("#bd-sessions", `<div class="empty">${esc(e.message)}</div>`); }
}

function imagesIn(text) {
  const names = [...new Set((text.match(/[\w./-]+\.(?:png|jpe?g|gif|svg|webp)/gi) || []).map((n) => n.replace(/^\.\//, "")))];
  const known = names.map((n) => bdState.files.find((f) => f.path === n || f.path.endsWith("/" + n))).filter(Boolean);
  return known.map((f) => imageCard(f)).join("");
}
function imageCard(f) {
  return `<figure class="img-card"><img src="/api/builder/raw?path=${encodeURIComponent(f.path)}&t=${f.mtime}" alt="${esc(f.path)}" loading="lazy"><figcaption>${I.image} ${esc(f.path)} · made in the sandbox</figcaption></figure>`;
}

async function openBuilderSession(id, note) {
  bdState.session = id; saveSession("builder", id);
  const box = $("#bd-chat"); if (!box) return;
  box.innerHTML = '<div class="empty"><span class="spinner"></span> loading the session from Oracle…</div>';
  try {
    if (!bdState.files.length) await loadFiles();
    const d = await getJSON(`/api/builder/sessions/${encodeURIComponent(id)}`);
    box.innerHTML = `<div class="sys-note">${I.history} ${note || `Session <span class="mono">${esc(id.slice(0, 8))}…</span> read back from Oracle: ${d.messages.length} messages. Send a message to resume it with full context.`}</div>` + transcriptHTML(d.messages, { branch: true, images: imagesIn });
    attachStoredResults(box);
    $$(".branch-btn", box).forEach((b) => b.addEventListener("click", () => branchBuilder(b.dataset.uuid)));
    box.scrollTop = box.scrollHeight;
    setText("#bd-current", `session ${id.slice(0, 8)}…`);
    flow("live", [["user", "api"], ["api", "store"], ["store", "api"], ["api", "user"]], "#34d399");
  } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
  loadBuilderSessions();
}

async function branchBuilder(uuid) {
  if (!bdState.session) return;
  try {
    const r = await postJSON("/api/builder/branch", { session_id: bdState.session, message_uuid: uuid });
    await openBuilderSession(r.session_id, `${I.branch} New session <span class="mono">${esc(r.session_id.slice(0, 8))}…</span> branched from <span class="mono">${esc(r.branched_from.slice(0, 8))}…</span> at the reply you picked. The original is unchanged.`);
  } catch (e) { alertInline("#bd-chat", e.message); }
}

async function sendBuilder() {
  const input = $("#bd-input"), message = input.value.trim();
  if (!message || state.abort) return;
  const box = $("#bd-chat");
  if (box.querySelector(".empty")) box.innerHTML = "";
  box.insertAdjacentHTML("beforeend", `<div class="msg user"><div class="avatar user">YOU</div><div class="bubble">${renderRich(message)}</div></div>`);
  input.value = ""; autosize(input, 200);
  $("#bd-send").disabled = true; setText("#bd-current", "working…");
  flow("live", [["user", "api"], ["api", "sdk"]], "#f472b6");
  const render = liveRenderer(box, {
    files: (ev, b) => {
      ev.changed.forEach((f) => { const i = bdState.files.findIndex((x) => x.path === f.path); if (i >= 0) bdState.files[i] = f; else bdState.files.unshift(f); });
      const imgs = ev.changed.filter((f) => f.kind === "image");
      const div = document.createElement("div"); div.className = "files-chip";
      div.innerHTML = `${I.file} sandbox: ${ev.changed.map((f) => `<span class="mono">${esc(f.path)}</span>`).join(", ")}${imgs.map(imageCard).join("")}`;
      b.appendChild(div); renderFiles();
    },
  });
  state.abort = new AbortController();
  try {
    await streamSSE("/api/builder/chat", { message, session_id: bdState.session }, (ev) => {
      render(ev); liveEvent(ev);
      if (ev.type === "session" || ev.type === "result") { bdState.session = ev.session_id; saveSession("builder", ev.session_id); }
      if (ev.type === "artifacts_ready") { bdState.files = ev.files; renderFiles(); }
    }, state.abort.signal);
  } catch (e) { render({ type: "error", message: e.message }); }
  finally {
    state.abort = null;
    const b = $("#bd-send"); if (b) b.disabled = false;
    setText("#bd-current", bdState.session ? `session ${bdState.session.slice(0, 8)}…` : "");
    loadBuilderSessions(); loadAutomations();
  }
}

async function loadFiles() {
  try { const d = await getJSON("/api/builder/files"); bdState.files = d.files; renderFiles(); } catch (_) {}
}
function renderFiles() {
  const box = $("#bd-files"); if (!box) return;
  if (!bdState.files.length) { box.innerHTML = '<div class="hint">Empty.</div>'; return; }
  const procedural = (p) => /\.py$|README\.md$/i.test(p);
  box.innerHTML = bdState.files.map((f) => `<button class="ft ${f.kind} ${procedural(f.path) ? "proc" : ""}" data-p="${esc(f.path)}">${f.kind === "image" ? I.image : I.file}<span>${esc(f.path)}</span>${procedural(f.path) ? '<em>tool</em>' : ""}<small>${f.size < 1024 ? f.size + " B" : (f.size / 1024).toFixed(1) + " KB"}</small></button>`).join("");
  $$(".ft", box).forEach((b) => b.addEventListener("click", () => previewFile(b.dataset.p)));
}
async function previewFile(path) {
  const f = bdState.files.find((x) => x.path === path);
  $("#file-drawer").hidden = false; setText("#drawer-title", path);
  if (f && f.kind === "image") { setHTML("#drawer-body", imageCard(f)); return; }
  setHTML("#drawer-body", '<span class="spinner"></span>');
  try { const d = await getJSON(`/api/builder/file?path=${encodeURIComponent(path)}`); setHTML("#drawer-body", `<pre class="file-pre">${esc(d.content)}${d.truncated ? "\n… (truncated)" : ""}</pre>`); }
  catch (e) { setHTML("#drawer-body", esc(e.message)); }
}

// ── scenario player ─────────────────────────────────────────────────────
function wireScenarios() {
  $$(".scen").forEach((b) => b.addEventListener("click", () => { $$(".scen").forEach((x) => x.classList.toggle("active", x === b)); loadScenario(b.dataset.sc); }));
  $("#sc-play").addEventListener("click", togglePlay);
  $("#sc-step").addEventListener("click", () => { stopPlay(); playStep(); });
  $("#sc-reset").addEventListener("click", () => { stopPlay(); if (bdState.scenario) loadScenario(bdState.scenario); });
  $$("#ref-svg .an").forEach((n) => n.addEventListener("click", () => showComponent(n.dataset.node)));
  loadScenario("build", true);
}
function loadScenario(key, quiet) {
  stopPlay();
  bdState.scenario = key; bdState.step = 0;
  $$(".scen").forEach((x) => x.classList.toggle("active", x.dataset.sc === key));
  $$("#ref-svg .an").forEach((n) => n.classList.remove("hot", "deny", "visited"));
  const s = SCENARIOS[key];
  setHTML("#sc-narr", `<div class="sc-title">${esc(s.title)}</div><ol class="sc-steps">${s.steps.map((st, i) => `<li data-i="${i}">${esc(st.text)}</li>`).join("")}</ol>${quiet ? "" : ""}`);
}
async function playStep() {
  const s = SCENARIOS[bdState.scenario]; if (!s || bdState.step >= s.steps.length) { stopPlay(); return false; }
  const st = s.steps[bdState.step];
  $$("#sc-narr li").forEach((li) => li.classList.toggle("now", +li.dataset.i === bdState.step));
  $$("#sc-narr li").forEach((li) => li.classList.toggle("done", +li.dataset.i < bdState.step));
  bdState.step++;
  for (const [a, b] of st.hops) {
    pulseNode("ref", a); await sendPacket("ref", a, b, null, 650); pulseNode("ref", b);
    document.getElementById(`ref-n-${a}`)?.classList.add("visited"); document.getElementById(`ref-n-${b}`)?.classList.add("visited");
  }
  if (st.deny) pulseNode("ref", "hook", "deny", 3000);
  return true;
}
function togglePlay() {
  if (bdState.playing) { stopPlay(); return; }
  bdState.playing = true; $("#sc-play").innerHTML = I.pause;
  (async () => {
    if (bdState.step >= SCENARIOS[bdState.scenario].steps.length) loadScenario(bdState.scenario);
    bdState.playing = true; $("#sc-play").innerHTML = I.pause;
    while (bdState.playing && $("#sc-play")) { const more = await playStep(); if (!more) break; await sleep(700); }
    stopPlay();
  })();
}
function stopPlay() { bdState.playing = false; const b = $("#sc-play"); if (b) b.innerHTML = I.play; }
function showComponent(id) {
  const n = ARCH_BY_ID[id]; if (!n) return;
  setHTML("#comp-detail", `<div class="cd-title"><i class="cd-dot ${n.kind}"></i>${esc(n.label)} <span class="hint">${esc(n.sub)}</span></div><p>${esc(n.detail)}</p><div class="mono cd-code">${esc(n.code)}</div>`);
  pulseNode("ref", id, "hot", 1500); pulseNode("live", id, "hot", 1500);
}
