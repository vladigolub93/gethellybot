(function () {
  const state = {
    session: null,
    usersPayload: null,
    matchesPayload: null,
    analyticsPayload: null,
    currentMatchDetail: null,
    selectedUserIds: new Set(),
    messagePreview: null,
    messageDraft: "",
    usersFilters: {
      role: "",
      status: "",
      candidate_state: "",
      vacancy_state: "",
      search: "",
    },
    matchesFilters: {
      status: "",
      fit_band: "",
      search: "",
    },
  };

  const appEl = document.getElementById("app");

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function badgeTone(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("approved") || text.includes("strong") || text === "active" || text === "open") return "good";
    if (text.includes("skip") || text.includes("reject") || text.includes("blocked") || text.includes("expired") || text.includes("not_fit")) return "bad";
    if (text.includes("pending") || text.includes("review") || text.includes("await") || text.includes("medium")) return "warn";
    return "accent";
  }

  function renderBadge(value) {
    const text = value === null || value === undefined || value === "" ? "n/a" : String(value);
    return `<span class="badge ${badgeTone(text)}">${escapeHtml(text)}</span>`;
  }

  function routeFromHash() {
    const hash = window.location.hash.replace(/^#/, "");
    if (!hash) return { name: "dashboard" };
    if (hash.startsWith("/matches/")) {
      return { name: "match-detail", id: hash.split("/")[2] };
    }
    return { name: hash.replace(/^\//, "") || "dashboard" };
  }

  function setRoute(value) {
    window.location.hash = value.startsWith("/") ? value : `/${value}`;
  }

  async function api(path, options) {
    const response = await fetch(path, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(options && options.headers ? options.headers : {}),
      },
      ...options,
    });
    if (response.status === 401) {
      state.session = null;
      renderLogin();
      throw new Error("Unauthorized");
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const payload = await response.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch (_) {}
      throw new Error(detail);
    }
    return response.json();
  }

  async function bootstrapSession() {
    try {
      const payload = await api("/admin/api/session");
      state.session = payload.session;
      await Promise.all([loadAnalytics(), loadUsers(), loadMatches()]);
      renderApp();
    } catch (_) {
      renderLogin();
    }
  }

  async function loadAnalytics() {
    state.analyticsPayload = await api("/admin/api/analytics/overview");
  }

  async function loadUsers() {
    const params = new URLSearchParams();
    Object.entries(state.usersFilters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    state.usersPayload = await api(`/admin/api/users${params.toString() ? `?${params}` : ""}`);
  }

  async function loadMatches() {
    const params = new URLSearchParams();
    Object.entries(state.matchesFilters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    state.matchesPayload = await api(`/admin/api/matches${params.toString() ? `?${params}` : ""}`);
  }

  async function loadMatchDetail(matchId) {
    state.currentMatchDetail = await api(`/admin/api/matches/${matchId}`);
  }

  function renderLogin(errorText) {
    appEl.innerHTML = `
      <section class="login-card">
        <p class="eyebrow">Helly Admin</p>
        <h1>Admin Access</h1>
        <p class="muted">Browser-only admin panel. PIN is verified by backend and stored in a server session cookie.</p>
        <form id="login-form" class="login-form">
          <input id="pin-input" type="password" placeholder="Enter admin PIN" autocomplete="current-password" />
          ${errorText ? `<p class="muted" style="color: var(--danger);">${escapeHtml(errorText)}</p>` : ""}
          <button class="primary-btn" type="submit">Unlock Admin</button>
        </form>
      </section>
    `;
    document.getElementById("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const pin = document.getElementById("pin-input").value || "";
      try {
        await api("/admin/api/auth/pin", {
          method: "POST",
          body: JSON.stringify({ pin }),
        });
        await bootstrapSession();
      } catch (error) {
        renderLogin(error.message || "PIN login failed.");
      }
    });
  }

  function renderMetricCard(title, value, note) {
    return `
      <section class="metric-card">
        <div class="metric-value">${escapeHtml(value)}</div>
        <div>${escapeHtml(title)}</div>
        ${note ? `<p class="muted" style="margin-top: 8px;">${escapeHtml(note)}</p>` : ""}
      </section>
    `;
  }

  function navButton(route, label) {
    const active = routeFromHash().name === route;
    return `<button class="${active ? "active " : ""}secondary-btn" data-route="${route}">${escapeHtml(label)}</button>`;
  }

  function renderShell(innerHtml) {
    appEl.innerHTML = `
      <div class="topbar">
        <div>
          <p class="eyebrow">Helly Admin</p>
          <h1 style="margin-bottom: 6px;">Operations Panel</h1>
          <p class="muted" style="margin-bottom: 0;">Real backend data, browser auth via PIN, direct links for match triage.</p>
        </div>
        <div class="topbar-actions">
          <button class="secondary-btn" id="refresh-all">Refresh</button>
          <button class="secondary-btn" id="logout-btn">Logout</button>
        </div>
      </div>
      <nav class="nav panel" style="margin-bottom: 16px; padding: 12px;">
        ${navButton("dashboard", "Dashboard")}
        ${navButton("users", "Users")}
        ${navButton("matches", "Matches")}
        ${navButton("messages", "Messages")}
      </nav>
      ${innerHtml}
    `;
    document.querySelectorAll("[data-route]").forEach((button) => {
      button.addEventListener("click", () => setRoute(button.getAttribute("data-route")));
    });
    document.getElementById("refresh-all").addEventListener("click", async () => {
      await Promise.all([loadAnalytics(), loadUsers(), loadMatches()]);
      if (routeFromHash().name === "match-detail" && routeFromHash().id) {
        await loadMatchDetail(routeFromHash().id);
      }
      renderApp();
    });
    document.getElementById("logout-btn").addEventListener("click", async () => {
      await api("/admin/api/auth/logout", { method: "POST" });
      state.session = null;
      renderLogin();
    });
  }

  function renderDashboard() {
    const analytics = state.analyticsPayload || {};
    const users = analytics.users || {};
    const candidates = analytics.candidates || {};
    const vacancies = analytics.vacancies || {};
    const matches = analytics.matches || {};
    const funnel = analytics.funnel || {};
    return `
      <div class="screen">
        <div class="metrics-grid">
          ${renderMetricCard("Users", users.total || 0, `Blocked: ${users.blocked || 0}`)}
          ${renderMetricCard("Candidates", candidates.total || 0, `Ready: ${candidates.ready || 0}`)}
          ${renderMetricCard("Vacancies", vacancies.total || 0, `Open: ${vacancies.open || 0}`)}
          ${renderMetricCard("Matches", matches.total || 0, `Contact shares: ${matches.contactShares || 0}`)}
          ${renderMetricCard("Approvals", matches.approvals || 0, `Skips: ${matches.skips || 0}`)}
        </div>
        <div class="split-layout">
          <section class="panel">
            <h2>Funnel</h2>
            <div class="pill-row">
              ${Object.entries(funnel).map(([key, value]) => `<span class="badge accent">${escapeHtml(`${key}: ${value}`)}</span>`).join("")}
            </div>
          </section>
          <section class="panel">
            <h2>Role Distribution</h2>
            <div class="pill-row">
              ${Object.entries((users.byRole || {})).map(([key, value]) => `<span class="badge ${badgeTone(key)}">${escapeHtml(`${key}: ${value}`)}</span>`).join("")}
            </div>
          </section>
        </div>
        <section class="panel">
          <h2>Recent Matching Runs</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Vacancy</th>
                  <th>Trigger</th>
                  <th>Status</th>
                  <th>Pool</th>
                  <th>Filtered</th>
                  <th>Shortlisted</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                ${(analytics.recentMatchingRuns || []).map((run) => `
                  <tr>
                    <td>${escapeHtml(run.id)}</td>
                    <td>${escapeHtml(run.vacancyId)}</td>
                    <td>${escapeHtml(run.triggerType)}</td>
                    <td>${renderBadge(run.status)}</td>
                    <td>${escapeHtml(run.candidatePoolCount)}</td>
                    <td>${escapeHtml(run.hardFilteredCount)}</td>
                    <td>${escapeHtml(run.shortlistedCount)}</td>
                    <td>${escapeHtml(run.createdAt || "")}</td>
                  </tr>
                `).join("") || `<tr><td colspan="8" class="empty-state">No matching runs yet.</td></tr>`}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    `;
  }

  function renderUsers() {
    const payload = state.usersPayload || { items: [], filters: {} };
    const items = payload.items || [];
    const filters = payload.filters || {};
    const detail = `<section class="detail-card" id="users-side-panel">
      <h3>Selected Users</h3>
      <p class="muted">Pick rows to block, unblock, or prepare a bot message.</p>
      <div class="selection-summary">
        <span class="badge accent">${state.selectedUserIds.size} selected</span>
      </div>
      <div class="inline-actions" style="margin-top: 14px;">
        <button class="secondary-btn" id="users-block-btn">Block</button>
        <button class="secondary-btn" id="users-unblock-btn">Unblock</button>
        <button class="secondary-btn" id="users-message-btn">Message</button>
      </div>
      <p class="muted" style="margin-top: 14px;">Delete is intentionally single-user because it is hard-destructive.</p>
    </section>`;

    return `
      <div class="screen">
        <section class="panel">
          <div class="filters">
            <div class="toolbar">
              <select id="users-role-filter">
                <option value="">All roles</option>
                ${(filters.roleOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.role === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
              <select id="users-status-filter">
                <option value="">All statuses</option>
                ${(filters.statusOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.status === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
              <select id="users-candidate-state-filter">
                <option value="">All candidate states</option>
                ${(filters.candidateStateOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.candidate_state === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
              <select id="users-vacancy-state-filter">
                <option value="">All vacancy states</option>
                ${(filters.vacancyStateOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.vacancy_state === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
              <input id="users-search-filter" placeholder="Search name, username, telegram id, role title" value="${escapeHtml(state.usersFilters.search || "")}" />
              <button class="primary-btn" id="users-apply-filters">Apply Filters</button>
            </div>
          </div>
        </section>
        <div class="split-layout">
          <section class="panel">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th><input type="checkbox" id="users-select-all" /></th>
                    <th>Name</th>
                    <th>Telegram</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Candidate state</th>
                    <th>Vacancy states</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${items.map((item) => {
                    const checked = state.selectedUserIds.has(item.id) ? "checked" : "";
                    return `
                      <tr>
                        <td><input type="checkbox" class="user-select" data-user-id="${escapeHtml(item.id)}" ${checked} /></td>
                        <td>
                          <strong>${escapeHtml(item.candidateName || item.displayName || item.username || item.telegramUserId)}</strong><br />
                          <span class="muted">${escapeHtml(item.id)}</span>
                        </td>
                        <td>@${escapeHtml(item.username || "—")}<br /><span class="muted">${escapeHtml(item.telegramUserId)}</span></td>
                        <td>${renderBadge(item.role)}</td>
                        <td>${renderBadge(item.status)}</td>
                        <td>${item.candidateState ? renderBadge(item.candidateState) : '<span class="muted">—</span>'}</td>
                        <td>${(item.vacancyStates || []).length ? item.vacancyStates.map(renderBadge).join(" ") : '<span class="muted">—</span>'}</td>
                        <td>
                          <div class="inline-actions">
                            <button class="secondary-btn user-view-btn" data-user-id="${escapeHtml(item.id)}">Open</button>
                            <button class="danger-btn user-delete-btn" data-user-id="${escapeHtml(item.id)}">Delete</button>
                          </div>
                        </td>
                      </tr>
                    `;
                  }).join("") || `<tr><td colspan="8" class="empty-state">No users found for the selected filters.</td></tr>`}
                </tbody>
              </table>
            </div>
          </section>
          ${detail}
        </div>
      </div>
    `;
  }

  function renderMatchDetailPanel(detail) {
    if (!detail) {
      return `
        <section class="detail-card">
          <h3>Match Detail</h3>
          <p class="muted">Pick a match row or open a direct match link.</p>
        </section>
      `;
    }
    const match = detail.match || {};
    const vacancy = detail.vacancy || {};
    const candidate = detail.candidate || {};
    const run = detail.run || {};
    return `
      <section class="detail-card">
        <div class="detail-block">
          <h3>Match</h3>
          <p><strong>${escapeHtml(match.id || "")}</strong></p>
          <div class="pill-row">
            ${renderBadge(match.statusLabel || match.status)}
            ${match.fitBand ? renderBadge(match.fitBand) : ""}
          </div>
          ${match.adminUrl ? `<p style="margin-top: 12px;"><a href="${escapeHtml(match.adminUrl)}" target="_blank" rel="noreferrer">Open direct admin link</a></p>` : ""}
        </div>
        <div class="detail-block">
          <h4>Vacancy</h4>
          <p><strong>${escapeHtml(vacancy.roleTitle || "—")}</strong></p>
          <p class="muted">${escapeHtml(vacancy.projectDescription || vacancy.summary?.approvalSummaryText || "No project description saved.")}</p>
          <div class="pill-row">
            ${vacancy.budget ? renderBadge(vacancy.budget) : ""}
            ${vacancy.workFormat ? renderBadge(vacancy.workFormat) : ""}
            ${vacancy.requiredEnglishLevel ? renderBadge(vacancy.requiredEnglishLevel) : ""}
            ${vacancy.teamSize ? renderBadge(`team ${vacancy.teamSize}`) : ""}
          </div>
        </div>
        <div class="detail-block">
          <h4>Candidate</h4>
          <p><strong>${escapeHtml(candidate.name || "Candidate")}</strong></p>
          <p class="muted">${escapeHtml(candidate.summary?.approvalSummaryText || candidate.summary?.headline || "No candidate summary saved.")}</p>
          <div class="pill-row">
            ${candidate.salaryExpectation ? renderBadge(candidate.salaryExpectation) : ""}
            ${candidate.workFormat ? renderBadge(candidate.workFormat) : ""}
            ${candidate.englishLevel ? renderBadge(candidate.englishLevel) : ""}
          </div>
        </div>
        <div class="detail-block">
          <h4>Reasons</h4>
          <p>${escapeHtml(match.llmRationale || "No LLM rationale saved.")}</p>
          ${match.filterReasonCodes && match.filterReasonCodes.length ? `<p class="muted">Filter reasons: ${escapeHtml(match.filterReasonCodes.join(", "))}</p>` : ""}
          ${match.gapSignals && match.gapSignals.length ? `<p class="muted">Gaps: ${escapeHtml(match.gapSignals.join(" · "))}</p>` : ""}
        </div>
        <div class="detail-block">
          <h4>Matching Run</h4>
          <p class="muted">Trigger: ${escapeHtml(run.triggerType || "—")} · Pool: ${escapeHtml(run.candidatePoolCount || 0)} · Shortlisted: ${escapeHtml(run.shortlistedCount || 0)}</p>
        </div>
      </section>
    `;
  }

  function renderMatches() {
    const payload = state.matchesPayload || { items: [], filters: {} };
    const items = payload.items || [];
    const filters = payload.filters || {};
    return `
      <div class="screen">
        <section class="panel">
          <div class="toolbar">
            <select id="matches-status-filter">
              <option value="">All statuses</option>
              ${(filters.statusOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.matchesFilters.status === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
            </select>
            <select id="matches-fit-filter">
              <option value="">All fit bands</option>
              ${(filters.fitBandOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.matchesFilters.fit_band === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
            </select>
            <input id="matches-search-filter" placeholder="Search role, candidate, manager, match id" value="${escapeHtml(state.matchesFilters.search || "")}" />
            <button class="primary-btn" id="matches-apply-filters">Apply Filters</button>
          </div>
        </section>
        <div class="split-layout">
          <section class="panel">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Match</th>
                    <th>Vacancy</th>
                    <th>Candidate</th>
                    <th>Manager</th>
                    <th>Status</th>
                    <th>Fit</th>
                    <th>Reasons</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  ${items.map((item) => `
                    <tr>
                      <td><strong>${escapeHtml(item.id)}</strong></td>
                      <td>${escapeHtml(item.roleTitle || "—")}</td>
                      <td>${escapeHtml(item.candidateName || "Candidate")}</td>
                      <td>${escapeHtml(item.managerName || "—")}</td>
                      <td>${renderBadge(item.statusLabel || item.status)}</td>
                      <td>${item.fitBand ? renderBadge(item.fitBand) : '<span class="muted">—</span>'}</td>
                      <td>
                        <div>${escapeHtml(item.llmRationale || "—")}</div>
                        ${item.filterReasonCodes && item.filterReasonCodes.length ? `<div class="muted">${escapeHtml(item.filterReasonCodes.join(", "))}</div>` : ""}
                      </td>
                      <td><button class="secondary-btn match-open-btn" data-match-id="${escapeHtml(item.id)}">Open</button></td>
                    </tr>
                  `).join("") || `<tr><td colspan="8" class="empty-state">No matches found.</td></tr>`}
                </tbody>
              </table>
            </div>
          </section>
          ${renderMatchDetailPanel(state.currentMatchDetail)}
        </div>
      </div>
    `;
  }

  function renderMessages() {
    const selected = Array.from(state.selectedUserIds);
    return `
      <div class="screen">
        <section class="panel">
          <h2>Bot Messaging</h2>
          <p class="muted">Send a real Telegram bot message through the existing notification pipeline. Blocked users and users without a private chat are automatically skipped.</p>
        </section>
        <div class="split-layout">
          <section class="panel">
            <div class="message-form">
              <div class="selection-summary">
                <span class="badge accent">${selected.length} selected recipients</span>
              </div>
              <textarea id="message-text" placeholder="Write the message that should be sent from the bot.">${escapeHtml(state.messageDraft || state.messagePreview?.message?.text || "")}</textarea>
              <div class="inline-actions">
                <button class="secondary-btn" id="message-preview-btn">Preview</button>
                <button class="primary-btn" id="message-send-btn">Send</button>
              </div>
            </div>
          </section>
          <section class="detail-card">
            <h3>Preview</h3>
            ${state.messagePreview ? `
              <div class="preview-card">
                <p>${escapeHtml(state.messagePreview.message.text)}</p>
              </div>
              <div class="detail-block" style="margin-top: 16px;">
                <h4>Deliverable</h4>
                <div class="preview-list">
                  ${(state.messagePreview.deliverable || []).map((row) => `<span class="badge good">${escapeHtml(row.displayName || row.username || row.telegramUserId)}</span>`).join("") || '<span class="muted">No deliverable recipients.</span>'}
                </div>
              </div>
              <div class="detail-block">
                <h4>Skipped</h4>
                <div class="preview-list">
                  ${(state.messagePreview.skipped || []).map((row) => `<span class="badge bad">${escapeHtml(`${row.userId}: ${row.reason}`)}</span>`).join("") || '<span class="muted">No skipped recipients.</span>'}
                </div>
              </div>
            ` : `<p class="muted">Preview will appear here after you validate the current selection and message text.</p>`}
          </section>
        </div>
      </div>
    `;
  }

  async function renderApp() {
    if (!state.session) {
      renderLogin();
      return;
    }
    const route = routeFromHash();
    if (route.name === "match-detail" && route.id) {
      await loadMatchDetail(route.id);
    } else if (route.name !== "matches") {
      state.currentMatchDetail = null;
    }

    let body = "";
    if (route.name === "users") {
      body = renderUsers();
    } else if (route.name === "matches" || route.name === "match-detail") {
      body = renderMatches();
    } else if (route.name === "messages") {
      body = renderMessages();
    } else {
      body = renderDashboard();
    }
    renderShell(body);
    bindDashboardEvents();
  }

  function bindDashboardEvents() {
    const route = routeFromHash();

    if (route.name === "users") {
      const selectAll = document.getElementById("users-select-all");
      if (selectAll) {
        selectAll.addEventListener("change", (event) => {
          const checked = Boolean(event.target.checked);
          (state.usersPayload.items || []).forEach((item) => {
            if (checked) state.selectedUserIds.add(item.id);
            else state.selectedUserIds.delete(item.id);
          });
          renderApp();
        });
      }
      document.querySelectorAll(".user-select").forEach((checkbox) => {
        checkbox.addEventListener("change", (event) => {
          const userId = event.target.getAttribute("data-user-id");
          if (event.target.checked) state.selectedUserIds.add(userId);
          else state.selectedUserIds.delete(userId);
        });
      });
      document.getElementById("users-apply-filters").addEventListener("click", async () => {
        state.usersFilters.role = document.getElementById("users-role-filter").value;
        state.usersFilters.status = document.getElementById("users-status-filter").value;
        state.usersFilters.candidate_state = document.getElementById("users-candidate-state-filter").value;
        state.usersFilters.vacancy_state = document.getElementById("users-vacancy-state-filter").value;
        state.usersFilters.search = document.getElementById("users-search-filter").value.trim();
        await loadUsers();
        renderApp();
      });
      document.getElementById("users-block-btn").addEventListener("click", async () => {
        if (!state.selectedUserIds.size) return;
        const reason = window.prompt("Optional block reason", "") || null;
        await api("/admin/api/users/block", {
          method: "POST",
          body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), reason }),
        });
        await loadUsers();
        renderApp();
      });
      document.getElementById("users-unblock-btn").addEventListener("click", async () => {
        if (!state.selectedUserIds.size) return;
        await api("/admin/api/users/unblock", {
          method: "POST",
          body: JSON.stringify({ userIds: Array.from(state.selectedUserIds) }),
        });
        await loadUsers();
        renderApp();
      });
      document.getElementById("users-message-btn").addEventListener("click", () => {
        setRoute("messages");
      });
      document.querySelectorAll(".user-view-btn").forEach((button) => {
        button.addEventListener("click", async () => {
          const payload = await api(`/admin/api/users/${button.getAttribute("data-user-id")}`);
          const sidePanel = document.getElementById("users-side-panel");
          sidePanel.innerHTML = `
            <h3>User Detail</h3>
            <div class="detail-block">
              <p><strong>${escapeHtml(payload.user.candidateName || payload.user.displayName || payload.user.username || payload.user.telegramUserId)}</strong></p>
              <div class="pill-row">
                ${renderBadge(payload.user.role)}
                ${renderBadge(payload.user.status)}
                ${payload.user.candidateState ? renderBadge(payload.user.candidateState) : ""}
              </div>
            </div>
            ${payload.candidate ? `<div class="detail-block"><h4>Candidate</h4><p>${escapeHtml(payload.candidate.summary?.approvalSummaryText || payload.candidate.summary?.headline || "No summary.")}</p></div>` : ""}
            ${payload.vacancies && payload.vacancies.length ? `<div class="detail-block"><h4>Vacancies</h4><div class="preview-list">${payload.vacancies.map((vacancy) => `<span class="badge accent">${escapeHtml(`${vacancy.roleTitle || "Vacancy"} · ${vacancy.state}`)}</span>`).join("")}</div></div>` : ""}
            <div class="detail-block"><h4>Stats</h4><div class="pill-row">${Object.entries(payload.stats || {}).map(([key, value]) => `<span class="badge accent">${escapeHtml(`${key}: ${value}`)}</span>`).join("")}</div></div>
          `;
        });
      });
      document.querySelectorAll(".user-delete-btn").forEach((button) => {
        button.addEventListener("click", async () => {
          const userId = button.getAttribute("data-user-id");
          if (!window.confirm("Hard delete this user and all related history?")) return;
          await api(`/admin/api/users/${userId}`, { method: "DELETE" });
          state.selectedUserIds.delete(userId);
          await Promise.all([loadUsers(), loadAnalytics(), loadMatches()]);
          renderApp();
        });
      });
    }

    if (route.name === "matches" || route.name === "match-detail") {
      const applyBtn = document.getElementById("matches-apply-filters");
      if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
          state.matchesFilters.status = document.getElementById("matches-status-filter").value;
          state.matchesFilters.fit_band = document.getElementById("matches-fit-filter").value;
          state.matchesFilters.search = document.getElementById("matches-search-filter").value.trim();
          await loadMatches();
          if (route.name === "match-detail" && route.id) {
            await loadMatchDetail(route.id);
          }
          renderApp();
        });
      }
      document.querySelectorAll(".match-open-btn").forEach((button) => {
        button.addEventListener("click", () => {
          setRoute(`/matches/${button.getAttribute("data-match-id")}`);
        });
      });
    }

    if (route.name === "messages") {
      const messageInput = document.getElementById("message-text");
      if (messageInput) {
        messageInput.addEventListener("input", (event) => {
          state.messageDraft = event.target.value || "";
        });
      }
      document.getElementById("message-preview-btn").addEventListener("click", async () => {
        if (!state.selectedUserIds.size) {
          alert("Select at least one user first.");
          return;
        }
        const text = document.getElementById("message-text").value || "";
        state.messageDraft = text;
        state.messagePreview = await api("/admin/api/messages/preview", {
          method: "POST",
          body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), text }),
        });
        renderApp();
      });
      document.getElementById("message-send-btn").addEventListener("click", async () => {
        if (!state.selectedUserIds.size) {
          alert("Select at least one user first.");
          return;
        }
        const text = document.getElementById("message-text").value || "";
        state.messageDraft = text;
        if (!window.confirm("Send this bot message to all deliverable recipients?")) return;
        await api("/admin/api/messages/send", {
          method: "POST",
          body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), text }),
        });
        state.messagePreview = null;
        state.messageDraft = "";
        await loadUsers();
        alert("Messages queued through the real bot notification pipeline.");
        renderApp();
      });
    }
  }

  window.addEventListener("hashchange", () => {
    if (!state.session) {
      renderLogin();
      return;
    }
    renderApp();
  });

  bootstrapSession();
})();
