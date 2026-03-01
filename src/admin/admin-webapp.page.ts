export function renderAdminWebappPage(): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Helly Admin</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7faf8;
      --card: #ffffff;
      --text: #1a2a22;
      --muted: #587062;
      --accent: #10684f;
      --danger: #b42318;
      --border: #dde7e1;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: radial-gradient(circle at top right, #d2e8dd 0%, var(--bg) 44%);
      color: var(--text);
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 16px;
      display: grid;
      gap: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
    }
    h1, h2 { margin: 0 0 10px; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; }
    .muted { color: var(--muted); }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    input {
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      min-width: 240px;
      font-size: 14px;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 12px;
      background: var(--accent);
      color: #fff;
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary { background: #5a6b62; }
    button.danger { background: var(--danger); }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
    }
    .stat {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: #fbfdfc;
    }
    .stat .label { color: var(--muted); font-size: 12px; }
    .stat .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      border-bottom: 1px solid var(--border);
      text-align: left;
      padding: 8px;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 600; }
    .hide { display: none; }
    .status { font-size: 12px; color: var(--muted); min-height: 18px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Helly Admin</h1>
      <div id="tgInfo" class="muted">Telegram context is loading...</div>
    </div>

    <div id="loginCard" class="card">
      <h2>Admin Login</h2>
      <div class="row">
        <input id="pinInput" type="password" placeholder="Enter admin PIN" autocomplete="off" />
        <button id="loginBtn">Sign in</button>
      </div>
      <div id="loginStatus" class="status"></div>
    </div>

    <div id="dashboard" class="hide">
      <div class="card">
        <div class="row" style="justify-content: space-between;">
          <h2>Overview</h2>
          <div class="row">
            <button id="refreshBtn" class="secondary">Refresh</button>
            <button id="logoutBtn" class="secondary">Logout</button>
          </div>
        </div>
        <div id="stats" class="stats"></div>
      </div>

      <div class="card">
        <h2>Jobs</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Title</th><th>Domain</th><th>Status</th><th>Manager</th><th>Action</th></tr>
          </thead>
          <tbody id="jobsBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>Users</h2>
        <table>
          <thead>
            <tr><th>Telegram ID</th><th>Name</th><th>Role</th><th>Contact</th><th>Lang</th><th>Action</th></tr>
          </thead>
          <tbody id="usersBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>Matches</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Job</th><th>Candidate</th><th>Score</th><th>Status</th><th>Created</th></tr>
          </thead>
          <tbody id="matchesBody"></tbody>
        </table>
      </div>

      <div class="card">
        <h2>Quality Flags and Errors</h2>
        <table>
          <thead>
            <tr><th>Time</th><th>Entity</th><th>Flag</th></tr>
          </thead>
          <tbody id="flagsBody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
    if (tg) {
      tg.ready();
      tg.expand();
    }

    const state = {
      initData: tg ? (tg.initData || "") : "",
      loggedIn: false,
    };

    const tgInfoEl = document.getElementById("tgInfo");
    const loginStatusEl = document.getElementById("loginStatus");
    const loginCardEl = document.getElementById("loginCard");
    const dashboardEl = document.getElementById("dashboard");

    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const user = tg.initDataUnsafe.user;
      const username = user.username ? "@" + user.username : "";
      tgInfoEl.textContent = "Telegram user: " + user.id + " " + username;
    } else {
      tgInfoEl.textContent = "Open this page inside Telegram bot web app.";
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
      loginStatusEl.style.color = isError ? "#b42318" : "#587062";
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
        loginCardEl.classList.add("hide");
        dashboardEl.classList.remove("hide");
        await loadDashboard();
      } catch (error) {
        setStatus(error.message || "Login failed", true);
      }
    }

    async function loadSession() {
      try {
        await request("/admin/api/session", { method: "GET" });
        state.loggedIn = true;
        loginCardEl.classList.add("hide");
        dashboardEl.classList.remove("hide");
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
        ["Jobs", stats.jobsTotal],
        ["Active jobs", stats.jobsActive],
        ["Matches", stats.matchesTotal],
        ["Contact shared", stats.matchesContactShared],
        ["Applied", stats.candidatesApplied],
        ["Flags 24h", stats.qualityFlags24h],
      ];
      container.innerHTML = entries.map(([label, value]) =>
        '<div class="stat"><div class="label">' + escapeHtml(String(label)) + '</div><div class="value">' + escapeHtml(String(value)) + '</div></div>'
      ).join("");
    }

    function renderJobs(rows) {
      const body = document.getElementById("jobsBody");
      body.innerHTML = rows.map((row) => {
        return '<tr>' +
          '<td>' + escapeHtml(row.id) + '</td>' +
          '<td>' + escapeHtml(row.title) + '</td>' +
          '<td>' + escapeHtml(row.domain) + '</td>' +
          '<td>' + escapeHtml(row.status) + '</td>' +
          '<td>' + escapeHtml(String(row.managerTelegramUserId)) + '</td>' +
          '<td><button class="danger" onclick="deleteJob(\'' + escapeAttr(row.id) + '\')">Delete</button></td>' +
        '</tr>';
      }).join("");
    }

    function renderUsers(rows) {
      const body = document.getElementById("usersBody");
      body.innerHTML = rows.map((row) => {
        return '<tr>' +
          '<td>' + escapeHtml(String(row.telegramUserId)) + '</td>' +
          '<td>' + escapeHtml((row.fullName || "") + (row.username ? " (" + row.username + ")" : "")) + '</td>' +
          '<td>' + escapeHtml(row.role) + '</td>' +
          '<td>' + escapeHtml(row.contactShared ? "yes" : "no") + '</td>' +
          '<td>' + escapeHtml(row.preferredLanguage) + '</td>' +
          '<td><button class="danger" onclick="deleteUser(' + Number(row.telegramUserId) + ')">Delete</button></td>' +
        '</tr>';
      }).join("");
    }

    function renderMatches(rows) {
      const body = document.getElementById("matchesBody");
      body.innerHTML = rows.map((row) => {
        return '<tr>' +
          '<td>' + escapeHtml(row.id) + '</td>' +
          '<td>' + escapeHtml(row.jobId || "-") + '</td>' +
          '<td>' + escapeHtml(String(row.candidateTelegramUserId)) + '</td>' +
          '<td>' + escapeHtml(row.totalScore != null ? String(row.totalScore) : "-") + '</td>' +
          '<td>' + escapeHtml(row.status) + '</td>' +
          '<td>' + escapeHtml(row.createdAt || "-") + '</td>' +
        '</tr>';
      }).join("");
    }

    function renderFlags(rows) {
      const body = document.getElementById("flagsBody");
      body.innerHTML = rows.map((row) => {
        return '<tr>' +
          '<td>' + escapeHtml(row.createdAt || "-") + '</td>' +
          '<td>' + escapeHtml(row.entityType + ':' + row.entityId) + '</td>' +
          '<td>' + escapeHtml(row.flag) + '</td>' +
        '</tr>';
      }).join("");
    }

    async function loadDashboard() {
      const data = await request("/admin/api/dashboard", { method: "GET" });
      renderStats(data.stats);
      renderJobs(data.jobs || []);
      renderUsers(data.users || []);
      renderMatches(data.matches || []);
      renderFlags(data.qualityFlags || []);
    }

    async function logout() {
      await request("/admin/api/auth/logout", { method: "POST" });
      state.loggedIn = false;
      dashboardEl.classList.add("hide");
      loginCardEl.classList.remove("hide");
      setStatus("Logged out", false);
    }

    window.deleteJob = async function(jobId) {
      if (!confirm("Delete job " + jobId + " and linked matches?")) {
        return;
      }
      await request("/admin/api/jobs/" + encodeURIComponent(jobId), { method: "DELETE" });
      await loadDashboard();
    };

    window.deleteUser = async function(userId) {
      if (!confirm("Delete user " + userId + " and all related data?")) {
        return;
      }
      await request("/admin/api/users/" + encodeURIComponent(String(userId)), { method: "DELETE" });
      await loadDashboard();
    };

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

    loadSession();
  </script>
</body>
</html>`;
}
