(function () {
  const state = {
    session: null,
    usersPayload: null,
    matchesPayload: null,
    analyticsPayload: null,
    currentMatchDetail: null,
    currentUserDetail: null,
    selectedUserIds: new Set(),
    messagePreview: null,
    messagePreviewContextKey: null,
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
    ui: {
      modal: null,
      toasts: [],
      isRefreshing: false,
    },
  };

  const appEl = document.getElementById("app");
  const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function compactText(value, limit) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    if (text.length <= limit) return text;
    return `${text.slice(0, limit - 1).trimEnd()}…`;
  }

  function formatDateTime(value) {
    if (!value) return "—";
    try {
      return dateTimeFormatter.format(new Date(value));
    } catch (_) {
      return String(value);
    }
  }

  function badgeTone(value) {
    const text = String(value || "").toLowerCase();
    if (
      text.includes("approved")
      || text.includes("strong")
      || text === "active"
      || text === "open"
      || text.includes("shared")
      || text.includes("success")
      || text.includes("sent")
    ) return "good";
    if (
      text.includes("skip")
      || text.includes("reject")
      || text.includes("blocked")
      || text.includes("expired")
      || text.includes("not_fit")
      || text.includes("failed")
      || text.includes("cancel")
      || text.includes("deleted")
    ) return "bad";
    if (
      text.includes("pending")
      || text.includes("review")
      || text.includes("await")
      || text.includes("medium")
      || text.includes("queue")
    ) return "warn";
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

  function searchParams() {
    return new URLSearchParams(window.location.search);
  }

  function applyUrlState() {
    const params = searchParams();
    state.usersFilters.role = params.get("u_role") || "";
    state.usersFilters.status = params.get("u_status") || "";
    state.usersFilters.candidate_state = params.get("u_candidate_state") || "";
    state.usersFilters.vacancy_state = params.get("u_vacancy_state") || "";
    state.usersFilters.search = params.get("u_search") || "";

    state.matchesFilters.status = params.get("m_status") || "";
    state.matchesFilters.fit_band = params.get("m_fit_band") || "";
    state.matchesFilters.search = params.get("m_search") || "";
  }

  function syncUrlState() {
    const params = searchParams();
    const values = {
      u_role: state.usersFilters.role,
      u_status: state.usersFilters.status,
      u_candidate_state: state.usersFilters.candidate_state,
      u_vacancy_state: state.usersFilters.vacancy_state,
      u_search: state.usersFilters.search,
      m_status: state.matchesFilters.status,
      m_fit_band: state.matchesFilters.fit_band,
      m_search: state.matchesFilters.search,
      user_id: routeFromHash().name === "users" && state.currentUserDetail ? state.currentUserDetail.user.id : "",
    };
    Object.entries(values).forEach(([key, value]) => {
      if (value) params.set(key, value);
      else params.delete(key);
    });
    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }

  function selectedUserPreview() {
    const ids = Array.from(state.selectedUserIds);
    const known = new Map(((state.usersPayload && state.usersPayload.items) || []).map((item) => [item.id, item]));
    return ids.slice(0, 8).map((id) => {
      const item = known.get(id);
      return item ? (item.candidateName || item.displayName || item.username || item.telegramUserId) : id;
    });
  }

  function showToast({ tone = "accent", title, body, timeout = 4200 }) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    state.ui.toasts = [...state.ui.toasts, { id, tone, title, body }];
    renderApp();
    window.setTimeout(() => {
      state.ui.toasts = state.ui.toasts.filter((toast) => toast.id !== id);
      renderApp();
    }, timeout);
  }

  function showModal(config) {
    state.ui.modal = config;
    document.body.classList.add("modal-open");
    renderApp();
  }

  function hideModal() {
    state.ui.modal = null;
    document.body.classList.remove("modal-open");
    renderApp();
  }

  function currentMessagePreviewKey(text) {
    return JSON.stringify({
      userIds: Array.from(state.selectedUserIds).sort(),
      text: String(text || "").trim(),
    });
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

  async function withBusy(task, options = {}) {
    const { successText, errorPrefix } = options;
    state.ui.isRefreshing = true;
    renderApp();
    try {
      const result = await task();
      if (successText) {
        showToast({ tone: "good", title: "Done", body: successText });
      }
      return result;
    } catch (error) {
      showToast({
        tone: "bad",
        title: "Action failed",
        body: `${errorPrefix || "Request failed"}: ${error.message || error}`,
        timeout: 6000,
      });
      throw error;
    } finally {
      state.ui.isRefreshing = false;
      renderApp();
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

  async function loadUserDetail(userId) {
    if (!userId) {
      state.currentUserDetail = null;
      return;
    }
    state.currentUserDetail = await api(`/admin/api/users/${userId}`);
  }

  async function loadMatchDetail(matchId) {
    if (!matchId) {
      state.currentMatchDetail = null;
      return;
    }
    state.currentMatchDetail = await api(`/admin/api/matches/${matchId}`);
  }

  async function refreshAll() {
    await Promise.all([loadAnalytics(), loadUsers(), loadMatches()]);
    const route = routeFromHash();
    if (route.name === "match-detail" && route.id) {
      await loadMatchDetail(route.id);
    }
    const params = searchParams();
    if (route.name === "users" && params.get("user_id")) {
      await loadUserDetail(params.get("user_id"));
    } else if (route.name !== "users") {
      state.currentUserDetail = null;
    }
  }

  async function bootstrapSession() {
    applyUrlState();
    try {
      const payload = await api("/admin/api/session");
      state.session = payload.session;
      await refreshAll();
      renderApp();
    } catch (_) {
      renderLogin();
    }
  }

  function renderLogin(errorText) {
    appEl.innerHTML = `
      <section class="login-card">
        <p class="eyebrow">Helly Admin</p>
        <h1>Admin Access</h1>
        <p class="muted">Browser-only admin panel. PIN is verified by backend and stored in a server session cookie.</p>
        <form id="login-form" class="login-form">
          <div class="form-field">
            <label class="form-label" for="pin-input">Admin PIN</label>
            <input
              id="pin-input"
              name="admin_pin"
              type="password"
              placeholder="Enter the admin PIN…"
              autocomplete="current-password"
              spellcheck="false"
            />
          </div>
          ${errorText ? `<p class="danger-copy">${escapeHtml(errorText)}</p>` : ""}
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
        <div class="metric-value mono">${escapeHtml(value)}</div>
        <div>${escapeHtml(title)}</div>
        ${note ? `<p class="muted" style="margin-top: 8px;">${escapeHtml(note)}</p>` : ""}
      </section>
    `;
  }

  function navButton(route, label) {
    const active = routeFromHash().name === route;
    return `<button class="secondary-btn ${active ? "active" : ""}" data-route="${route}">${escapeHtml(label)}</button>`;
  }

  function renderToasts() {
    if (!state.ui.toasts.length) return "";
    return `
      <div class="toast-layer" aria-live="polite">
        ${state.ui.toasts.map((toast) => `
          <section class="toast ${escapeHtml(toast.tone)}">
            <strong>${escapeHtml(toast.title || "Notice")}</strong>
            ${toast.body ? `<div class="muted" style="margin-top: 6px;">${escapeHtml(toast.body)}</div>` : ""}
          </section>
        `).join("")}
      </div>
    `;
  }

  function renderModal() {
    const modal = state.ui.modal;
    if (!modal) return "";
    const confirmNeedsValue = modal.requireTypedValue || modal.promptLabel;
    const confirmToneClass = modal.confirmTone === "danger" ? "danger-btn" : "primary-btn";
    return `
      <div class="modal-layer" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <section class="modal-card">
          <p class="eyebrow">${escapeHtml(modal.eyebrow || "Admin action")}</p>
          <h2 id="modal-title">${escapeHtml(modal.title || "Confirm action")}</h2>
          ${modal.body ? `<p class="muted break-words">${escapeHtml(modal.body)}</p>` : ""}
          ${modal.html ? `<div>${modal.html}</div>` : ""}
          ${confirmNeedsValue ? `
            <div class="form-field" style="margin-top: 14px;">
              <label class="form-label" for="modal-input">${escapeHtml(modal.promptLabel || "Input")}</label>
              ${modal.multiline ? `
                <textarea id="modal-input" placeholder="${escapeHtml(modal.promptPlaceholder || "")}">${escapeHtml(modal.initialValue || "")}</textarea>
              ` : `
                <input
                  id="modal-input"
                  type="${escapeHtml(modal.promptType || "text")}"
                  placeholder="${escapeHtml(modal.promptPlaceholder || "")}"
                  value="${escapeHtml(modal.initialValue || "")}"
                  autocomplete="off"
                />
              `}
              ${modal.helperText ? `<div class="helper-text">${escapeHtml(modal.helperText)}</div>` : ""}
            </div>
          ` : ""}
          <div class="modal-actions">
            <button class="secondary-btn" id="modal-cancel-btn" type="button">${escapeHtml(modal.cancelLabel || "Cancel")}</button>
            <button class="${confirmToneClass}" id="modal-confirm-btn" type="button">${escapeHtml(modal.confirmLabel || "Confirm")}</button>
          </div>
        </section>
      </div>
    `;
  }

  function renderShell(innerHtml) {
    appEl.innerHTML = `
      <div class="topbar">
        <div>
          <p class="eyebrow">Helly Admin</p>
          <h1 style="margin-bottom: 6px;">Operations Panel</h1>
          <p class="muted" style="margin-bottom: 0;">Real backend data, browser auth via PIN, direct links for match triage.</p>
          <div class="topbar-status">
            <span class="status-dot" aria-hidden="true"></span>
            <span class="muted">${state.ui.isRefreshing ? "Refreshing data…" : "Live data mode"}</span>
          </div>
        </div>
        <div class="topbar-actions">
          <button class="secondary-btn" id="refresh-all" ${state.ui.isRefreshing ? "disabled" : ""}>
            ${state.ui.isRefreshing ? "Refreshing…" : "Refresh"}
          </button>
          <button class="secondary-btn" id="logout-btn">Logout</button>
        </div>
      </div>
      <nav class="nav panel" aria-label="Admin navigation">
        ${navButton("dashboard", "Dashboard")}
        ${navButton("users", "Users")}
        ${navButton("matches", "Matches")}
        ${navButton("messages", "Messages")}
      </nav>
      ${innerHtml}
      ${renderToasts()}
      ${renderModal()}
    `;
    document.querySelectorAll("[data-route]").forEach((button) => {
      button.addEventListener("click", () => setRoute(button.getAttribute("data-route")));
    });
    document.getElementById("refresh-all").addEventListener("click", async () => {
      await withBusy(async () => {
        await refreshAll();
        renderApp();
      }, { successText: "Admin data refreshed.", errorPrefix: "Refresh failed" });
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
            <div class="section-head">
              <div>
                <h2>Funnel</h2>
                <p class="muted">Use this as a quick read on where matching is currently stalling.</p>
              </div>
            </div>
            <div class="pill-row">
              ${Object.entries(funnel).map(([key, value]) => `<span class="badge accent">${escapeHtml(`${key}: ${value}`)}</span>`).join("")}
            </div>
          </section>
          <section class="panel">
            <div class="section-head">
              <div>
                <h2>Role Distribution</h2>
                <p class="muted">Real current users grouped by effective product role.</p>
              </div>
            </div>
            <div class="pill-row">
              ${Object.entries((users.byRole || {})).map(([key, value]) => `<span class="badge ${badgeTone(key)}">${escapeHtml(`${key}: ${value}`)}</span>`).join("")}
            </div>
          </section>
        </div>
        <section class="panel">
          <div class="section-head">
            <div>
              <h2>Recent Matching Runs</h2>
              <p class="muted">Newest runs only. Open Matches to inspect actual outcomes and candidate quality.</p>
            </div>
          </div>
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
                    <td class="mono">${escapeHtml(run.id)}</td>
                    <td class="mono">${escapeHtml(run.vacancyId)}</td>
                    <td>${renderBadge(run.triggerType)}</td>
                    <td>${renderBadge(run.status)}</td>
                    <td class="mono">${escapeHtml(run.candidatePoolCount)}</td>
                    <td class="mono">${escapeHtml(run.hardFilteredCount)}</td>
                    <td class="mono">${escapeHtml(run.shortlistedCount)}</td>
                    <td>${escapeHtml(formatDateTime(run.createdAt))}</td>
                  </tr>
                `).join("") || `<tr><td colspan="8" class="empty-state">No matching runs yet.</td></tr>`}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    `;
  }

  function renderUserDetailPanel(detail) {
    if (!detail) {
      return `
        <section class="detail-card side-panel">
          <h3>User Detail</h3>
          <p class="muted">Pick a row to inspect the user, recent matches, notifications, and message history.</p>
        </section>
      `;
    }
    const user = detail.user || {};
    const candidate = detail.candidate || null;
    const vacancies = detail.vacancies || [];
    const recentMatches = detail.recentMatches || [];
    const recentNotifications = detail.recentNotifications || [];
    const recentMessages = detail.recentMessages || [];
    return `
      <section class="detail-card side-panel" id="users-side-panel">
        <div class="section-head">
          <div>
            <h3>${escapeHtml(user.candidateName || user.displayName || user.username || user.telegramUserId || "User")}</h3>
            <p class="muted">${escapeHtml(user.id || "")}</p>
          </div>
          <button class="ghost-btn" id="close-user-detail-btn" type="button">Close</button>
        </div>
        <div class="detail-block">
          <div class="pill-row">
            ${renderBadge(user.role)}
            ${renderBadge(user.status)}
            ${user.candidateState ? renderBadge(user.candidateState) : ""}
            ${user.blockedReason ? `<span class="badge bad">${escapeHtml(`reason: ${user.blockedReason}`)}</span>` : ""}
          </div>
          <div class="detail-grid" style="margin-top: 12px;">
            <div class="key-value"><span class="label">Telegram</span><div>@${escapeHtml(user.username || "—")}</div></div>
            <div class="key-value"><span class="label">Telegram User Id</span><div class="mono">${escapeHtml(user.telegramUserId || "—")}</div></div>
            <div class="key-value"><span class="label">Updated</span><div>${escapeHtml(formatDateTime(user.updatedAt))}</div></div>
            <div class="key-value"><span class="label">Stats</span><div>${escapeHtml(`matches ${detail.stats.matchCount || 0} · notifications ${detail.stats.notificationCount || 0} · messages ${detail.stats.rawMessageCount || 0}`)}</div></div>
          </div>
        </div>
        ${candidate ? `
          <div class="detail-block">
            <h4>Candidate Profile</h4>
            <p class="muted break-words">${escapeHtml(candidate.summary?.approvalSummaryText || candidate.summary?.headline || "No candidate summary saved.")}</p>
            <div class="pill-row">
              ${candidate.salaryExpectation ? renderBadge(candidate.salaryExpectation) : ""}
              ${candidate.workFormat ? renderBadge(candidate.workFormat) : ""}
              ${candidate.englishLevel ? renderBadge(candidate.englishLevel) : ""}
              ${candidate.preferredDomains ? renderBadge(candidate.preferredDomains) : ""}
            </div>
          </div>
        ` : ""}
        ${vacancies.length ? `
          <div class="detail-block">
            <h4>Open Vacancies</h4>
            <div class="preview-list">
              ${vacancies.map((vacancy) => `<span class="badge accent">${escapeHtml(`${vacancy.roleTitle || "Vacancy"} · ${vacancy.state || "—"}`)}</span>`).join("")}
            </div>
          </div>
        ` : ""}
        <div class="detail-block">
          <h4>Recent Matches</h4>
          ${recentMatches.length ? `
            <div class="timeline-list">
              ${recentMatches.map((match) => `
                <div class="timeline-card">
                  <div class="section-head">
                    <div>
                      <div class="timeline-title">${escapeHtml(match.roleTitle || "Match")}</div>
                      <div class="timeline-meta">${escapeHtml(match.candidateName || user.candidateName || "Candidate")} · ${escapeHtml(formatDateTime(match.updatedAt))}</div>
                    </div>
                    <button class="secondary-btn open-match-from-user" data-match-id="${escapeHtml(match.id)}" type="button">Open Match</button>
                  </div>
                  <div class="pill-row">
                    ${renderBadge(match.statusLabel || match.status)}
                    ${match.fitBand ? renderBadge(match.fitBand) : ""}
                  </div>
                </div>
              `).join("")}
            </div>
          ` : `<p class="muted">No matches tied to this user yet.</p>`}
        </div>
        <div class="detail-block">
          <h4>Recent Notifications</h4>
          ${recentNotifications.length ? `
            <div class="timeline-list">
              ${recentNotifications.map((row) => `
                <div class="summary-card">
                  <div class="pill-row">
                    ${renderBadge(row.templateKey)}
                    ${renderBadge(row.status)}
                  </div>
                  <div class="helper-text">${escapeHtml(formatDateTime(row.createdAt))}</div>
                  <div class="break-words">${escapeHtml(row.textPreview || row.lastError || "No preview text.")}</div>
                </div>
              `).join("")}
            </div>
          ` : `<p class="muted">No recent notifications.</p>`}
        </div>
        <div>
          <h4>Recent Messages</h4>
          ${recentMessages.length ? `
            <div class="timeline-list">
              ${recentMessages.map((row) => `
                <div class="summary-card">
                  <div class="pill-row">
                    ${renderBadge(row.direction)}
                    ${renderBadge(row.contentType)}
                  </div>
                  <div class="helper-text">${escapeHtml(formatDateTime(row.createdAt))}</div>
                  <div class="break-words">${escapeHtml(row.textPreview || "No text payload.")}</div>
                </div>
              `).join("")}
            </div>
          ` : `<p class="muted">No recent raw messages.</p>`}
        </div>
      </section>
    `;
  }

  function renderUsers() {
    const payload = state.usersPayload || { items: [], filters: {} };
    const items = payload.items || [];
    const filters = payload.filters || {};
    const selectedPreview = selectedUserPreview();
    return `
      <div class="screen">
        <section class="panel">
          <div class="section-head">
            <div>
              <h2>Users</h2>
              <p class="muted">Filter by role, state, and activity before taking destructive or messaging actions.</p>
            </div>
          </div>
          <div class="toolbar">
            <div class="form-field">
              <label class="form-label" for="users-role-filter">Role</label>
              <select id="users-role-filter" name="users_role_filter">
                <option value="">All roles</option>
                ${(filters.roleOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.role === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="users-status-filter">Status</label>
              <select id="users-status-filter" name="users_status_filter">
                <option value="">All statuses</option>
                ${(filters.statusOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.status === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="users-candidate-state-filter">Candidate State</label>
              <select id="users-candidate-state-filter" name="users_candidate_state_filter">
                <option value="">All candidate states</option>
                ${(filters.candidateStateOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.candidate_state === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="users-vacancy-state-filter">Vacancy State</label>
              <select id="users-vacancy-state-filter" name="users_vacancy_state_filter">
                <option value="">All vacancy states</option>
                ${(filters.vacancyStateOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.usersFilters.vacancy_state === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="users-search-filter">Search</label>
              <input id="users-search-filter" name="users_search_filter" placeholder="Name, username, telegram id, role title…" value="${escapeHtml(state.usersFilters.search || "")}" autocomplete="off" />
            </div>
            <div class="form-field">
              <label class="form-label" for="users-apply-filters">Filters</label>
              <div class="action-row">
                <button class="primary-btn" id="users-apply-filters" type="button">Apply</button>
                <button class="ghost-btn" id="users-clear-filters" type="button">Clear</button>
              </div>
            </div>
          </div>
        </section>
        <div class="selection-bar sticky">
          <div>
            <div class="pill-row">
              <span class="badge accent">${escapeHtml(`${state.selectedUserIds.size} selected`)}</span>
              ${selectedPreview.map((label) => `<span class="badge muted">${escapeHtml(label)}</span>`).join("")}
            </div>
            <div class="helper-text" style="margin-top: 8px;">Hard delete is intentionally single-user. Bulk actions cover block, unblock, and messaging.</div>
          </div>
          <div class="inline-actions">
            <button class="secondary-btn" id="users-block-btn" type="button" ${state.selectedUserIds.size ? "" : "disabled"}>Block</button>
            <button class="secondary-btn" id="users-unblock-btn" type="button" ${state.selectedUserIds.size ? "" : "disabled"}>Unblock</button>
            <button class="primary-btn" id="users-message-btn" type="button" ${state.selectedUserIds.size ? "" : "disabled"}>Message</button>
          </div>
        </div>
        <div class="split-layout">
          <section class="panel">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th><input type="checkbox" id="users-select-all" aria-label="Select all visible users" /></th>
                    <th>Name</th>
                    <th>Telegram</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Candidate State</th>
                    <th>Vacancy States</th>
                    <th>Updated</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${items.map((item) => {
                    const checked = state.selectedUserIds.has(item.id) ? "checked" : "";
                    return `
                      <tr>
                        <td><input type="checkbox" class="user-select" data-user-id="${escapeHtml(item.id)}" ${checked} aria-label="Select ${escapeHtml(item.candidateName || item.displayName || item.username || item.telegramUserId)}" /></td>
                        <td>
                          <div class="cell-stack">
                            <strong>${escapeHtml(item.candidateName || item.displayName || item.username || item.telegramUserId)}</strong>
                            <span class="muted mono">${escapeHtml(item.id)}</span>
                          </div>
                        </td>
                        <td>
                          <div class="cell-stack">
                            <span>${escapeHtml(item.username ? `@${item.username}` : "—")}</span>
                            <span class="muted mono">${escapeHtml(item.telegramUserId)}</span>
                          </div>
                        </td>
                        <td>${renderBadge(item.role)}</td>
                        <td>${renderBadge(item.status)}</td>
                        <td>${item.candidateState ? renderBadge(item.candidateState) : '<span class="muted">—</span>'}</td>
                        <td>${(item.vacancyStates || []).length ? item.vacancyStates.map(renderBadge).join(" ") : '<span class="muted">—</span>'}</td>
                        <td>${escapeHtml(formatDateTime(item.updatedAt))}</td>
                        <td>
                          <div class="inline-actions">
                            <button class="secondary-btn user-view-btn" data-user-id="${escapeHtml(item.id)}" type="button">Open</button>
                            <button class="danger-btn user-delete-btn" data-user-id="${escapeHtml(item.id)}" data-user-label="${escapeHtml(item.candidateName || item.displayName || item.username || item.telegramUserId)}" type="button">Delete</button>
                          </div>
                        </td>
                      </tr>
                    `;
                  }).join("") || `<tr><td colspan="9" class="empty-state">No users found for the selected filters.</td></tr>`}
                </tbody>
              </table>
            </div>
          </section>
          ${renderUserDetailPanel(state.currentUserDetail)}
        </div>
      </div>
    `;
  }

  function buildMatchTimeline(detail) {
    const items = [];
    (detail.timeline || []).forEach((entry) => {
      items.push({
        id: entry.id,
        tone: badgeTone(entry.toState || entry.triggerType || "accent"),
        title: `${entry.fromState || "—"} → ${entry.toState || "—"}`,
        meta: `${entry.triggerType || "unknown trigger"} · ${formatDateTime(entry.createdAt)}`,
        body: entry.metadata && Object.keys(entry.metadata).length ? JSON.stringify(entry.metadata) : "",
      });
    });
    if (detail.introduction) {
      items.unshift({
        id: detail.introduction.id,
        tone: "good",
        title: "Contacts shared",
        meta: `${detail.introduction.mode || "telegram_handoff"} · ${formatDateTime(detail.introduction.introducedAt)}`,
        body: "",
      });
    }
    return items;
  }

  function renderMatchDetailPanel(detail) {
    if (!detail) {
      return `
        <section class="detail-card side-panel">
          <h3>Match Detail</h3>
          <p class="muted">Pick a match row or open a direct match link.</p>
        </section>
      `;
    }
    const match = detail.match || {};
    const vacancy = detail.vacancy || {};
    const candidate = detail.candidate || {};
    const run = detail.run || {};
    const notifications = detail.notifications || [];
    const timeline = buildMatchTimeline(detail);
    return `
      <section class="detail-card side-panel">
        <div class="section-head">
          <div>
            <h3>Match Detail</h3>
            <p class="muted mono">${escapeHtml(match.id || "")}</p>
          </div>
          <div class="inline-actions">
            <button class="ghost-btn" id="close-match-detail-btn" type="button">Back</button>
            ${match.adminUrl ? `<a class="secondary-btn" href="${escapeHtml(match.adminUrl)}" target="_blank" rel="noreferrer">Direct Link</a>` : ""}
          </div>
        </div>
        <div class="detail-block">
          <div class="pill-row">
            ${renderBadge(match.statusLabel || match.status)}
            ${match.fitBand ? renderBadge(match.fitBand) : ""}
            ${match.hardFilterPassed === false ? renderBadge("hard-filter failed") : ""}
          </div>
          <div class="detail-grid" style="margin-top: 12px;">
            <div class="key-value"><span class="label">Deterministic</span><div class="mono">${escapeHtml(match.deterministicScore ?? "—")}</div></div>
            <div class="key-value"><span class="label">LLM Rank</span><div class="mono">${escapeHtml(match.llmRankScore ?? "—")}</div></div>
            <div class="key-value"><span class="label">Embedding</span><div class="mono">${escapeHtml(match.embeddingScore ?? "—")}</div></div>
            <div class="key-value"><span class="label">Updated</span><div>${escapeHtml(formatDateTime(match.updatedAt))}</div></div>
          </div>
        </div>
        <div class="detail-block">
          <h4>Vacancy</h4>
          <div class="summary-card">
            <strong>${escapeHtml(vacancy.roleTitle || "—")}</strong>
            <div class="break-words">${escapeHtml(vacancy.projectDescription || vacancy.summary?.approvalSummaryText || "No project description saved.")}</div>
            <div class="pill-row">
              ${vacancy.budget ? renderBadge(vacancy.budget) : ""}
              ${vacancy.workFormat ? renderBadge(vacancy.workFormat) : ""}
              ${vacancy.requiredEnglishLevel ? renderBadge(vacancy.requiredEnglishLevel) : ""}
              ${vacancy.teamSize ? renderBadge(`team ${vacancy.teamSize}`) : ""}
              ${(vacancy.primaryTechStack || []).map(renderBadge).join("")}
            </div>
          </div>
        </div>
        <div class="detail-block">
          <h4>Candidate</h4>
          <div class="summary-card">
            <strong>${escapeHtml(candidate.name || "Candidate")}</strong>
            <div class="break-words">${escapeHtml(candidate.summary?.approvalSummaryText || candidate.summary?.headline || "No candidate summary saved.")}</div>
            <div class="pill-row">
              ${candidate.salaryExpectation ? renderBadge(candidate.salaryExpectation) : ""}
              ${candidate.workFormat ? renderBadge(candidate.workFormat) : ""}
              ${candidate.englishLevel ? renderBadge(candidate.englishLevel) : ""}
              ${candidate.preferredDomains ? renderBadge(candidate.preferredDomains) : ""}
            </div>
          </div>
        </div>
        <div class="detail-block">
          <h4>Rationale</h4>
          <div class="summary-card">
            <div class="break-words">${escapeHtml(match.llmRationale || "No LLM rationale saved.")}</div>
            ${match.filterReasonCodes && match.filterReasonCodes.length ? `<div class="helper-text">Filter reasons: ${escapeHtml(match.filterReasonCodes.join(", "))}</div>` : ""}
            ${match.gapSignals && match.gapSignals.length ? `<div class="helper-text">Gaps: ${escapeHtml(match.gapSignals.join(" · "))}</div>` : ""}
            ${match.matchedSignals && match.matchedSignals.length ? `<div class="helper-text">Matched signals: ${escapeHtml(match.matchedSignals.join(" · "))}</div>` : ""}
          </div>
        </div>
        <div class="detail-block">
          <h4>Timeline</h4>
          ${timeline.length ? `
            <div class="timeline-list">
              ${timeline.map((item) => `
                <div class="timeline-item ${escapeHtml(item.tone)}">
                  <div class="timeline-title">${escapeHtml(item.title)}</div>
                  <div class="timeline-meta">${escapeHtml(item.meta)}</div>
                  ${item.body ? `<div class="helper-text break-words" style="margin-top: 6px;">${escapeHtml(compactText(item.body, 220))}</div>` : ""}
                </div>
              `).join("")}
            </div>
          ` : `<p class="muted">No timeline events recorded for this match yet.</p>`}
        </div>
        <div class="detail-block">
          <h4>Related Notifications</h4>
          ${notifications.length ? `
            <div class="timeline-list">
              ${notifications.map((row) => `
                <div class="summary-card">
                  <div class="pill-row">
                    ${renderBadge(row.templateKey)}
                    ${renderBadge(row.status)}
                  </div>
                  <div class="helper-text">${escapeHtml(formatDateTime(row.createdAt))}</div>
                  <div class="break-words">${escapeHtml(row.textPreview || row.lastError || "No preview text.")}</div>
                </div>
              `).join("")}
            </div>
          ` : `<p class="muted">No notifications attached to this match.</p>`}
        </div>
        <div>
          <h4>Matching Run</h4>
          <div class="summary-card">
            <div class="helper-text">Trigger: ${escapeHtml(run.triggerType || "—")} · Pool: ${escapeHtml(run.candidatePoolCount || 0)} · Filtered: ${escapeHtml(run.hardFilteredCount || 0)} · Shortlisted: ${escapeHtml(run.shortlistedCount || 0)}</div>
          </div>
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
          <div class="section-head">
            <div>
              <h2>Matches</h2>
              <p class="muted">This is the primary triage view for matching quality, decisions, and contact share outcomes.</p>
            </div>
          </div>
          <div class="toolbar">
            <div class="form-field">
              <label class="form-label" for="matches-status-filter">Status</label>
              <select id="matches-status-filter" name="matches_status_filter">
                <option value="">All statuses</option>
                ${(filters.statusOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.matchesFilters.status === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="matches-fit-filter">Fit Band</label>
              <select id="matches-fit-filter" name="matches_fit_filter">
                <option value="">All fit bands</option>
                ${(filters.fitBandOptions || []).map((value) => `<option value="${escapeHtml(value)}" ${state.matchesFilters.fit_band === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
              </select>
            </div>
            <div class="form-field">
              <label class="form-label" for="matches-search-filter">Search</label>
              <input id="matches-search-filter" name="matches_search_filter" placeholder="Role, candidate, manager, match id…" value="${escapeHtml(state.matchesFilters.search || "")}" autocomplete="off" />
            </div>
            <div class="form-field">
              <label class="form-label" for="matches-apply-filters">Filters</label>
              <div class="action-row">
                <button class="primary-btn" id="matches-apply-filters" type="button">Apply</button>
                <button class="ghost-btn" id="matches-clear-filters" type="button">Clear</button>
              </div>
            </div>
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
                    <th>Rationale</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  ${items.map((item) => `
                    <tr>
                      <td><div class="cell-stack"><strong class="mono">${escapeHtml(item.id)}</strong><span class="subtle">${escapeHtml(formatDateTime(item.updatedAt))}</span></div></td>
                      <td>${escapeHtml(item.roleTitle || "—")}</td>
                      <td>${escapeHtml(item.candidateName || "Candidate")}</td>
                      <td>${escapeHtml(item.managerName || "—")}</td>
                      <td>${renderBadge(item.statusLabel || item.status)}</td>
                      <td>${item.fitBand ? renderBadge(item.fitBand) : '<span class="muted">—</span>'}</td>
                      <td>
                        <div class="cell-stack">
                          <div class="break-words">${escapeHtml(item.llmRationale || "—")}</div>
                          ${item.filterReasonCodes && item.filterReasonCodes.length ? `<div class="subtle">${escapeHtml(item.filterReasonCodes.join(", "))}</div>` : ""}
                        </div>
                      </td>
                      <td><button class="secondary-btn match-open-btn" data-match-id="${escapeHtml(item.id)}" type="button">Open</button></td>
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
    const preview = state.messagePreview;
    const selectedPreview = selectedUserPreview();
    return `
      <div class="screen">
        <section class="panel">
          <div class="section-head">
            <div>
              <h2>Bot Messaging</h2>
              <p class="muted">Messages go through the real notification pipeline. Blocked users and users without a private chat are skipped automatically.</p>
            </div>
          </div>
        </section>
        <div class="selection-bar">
          <div>
            <div class="pill-row">
              <span class="badge accent">${escapeHtml(`${selected.length} selected recipients`)}</span>
              ${selectedPreview.map((label) => `<span class="badge muted">${escapeHtml(label)}</span>`).join("")}
            </div>
            <div class="helper-text" style="margin-top: 8px;">Use Preview first to inspect who will actually receive the message.</div>
          </div>
          <div class="stats-row">
            ${preview ? `<span class="badge good">${escapeHtml(`deliverable ${preview.counts.deliverable || 0}`)}</span>` : ""}
            ${preview ? `<span class="badge bad">${escapeHtml(`skipped ${preview.counts.skipped || 0}`)}</span>` : ""}
          </div>
        </div>
        <div class="split-layout">
          <section class="panel">
            <div class="message-form">
              <div class="form-field">
                <label class="form-label" for="message-text">Bot message</label>
                <textarea id="message-text" name="admin_bot_message" placeholder="Write the message that should be sent from the bot…">${escapeHtml(state.messageDraft || preview?.message?.text || "")}</textarea>
              </div>
              <div class="inline-actions">
                <button class="secondary-btn" id="message-preview-btn" type="button" ${selected.length ? "" : "disabled"}>Preview</button>
                <button class="primary-btn" id="message-send-btn" type="button" ${selected.length ? "" : "disabled"}>Send</button>
              </div>
            </div>
          </section>
          <section class="detail-card side-panel">
            <h3>Preview</h3>
            ${preview ? `
              <div class="preview-card">
                <p class="break-words">${escapeHtml(preview.message.text)}</p>
              </div>
              <div class="detail-block" style="margin-top: 16px;">
                <h4>Deliverable</h4>
                <div class="preview-list">
                  ${(preview.deliverable || []).map((row) => `<span class="badge good">${escapeHtml(row.displayName || row.username || row.telegramUserId)}</span>`).join("") || '<span class="muted">No deliverable recipients.</span>'}
                </div>
              </div>
              <div>
                <h4>Skipped</h4>
                <div class="timeline-list">
                  ${(preview.skipped || []).map((row) => `
                    <div class="summary-card">
                      <div class="pill-row">
                        ${renderBadge(row.reason)}
                      </div>
                      <div class="helper-text mono">${escapeHtml(row.userId)}</div>
                    </div>
                  `).join("") || '<span class="muted">No skipped recipients.</span>'}
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
    const params = searchParams();
    if (route.name === "match-detail" && route.id) {
      await loadMatchDetail(route.id);
    } else if (route.name !== "matches") {
      state.currentMatchDetail = null;
    }
    if (route.name === "users" && params.get("user_id")) {
      await loadUserDetail(params.get("user_id"));
    } else if (route.name !== "users") {
      state.currentUserDetail = null;
    }

    let body = "";
    if (route.name === "users") body = renderUsers();
    else if (route.name === "matches" || route.name === "match-detail") body = renderMatches();
    else if (route.name === "messages") body = renderMessages();
    else body = renderDashboard();

    renderShell(body);
    bindDashboardEvents();
  }

  function openUserDetail(userId) {
    withBusy(async () => {
      await loadUserDetail(userId);
      syncUrlState();
      renderApp();
    }, { errorPrefix: "Failed to load user detail" });
  }

  function clearUserDetail() {
    state.currentUserDetail = null;
    syncUrlState();
    renderApp();
  }

  function bindModalEvents() {
    const modal = state.ui.modal;
    if (!modal) return;
    const cancelBtn = document.getElementById("modal-cancel-btn");
    const confirmBtn = document.getElementById("modal-confirm-btn");
    const input = document.getElementById("modal-input");
    const updateConfirmState = () => {
      if (!confirmBtn) return;
      if (modal.requireTypedValue) {
        confirmBtn.disabled = (input ? input.value.trim() : "") !== modal.requireTypedValue;
      }
    };
    if (input) {
      input.addEventListener("input", updateConfirmState);
      updateConfirmState();
    }
    cancelBtn.addEventListener("click", hideModal);
    confirmBtn.addEventListener("click", async () => {
      try {
        const value = input ? input.value : "";
        await modal.onConfirm(value);
        hideModal();
      } catch (_) {}
    });
  }

  function bindDashboardEvents() {
    bindModalEvents();
    const route = routeFromHash();

    if (route.name === "users") {
      const selectAll = document.getElementById("users-select-all");
      if (selectAll) {
        selectAll.checked = (state.usersPayload.items || []).length > 0
          && (state.usersPayload.items || []).every((item) => state.selectedUserIds.has(item.id));
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
          renderApp();
        });
      });
      document.getElementById("users-apply-filters").addEventListener("click", async () => {
        state.usersFilters.role = document.getElementById("users-role-filter").value;
        state.usersFilters.status = document.getElementById("users-status-filter").value;
        state.usersFilters.candidate_state = document.getElementById("users-candidate-state-filter").value;
        state.usersFilters.vacancy_state = document.getElementById("users-vacancy-state-filter").value;
        state.usersFilters.search = document.getElementById("users-search-filter").value.trim();
        syncUrlState();
        await withBusy(async () => {
          await loadUsers();
          renderApp();
        }, { errorPrefix: "Failed to load users" });
      });
      document.getElementById("users-clear-filters").addEventListener("click", async () => {
        state.usersFilters = { role: "", status: "", candidate_state: "", vacancy_state: "", search: "" };
        syncUrlState();
        await withBusy(async () => {
          await loadUsers();
          renderApp();
        }, { errorPrefix: "Failed to clear user filters" });
      });
      document.getElementById("users-block-btn").addEventListener("click", () => {
        showModal({
          eyebrow: "Moderation",
          title: `Block ${state.selectedUserIds.size} user${state.selectedUserIds.size === 1 ? "" : "s"}`,
          body: "Blocking stops inbound bot interactions, stops outbound bot sends, and removes the user from matching.",
          promptLabel: "Optional block reason",
          promptPlaceholder: "Add context for future admins…",
          multiline: true,
          confirmLabel: "Block users",
          confirmTone: "danger",
          onConfirm: async (reason) => {
            await withBusy(async () => {
              await api("/admin/api/users/block", {
                method: "POST",
                body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), reason: reason || null }),
              });
              await loadUsers();
              if (state.currentUserDetail && state.selectedUserIds.has(state.currentUserDetail.user.id)) {
                await loadUserDetail(state.currentUserDetail.user.id);
              }
              renderApp();
            }, { successText: "Selected users blocked.", errorPrefix: "Block failed" });
          },
        });
      });
      document.getElementById("users-unblock-btn").addEventListener("click", () => {
        showModal({
          eyebrow: "Moderation",
          title: `Unblock ${state.selectedUserIds.size} user${state.selectedUserIds.size === 1 ? "" : "s"}`,
          body: "This restores normal bot interactions and matching eligibility.",
          confirmLabel: "Unblock users",
          onConfirm: async () => {
            await withBusy(async () => {
              await api("/admin/api/users/unblock", {
                method: "POST",
                body: JSON.stringify({ userIds: Array.from(state.selectedUserIds) }),
              });
              await loadUsers();
              if (state.currentUserDetail && state.selectedUserIds.has(state.currentUserDetail.user.id)) {
                await loadUserDetail(state.currentUserDetail.user.id);
              }
              renderApp();
            }, { successText: "Selected users unblocked.", errorPrefix: "Unblock failed" });
          },
        });
      });
      document.getElementById("users-message-btn").addEventListener("click", () => {
        setRoute("messages");
      });
      document.querySelectorAll(".user-view-btn").forEach((button) => {
        button.addEventListener("click", () => openUserDetail(button.getAttribute("data-user-id")));
      });
      document.querySelectorAll(".user-delete-btn").forEach((button) => {
        button.addEventListener("click", () => {
          const userId = button.getAttribute("data-user-id");
          const label = button.getAttribute("data-user-label");
          showModal({
            eyebrow: "Hard delete",
            title: `Delete ${label}?`,
            body: "This permanently removes the user and all related history from the database. This action cannot be undone.",
            promptLabel: 'Type DELETE to confirm',
            promptPlaceholder: "DELETE",
            requireTypedValue: "DELETE",
            helperText: "Use this only when you intentionally want irreversible deletion.",
            confirmLabel: "Delete user",
            confirmTone: "danger",
            onConfirm: async () => {
              await withBusy(async () => {
                await api(`/admin/api/users/${userId}`, { method: "DELETE" });
                state.selectedUserIds.delete(userId);
                if (state.currentUserDetail && state.currentUserDetail.user.id === userId) {
                  state.currentUserDetail = null;
                }
                await Promise.all([loadUsers(), loadAnalytics(), loadMatches()]);
                syncUrlState();
                renderApp();
              }, { successText: "User hard-deleted.", errorPrefix: "Delete failed" });
            },
          });
        });
      });
      document.querySelectorAll(".open-match-from-user").forEach((button) => {
        button.addEventListener("click", () => setRoute(`/matches/${button.getAttribute("data-match-id")}`));
      });
      const closeUserDetailBtn = document.getElementById("close-user-detail-btn");
      if (closeUserDetailBtn) closeUserDetailBtn.addEventListener("click", clearUserDetail);
    }

    if (route.name === "matches" || route.name === "match-detail") {
      const applyBtn = document.getElementById("matches-apply-filters");
      if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
          state.matchesFilters.status = document.getElementById("matches-status-filter").value;
          state.matchesFilters.fit_band = document.getElementById("matches-fit-filter").value;
          state.matchesFilters.search = document.getElementById("matches-search-filter").value.trim();
          syncUrlState();
          await withBusy(async () => {
            await loadMatches();
            if (route.name === "match-detail" && route.id) {
              await loadMatchDetail(route.id);
            }
            renderApp();
          }, { errorPrefix: "Failed to load matches" });
        });
      }
      const clearBtn = document.getElementById("matches-clear-filters");
      if (clearBtn) {
        clearBtn.addEventListener("click", async () => {
          state.matchesFilters = { status: "", fit_band: "", search: "" };
          syncUrlState();
          await withBusy(async () => {
            await loadMatches();
            if (route.name === "match-detail" && route.id) {
              await loadMatchDetail(route.id);
            }
            renderApp();
          }, { errorPrefix: "Failed to clear match filters" });
        });
      }
      document.querySelectorAll(".match-open-btn").forEach((button) => {
        button.addEventListener("click", () => {
          setRoute(`/matches/${button.getAttribute("data-match-id")}`);
        });
      });
      const closeMatchDetailBtn = document.getElementById("close-match-detail-btn");
      if (closeMatchDetailBtn) {
        closeMatchDetailBtn.addEventListener("click", () => setRoute("matches"));
      }
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
          showToast({ tone: "warn", title: "No recipients", body: "Select at least one user first." });
          return;
        }
        const text = document.getElementById("message-text").value || "";
        state.messageDraft = text;
        await withBusy(async () => {
          state.messagePreview = await api("/admin/api/messages/preview", {
            method: "POST",
            body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), text }),
          });
          state.messagePreviewContextKey = currentMessagePreviewKey(text);
          renderApp();
        }, { successText: "Message preview updated.", errorPrefix: "Preview failed" });
      });
      document.getElementById("message-send-btn").addEventListener("click", async () => {
        if (!state.selectedUserIds.size) {
          showToast({ tone: "warn", title: "No recipients", body: "Select at least one user first." });
          return;
        }
        const text = document.getElementById("message-text").value || "";
        state.messageDraft = text;
        const previewKey = currentMessagePreviewKey(text);
        if (!state.messagePreview || state.messagePreviewContextKey !== previewKey) {
          await withBusy(async () => {
            state.messagePreview = await api("/admin/api/messages/preview", {
              method: "POST",
              body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), text }),
            });
            state.messagePreviewContextKey = previewKey;
          }, { errorPrefix: "Preview failed" });
        }
        const preview = state.messagePreview;
        showModal({
          eyebrow: "Bot messaging",
          title: "Send this bot message?",
          body: `Selected: ${preview.counts.selected || 0}. Deliverable: ${preview.counts.deliverable || 0}. Skipped: ${preview.counts.skipped || 0}.`,
          html: `<div class="preview-card"><p class="break-words">${escapeHtml(compactText(text, 280))}</p></div>`,
          confirmLabel: "Queue message",
          onConfirm: async () => {
            await withBusy(async () => {
              await api("/admin/api/messages/send", {
                method: "POST",
                body: JSON.stringify({ userIds: Array.from(state.selectedUserIds), text }),
              });
              state.messagePreview = null;
              state.messagePreviewContextKey = null;
              state.messageDraft = "";
              await loadUsers();
              renderApp();
            }, { successText: "Messages queued through the real bot pipeline.", errorPrefix: "Send failed" });
          },
        });
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

  window.addEventListener("popstate", () => {
    applyUrlState();
    if (!state.session) {
      renderLogin();
      return;
    }
    renderApp();
  });

  bootstrapSession();
})();
