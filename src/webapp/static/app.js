(function () {
  const state = {
    sessionToken: null,
    session: null,
    apiCache: new Map(),
    backButtonHandlerBound: false,
    theme: "terminal",
  };
  const TERMINAL_THEME = "terminal";

  const appEl = document.getElementById("app");
  const appShellEl = document.querySelector(".app-shell");
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const handleTelegramBack = () => {
    if (getCurrentRoute() === "home") {
      if (tg && typeof tg.close === "function") {
        tg.close();
      }
      return;
    }
    window.history.back();
  };

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function truncateText(value, maxLength) {
    const text = String(value || "");
    if (!text || text.length <= maxLength) return text;
    return `${text.slice(0, maxLength - 1).trimEnd()}…`;
  }

  function updateThemeColorMeta(color) {
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    if (themeMeta) {
      themeMeta.setAttribute("content", color);
    }
  }

  function applyViewportMetrics() {
    const fallbackHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    const stableHeight = tg && Number.isFinite(Number(tg.viewportStableHeight))
      ? Number(tg.viewportStableHeight)
      : fallbackHeight;
    document.documentElement.style.setProperty("--app-height", `${Math.round(stableHeight)}px`);
  }

  function applyTelegramChrome() {
    const backgroundColor = "#141415";
    const surfaceColor = "#1c1c1e";
    updateThemeColorMeta(backgroundColor);
    if (!tg) return;
    try {
      if (typeof tg.setHeaderColor === "function") {
        tg.setHeaderColor(backgroundColor);
      }
    } catch (_) {}
    try {
      if (typeof tg.setBackgroundColor === "function") {
        tg.setBackgroundColor(backgroundColor);
      }
    } catch (_) {}
    try {
      if (
        typeof tg.setBottomBarColor === "function" &&
        typeof tg.isVersionAtLeast === "function" &&
        tg.isVersionAtLeast("7.10")
      ) {
        tg.setBottomBarColor(surfaceColor);
      }
    } catch (_) {}
  }

  function bindTelegramRuntime() {
    applyViewportMetrics();
    applyTelegramChrome();
    window.addEventListener("resize", applyViewportMetrics);
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", applyViewportMetrics);
    }
    if (!tg || typeof tg.onEvent !== "function") return;
    tg.onEvent("themeChanged", applyTelegramChrome);
    tg.onEvent("viewportChanged", applyViewportMetrics);
    tg.onEvent("safeAreaChanged", applyViewportMetrics);
    tg.onEvent("contentSafeAreaChanged", applyViewportMetrics);
  }

  function normalizeTheme(value) {
    return TERMINAL_THEME;
  }

  function syncThemeInUrl() {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.delete("theme");
    const nextUrl = `${currentUrl.pathname}${currentUrl.search}`;
    window.history.replaceState(window.history.state || { route: getCurrentRoute() }, "", nextUrl);
  }

  function withCurrentTheme(url) {
    const nextUrl = new URL(url, window.location.origin);
    nextUrl.searchParams.delete("theme");
    return nextUrl.toString();
  }

  function setTheme(theme, options) {
    state.theme = normalizeTheme(theme);
    document.documentElement.setAttribute("data-theme", state.theme);
    syncThemeInUrl();
    applyTelegramChrome();
    if (options && options.rerender && state.session) {
      renderRoute();
    }
  }

  function initializeTheme() {
    setTheme(TERMINAL_THEME, { rerender: false });
  }

  function tapFeedback() {
    try {
      if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.impactOccurred === "function") {
        tg.HapticFeedback.impactOccurred("light");
      }
    } catch (_) {}
  }

  function badgeTone(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("approved") || text.includes("completed") || text.includes("accepted")) return "good";
    if (text.includes("reject") || text.includes("declined") || text.includes("expired")) return "bad";
    if (text.includes("queued") || text.includes("review") || text.includes("waiting")) return "warn";
    return "accent";
  }

  function formatRelativeTime(isoValue) {
    if (!isoValue) return "Unknown";
    const date = new Date(isoValue);
    if (Number.isNaN(date.getTime())) return isoValue;
    const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
    const absSeconds = Math.abs(diffSeconds);
    const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
    if (absSeconds < 60) return rtf.format(Math.round(diffSeconds), "second");
    if (absSeconds < 3600) return rtf.format(Math.round(diffSeconds / 60), "minute");
    if (absSeconds < 86400) return rtf.format(Math.round(diffSeconds / 3600), "hour");
    return rtf.format(Math.round(diffSeconds / 86400), "day");
  }

  function renderBlocked(title, body) {
    appEl.innerHTML = `
      <section class="state-card">
        <p class="eyebrow">Access</p>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(body)}</p>
      </section>
    `;
  }

  function renderError(title, body) {
    appEl.innerHTML = `
      <section class="state-card">
        <p class="eyebrow">Error</p>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(body)}</p>
      </section>
    `;
  }

  async function api(path) {
    if (state.apiCache.has(path)) {
      return state.apiCache.get(path);
    }
    const request = fetch(path, {
      headers: state.sessionToken
        ? { Authorization: `Bearer ${state.sessionToken}` }
        : {},
    }).then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Request failed.");
      }
      return data;
    });
    state.apiCache.set(path, request);
    try {
      return await request;
    } catch (error) {
      state.apiCache.delete(path);
      throw error;
    }
  }

  function listChips(values) {
    if (!values || !values.length) {
      return `<div class="empty-state">No data yet.</div>`;
    }
    return `<div class="list-chips">${values
      .map((value) => `<span class="chip">${escapeHtml(value)}</span>`)
      .join("")}</div>`;
  }

  function includesAny(value, fragments) {
    const text = String(value || "").toLowerCase();
    return fragments.some((fragment) => text.includes(fragment));
  }

  function sumBy(items, key) {
    return (items || []).reduce((total, item) => {
      const value = Number(item && item[key]);
      return total + (Number.isFinite(value) ? value : 0);
    }, 0);
  }

  function formatScore(value) {
    if (value === null || value === undefined || value === "") return "N/A";
    return String(value);
  }

  function isTerminalTheme() {
    return state.theme === TERMINAL_THEME;
  }

  function terminalToken(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "value";
  }

  function renderStatsStrip(items) {
    const visibleItems = (items || []).filter((item) => item && item.value !== null && item.value !== undefined && item.value !== "");
    if (!visibleItems.length) return "";
    return `
      <section class="stats-strip">
        ${visibleItems.map((item) => {
          const rawValue = String(item.value);
          const isLongValue = rawValue.length > 18;
          const displayValue = isLongValue ? truncateText(rawValue, 28) : rawValue;
          return `
          <article class="stat-card ${isTerminalTheme() ? "terminal-stat-card" : ""}">
            <span class="stat-value ${isLongValue ? "stat-value-long" : ""}" title="${escapeHtml(rawValue)}">${escapeHtml(displayValue)}</span>
            <span class="stat-label">${escapeHtml(isTerminalTheme() ? terminalToken(item.label) : item.label)}</span>
          </article>
        `;
        }).join("")}
      </section>
    `;
  }

  function renderCardMetrics(metrics) {
    const visibleMetrics = (metrics || []).filter((metric) => metric && metric.value !== null && metric.value !== undefined && metric.value !== "");
    if (!visibleMetrics.length) return "";
    if (isTerminalTheme()) {
      return `
        <div class="terminal-metrics">
          ${visibleMetrics.map((metric) => `
            <div class="terminal-metric">
              <span class="terminal-metric-key">${escapeHtml(terminalToken(metric.label))}</span>
              <span class="terminal-metric-value">${escapeHtml(metric.value)}</span>
            </div>
          `).join("")}
        </div>
      `;
    }
    return `
      <div class="card-metrics">
        ${visibleMetrics.map((metric) => `
          <div class="metric">
            <span class="metric-label">${escapeHtml(metric.label)}</span>
            <span class="metric-value">${escapeHtml(metric.value)}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderCardNote(value, extraClass) {
    if (!value) return "";
    const classes = ["card-note"];
    if (isTerminalTheme()) classes.push("card-note-terminal");
    if (extraClass) classes.push(extraClass);
    return `<p class="${classes.join(" ")}">${escapeHtml(value)}</p>`;
  }

  function renderInlineMetrics(metrics, extraClass) {
    const visibleMetrics = (metrics || []).filter((metric) => metric && metric.value !== null && metric.value !== undefined && metric.value !== "");
    const className = extraClass ? `inline-metrics ${extraClass}` : "inline-metrics";
    if (!visibleMetrics.length) return "";
    return `
      <div class="${className}">
        ${visibleMetrics.map((metric) => `
          <div class="inline-metric">
            <span class="inline-metric-label">${escapeHtml(isTerminalTheme() ? terminalToken(metric.label) : metric.label)}</span>
            <span class="inline-metric-value">${escapeHtml(metric.value)}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderActionPanel(challenge) {
    if (!challenge || !challenge.eligible || !challenge.launchUrl) return "";
    return `
      <section class="detail-panel action-panel ${isTerminalTheme() ? "action-panel-terminal" : ""}">
        <div class="action-panel-copy">
          <p class="eyebrow">${isTerminalTheme() ? "idle_mode" : "While you wait"}</p>
          <h3 class="section-title">${isTerminalTheme() ? "run helly.cv_challenge" : "Play Helly CV Challenge"}</h3>
          <p class="card-note">${escapeHtml(challenge.body || "Tap only the skills that really appear in your CV.")}</p>
        </div>
        ${isTerminalTheme() ? `
          <div class="terminal-command-row">
            <span class="terminal-prompt">&gt;</span>
            <span class="terminal-command">launch /cv-challenge --profile current</span>
          </div>
        ` : ""}
        <button class="action-button" type="button" data-open-url="${escapeHtml(withCurrentTheme(challenge.launchUrl))}">${isTerminalTheme() ? "Run challenge" : "Play challenge"}</button>
      </section>
    `;
  }

  function renderDetailSection(title, rows) {
    return `
      <section class="detail-panel ${isTerminalTheme() ? "detail-panel-terminal" : ""}">
        ${isTerminalTheme() ? `
          <div class="terminal-section-head">
            <span class="terminal-prompt">$</span>
            <span class="terminal-section-title">${escapeHtml(terminalToken(title))}</span>
          </div>
        ` : ""}
        <h3 class="section-title">${escapeHtml(title)}</h3>
        <dl class="detail-grid ${isTerminalTheme() ? "detail-grid-terminal" : ""}">
          ${rows
            .filter((row) => row.value !== null && row.value !== undefined && row.value !== "")
            .map((row) => `
              <div class="${row.full ? "span-full" : ""}">
                <dt>${escapeHtml(isTerminalTheme() ? terminalToken(row.label) : row.label)}</dt>
                <dd>${row.raw ? row.value : escapeHtml(row.value)}</dd>
              </div>
            `)
            .join("")}
        </dl>
      </section>
    `;
  }

  function updateBackButton() {
    if (!tg || !tg.BackButton) return;
    if (getCurrentRoute() === "home") {
      if (state.backButtonHandlerBound && typeof tg.BackButton.offClick === "function") {
        tg.BackButton.offClick(handleTelegramBack);
        state.backButtonHandlerBound = false;
      }
      tg.BackButton.hide();
      return;
    }
    if (!state.backButtonHandlerBound && typeof tg.BackButton.onClick === "function") {
      tg.BackButton.onClick(handleTelegramBack);
      state.backButtonHandlerBound = true;
    }
    tg.BackButton.show();
  }

  function updateTopbar(route) {
    if (!appShellEl) return;
    const compact = sanitizeRoute(route) !== "home";
    appShellEl.classList.toggle("topbar-compact", compact);
  }

  function sanitizeRoute(route) {
    return route && route !== "#" ? String(route).replace(/^#/, "") : "home";
  }

  function getCurrentRoute() {
    return sanitizeRoute((window.history.state && window.history.state.route) || "home");
  }

  function applyRoute(route, options) {
    const nextRoute = sanitizeRoute(route);
    const method = options && options.replace ? "replaceState" : "pushState";
    window.history[method]({ route: nextRoute }, "", window.location.pathname + window.location.search);
    renderRoute();
  }

  function pushRoute(route) {
    applyRoute(route, { replace: false });
  }

  async function renderHome() {
    const role = state.session.role;
    if (role === "unknown") {
      renderBlocked(
        "Dashboard is locked",
        "Continue with Helly in Telegram first. Once your role is identified, this dashboard will unlock."
      );
      return;
    }

    if (role === "candidate") {
      const payload = await api("/webapp/api/candidate/opportunities");
      const items = payload.items || [];
      const activeInterviewCount = items.filter((item) =>
        includesAny(item.interviewStateLabel, ["queued", "active", "accepted", "started", "progress", "invited"])
      ).length;
      const completedInterviewCount = items.filter((item) =>
        includesAny(item.interviewStateLabel, ["completed"])
      ).length;
      appEl.innerHTML = `
        <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
          <p class="eyebrow">${isTerminalTheme() ? "candidate_session" : "Candidate view"}</p>
          <h2>My Opportunities</h2>
          <p>Your current matches, interview state and saved profile context.</p>
        </section>
        ${renderStatsStrip([
          { label: "Opportunities", value: String(items.length) },
          { label: "In interview", value: String(activeInterviewCount) },
          { label: "Completed", value: String(completedInterviewCount) }
        ])}
        ${renderActionPanel(payload.cvChallenge)}
        <section class="detail-panel">
          <h3 class="section-title">Profile Snapshot</h3>
          <dl class="detail-grid">
            <div><dt>Location</dt><dd>${escapeHtml(payload.profile.location || "Not set")}</dd></div>
            <div><dt>Work format</dt><dd>${escapeHtml(payload.profile.workFormat || "Not set")}</dd></div>
            <div><dt>Salary</dt><dd>${escapeHtml(payload.profile.salaryExpectation || "Not set")}</dd></div>
            <div class="span-full"><dt>Summary</dt><dd>${escapeHtml(truncateText((payload.profile.summary || {}).approvalSummaryText || "No summary yet.", 220))}</dd></div>
          </dl>
        </section>
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card card-compact ${isTerminalTheme() ? "card-terminal" : ""}" data-route="candidate-match:${item.id}">
              <div class="card-head card-head-compact">
                <div class="card-title-wrap">
                  <h3>${escapeHtml(item.roleTitle || "Untitled role")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.stageLabel)}">${escapeHtml(item.stageLabel || "Unknown")}</span>
              </div>
              ${renderInlineMetrics([
                { label: "Budget", value: item.budget || "Not set" },
                { label: "Interview", value: item.interviewStateLabel || "Not started" },
                { label: "Updated", value: formatRelativeTime(item.updatedAt) }
              ])}
            </article>
          `).join("") : `<div class="empty-state">No opportunities yet. Once Helly creates matches for you, they will appear here.</div>`}
        </section>
        <p class="footer-note">Read-only mode. Apply, skip and interview actions still happen in the bot chat.</p>
      `;
      bindCards();
      bindActionButtons();
      return;
    }

    if (role === "hiring_manager") {
      const payload = await api("/webapp/api/hiring-manager/vacancies");
      const items = payload.items || [];
      const totalCandidateCount = sumBy(items, "candidateCount");
      const totalActivePipelineCount = sumBy(items, "activePipelineCount");
      const totalCompletedInterviewCount = sumBy(items, "completedInterviewCount");
      appEl.innerHTML = `
        <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
          <p class="eyebrow">${isTerminalTheme() ? "manager_session" : "Manager view"}</p>
          <h2>My Vacancies</h2>
          <p>${isTerminalTheme() ? "Inspect live vacancy queues, candidate pipeline depth and interview throughput." : "One clean view of your live candidate pipeline and interview progress."}</p>
        </section>
        ${renderStatsStrip([
          { label: "Vacancies", value: String(items.length) },
          { label: "Candidates", value: String(totalCandidateCount) },
          { label: "In pipeline", value: String(totalActivePipelineCount) },
          { label: "Interviewed", value: String(totalCompletedInterviewCount) }
        ])}
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card card-compact ${isTerminalTheme() ? "card-terminal" : ""}" data-route="manager-vacancy:${item.id}">
              <div class="card-head card-head-compact">
                <div class="card-title-wrap">
                  <h3>${escapeHtml(item.roleTitle || "Untitled vacancy")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.state)}">${escapeHtml(item.state || "Unknown")}</span>
              </div>
              ${renderCardMetrics([
                { label: "Candidates", value: String(item.candidateCount) },
                { label: "In pipeline", value: String(item.activePipelineCount) },
                { label: "Interviewed", value: String(item.completedInterviewCount) }
              ])}
              ${renderCardNote(`Updated ${formatRelativeTime(item.updatedAt)}`)}
            </article>
          `).join("") : `<div class="empty-state">No vacancies yet. Open a vacancy in the Telegram bot and it will show up here.</div>`}
        </section>
      `;
      bindCards();
      return;
    }

    if (role === "admin") {
      const payload = await api("/webapp/api/admin/vacancies");
      const items = payload.items || [];
      const totalCandidateCount = sumBy(items, "candidateCount");
      const totalCompletedInterviewCount = sumBy(items, "completedInterviewCount");
      appEl.innerHTML = `
        <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
          <p class="eyebrow">${isTerminalTheme() ? "admin_session" : "Admin view"}</p>
          <h2>All Vacancies</h2>
          <p>${isTerminalTheme() ? "Production-wide read-only shell across all live vacancy records." : "Read-only visibility across the full Helly production pipeline."}</p>
        </section>
        ${renderStatsStrip([
          { label: "Vacancies", value: String(items.length) },
          { label: "Candidates", value: String(totalCandidateCount) },
          { label: "Interviewed", value: String(totalCompletedInterviewCount) }
        ])}
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card card-compact ${isTerminalTheme() ? "card-terminal" : ""}" data-route="admin-vacancy:${item.id}">
              <div class="card-head card-head-compact">
                <div class="card-title-wrap">
                  <h3>${escapeHtml(item.roleTitle || "Untitled vacancy")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.state)}">${escapeHtml(item.state || "Unknown")}</span>
              </div>
              ${renderCardMetrics([
                { label: "Manager", value: item.managerName || "Unknown" },
                { label: "Candidates", value: String(item.candidateCount) },
                { label: "Interviewed", value: String(item.completedInterviewCount) }
              ])}
              ${renderCardNote(`Updated ${formatRelativeTime(item.updatedAt)}`)}
            </article>
          `).join("") : `<div class="empty-state">No vacancies found.</div>`}
        </section>
      `;
      bindCards();
    }
  }

  async function renderCandidateMatch(matchId) {
    const payload = await api(`/webapp/api/candidate/opportunities/${matchId}`);
    appEl.innerHTML = `
      <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
        <p class="eyebrow">${isTerminalTheme() ? "match_record" : "Opportunity detail"}</p>
        <h2>${escapeHtml(payload.vacancy.roleTitle || "Opportunity")}</h2>
        <p>Current opportunity, profile and interview context.</p>
      </section>
      ${renderStatsStrip([
        { label: "Stage", value: payload.match.statusLabel || "Unknown" },
        { label: "Interview", value: payload.interview.stateLabel || "Not started" },
        { label: "Score", value: formatScore(payload.evaluation.finalScore) }
      ])}
      ${renderDetailSection("Match", [
        { label: "Updated", value: formatRelativeTime(payload.match.updatedAt) },
        { label: "Manager decision", value: payload.match.managerDecisionAt ? formatRelativeTime(payload.match.managerDecisionAt) : "Pending" }
      ])}
      ${renderDetailSection("Vacancy", [
        { label: "Budget", value: payload.vacancy.budget || "Not specified" },
        { label: "Work format", value: payload.vacancy.workFormat || "Not specified" },
        { label: "Allowed countries", value: (payload.vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Tech stack", value: (payload.vacancy.primaryTechStack || []).join(", ") || "Not specified", full: true },
        { label: "Project", value: payload.vacancy.projectDescription || "Not specified", full: true }
      ])}
      ${renderDetailSection("Your profile snapshot", [
        { label: "Name", value: payload.candidate.name || "Candidate" },
        { label: "Location", value: payload.candidate.location || "Not specified" },
        { label: "Work format", value: payload.candidate.workFormat || "Not specified" },
        { label: "Salary", value: payload.candidate.salaryExpectation || "Not specified" },
        { label: "Summary", value: (payload.candidate.summary || {}).approvalSummaryText || "No saved summary.", full: true }
      ])}
      ${renderDetailSection("Interview outcome", [
        { label: "Summary", value: payload.evaluation.interviewSummary || "No interview summary yet.", full: true },
        { label: "Recommendation", value: payload.evaluation.recommendation || "Not available" },
        { label: "Strengths", value: listChips(payload.evaluation.strengths || []), raw: true, full: true },
        { label: "Risks", value: listChips(payload.evaluation.risks || []), raw: true, full: true }
      ])}
    `;
  }

  async function renderVacancy(rolePrefix, vacancyId) {
    const detailPath = rolePrefix === "manager"
      ? `/webapp/api/hiring-manager/vacancies/${vacancyId}`
      : `/webapp/api/admin/vacancies/${vacancyId}`;
    const matchesPath = rolePrefix === "manager"
      ? `/webapp/api/hiring-manager/vacancies/${vacancyId}/matches`
      : `/webapp/api/admin/vacancies/${vacancyId}/matches`;
    const [detail, matchesPayload] = await Promise.all([api(detailPath), api(matchesPath)]);
    const vacancy = detail.vacancy;
    const stats = detail.stats;
    const items = matchesPayload.items || [];
    appEl.innerHTML = `
      <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
        <p class="eyebrow">${escapeHtml(isTerminalTheme() ? `${rolePrefix}_vacancy_record` : `${rolePrefix} vacancy`)}</p>
        <h2>${escapeHtml(vacancy.roleTitle || "Vacancy")}</h2>
        <p>${rolePrefix === "manager" ? "Candidate pipeline and saved vacancy context." : "Cross-role vacancy overview and candidate pipeline."}</p>
      </section>
      ${renderStatsStrip([
        { label: "State", value: vacancy.state || "Unknown" },
        { label: "Candidates", value: String(stats.candidateCount) },
        { label: "In pipeline", value: String(stats.activePipelineCount) },
        { label: "Interviewed", value: String(stats.completedInterviewCount) }
      ])}
      ${renderDetailSection("Vacancy snapshot", [
        { label: "Budget", value: vacancy.budget || "Not specified" },
        { label: "Work format", value: vacancy.workFormat || "Not specified" },
        { label: "Allowed countries", value: (vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Tech stack", value: (vacancy.primaryTechStack || []).join(", ") || "Not specified", full: true },
        { label: "Project", value: vacancy.projectDescription || "Not specified", full: true },
        { label: "Summary", value: (vacancy.summary || {}).approvalSummaryText || "No stored summary.", full: true }
      ])}
      <section class="detail-panel ${isTerminalTheme() ? "detail-panel-terminal" : ""}">
        ${isTerminalTheme() ? `
          <div class="terminal-section-head">
            <span class="terminal-prompt">$</span>
            <span class="terminal-section-title">candidate_pipeline</span>
          </div>
        ` : ""}
        <h3 class="section-title">Candidate pipeline</h3>
        <div class="list">
          ${items.length ? items.map((item) => `
            <article class="card card-compact ${isTerminalTheme() ? "card-terminal" : ""}" data-route="${rolePrefix}-match:${item.id}">
              <div class="card-head card-head-compact">
                <div class="card-title-wrap">
                  <h3>${escapeHtml(item.candidateName || "Candidate")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.stageLabel)}">${escapeHtml(item.stageLabel || "Unknown")}</span>
              </div>
              ${renderInlineMetrics([
                { label: "Location", value: item.location || "Not set" },
                { label: "Interview", value: item.interviewStateLabel || "Not started" },
                { label: "Salary", value: item.salaryExpectation || "Not set" }
              ], "inline-metrics-compact")}
              ${renderCardNote(truncateText(((item.summary || {}).approvalSummaryText) || "No summary yet.", 96), "card-note-compact")}
            </article>
          `).join("") : `<div class="empty-state">No candidates are attached to this vacancy yet.</div>`}
        </div>
      </section>
    `;
    bindCards();
  }

  async function renderManagerMatch(rolePrefix, matchId) {
    const path = rolePrefix === "manager"
      ? `/webapp/api/hiring-manager/matches/${matchId}`
      : `/webapp/api/admin/matches/${matchId}`;
    const payload = await api(path);
    appEl.innerHTML = `
      <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
        <p class="eyebrow">${isTerminalTheme() ? "candidate_record" : "Match detail"}</p>
        <h2>${escapeHtml(payload.candidate.name || "Candidate")}</h2>
        <p>${escapeHtml(payload.vacancy.roleTitle || "Vacancy")} • review snapshot</p>
      </section>
      ${renderStatsStrip([
        { label: "Stage", value: payload.match.statusLabel || "Unknown" },
        { label: "Interview", value: payload.interview.stateLabel || "Not started" },
        { label: "Recommendation", value: payload.evaluation.recommendation || "N/A" },
        { label: "Score", value: formatScore(payload.evaluation.finalScore) }
      ])}
      ${renderDetailSection("Candidate", [
        { label: "Location", value: payload.candidate.location || "Not specified" },
        { label: "Work format", value: payload.candidate.workFormat || "Not specified" },
        { label: "Salary", value: payload.candidate.salaryExpectation || "Not specified" },
        { label: "Summary", value: (payload.candidate.summary || {}).approvalSummaryText || "No saved summary.", full: true },
        { label: "Skills", value: listChips((payload.candidate.summary || {}).skills || []), raw: true, full: true }
      ])}
      ${renderDetailSection("Interview", [
        { label: "Summary", value: payload.evaluation.interviewSummary || "No interview summary yet.", full: true },
        { label: "Strengths", value: listChips(payload.evaluation.strengths || []), raw: true, full: true },
        { label: "Risks", value: listChips(payload.evaluation.risks || []), raw: true, full: true }
      ])}
      ${renderDetailSection("Vacancy context", [
        { label: "Role", value: payload.vacancy.roleTitle || "Not specified" },
        { label: "Budget", value: payload.vacancy.budget || "Not specified" },
        { label: "Work format", value: payload.vacancy.workFormat || "Not specified" },
        { label: "Tech stack", value: (payload.vacancy.primaryTechStack || []).join(", ") || "Not specified", full: true },
        { label: "Project", value: payload.vacancy.projectDescription || "Not specified", full: true }
      ])}
    `;
  }

  function bindCards() {
    Array.from(document.querySelectorAll("[data-route]")).forEach((node) => {
      const route = node.getAttribute("data-route");
      node.setAttribute("tabindex", "0");
      node.setAttribute("role", "button");
      node.addEventListener("click", () => {
        tapFeedback();
        pushRoute(route);
      });
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          tapFeedback();
          pushRoute(route);
        }
      });
    });
  }

  function bindActionButtons() {
    Array.from(document.querySelectorAll("[data-open-url]")).forEach((node) => {
      const targetUrl = node.getAttribute("data-open-url");
      node.addEventListener("click", () => {
        tapFeedback();
        window.location.assign(targetUrl);
      });
    });
  }

  async function renderRoute() {
    const currentRoute = getCurrentRoute();
    updateBackButton();
    updateTopbar(currentRoute);
    if (!state.session) return;
    try {
      if (currentRoute === "home") {
        await renderHome();
        return;
      }

      const parts = currentRoute.split(":");
      if (parts.length !== 2) {
        await renderHome();
        return;
      }
      const route = parts[0];
      const id = parts[1];
      if (route === "candidate-match") return await renderCandidateMatch(id);
      if (route === "manager-vacancy") return await renderVacancy("manager", id);
      if (route === "manager-match") return await renderManagerMatch("manager", id);
      if (route === "admin-vacancy") return await renderVacancy("admin", id);
      if (route === "admin-match") return await renderManagerMatch("admin", id);
      await renderHome();
    } catch (error) {
      renderError("Dashboard request failed", error.message || "Unable to load this screen.");
    }
  }

  async function boot() {
    try {
      initializeTheme();
      bindTelegramRuntime();
      if (tg) {
        if (tg.BackButton && typeof tg.BackButton.hide === "function") {
          tg.BackButton.hide();
        }
        if (typeof tg.ready === "function") {
          tg.ready();
        }
        if (typeof tg.expand === "function") {
          tg.expand();
        }
        if (typeof tg.enableVerticalSwipes === "function") {
          tg.enableVerticalSwipes();
        }
      }

      const initDataFromQuery = new URLSearchParams(window.location.search).get("initData");
      const initData = (tg && tg.initData) || initDataFromQuery;
      if (!initData) {
        renderBlocked(
          "Open this inside Helly",
          "This WebApp needs Telegram Mini App auth. Open it from the Helly bot button inside Telegram."
        );
        return;
      }

      const authResponse = await fetch("/webapp/api/auth/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData }),
      });
      const authPayload = await authResponse.json().catch(() => ({}));
      if (!authResponse.ok) {
        throw new Error(authPayload.detail || "Telegram authentication failed.");
      }
      state.sessionToken = authPayload.sessionToken;

      const sessionPayload = await api("/webapp/api/session");
      state.session = sessionPayload.session;
      const initialRoute = sanitizeRoute(window.location.hash || "home");
      window.history.replaceState({ route: initialRoute }, "", window.location.pathname + window.location.search);
      await renderRoute();
      window.addEventListener("popstate", renderRoute);
    } catch (error) {
      renderError("Unable to open Helly Dashboard", error.message || "Unknown error.");
    }
  }

  boot();
})();
