export function renderAdminWebappPage(): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover" />
  <title>Helly Admin</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      --bg: #0a0a0d;
      --text: #f4f4f7;
      --muted: #9ca0ad;
      --accent: #7b2cff;
      --accent-soft: rgba(123, 44, 255, 0.2);
      --border: rgba(255, 255, 255, 0.08);
      --danger: #ff5757;
      --ok: #2cd482;
      --warn: #f7b73f;
      --safe-top: 0px;
      --safe-bottom: 0px;
      --safe-left: 0px;
      --safe-right: 0px;
    }

    * {
      box-sizing: border-box;
      min-width: 0;
    }

    html,
    body {
      margin: 0;
      padding: 0;
      width: 100%;
      max-width: 100%;
      overflow-x: hidden;
      background: radial-gradient(circle at 12% -18%, #211239 0%, #0a0a0d 56%);
      color: var(--text);
      font-family: "SF Pro Text", "Inter", "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }

    .app {
      width: 100%;
      max-width: 940px;
      margin: 0 auto;
      padding-top: calc(14px + var(--safe-top));
      padding-bottom: calc(18px + var(--safe-bottom));
      padding-left: calc(12px + var(--safe-left));
      padding-right: calc(12px + var(--safe-right));
      display: grid;
      gap: 10px;
    }

    .card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01));
      backdrop-filter: blur(6px);
    }

    .logo {
      font-size: 26px;
      font-weight: 700;
      letter-spacing: 0.2px;
      line-height: 1;
    }

    .logo .mark {
      color: var(--accent);
    }

    .muted {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }

    .title {
      margin: 0;
      font-size: 15px;
      font-weight: 650;
      color: var(--text);
    }

    .subtitle {
      margin: 2px 0 0;
      font-size: 12px;
      color: var(--muted);
    }

    .row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }

    .grow {
      flex: 1;
    }

    input {
      width: 100%;
      padding: 11px 12px;
      border-radius: 11px;
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      outline: none;
      font-size: 14px;
    }

    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }

    button {
      border: 0;
      border-radius: 11px;
      padding: 10px 12px;
      min-height: 38px;
      font-size: 13px;
      font-weight: 650;
      color: #fff;
      background: var(--accent);
      cursor: pointer;
      transition: transform 0.08s ease, opacity 0.2s ease;
      white-space: nowrap;
    }

    button:active { transform: translateY(1px); }
    button.secondary { background: rgba(255, 255, 255, 0.12); }
    button.danger {
      background: rgba(255, 87, 87, 0.18);
      border: 1px solid rgba(255, 87, 87, 0.55);
      color: #ffd6d6;
    }

    .status {
      min-height: 16px;
      font-size: 12px;
      color: var(--muted);
      margin-top: 8px;
      overflow-wrap: anywhere;
    }

    .hidden { display: none !important; }

    .tabs {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 6px;
    }

    .tab-btn {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
      min-height: 34px;
      padding: 8px 4px;
    }

    .tab-btn.active {
      color: #fff;
      border-color: rgba(123, 44, 255, 0.7);
      background: linear-gradient(180deg, rgba(123, 44, 255, 0.25), rgba(123, 44, 255, 0.16));
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px;
    }

    .stat {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px;
      background: rgba(255, 255, 255, 0.02);
    }

    .stat .k {
      color: var(--muted);
      font-size: 11px;
    }

    .stat .v {
      margin-top: 4px;
      font-size: 20px;
      font-weight: 700;
      color: #fff;
    }

    .consistency {
      margin-top: 9px;
      border-radius: 11px;
      border: 1px solid var(--border);
      padding: 10px;
      font-size: 12px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.02);
      display: grid;
      gap: 5px;
    }

    .consistency .good { color: #8de8bd; }
    .consistency .warn { color: #f7d48a; }

    .list {
      display: grid;
      gap: 8px;
    }

    .item {
      border: 1px solid var(--border);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.02);
      padding: 10px;
      display: grid;
      gap: 6px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    .item-head {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: flex-start;
    }

    .item-title {
      font-size: 14px;
      font-weight: 650;
      color: #fff;
      line-height: 1.3;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      line-height: 1;
      border: 1px solid var(--border);
      color: var(--muted);
      background: rgba(255, 255, 255, 0.04);
      white-space: nowrap;
    }

    .pill.ok {
      border-color: rgba(44, 212, 130, 0.45);
      color: #8de8bd;
      background: rgba(44, 212, 130, 0.14);
    }

    .pill.warn {
      border-color: rgba(247, 183, 63, 0.45);
      color: #f9d58f;
      background: rgba(247, 183, 63, 0.12);
    }

    .kv {
      display: grid;
      gap: 4px;
    }

    .kv-row {
      display: grid;
      grid-template-columns: 122px 1fr;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
    }

    .kv-row b {
      color: #d7d8de;
      font-weight: 550;
    }

    .item-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }

    .empty {
      color: var(--muted);
      font-size: 13px;
      padding: 10px;
      border: 1px dashed var(--border);
      border-radius: 11px;
      text-align: center;
    }

    @media (max-width: 680px) {
      .tabs {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @media (max-width: 520px) {
      .stats {
        grid-template-columns: 1fr;
      }
      .kv-row {
        grid-template-columns: 1fr;
        gap: 2px;
      }
      .item-actions {
        justify-content: stretch;
      }
      .item-actions button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <section class="card">
      <div class="logo"><span class="mark">&gt;</span>helly<span class="mark">_</span></div>
      <div id="tgInfo" class="muted" style="margin-top:8px;">Telegram context is loading...</div>
    </section>

    <section id="loginCard" class="card">
      <h1 class="title">Admin sign in</h1>
      <p class="subtitle">PIN plus Telegram identity check, session TTL 1 hour.</p>
      <div class="row" style="margin-top:10px;">
        <div class="grow"><input id="pinInput" type="password" placeholder="Enter admin PIN" autocomplete="off" /></div>
        <button id="loginBtn">Sign in</button>
      </div>
      <div id="loginStatus" class="status"></div>
    </section>

    <section id="dashboard" class="hidden">
      <div class="card">
        <div class="row" style="justify-content: space-between; margin-bottom: 10px;">
          <div>
            <h2 class="title">Operations dashboard</h2>
            <p class="subtitle" id="generatedAtLine">Loading...</p>
          </div>
          <div class="row">
            <button id="refreshBtn" class="secondary">Refresh</button>
            <button id="logoutBtn" class="secondary">Logout</button>
          </div>
        </div>
        <div id="stats" class="stats"></div>
        <div id="consistency" class="consistency"></div>
      </div>

      <div class="card">
        <div class="tabs">
          <button class="tab-btn active" data-tab="jobs">Jobs</button>
          <button class="tab-btn" data-tab="candidates">Candidates</button>
          <button class="tab-btn" data-tab="interviews">Interviews</button>
          <button class="tab-btn" data-tab="users">Users</button>
          <button class="tab-btn" data-tab="matches">Matches</button>
          <button class="tab-btn" data-tab="flags">Flags</button>
          <button class="tab-btn" data-tab="events">Events</button>
        </div>
      </div>

      <div id="tab-jobs" class="card tab-content">
        <h3 class="title">Jobs</h3>
        <div id="jobsList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-candidates" class="card tab-content hidden">
        <h3 class="title">Candidates</h3>
        <div id="candidatesList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-interviews" class="card tab-content hidden">
        <h3 class="title">Interview progress</h3>
        <div id="interviewsList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-users" class="card tab-content hidden">
        <h3 class="title">Users</h3>
        <div id="usersList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-matches" class="card tab-content hidden">
        <h3 class="title">Matches</h3>
        <div id="matchesList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-flags" class="card tab-content hidden">
        <h3 class="title">Quality flags and errors</h3>
        <div id="flagsList" class="list" style="margin-top:10px;"></div>
      </div>

      <div id="tab-events" class="card tab-content hidden">
        <h3 class="title">Data deletion and events</h3>
        <div id="eventsList" class="list" style="margin-top:10px;"></div>
      </div>
    </section>
  </div>

  <script>
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (tg) {
      tg.ready();
      tg.expand();
      if (typeof tg.setHeaderColor === "function") {
        try { tg.setHeaderColor("#0a0a0d"); } catch {}
      }
      if (typeof tg.setBackgroundColor === "function") {
        try { tg.setBackgroundColor("#0a0a0d"); } catch {}
      }
      if (typeof tg.disableVerticalSwipes === "function") {
        try { tg.disableVerticalSwipes(); } catch {}
      }
    }

    const state = {
      initData: tg ? (tg.initData || "") : "",
      loggedIn: false,
      currentTab: "jobs",
    };

    const tgInfoEl = document.getElementById("tgInfo");
    const loginStatusEl = document.getElementById("loginStatus");
    const loginCardEl = document.getElementById("loginCard");
    const dashboardEl = document.getElementById("dashboard");

    applyTelegramTheme();
    applySafeAreaInsets();

    if (tg && tg.onEvent) {
      tg.onEvent("themeChanged", applyTelegramTheme);
      tg.onEvent("safeAreaChanged", applySafeAreaInsets);
      tg.onEvent("contentSafeAreaChanged", applySafeAreaInsets);
    }

    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const user = tg.initDataUnsafe.user;
      const username = user.username ? "@" + user.username : "";
      tgInfoEl.textContent = "Telegram user " + user.id + " " + username;
    } else {
      tgInfoEl.textContent = "Open this mini app from your bot menu button inside Telegram.";
    }

    async function request(path, options) {
      const response = await fetch(path, {
        credentials: "include",
        headers: { "content-type": "application/json" },
        ...(options || {}),
      });
      const json = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(json.error || json.message || ("HTTP " + response.status));
      }
      return json;
    }

    function setStatus(text, isError) {
      loginStatusEl.textContent = text || "";
      loginStatusEl.style.color = isError ? "#ff8383" : "#9ca0ad";
    }

    async function login() {
      const pin = document.getElementById("pinInput").value.trim();
      if (!pin) {
        setStatus("Please enter PIN", true);
        return;
      }
      setStatus("Signing in...", false);
      try {
        await request("/admin/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ pin, initData: state.initData || null }),
        });
        state.loggedIn = true;
        loginCardEl.classList.add("hidden");
        dashboardEl.classList.remove("hidden");
        await loadDashboard();
      } catch (error) {
        setStatus(error.message || "Login failed", true);
      }
    }

    async function loadSession() {
      try {
        await request("/admin/api/session", { method: "GET" });
        state.loggedIn = true;
        loginCardEl.classList.add("hidden");
        dashboardEl.classList.remove("hidden");
        await loadDashboard();
      } catch {
        state.loggedIn = false;
      }
    }

    function renderStats(stats) {
      const container = document.getElementById("stats");
      const entries = [
        ["Users", stats.usersTotal],
        ["Candidates", stats.candidatesTotal],
        ["Managers", stats.managersTotal],
        ["Interviews", stats.interviewsTotal],
        ["Candidate done", stats.candidateInterviewsCompleted || 0],
        ["Candidate in progress", stats.candidateInterviewsInProgress || 0],
        ["Manager done", stats.managerInterviewsCompleted || 0],
        ["Manager in progress", stats.managerInterviewsInProgress || 0],
        ["Jobs", stats.jobsTotal],
        ["Active jobs", stats.jobsActive],
        ["Matches", stats.matchesTotal],
        ["Contact shared", stats.matchesContactShared],
        ["Applied", stats.candidatesApplied],
        ["Flags 24h", stats.qualityFlags24h],
      ];
      container.innerHTML = entries.map(([label, value]) =>
        '<div class="stat"><div class="k">' + escapeHtml(String(label)) + '</div><div class="v">' + escapeHtml(String(value)) + '</div></div>'
      ).join("");
    }

    function renderConsistency(consistency) {
      const root = document.getElementById('consistency');
      const qdrantState = consistency.qdrantEnabled ? 'enabled' : 'disabled';
      const gap = consistency.vectorSyncGap;
      const gapLine = gap == null
        ? '<span class="warn">Qdrant candidate count is unavailable</span>'
        : gap === 0
          ? '<span class="good">Vector sync is healthy, gap 0</span>'
          : '<span class="warn">Vector sync gap: ' + escapeHtml(String(gap)) + '</span>';

      root.innerHTML =
        '<div>Supabase: <span class="good">' + (consistency.supabaseConfigured ? 'configured' : 'not configured') + '</span></div>' +
        '<div>Qdrant: <span class="' + (consistency.qdrantEnabled ? 'good' : 'warn') + '">' + qdrantState + '</span></div>' +
        '<div>Candidate profiles in Supabase: <b>' + escapeHtml(String(consistency.candidateProfilesInSupabase)) + '</b></div>' +
        '<div>Candidate vectors in Qdrant: <b>' + escapeHtml(consistency.candidateVectorsInQdrant == null ? 'n/a' : String(consistency.candidateVectorsInQdrant)) + '</b></div>' +
        '<div>' + gapLine + '</div>';
    }

    function renderJobs(rows) {
      const list = document.getElementById("jobsList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No jobs found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">' + escapeHtml(row.title) + '</div><span class="pill">' + escapeHtml(row.status) + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>ID</b><span>' + escapeHtml(row.id) + '</span></div>' +
            '<div class="kv-row"><b>Domain</b><span>' + escapeHtml(row.domain) + '</span></div>' +
            '<div class="kv-row"><b>Manager</b><span>' + escapeHtml(String(row.managerTelegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Format</b><span>' + escapeHtml(row.workFormat) + '</span></div>' +
            '<div class="kv-row"><b>Interview</b><span>' + escapeHtml(row.managerInterviewStatus || 'not_started') + '</span></div>' +
            '<div class="kv-row"><b>Updated</b><span>' + escapeHtml(row.updatedAt || '-') + '</span></div>' +
          '</div>' +
          '<div class="item-actions"><button class="danger" onclick="deleteJob(\'' + escapeAttr(row.id) + '\')">Delete job</button></div>' +
        '</article>';
      }).join("");
    }

    function renderCandidates(rows) {
      const list = document.getElementById("candidatesList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No candidates found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        const name = (row.fullName || "Unknown") + (row.username ? " (" + row.username + ")" : "");
        const confidenceClass = row.interviewConfidence === 'low' ? 'warn' : (row.interviewConfidence ? 'ok' : '');
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">' + escapeHtml(name) + '</div><span class="pill ' + confidenceClass + '">' + escapeHtml(row.interviewConfidence || 'no confidence') + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Telegram ID</b><span>' + escapeHtml(String(row.telegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Profile status</b><span>' + escapeHtml(row.profileStatus) + '</span></div>' +
            '<div class="kv-row"><b>Interview</b><span>' + escapeHtml(row.interviewStatus || 'not_started') + '</span></div>' +
            '<div class="kv-row"><b>Mandatory complete</b><span>' + (row.candidateProfileComplete ? 'yes' : 'no') + '</span></div>' +
            '<div class="kv-row"><b>Contact shared</b><span>' + (row.contactShared ? 'yes' : 'no') + '</span></div>' +
            '<div class="kv-row"><b>Updated</b><span>' + escapeHtml(row.updatedAt || '-') + '</span></div>' +
          '</div>' +
          '<div class="item-actions"><button class="danger" onclick="deleteCandidate(' + Number(row.telegramUserId) + ')">Delete candidate</button></div>' +
        '</article>';
      }).join("");
    }

    function renderUsers(rows) {
      const list = document.getElementById("usersList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No users found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        const name = (row.fullName || "Unknown") + (row.username ? " (" + row.username + ")" : "");
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">' + escapeHtml(name) + '</div><span class="pill ' + (row.contactShared ? 'ok' : '') + '">' + (row.contactShared ? 'contact shared' : 'no contact') + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Telegram ID</b><span>' + escapeHtml(String(row.telegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Role</b><span>' + escapeHtml(row.role) + '</span></div>' +
            '<div class="kv-row"><b>Language</b><span>' + escapeHtml(row.preferredLanguage) + '</span></div>' +
            '<div class="kv-row"><b>Candidate interview</b><span>' + escapeHtml(row.candidateInterviewStatus || 'not_started') + '</span></div>' +
            '<div class="kv-row"><b>Manager interview</b><span>' + escapeHtml(row.managerInterviewStatus || 'not_started') + '</span></div>' +
            '<div class="kv-row"><b>Candidate complete</b><span>' + (row.candidateProfileComplete ? 'yes' : 'no') + '</span></div>' +
            '<div class="kv-row"><b>Updated</b><span>' + escapeHtml(row.updatedAt || '-') + '</span></div>' +
          '</div>' +
          '<div class="item-actions"><button class="danger" onclick="deleteUser(' + Number(row.telegramUserId) + ')">Delete user</button></div>' +
        '</article>';
      }).join("");
    }

    function renderInterviews(interviewProgress) {
      const list = document.getElementById("interviewsList");
      const candidates = (interviewProgress && interviewProgress.candidates) || [];
      const managers = (interviewProgress && interviewProgress.managers) || [];
      const rows = []
        .concat(candidates.map((row) => ({ ...row, role: 'candidate' })))
        .concat(managers.map((row) => ({ ...row, role: 'manager' })));

      if (!rows.length) {
        list.innerHTML = '<div class="empty">No interview progress data found.</div>';
        return;
      }

      list.innerHTML = rows.map((row) => {
        const name = (row.fullName || "Unknown") + (row.username ? " (" + row.username + ")" : "");
        const statusClass = row.status === 'completed' ? 'ok' : (row.status === 'in_progress' ? 'warn' : '');
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">' + escapeHtml(name) + '</div><span class="pill ' + statusClass + '">' + escapeHtml(row.status || 'not_started') + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Telegram ID</b><span>' + escapeHtml(String(row.telegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Role</b><span>' + escapeHtml(row.role) + '</span></div>' +
            '<div class="kv-row"><b>Current state</b><span>' + escapeHtml(row.currentState || 'unknown') + '</span></div>' +
            '<div class="kv-row"><b>Updated</b><span>' + escapeHtml(row.updatedAt || '-') + '</span></div>' +
          '</div>' +
        '</article>';
      }).join("");
    }

    function renderMatches(rows) {
      const list = document.getElementById("matchesList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No matches found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">Match ' + escapeHtml(row.id) + '</div><span class="pill">' + escapeHtml(row.status) + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Job ID</b><span>' + escapeHtml(row.jobId || '-') + '</span></div>' +
            '<div class="kv-row"><b>Candidate</b><span>' + escapeHtml(String(row.candidateTelegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Manager</b><span>' + escapeHtml(String(row.managerTelegramUserId)) + '</span></div>' +
            '<div class="kv-row"><b>Total score</b><span>' + escapeHtml(row.totalScore != null ? String(row.totalScore) : '-') + '</span></div>' +
            '<div class="kv-row"><b>Created</b><span>' + escapeHtml(row.createdAt || '-') + '</span></div>' +
          '</div>' +
        '</article>';
      }).join("");
    }

    function renderFlags(rows) {
      const list = document.getElementById("flagsList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No quality flags found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">' + escapeHtml(row.flag) + '</div><span class="pill">' + escapeHtml(row.entityType) + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Entity</b><span>' + escapeHtml(row.entityType + ':' + row.entityId) + '</span></div>' +
            '<div class="kv-row"><b>Time</b><span>' + escapeHtml(row.createdAt || '-') + '</span></div>' +
          '</div>' +
        '</article>';
      }).join("");
    }

    function renderEvents(rows) {
      const list = document.getElementById("eventsList");
      if (!rows.length) {
        list.innerHTML = '<div class="empty">No deletion events found.</div>';
        return;
      }
      list.innerHTML = rows.map((row) => {
        const pillClass = row.status === 'requested' ? 'warn' : 'ok';
        return '<article class="item">' +
          '<div class="item-head"><div class="item-title">Deletion request for ' + escapeHtml(String(row.telegramUserId)) + '</div><span class="pill ' + pillClass + '">' + escapeHtml(row.status) + '</span></div>' +
          '<div class="kv">' +
            '<div class="kv-row"><b>Reason</b><span>' + escapeHtml(row.reason) + '</span></div>' +
            '<div class="kv-row"><b>Requested</b><span>' + escapeHtml(row.requestedAt || '-') + '</span></div>' +
            '<div class="kv-row"><b>Updated</b><span>' + escapeHtml(row.updatedAt || '-') + '</span></div>' +
          '</div>' +
        '</article>';
      }).join("");
    }

    function setTab(tabName) {
      state.currentTab = tabName;
      document.querySelectorAll('.tab-btn').forEach((button) => {
        const active = button.getAttribute('data-tab') === tabName;
        button.classList.toggle('active', active);
      });
      const sections = ["jobs", "candidates", "interviews", "users", "matches", "flags", "events"];
      sections.forEach((name) => {
        const section = document.getElementById('tab-' + name);
        section.classList.toggle('hidden', tabName !== name);
      });
    }

    async function loadDashboard() {
      const data = await request("/admin/api/dashboard", { method: "GET" });
      document.getElementById('generatedAtLine').textContent = 'Snapshot ' + (data.generatedAt || new Date().toISOString());
      renderStats(data.stats || {});
      renderConsistency(data.consistency || {});
      renderJobs(data.jobs || []);
      renderCandidates(data.candidates || []);
      renderInterviews(data.interviewProgress || {});
      renderUsers(data.users || []);
      renderMatches(data.matches || []);
      renderFlags(data.qualityFlags || []);
      renderEvents(data.deletionRequests || []);
      setTab(state.currentTab);
    }

    async function logout() {
      await request("/admin/api/auth/logout", { method: "POST" });
      state.loggedIn = false;
      dashboardEl.classList.add("hidden");
      loginCardEl.classList.remove("hidden");
      setStatus("Logged out", false);
    }

    window.deleteJob = async function(jobId) {
      if (!confirm("Delete job " + jobId + " and linked matches?")) {
        return;
      }
      const result = await request("/admin/api/jobs/" + encodeURIComponent(jobId), { method: "DELETE" });
      if (!result.ok) {
        alert(result.message || 'Delete failed');
      } else if (result.verification && result.verification.remainingRefs && result.verification.remainingRefs.length) {
        alert('Deleted with warnings: ' + result.verification.remainingRefs.join(', '));
      }
      await loadDashboard();
    };

    window.deleteUser = async function(userId) {
      if (!confirm("Delete user " + userId + " and all related data?")) {
        return;
      }
      const result = await request("/admin/api/users/" + encodeURIComponent(String(userId)), { method: "DELETE" });
      if (!result.ok) {
        alert(result.message || 'Delete failed');
      } else if (result.verification && result.verification.remainingRefs && result.verification.remainingRefs.length) {
        alert('Deleted with warnings: ' + result.verification.remainingRefs.join(', '));
      }
      await loadDashboard();
    };

    window.deleteCandidate = async function(userId) {
      if (!confirm("Delete candidate " + userId + " and all related data?")) {
        return;
      }
      const result = await request("/admin/api/candidates/" + encodeURIComponent(String(userId)), { method: "DELETE" });
      if (!result.ok) {
        alert(result.message || 'Delete failed');
      } else if (result.verification && result.verification.remainingRefs && result.verification.remainingRefs.length) {
        alert('Deleted with warnings: ' + result.verification.remainingRefs.join(', '));
      }
      await loadDashboard();
    };

    function applyTelegramTheme() {
      if (!tg || !tg.themeParams) {
        return;
      }
      const theme = tg.themeParams;
      setCssVar('--bg', theme.bg_color || '#0a0a0d');
      setCssVar('--text', theme.text_color || '#f4f4f7');
      setCssVar('--muted', theme.hint_color || '#9ca0ad');
      setCssVar('--accent', theme.button_color || '#7b2cff');
      if (theme.button_color) {
        setCssVar('--accent-soft', withAlpha(theme.button_color, 0.2));
      }
      document.body.style.background = 'radial-gradient(circle at 12% -18%, ' + withAlpha(theme.button_color || '#7b2cff', 0.24) + ' 0%, ' + (theme.bg_color || '#0a0a0d') + ' 56%)';
    }

    function applySafeAreaInsets() {
      if (!tg) {
        return;
      }
      const inset = tg.safeAreaInset || tg.contentSafeAreaInset || {};
      setCssVar('--safe-top', px(inset.top));
      setCssVar('--safe-bottom', px(inset.bottom));
      setCssVar('--safe-left', px(inset.left));
      setCssVar('--safe-right', px(inset.right));
    }

    function setCssVar(name, value) {
      if (!value) return;
      document.documentElement.style.setProperty(name, value);
    }

    function withAlpha(color, alpha) {
      const hex = String(color || '').trim();
      if (!hex.startsWith('#') || (hex.length !== 7 && hex.length !== 4)) {
        return 'rgba(123,44,255,' + alpha + ')';
      }
      const normalized = hex.length === 4
        ? '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3]
        : hex;
      const r = parseInt(normalized.slice(1, 3), 16);
      const g = parseInt(normalized.slice(3, 5), 16);
      const b = parseInt(normalized.slice(5, 7), 16);
      return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function px(value) {
      const n = Number(value || 0);
      return Number.isFinite(n) ? n + 'px' : '0px';
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function escapeAttr(value) {
      return String(value).replaceAll("'", "&#039;");
    }

    document.getElementById("loginBtn").addEventListener("click", login);
    document.getElementById("refreshBtn").addEventListener("click", loadDashboard);
    document.getElementById("logoutBtn").addEventListener("click", logout);
    document.getElementById("pinInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        login();
      }
    });

    document.querySelectorAll('.tab-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const tabName = button.getAttribute('data-tab') || 'jobs';
        setTab(tabName);
      });
    });

    loadSession();
  </script>
</body>
</html>`;
}
