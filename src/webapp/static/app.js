(function () {
  const state = {
    sessionToken: null,
    session: null,
    backButtonHandlerBound: false,
    theme: "terminal",
    disclosureCounter: 0,
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

  function firstNonEmpty() {
    for (let index = 0; index < arguments.length; index += 1) {
      const value = arguments[index];
      if (value === null || value === undefined) continue;
      if (String(value).trim()) return value;
    }
    return "";
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
    if (text.includes("approved") || text.includes("completed") || text.includes("accepted") || text.includes("connected")) return "good";
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

  function formatAbsoluteTime(isoValue) {
    if (!isoValue) return "Unknown";
    const date = new Date(isoValue);
    if (Number.isNaN(date.getTime())) return isoValue;
    return new Intl.DateTimeFormat("en", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function formatEventTime(isoValue, fallback) {
    if (!isoValue) return fallback !== undefined ? fallback : "Pending";
    const relative = formatRelativeTime(isoValue);
    const absolute = formatAbsoluteTime(isoValue);
    return relative === absolute ? absolute : `${relative} · ${absolute}`;
  }

  function renderRoleCheck(note) {
    appEl.innerHTML = `
      <section class="state-card loading-card">
        <p class="eyebrow">Loading</p>
        <h2>Checking your role</h2>
        <p>${escapeHtml(note)}</p>
      </section>
    `;
  }

  function renderLoadingState(title, body, eyebrow) {
    appEl.innerHTML = `
      <section class="state-card loading-card">
        <p class="eyebrow">${escapeHtml(eyebrow || "Loading")}</p>
        <h2>${escapeHtml(title)}</h2>
        <p>${escapeHtml(body)}</p>
      </section>
    `;
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
    const response = await fetch(path, {
      headers: state.sessionToken
        ? { Authorization: `Bearer ${state.sessionToken}` }
        : {},
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || "Request failed.");
    }
    return data;
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
          <h3 class="section-title">${isTerminalTheme() ? "CV Challenge" : "Play Helly CV Challenge"}</h3>
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
    const visibleRows = (rows || []).filter((row) => row.value !== null && row.value !== undefined && row.value !== "");
    if (!visibleRows.length) return "";
    return `
      <section class="detail-panel ${isTerminalTheme() ? "detail-panel-terminal" : ""}">
        ${isTerminalTheme() ? `
          <div class="terminal-section-head">
            <span class="terminal-prompt">$</span>
            <span class="terminal-section-title">${escapeHtml(terminalToken(title))}</span>
          </div>
        ` : ""}
        ${isTerminalTheme() ? "" : `<h3 class="section-title">${escapeHtml(title)}</h3>`}
        <dl class="detail-grid ${isTerminalTheme() ? "detail-grid-terminal" : ""}">
          ${visibleRows
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

  function renderPanel(title, content) {
    if (!content) return "";
    return `
      <section class="detail-panel ${isTerminalTheme() ? "detail-panel-terminal" : ""}">
        ${isTerminalTheme() ? `
          <div class="terminal-section-head">
            <span class="terminal-prompt">$</span>
            <span class="terminal-section-title">${escapeHtml(terminalToken(title))}</span>
          </div>
        ` : `<h3 class="section-title">${escapeHtml(title)}</h3>`}
        ${content}
      </section>
    `;
  }

  function renderTextPanel(title, value, emptyText) {
    const text = String(value || "").trim();
    if (!text && !emptyText) return "";
    return renderPanel(
      title,
      `<p class="card-note">${escapeHtml(text || emptyText).replace(/\n/g, "<br />")}</p>`
    );
  }

  function renderExpandableTextPanel(title, value, emptyText, options) {
    const text = String(value || "").trim();
    if (!text && !emptyText) return "";
    if (!text) return renderTextPanel(title, "", emptyText);
    const previewLength = Number(options && options.previewLength) || 260;
    if (text.length <= previewLength) {
      return renderTextPanel(title, text, emptyText);
    }
    const disclosureId = `panel-disclosure-${state.disclosureCounter += 1}`;
    const openLabel = isTerminalTheme() ? "show_full_text" : "Show full text";
    const closeLabel = isTerminalTheme() ? "hide_full_text" : "Hide full text";
    return renderPanel(
      title,
      `
        <p class="card-note">${escapeHtml(truncateText(text, previewLength)).replace(/\n/g, "<br />")}</p>
        <button
          class="panel-toggle"
          type="button"
          data-toggle-section="${escapeHtml(disclosureId)}"
          data-label-open="${escapeHtml(openLabel)}"
          data-label-close="${escapeHtml(closeLabel)}"
          aria-expanded="false"
        >${escapeHtml(openLabel)}</button>
        <div id="${escapeHtml(disclosureId)}" class="panel-toggle-target is-hidden">
          <p class="card-note">${escapeHtml(text).replace(/\n/g, "<br />")}</p>
        </div>
      `
    );
  }

  function renderChipPanel(title, values, emptyText) {
    const items = values || [];
    if (!items.length && !emptyText) return "";
    return renderPanel(
      title,
      items.length
        ? listChips(items)
        : `<div class="empty-state">${escapeHtml(emptyText)}</div>`
    );
  }

  function renderScreenHeader(title, note, eyebrow) {
    return `
      <section class="screen-header ${isTerminalTheme() ? "screen-header-terminal" : ""}">
        ${eyebrow ? `<p class="eyebrow">${escapeHtml(isTerminalTheme() ? terminalToken(eyebrow) : eyebrow)}</p>` : ""}
        <h2>${escapeHtml(title)}</h2>
        ${note ? `<p>${escapeHtml(note)}</p>` : ""}
      </section>
    `;
  }

  function renderShortcutCard(options) {
    const actionAttr = options.route
      ? `data-route="${escapeHtml(options.route)}"`
      : `data-open-url="${escapeHtml(options.openUrl)}"`;
    const metrics = options.metrics || [];
    const visibleMetrics = metrics.filter((metric) => metric && metric.value);
    const headerClassName = options.badge
      ? "card-head card-head-compact has-badge"
      : "card-head card-head-compact";
    return `
      <article class="card card-compact ${isTerminalTheme() ? "card-terminal" : ""}" ${actionAttr}>
        ${options.kicker ? `<p class="card-kicker">${escapeHtml(options.kicker)}</p>` : ""}
        <div class="${headerClassName}">
          <div class="card-title-wrap">
            <h3>${escapeHtml(options.title || "Open")}</h3>
          </div>
          ${options.badge ? `<span class="badge" data-tone="${escapeHtml(options.badgeTone || "accent")}">${escapeHtml(options.badge)}</span>` : ""}
        </div>
        ${options.note ? renderCardNote(options.note, "card-note-compact") : ""}
        ${visibleMetrics.length ? renderInlineMetrics(visibleMetrics, visibleMetrics.length <= 2 ? "inline-metrics-compact" : "") : ""}
      </article>
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

  function buildProfilePreview(profile) {
    const summaryText = firstNonEmpty(
      profile && profile.summary && profile.summary.approvalSummaryText,
      [
        profile && profile.location,
        profile && profile.workFormat,
        profile && profile.salaryExpectation,
      ].filter(Boolean).join(" • ")
    );
    return truncateText(summaryText || "Open your profile.", 120);
  }

  function groupCandidateOpportunityItems(items) {
    const allItems = items || [];
    return {
      needsAction: allItems.filter((item) => item && item.needsAction),
      connected: allItems.filter((item) => item && item.stage === "approved"),
      inProgress: allItems.filter((item) => item && !item.needsAction && item.stage !== "approved"),
    };
  }

  function renderCandidateVacancyCard(item) {
    return renderShortcutCard({
      route: `candidate-vacancy:${item.id}`,
      title: item.roleTitle || "Vacancy",
      badge: item.stageLabel || "Status",
      badgeTone: badgeTone(item.stageLabel || item.stage),
      metrics: [
        { label: "Budget", value: item.budget || "Not set" },
        { label: "Format", value: item.workFormat || "Not set" },
        { label: "Updated", value: formatRelativeTime(item.updatedAt) },
      ],
    });
  }

  function renderManagerVacancyCard(item) {
    return renderShortcutCard({
      route: `manager-vacancy:${item.id}`,
      title: item.roleTitle || "Vacancy",
      badge: item.state || "State",
      badgeTone: badgeTone(item.state),
      note: `Updated ${formatRelativeTime(item.updatedAt)}`,
      metrics: [
        { label: "Candidates", value: String(item.candidateCount || 0) },
        { label: "Pipeline", value: String(item.activePipelineCount || 0) },
        { label: "Connected", value: String(item.connectedCount || 0) },
      ],
    });
  }

  function renderManagerCandidateCard(item) {
    return renderShortcutCard({
      route: `manager-candidate:${item.id}`,
      title: item.candidateName || "Candidate",
      badge: item.stageLabel || "Status",
      badgeTone: badgeTone(item.stageLabel || item.stage),
      note: truncateText(((item.summary || {}).approvalSummaryText) || "No summary yet.", 110),
      metrics: [
        { label: "Location", value: item.location || "Not set" },
        { label: "Salary", value: item.salaryExpectation || "Not set" },
        { label: "Format", value: item.workFormat || "Not set" },
      ],
    });
  }

  function renderCandidateProfileHome(profile) {
    const summaryText = firstNonEmpty(
      profile.summary && profile.summary.approvalSummaryText,
      profile.summary && profile.summary.experienceExcerpt
    );
    const skillsText = ((profile.summary && profile.summary.skills) || []).slice(0, 4).join(" • ");
    const answersText = [
      profile.answers && profile.answers.salaryExpectation,
      profile.answers && profile.answers.location,
      profile.answers && profile.answers.workFormat,
    ].filter(Boolean).join(" • ");
    appEl.innerHTML = `
      ${renderScreenHeader("Profile", firstNonEmpty(profile.targetRole, profile.headline, profile.name), "profile")}
      <section class="list">
        ${renderShortcutCard({
          route: "candidate-profile-section:summary",
          title: "Summary",
          note: truncateText(summaryText || "No summary yet.", 120),
        })}
        ${renderShortcutCard({
          route: "candidate-profile-section:skills",
          title: "Skills",
          note: truncateText(skillsText || "No skills yet.", 120),
        })}
        ${renderShortcutCard({
          route: "candidate-profile-section:answers",
          title: "Answers",
          note: truncateText(answersText || "No saved answers yet.", 120),
        })}
      </section>
    `;
    bindCards();
  }

  function renderCandidateProfileSection(profile, sectionKey) {
    if (sectionKey === "summary") {
      appEl.innerHTML = `
        ${renderScreenHeader("Summary", firstNonEmpty(profile.targetRole, profile.headline, profile.name), "summary")}
        ${renderTextPanel(
          "Summary",
          firstNonEmpty(
            profile.summary && profile.summary.approvalSummaryText,
            profile.summary && profile.summary.experienceExcerpt
          ),
          "No summary yet."
        )}
        ${renderDetailSection("Profile", [
          { label: "Headline", value: profile.summary && profile.summary.headline ? profile.summary.headline : "" },
          { label: "Target role", value: profile.summary && profile.summary.targetRole ? profile.summary.targetRole : "" },
          { label: "Experience", value: profile.summary && profile.summary.yearsExperience ? `${profile.summary.yearsExperience}+ years` : "" },
        ])}
        ${renderChipPanel("Skills", (profile.summary && profile.summary.skills) || [], "")}
      `;
      return;
    }

    if (sectionKey === "skills") {
      appEl.innerHTML = `
      ${renderScreenHeader("Skills", firstNonEmpty(profile.targetRole, profile.headline, profile.name), "skills")}
      ${renderChipPanel("Core skills", (profile.summary && profile.summary.skills) || [], "No skills yet.")}
      ${renderDetailSection("Profile context", [
        { label: "Target role", value: profile.summary && profile.summary.targetRole ? profile.summary.targetRole : "" },
        { label: "Experience", value: profile.summary && profile.summary.yearsExperience ? `${profile.summary.yearsExperience}+ years` : "" },
      ])}
    `;
      return;
    }

    if (sectionKey === "answers") {
      appEl.innerHTML = `
      ${renderScreenHeader("Answers", profile.name || "Profile", "answers")}
      ${renderDetailSection("Saved answers", [
        { label: "Salary", value: profile.answers && profile.answers.salaryExpectation ? profile.answers.salaryExpectation : "Not set" },
        { label: "Location", value: profile.answers && profile.answers.location ? profile.answers.location : "Not set" },
        { label: "Country", value: profile.answers && profile.answers.countryCode ? profile.answers.countryCode : "" },
        { label: "City", value: profile.answers && profile.answers.city ? profile.answers.city : "" },
        { label: "Work format", value: profile.answers && profile.answers.workFormat ? profile.answers.workFormat : "Not set" },
      ])}
    `;
      return;
    }

    renderCandidateProfileHome(profile);
  }

  async function renderHome() {
    const role = state.session.role;
    if (role === "unknown") {
      renderRoleCheck("Checking your role in Telegram. Finish the role setup in chat to continue.");
      return;
    }

    if (role === "candidate") {
      const payload = await api("/webapp/api/candidate/opportunities");
      const items = payload.items || [];
      const profile = payload.profile || {};
      const groups = groupCandidateOpportunityItems(items);
      appEl.innerHTML = `
        ${renderStatsStrip([
          { label: "Vacancies", value: String(items.length) },
          { label: "Needs action", value: String(groups.needsAction.length) },
          { label: "Connected", value: String(groups.connected.length) }
        ])}
        ${groups.needsAction.length ? `
          <section class="list">
            <p class="footer-note">Needs your reply</p>
            ${groups.needsAction.map(renderCandidateVacancyCard).join("")}
          </section>
        ` : ""}
        <section class="list">
          ${payload.cvChallenge && payload.cvChallenge.eligible && payload.cvChallenge.launchUrl
            ? renderShortcutCard({
              openUrl: withCurrentTheme(payload.cvChallenge.launchUrl),
              title: payload.cvChallenge.title || "CV Challenge",
              kicker: "Game",
              note: truncateText(payload.cvChallenge.body || "Open the game.", 120),
            })
            : ""}
          ${renderShortcutCard({
            route: "candidate-profile",
            title: firstNonEmpty(profile.targetRole, profile.headline, "Profile"),
            kicker: "Profile",
            note: buildProfilePreview(profile),
            metrics: [
              { label: "Location", value: profile.location || "" },
              { label: "Format", value: profile.workFormat || "" },
              { label: "Salary", value: profile.salaryExpectation || "" },
            ],
          })}
        </section>
        ${groups.inProgress.length ? `
          <section class="list">
            <p class="footer-note">In progress</p>
            ${groups.inProgress.map(renderCandidateVacancyCard).join("")}
          </section>
        ` : ""}
        ${groups.connected.length ? `
          <section class="list">
            <p class="footer-note">Connected</p>
            ${groups.connected.map(renderCandidateVacancyCard).join("")}
          </section>
        ` : ""}
        ${items.length ? "" : `
          <section class="list">
            <div class="empty-state">No vacancies yet. Helly will show new matches here as soon as a role fits your profile.</div>
          </section>
        `}
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
      const totalConnectedCount = sumBy(items, "connectedCount");
      appEl.innerHTML = `
        ${renderScreenHeader("Dashboard", "", "dashboard")}
        ${renderStatsStrip([
          { label: "Vacancies", value: String(items.length) },
          { label: "Candidates", value: String(totalCandidateCount) },
          { label: "Pipeline", value: String(totalActivePipelineCount) },
          { label: "Connected", value: String(totalConnectedCount) }
        ])}
        <section class="list">
          ${items.length ? items.map(renderManagerVacancyCard).join("") : `<div class="empty-state">No vacancies yet. Open a role and candidates will start appearing here.</div>`}
        </section>
      `;
      bindCards();
      return;
    }
  }

  async function renderCandidateVacancy(matchId) {
    const payload = await api(`/webapp/api/candidate/opportunities/${matchId}`);
    appEl.innerHTML = `
      ${renderScreenHeader(payload.vacancy.roleTitle || "Vacancy", "", "vacancy")}
      ${renderStatsStrip([
        { label: "Stage", value: payload.match.statusLabel || "Unknown" },
        { label: "Budget", value: payload.vacancy.budget || "Not specified" },
        { label: "Format", value: payload.vacancy.workFormat || "Not specified" },
        { label: "Updated", value: formatRelativeTime(payload.match.updatedAt) }
      ])}
      ${renderTextPanel("What happens now", payload.match.statusDescription || "", "")}
      ${renderDetailSection("Timeline", [
        { label: "Last updated", value: formatEventTime(payload.match.updatedAt) },
        { label: "Your reply", value: formatEventTime(payload.match.candidateRespondedAt, "Pending") },
        { label: "Manager decision", value: formatEventTime(payload.match.managerDecisionAt, "Pending") }
      ])}
      ${renderTextPanel(
        "Summary",
        firstNonEmpty(
          payload.vacancy.summary && payload.vacancy.summary.approvalSummaryText,
          payload.vacancy.summary && payload.vacancy.summary.projectDescriptionExcerpt,
          payload.vacancy.projectDescription
        ),
        "No summary yet."
      )}
      ${renderDetailSection("Vacancy", [
        { label: "Allowed countries", value: (payload.vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Seniority", value: payload.vacancy.seniority || "" },
        { label: "Team size", value: payload.vacancy.teamSize || "" },
        { label: "Project", value: payload.vacancy.projectDescription || "Not specified", full: true }
      ])}
      ${renderChipPanel("Tech stack", payload.vacancy.primaryTechStack || [], "")}
      ${renderExpandableTextPanel("Job description", payload.vacancy.source && payload.vacancy.source.text, "")}
    `;
    bindDisclosures();
  }

  async function renderManagerVacancy(vacancyId) {
    const detailPath = `/webapp/api/hiring-manager/vacancies/${vacancyId}`;
    const matchesPath = `/webapp/api/hiring-manager/vacancies/${vacancyId}/matches`;
    const [detail, matchesPayload] = await Promise.all([api(detailPath), api(matchesPath)]);
    const vacancy = detail.vacancy;
    const stats = detail.stats;
    const items = matchesPayload.items || [];
    appEl.innerHTML = `
      ${renderScreenHeader(vacancy.roleTitle || "Vacancy", "", "vacancy")}
      ${renderStatsStrip([
        { label: "Candidates", value: String(stats.candidateCount) },
        { label: "Pipeline", value: String(stats.activePipelineCount) },
        { label: "Connected", value: String(stats.connectedCount || 0) },
        { label: "Budget", value: vacancy.budget || "Not specified" }
      ])}
      <section class="list">
        <p class="footer-note">Candidates</p>
        ${items.length ? items.map(renderManagerCandidateCard).join("") : `<div class="empty-state">No candidates yet. As soon as Helly finds matches, they will appear here.</div>`}
      </section>
      ${renderTextPanel(
        "Summary",
        firstNonEmpty(
          vacancy.summary && vacancy.summary.approvalSummaryText,
          vacancy.summary && vacancy.summary.projectDescriptionExcerpt,
          vacancy.projectDescription
        ),
        "No summary yet."
      )}
      ${renderDetailSection("Vacancy", [
        { label: "Work format", value: vacancy.workFormat || "Not specified" },
        { label: "Allowed countries", value: (vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Team size", value: vacancy.teamSize || "" },
        { label: "Opened", value: vacancy.openedAt ? formatEventTime(vacancy.openedAt) : "" },
        { label: "Project", value: vacancy.projectDescription || "Not specified", full: true }
      ])}
      ${renderChipPanel("Tech stack", vacancy.primaryTechStack || [], "")}
      ${renderExpandableTextPanel("Job description", vacancy.source && vacancy.source.text, "")}
    `;
    bindCards();
    bindDisclosures();
  }

  async function renderManagerCandidate(matchId) {
    const payload = await api(`/webapp/api/hiring-manager/matches/${matchId}`);
    const hasDecisionSupport = Boolean(
      payload.interview.stateLabel ||
      payload.evaluation.recommendation ||
      payload.evaluation.interviewSummary ||
      (payload.evaluation.strengths || []).length ||
      (payload.evaluation.risks || []).length
    );
    appEl.innerHTML = `
      ${renderScreenHeader(payload.candidate.name || "Candidate", payload.vacancy.roleTitle || "", "candidate")}
      ${renderStatsStrip([
        { label: "Stage", value: payload.match.statusLabel || "Unknown" },
        { label: "Salary", value: payload.candidate.salaryExpectation || "Not specified" },
        { label: "Location", value: payload.candidate.location || "Not specified" },
        { label: "Format", value: payload.candidate.workFormat || "Not specified" },
        { label: "Updated", value: formatRelativeTime(payload.match.updatedAt) }
      ])}
      ${renderTextPanel("What happens now", payload.match.statusDescription || "", "")}
      ${renderDetailSection("Timeline", [
        { label: "Last updated", value: formatEventTime(payload.match.updatedAt) },
        { label: "Invitation sent", value: payload.match.invitationSentAt ? formatEventTime(payload.match.invitationSentAt) : "" },
        { label: "Candidate reply", value: payload.match.candidateRespondedAt ? formatEventTime(payload.match.candidateRespondedAt) : "" },
        { label: "Manager decision", value: payload.match.managerDecisionAt ? formatEventTime(payload.match.managerDecisionAt) : "" }
      ])}
      ${hasDecisionSupport ? renderDetailSection("Decision support", [
        { label: "Interview state", value: payload.interview.stateLabel || "Not started" },
        { label: "Recommendation", value: payload.evaluation.recommendation || "N/A" },
        { label: "Interview summary", value: payload.evaluation.interviewSummary || "No interview summary yet.", full: true },
        { label: "Strengths", value: listChips(payload.evaluation.strengths || []), raw: true, full: true },
        { label: "Risks", value: listChips(payload.evaluation.risks || []), raw: true, full: true }
      ]) : ""}
      ${renderTextPanel(
        "Summary",
        firstNonEmpty(
          payload.candidate.summary && payload.candidate.summary.approvalSummaryText,
          payload.candidate.summary && payload.candidate.summary.experienceExcerpt
        ),
        "No summary yet."
      )}
      ${renderChipPanel("Skills", (payload.candidate.summary || {}).skills || [], "")}
      ${renderDetailSection("Answers", [
        { label: "Salary", value: payload.candidate.answers && payload.candidate.answers.salaryExpectation ? payload.candidate.answers.salaryExpectation : payload.candidate.salaryExpectation || "Not specified" },
        { label: "Location", value: payload.candidate.answers && payload.candidate.answers.location ? payload.candidate.answers.location : payload.candidate.location || "Not specified" },
        { label: "Country", value: payload.candidate.answers && payload.candidate.answers.countryCode ? payload.candidate.answers.countryCode : payload.candidate.countryCode || "" },
        { label: "City", value: payload.candidate.answers && payload.candidate.answers.city ? payload.candidate.answers.city : payload.candidate.city || "" },
        { label: "Work format", value: payload.candidate.answers && payload.candidate.answers.workFormat ? payload.candidate.answers.workFormat : payload.candidate.workFormat || "Not specified" },
      ])}
      ${renderExpandableTextPanel("CV text", payload.candidate.source && payload.candidate.source.text, "")}
    `;
    bindDisclosures();
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
      if (node.tagName !== "BUTTON") {
        node.setAttribute("tabindex", "0");
        node.setAttribute("role", "button");
      }
      const activate = () => {
        tapFeedback();
        window.location.assign(targetUrl);
      };
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
      node.addEventListener("click", () => {
        activate();
      });
    });
  }

  function bindDisclosures() {
    Array.from(document.querySelectorAll("[data-toggle-section]")).forEach((node) => {
      const targetId = node.getAttribute("data-toggle-section");
      const target = targetId ? document.getElementById(targetId) : null;
      if (!target) return;
      node.addEventListener("click", () => {
        const isHidden = target.classList.contains("is-hidden");
        target.classList.toggle("is-hidden", !isHidden);
        node.setAttribute("aria-expanded", isHidden ? "true" : "false");
        node.textContent = isHidden
          ? node.getAttribute("data-label-close") || "Hide full text"
          : node.getAttribute("data-label-open") || "Show full text";
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
        renderLoadingState("Refreshing your home", "Loading the latest recruiting data.");
        await renderHome();
        return;
      }

      const parts = currentRoute.split(":");
      if (currentRoute === "candidate-profile") {
        renderLoadingState("Opening profile", "Loading your latest profile snapshot.");
        const payload = await api("/webapp/api/candidate/profile");
        renderCandidateProfileHome(payload.profile || {});
        return;
      }
      if (parts.length !== 2) {
        renderLoadingState("Refreshing your home", "Loading the latest recruiting data.");
        await renderHome();
        return;
      }
      const route = parts[0];
      const id = parts[1];
      if (route === "candidate-profile-section") {
        renderLoadingState("Opening profile", "Loading your latest profile snapshot.");
        const payload = await api("/webapp/api/candidate/profile");
        return renderCandidateProfileSection(payload.profile || {}, id);
      }
      if (route === "candidate-vacancy") {
        renderLoadingState("Opening vacancy", "Loading the latest role details.");
        return await renderCandidateVacancy(id);
      }
      if (route === "manager-vacancy") {
        renderLoadingState("Opening vacancy", "Loading the latest vacancy and candidate data.");
        return await renderManagerVacancy(id);
      }
      if (route === "manager-candidate") {
        renderLoadingState("Opening candidate", "Loading the latest candidate snapshot.");
        return await renderManagerCandidate(id);
      }
      renderLoadingState("Refreshing your home", "Loading the latest recruiting data.");
      await renderHome();
    } catch (error) {
      renderError("Dashboard request failed", error.message || "Unable to load this screen.");
    }
  }

  async function boot() {
    try {
      initializeTheme();
      bindTelegramRuntime();
      renderRoleCheck("Checking your role and loading the latest recruiting data.");
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
