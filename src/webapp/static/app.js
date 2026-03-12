(function () {
  const state = {
    sessionToken: null,
    session: null,
    backButtonHandlerBound: false,
    theme: "terminal",
    disclosureCounter: 0,
    managerHomeView: { filter: "all", sort: "updated" },
    managerHomePayload: null,
    managerVacancyViews: {},
    managerVacancyPayloads: {},
  };
  const TERMINAL_THEME = "terminal";
  const CLOSED_MATCH_STAGES = new Set([
    "rejected",
    "manager_skipped",
    "candidate_skipped",
    "candidate_declined_interview",
    "filtered_out",
    "expired",
  ]);

  const appEl = document.getElementById("app");
  const appShellEl = document.querySelector(".app-shell");
  const topbarNoteEl = document.getElementById("topbar-note");
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

  function splitExpandableText(value, maxLength) {
    const text = String(value || "");
    if (!text || text.length <= maxLength) {
      return { preview: text, remainder: "" };
    }

    const previewSlice = text.slice(0, maxLength);
    const lastBoundary = Math.max(previewSlice.lastIndexOf("\n"), previewSlice.lastIndexOf(" "));
    const splitIndex = lastBoundary >= Math.floor(maxLength * 0.6) ? lastBoundary : maxLength;
    const preview = text.slice(0, splitIndex).trimEnd();
    const remainder = text.slice(splitIndex).trimStart();

    if (!preview || !remainder) {
      return { preview: truncateText(text, maxLength), remainder: "" };
    }

    return {
      preview: `${preview}…`,
      remainder,
    };
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
    if (text.includes("strong")) return "good";
    if (text.includes("medium")) return "warn";
    if (text.includes("low")) return "bad";
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
        <p>${escapeHtml(note || "Checking your Telegram access and opening the right workspace.")}</p>
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
      return `<div class="empty-state">Nothing here yet.</div>`;
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

  function timeValue(isoValue) {
    const value = new Date(isoValue).getTime();
    return Number.isFinite(value) ? value : 0;
  }

  function pluralize(count, singular, plural) {
    return Number(count) === 1 ? singular : plural;
  }

  function isTerminalTheme() {
    return state.theme === TERMINAL_THEME;
  }

  function getCurrentRole() {
    return state.session && state.session.role ? state.session.role : "unknown";
  }

  function getTopbarNote(role) {
    if (role === "candidate") {
      return "Your profile, roles, and next steps in Telegram.";
    }
    if (role === "hiring_manager") {
      return "Your vacancies, candidates, and decisions in Telegram.";
    }
    return "Your recruiting flow in Telegram.";
  }

  function updateTopbarCopy() {
    if (!topbarNoteEl) return;
    topbarNoteEl.textContent = getTopbarNote(getCurrentRole());
  }

  function homeLoadingCopy() {
    if (getCurrentRole() === "candidate") {
      return {
        title: "Refreshing your matches",
        body: "Loading your latest profile and opportunity updates.",
      };
    }
    if (getCurrentRole() === "hiring_manager") {
      return {
        title: "Refreshing your hiring view",
        body: "Loading your latest vacancies and candidate updates.",
      };
    }
    return {
      title: "Refreshing Helly",
      body: "Loading the latest recruiting data.",
    };
  }

  function isClosedMatchStage(status) {
    return CLOSED_MATCH_STAGES.has(String(status || ""));
  }

  function getManagerHomeView() {
    return state.managerHomeView;
  }

  function getManagerVacancyView(vacancyId) {
    if (!state.managerVacancyViews[vacancyId]) {
      state.managerVacancyViews[vacancyId] = { filter: "all", sort: "needs-action" };
    }
    return state.managerVacancyViews[vacancyId];
  }

  function updateViewState(scope, key, value, id) {
    if (scope === "manager-home") {
      state.managerHomeView = {
        ...getManagerHomeView(),
        [key]: value,
      };
      return;
    }
    if (scope === "manager-vacancy" && id) {
      state.managerVacancyViews[id] = {
        ...getManagerVacancyView(id),
        [key]: value,
      };
    }
  }

  function filterManagerVacancies(items, filterKey) {
    const allItems = items || [];
    switch (filterKey) {
      case "needs-review":
        return allItems.filter((item) => Number(item && item.needsReviewCount) > 0);
      case "connected":
        return allItems.filter((item) => Number(item && item.connectedCount) > 0);
      case "closed":
        return allItems.filter((item) => String(item && item.state || "").toUpperCase() !== "OPEN");
      default:
        return allItems;
    }
  }

  function sortManagerVacancies(items, sortKey) {
    const allItems = [...(items || [])];
    const byUpdated = (left, right) => timeValue(right && right.updatedAt) - timeValue(left && left.updatedAt);
    if (sortKey === "needs-review") {
      allItems.sort((left, right) => (
        Number(right && right.needsReviewCount || 0) - Number(left && left.needsReviewCount || 0)
      ) || byUpdated(left, right));
      return allItems;
    }
    if (sortKey === "candidates") {
      allItems.sort((left, right) => (
        Number(right && right.candidateCount || 0) - Number(left && left.candidateCount || 0)
      ) || byUpdated(left, right));
      return allItems;
    }
    allItems.sort(byUpdated);
    return allItems;
  }

  function filterManagerCandidates(items, filterKey) {
    const allItems = items || [];
    switch (filterKey) {
      case "needs-review":
        return allItems.filter((item) => item && item.needsAction);
      case "connected":
        return allItems.filter((item) => item && item.stage === "approved");
      case "closed":
        return allItems.filter((item) => isClosedMatchStage(item && item.stage));
      default:
        return allItems;
    }
  }

  function fitBandPriority(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized === "strong") return 0;
    if (normalized === "medium") return 1;
    if (normalized === "low") return 2;
    if (normalized === "not_fit") return 3;
    return 9;
  }

  function sortManagerCandidates(items, sortKey) {
    const allItems = [...(items || [])];
    const byUpdated = (left, right) => timeValue(right && right.updatedAt) - timeValue(left && left.updatedAt);
    if (sortKey === "needs-action") {
      allItems.sort((left, right) => (
        Number(Boolean(right && right.needsAction)) - Number(Boolean(left && left.needsAction))
      ) || (
        fitBandPriority(left && left.fitBand) - fitBandPriority(right && right.fitBand)
      ) || byUpdated(left, right));
      return allItems;
    }
    allItems.sort(byUpdated);
    return allItems;
  }

  function renderFilteredEmptyState(message) {
    return `<div class="empty-state">${escapeHtml(message)}</div>`;
  }

  function renderViewControls(groups) {
    const visibleGroups = (groups || []).filter((group) => group && (group.items || []).length);
    if (!visibleGroups.length) return "";
    return `
      <section class="view-controls ${isTerminalTheme() ? "view-controls-terminal" : ""}">
        ${visibleGroups.map((group) => `
          <div class="view-controls-group">
            <p class="footer-note">${escapeHtml(group.label)}</p>
            <div class="control-bar">
              ${(group.items || []).map((item) => {
                const isActive = item.value === group.selectedValue;
                return `
                  <button
                    class="control-chip ${isActive ? "is-active" : ""}"
                    type="button"
                    data-view-scope="${escapeHtml(group.scope)}"
                    data-view-key="${escapeHtml(group.key)}"
                    data-view-value="${escapeHtml(item.value)}"
                    ${group.scopeId ? `data-view-id="${escapeHtml(group.scopeId)}"` : ""}
                    aria-pressed="${isActive ? "true" : "false"}"
                  >${escapeHtml(item.label)}</button>
                `;
              }).join("")}
            </div>
          </div>
        `).join("")}
      </section>
    `;
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

  function renderBadgeRow(values, tone) {
    const items = (values || []).filter((value) => value !== null && value !== undefined && String(value).trim());
    if (!items.length) return "";
    return `
      <div class="badge-row">
        ${items.map((value) => `<span class="badge" data-tone="${escapeHtml(tone || "accent")}">${escapeHtml(value)}</span>`).join("")}
      </div>
    `;
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
    const metrics = [
      challenge.correctSkillCount ? { label: "CV skills", value: String(challenge.correctSkillCount) } : null,
    ].filter(Boolean);
    return `
      <section class="detail-panel action-panel ${isTerminalTheme() ? "action-panel-terminal" : ""}">
        <div class="action-panel-copy">
          <p class="eyebrow">${isTerminalTheme() ? "game" : "Game"}</p>
          <h3 class="section-title">${challenge.title || "Helly CV Challenge"}</h3>
          <p class="card-note">${escapeHtml(challenge.body || "Tap only the skills that really appear in your CV.")}</p>
          ${metrics.length ? renderInlineMetrics(metrics, "inline-metrics-compact") : ""}
        </div>
        ${isTerminalTheme() ? `
          <div class="terminal-command-row">
            <span class="terminal-prompt">&gt;</span>
            <span class="terminal-command">launch /cv-challenge --profile current</span>
          </div>
        ` : ""}
        <button class="action-button" type="button" data-open-url="${escapeHtml(withCurrentTheme(challenge.launchUrl))}">${isTerminalTheme() ? "Start challenge" : "Start challenge"}</button>
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
    const { preview, remainder } = splitExpandableText(text, previewLength);
    if (!remainder) {
      return renderTextPanel(title, text, emptyText);
    }
    return renderPanel(
      title,
      `
        <p class="card-note">${escapeHtml(preview).replace(/\n/g, "<br />")}</p>
        <button
          class="panel-toggle"
          type="button"
          data-toggle-section="${escapeHtml(disclosureId)}"
          data-label-open="${escapeHtml(openLabel)}"
          data-label-close="${escapeHtml(closeLabel)}"
          aria-expanded="false"
        >${escapeHtml(openLabel)}</button>
        <div id="${escapeHtml(disclosureId)}" class="panel-toggle-target is-hidden">
          <p class="card-note">${escapeHtml(remainder).replace(/\n/g, "<br />")}</p>
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
    updateTopbarCopy();
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

  function groupCandidateOpportunityItems(items) {
    const allItems = items || [];
    return {
      needsAction: allItems.filter((item) => item && item.needsAction),
      connected: allItems.filter((item) => item && item.stage === "approved"),
      inProgress: allItems.filter((item) => item && !item.needsAction && item.stage !== "approved"),
    };
  }

  function renderCandidateVacancyCard(item) {
    const highlights = [];
    if (item.requiredEnglishLevel) {
      highlights.push(`${item.requiredEnglishLevel} English`);
    }
    if (item.officeCity) {
      highlights.push(item.officeCity);
    }
    if (item.hasTakeHomeTask === true) {
      highlights.push("Take-home");
    }
    if (item.hasLiveCoding === true) {
      highlights.push("Live coding");
    }
    if (item.hiringStages && item.hiringStages.length) {
      highlights.push(`${item.hiringStages.length} ${pluralize(item.hiringStages.length, "stage", "stages")}`);
    }
    return renderShortcutCard({
      route: `candidate-vacancy:${item.id}`,
      title: item.roleTitle || "Vacancy",
      badge: item.stageLabel || "Status",
      badgeTone: badgeTone(item.stageLabel || item.stage),
      note: highlights.join(" • "),
      metrics: [
        { label: "Budget", value: item.budget || "Not set" },
        { label: "Format", value: item.workFormat || "Not set" },
        { label: "Updated", value: formatRelativeTime(item.updatedAt) },
      ],
    });
  }

  function compactCompensation(value) {
    return String(value || "")
      .replace(/\s+per month$/i, "/mo")
      .replace(/\s+per year$/i, "/yr")
      .replace(/\s+per week$/i, "/wk")
      .replace(/\s+per day$/i, "/day")
      .replace(/\s+per hour$/i, "/hr")
      .trim();
  }

  function formatBooleanChoice(value, labels) {
    if (value === true) return labels && labels.yes ? labels.yes : "Yes";
    if (value === false) return labels && labels.no ? labels.no : "No";
    return "";
  }

  function formatJoinedValues(values) {
    return (values || [])
      .filter((value) => value !== null && value !== undefined && String(value).trim())
      .join(" • ");
  }

  function formatVacancyAssessment(value, options) {
    if (value === true) return options && options.yes ? options.yes : "Yes";
    if (value === false) return options && options.no ? options.no : "No";
    return "";
  }

  function renderCandidateProfileCard(profile) {
    const title = firstNonEmpty(profile.targetRole, profile.headline, "Your profile");
    const subtitle = profile.headline && profile.headline !== title ? profile.headline : "";
    const facts = [];
    if (profile.summary && profile.summary.yearsExperience) {
      facts.push(`${profile.summary.yearsExperience}+ years`);
    }
    if (profile.englishLevel) {
      facts.push(profile.englishLevel);
    }
    if (profile.workFormat) {
      facts.push(profile.workFormat);
    }
    if (profile.location) {
      facts.push(profile.location);
    }
    if (profile.salaryExpectation) {
      facts.push(compactCompensation(profile.salaryExpectation));
    }
    const skills = (profile.fullHardSkills || (profile.summary && profile.summary.skills) || []).slice(0, 4);
    const summaryText = firstNonEmpty(
      profile.summary && profile.summary.approvalSummaryText,
      profile.summary && profile.summary.experienceExcerpt
    );
    const renderedSummary = summaryText && summaryText !== title && summaryText !== subtitle
      ? truncateText(summaryText, 150)
      : "";

    return `
      <section class="detail-panel action-panel profile-home-card ${isTerminalTheme() ? "detail-panel-terminal" : ""}">
        <div class="action-panel-copy">
          <p class="eyebrow">${isTerminalTheme() ? "profile" : "Profile"}</p>
          <h3 class="profile-home-title">${escapeHtml(title)}</h3>
          ${subtitle ? `<p class="profile-home-subtitle">${escapeHtml(subtitle)}</p>` : ""}
          ${renderedSummary ? renderCardNote(renderedSummary, "profile-home-summary") : ""}
          ${renderBadgeRow(facts, "accent")}
          ${skills.length ? `<div class="profile-home-skills">${listChips(skills)}</div>` : ""}
        </div>
        <button class="action-button profile-home-button" type="button" data-route="candidate-profile">${isTerminalTheme() ? "Open profile" : "Open profile"}</button>
      </section>
    `;
  }

  function renderManagerVacancyCard(item) {
    const needsReviewCount = Number(item && item.needsReviewCount || 0);
    return renderShortcutCard({
      route: `manager-vacancy:${item.id}`,
      title: item.roleTitle || "Vacancy",
      badge: needsReviewCount ? "Needs review" : item.state || "State",
      badgeTone: needsReviewCount ? "warn" : badgeTone(item.state),
      note: needsReviewCount
        ? `${needsReviewCount} ${pluralize(needsReviewCount, "candidate", "candidates")} waiting for your review.`
        : `Updated ${formatRelativeTime(item.updatedAt)}`,
      metrics: [
        { label: "Candidates", value: String(item.candidateCount || 0) },
        { label: "Needs review", value: String(needsReviewCount) },
        { label: "Connected", value: String(item.connectedCount || 0) },
      ],
    });
  }

  function renderManagerCandidateCard(item) {
    const fitLabel = item.fitBandLabel || "";
    const gapText = formatJoinedValues(item.gapSignals || []);
    const summaryText = firstNonEmpty(
      gapText,
      item.needsAction ? item.stageDescription : "",
      (item.summary || {}).approvalSummaryText,
      "Candidate summary is still being prepared."
    );
    return renderShortcutCard({
      route: `manager-candidate:${item.id}`,
      title: item.candidateName || "Candidate",
      badge: fitLabel || item.stageLabel || "Status",
      badgeTone: badgeTone(fitLabel || item.stageLabel || item.stage),
      note: truncateText(summaryText, 110),
      metrics: [
        { label: "Stage", value: item.stageLabel || "Not set" },
        { label: "Location", value: item.location || "Not set" },
        { label: "English", value: item.englishLevel || "Not set" },
        { label: "Salary", value: item.salaryExpectation || "Not set" },
      ],
    });
  }

  function renderManagerHomeScreen(payload) {
    const items = payload.items || [];
    const view = getManagerHomeView();
    const filteredItems = sortManagerVacancies(filterManagerVacancies(items, view.filter), view.sort);
    const totalCandidateCount = sumBy(items, "candidateCount");
    const totalNeedsReviewCount = sumBy(items, "needsReviewCount");
    const totalConnectedCount = sumBy(items, "connectedCount");
    const emptyMessageByFilter = {
      "needs-review": "No vacancies need your review right now.",
      connected: "No vacancies have connected candidates yet.",
      closed: "No paused or closed vacancies yet.",
    };
    appEl.innerHTML = `
      ${renderScreenHeader("Dashboard", "", "dashboard")}
      ${renderStatsStrip([
        { label: "Vacancies", value: String(items.length) },
        { label: "Needs review", value: String(totalNeedsReviewCount) },
        { label: "Candidates", value: String(totalCandidateCount) },
        { label: "Connected", value: String(totalConnectedCount) }
      ])}
      ${items.length ? renderViewControls([
        {
          label: "Filter",
          scope: "manager-home",
          key: "filter",
          selectedValue: view.filter,
          items: [
            { label: "All", value: "all" },
            { label: "Needs review", value: "needs-review" },
            { label: "Connected", value: "connected" },
            { label: "Closed", value: "closed" },
          ],
        },
        {
          label: "Sort",
          scope: "manager-home",
          key: "sort",
          selectedValue: view.sort,
          items: [
            { label: "Updated", value: "updated" },
            { label: "Needs review first", value: "needs-review" },
            { label: "Most candidates", value: "candidates" },
          ],
        },
      ]) : ""}
      <section class="list">
        ${filteredItems.length
          ? filteredItems.map(renderManagerVacancyCard).join("")
          : renderFilteredEmptyState(emptyMessageByFilter[view.filter] || "No roles yet. Open or approve a role and Helly will start filling this list.")}
      </section>
    `;
    bindCards();
    bindViewControls();
  }

  function renderManagerVacancyScreen(vacancyId, detail, matchesPayload) {
    const vacancy = detail.vacancy;
    const stats = detail.stats;
    const items = matchesPayload.items || [];
    const view = getManagerVacancyView(vacancyId);
    const filteredItems = sortManagerCandidates(filterManagerCandidates(items, view.filter), view.sort);
    const emptyMessageByFilter = {
      "needs-review": "No candidates need your review in this vacancy right now.",
      connected: "No connected candidates in this vacancy yet.",
      closed: "No closed candidates in this vacancy yet.",
    };

    appEl.innerHTML = `
      ${renderScreenHeader(vacancy.roleTitle || "Vacancy", "", "vacancy")}
      ${renderStatsStrip([
        { label: "Candidates", value: String(stats.candidateCount) },
        { label: "Needs review", value: String(stats.needsReviewCount || 0) },
        { label: "Connected", value: String(stats.connectedCount || 0) }
      ])}
      <section class="list">
        <p class="footer-note">Candidates</p>
        ${items.length ? renderViewControls([
          {
            label: "Filter",
            scope: "manager-vacancy",
            scopeId: vacancyId,
            key: "filter",
            selectedValue: view.filter,
            items: [
              { label: "All", value: "all" },
              { label: "Needs review", value: "needs-review" },
              { label: "Connected", value: "connected" },
              { label: "Closed", value: "closed" },
            ],
          },
          {
            label: "Sort",
            scope: "manager-vacancy",
            scopeId: vacancyId,
            key: "sort",
            selectedValue: view.sort,
            items: [
              { label: "Needs action first", value: "needs-action" },
              { label: "Updated", value: "updated" },
            ],
          },
        ]) : ""}
        ${filteredItems.length
          ? filteredItems.map(renderManagerCandidateCard).join("")
          : renderFilteredEmptyState(emptyMessageByFilter[view.filter] || "No candidates yet. Helly is still matching this role and new candidates will appear here automatically.")}
      </section>
      ${renderTextPanel(
        "Summary",
        firstNonEmpty(
          vacancy.summary && vacancy.summary.approvalSummaryText,
          vacancy.summary && vacancy.summary.projectDescriptionExcerpt,
          vacancy.projectDescription
        ),
        "Helly is still preparing a short summary for this role."
      )}
      ${renderDetailSection("Vacancy", [
        { label: "Budget", value: vacancy.budget || "Not specified" },
        { label: "Work format", value: vacancy.workFormat || "Not specified" },
        { label: "Office city", value: vacancy.officeCity || "" },
        { label: "Allowed countries", value: (vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "English", value: vacancy.requiredEnglishLevel || "" },
        { label: "Take-home task", value: formatVacancyAssessment(vacancy.hasTakeHomeTask, { yes: "Included", no: "No" }) },
        { label: "Take-home compensation", value: vacancy.hasTakeHomeTask ? formatVacancyAssessment(vacancy.takeHomePaid, { yes: "Paid", no: "Unpaid" }) : "" },
        { label: "Live coding", value: formatVacancyAssessment(vacancy.hasLiveCoding, { yes: "Included", no: "No" }) },
        { label: "Team size", value: vacancy.teamSize || "" },
        { label: "Opened", value: vacancy.openedAt ? formatEventTime(vacancy.openedAt) : "" },
        { label: "Project", value: vacancy.projectDescription || "Not specified", full: true }
      ])}
      ${renderChipPanel("Hiring stages", vacancy.hiringStages || [], "")}
      ${renderChipPanel("Tech stack", vacancy.primaryTechStack || [], "")}
      ${renderExpandableTextPanel("Job description", vacancy.source && vacancy.source.text, "")}
    `;
    bindCards();
    bindDisclosures();
    bindViewControls();
  }

  function renderCandidateProfileHome(profile) {
    const summaryText = firstNonEmpty(
      profile.summary && profile.summary.approvalSummaryText,
      profile.summary && profile.summary.experienceExcerpt
    );
    const skillsText = (profile.fullHardSkills || (profile.summary && profile.summary.skills) || []).slice(0, 4).join(" • ");
    const answersText = [
      profile.answers && profile.answers.salaryExpectation,
      profile.answers && profile.answers.location,
      profile.answers && profile.answers.workFormat,
      profile.answers && profile.answers.englishLevel,
    ].filter(Boolean).join(" • ");
    appEl.innerHTML = `
      ${renderScreenHeader("Profile", firstNonEmpty(profile.targetRole, profile.headline, profile.name), "profile")}
      <section class="list">
        ${renderShortcutCard({
          route: "candidate-profile-section:summary",
          title: "Summary",
          note: truncateText(summaryText || "Your approved profile summary will appear here.", 120),
        })}
        ${renderShortcutCard({
          route: "candidate-profile-section:skills",
          title: "Skills",
          note: truncateText(skillsText || "Your core skills will appear here.", 120),
        })}
        ${renderShortcutCard({
          route: "candidate-profile-section:answers",
          title: "Answers",
          note: truncateText(answersText || "Your saved answers and preferences will appear here.", 120),
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
          "Your approved profile summary will appear here after processing."
        )}
        ${renderDetailSection("Profile", [
          { label: "Headline", value: profile.summary && profile.summary.headline ? profile.summary.headline : "" },
          { label: "Target role", value: profile.summary && profile.summary.targetRole ? profile.summary.targetRole : "" },
          { label: "Experience", value: profile.summary && profile.summary.yearsExperience ? `${profile.summary.yearsExperience}+ years` : "" },
        ])}
        ${renderChipPanel("Core skills", (profile.summary && profile.summary.skills) || [], "")}
      `;
      return;
    }

    if (sectionKey === "skills") {
      const fullSkills = profile.fullHardSkills || [];
      const coreSkills = (profile.summary && profile.summary.skills) || [];
      appEl.innerHTML = `
      ${renderScreenHeader("Skills", firstNonEmpty(profile.targetRole, profile.headline, profile.name), "skills")}
      ${renderChipPanel("Skills from your CV", fullSkills, "Your skills will appear here after your profile is processed.")}
      ${fullSkills.length && coreSkills.length ? renderChipPanel("Core summary skills", coreSkills, "") : ""}
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
        { label: "English", value: profile.answers && profile.answers.englishLevel ? profile.answers.englishLevel : "Not set" },
        { label: "Preferred domains", value: formatJoinedValues(profile.answers && profile.answers.preferredDomains), full: true },
        { label: "Take-home roles", value: formatBooleanChoice(profile.answers && profile.answers.showTakeHomeTaskRoles, { yes: "Show", no: "Hide" }) || "Not set" },
        { label: "Live coding roles", value: formatBooleanChoice(profile.answers && profile.answers.showLiveCodingRoles, { yes: "Show", no: "Hide" }) || "Not set" },
      ])}
    `;
      return;
    }

    renderCandidateProfileHome(profile);
  }

  async function renderHome() {
    const role = state.session.role;
    if (role === "unknown") {
      renderRoleCheck("Finish the role setup in chat to unlock the right workspace here.");
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
          ${renderActionPanel(payload.cvChallenge)}
          ${renderCandidateProfileCard(profile)}
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
            <div class="empty-state">No roles yet. Keep your profile up to date and Helly will add matching opportunities here when it finds a fit.</div>
          </section>
        `}
      `;
      bindCards();
      bindActionButtons();
      return;
    }

    if (role === "hiring_manager") {
      const payload = await api("/webapp/api/hiring-manager/vacancies");
      state.managerHomePayload = payload;
      renderManagerHomeScreen(payload);
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
      ${renderTextPanel("Why this role", payload.vacancy.whyThisRole || "", "")}
      ${renderChipPanel("Matching signals", payload.vacancy.matchSignals || [], "")}
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
        "Helly is still preparing a short summary for this role."
      )}
      ${renderDetailSection("Vacancy", [
        { label: "Allowed countries", value: (payload.vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Office city", value: payload.vacancy.officeCity || "" },
        { label: "English", value: payload.vacancy.requiredEnglishLevel || "" },
        { label: "Take-home task", value: formatVacancyAssessment(payload.vacancy.hasTakeHomeTask, { yes: "Included", no: "No" }) },
        { label: "Take-home compensation", value: payload.vacancy.hasTakeHomeTask ? formatVacancyAssessment(payload.vacancy.takeHomePaid, { yes: "Paid", no: "Unpaid" }) : "" },
        { label: "Live coding", value: formatVacancyAssessment(payload.vacancy.hasLiveCoding, { yes: "Included", no: "No" }) },
        { label: "Seniority", value: payload.vacancy.seniority || "" },
        { label: "Team size", value: payload.vacancy.teamSize || "" },
        { label: "Project", value: payload.vacancy.projectDescription || "Not specified", full: true }
      ])}
      ${renderChipPanel("Hiring stages", payload.vacancy.hiringStages || [], "")}
      ${renderChipPanel("Tech stack", payload.vacancy.primaryTechStack || [], "")}
      ${renderExpandableTextPanel("Job description", payload.vacancy.source && payload.vacancy.source.text, "")}
    `;
    bindDisclosures();
  }

  async function renderManagerVacancy(vacancyId) {
    const detailPath = `/webapp/api/hiring-manager/vacancies/${vacancyId}`;
    const matchesPath = `/webapp/api/hiring-manager/vacancies/${vacancyId}/matches`;
    const [detail, matchesPayload] = await Promise.all([api(detailPath), api(matchesPath)]);
    state.managerVacancyPayloads[vacancyId] = { detail, matchesPayload };
    renderManagerVacancyScreen(vacancyId, detail, matchesPayload);
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
        { label: "Fit", value: payload.candidate.fitBandLabel || "Unrated" },
        { label: "Salary", value: payload.candidate.salaryExpectation || "Not specified" },
        { label: "Location", value: payload.candidate.location || "Not specified" },
        { label: "Format", value: payload.candidate.workFormat || "Not specified" },
        { label: "Updated", value: formatRelativeTime(payload.match.updatedAt) }
      ])}
      ${renderTextPanel("What happens now", payload.match.statusDescription || "", "")}
      ${renderTextPanel("Why this candidate", payload.candidate.whyThisCandidate || "", "")}
      ${renderChipPanel("Fit gaps", payload.candidate.gapSignals || [], "")}
      ${renderChipPanel("Strong signals", payload.candidate.matchSignals || [], "")}
      ${renderChipPanel("Watchouts", payload.candidate.concerns || [], "")}
      ${renderDetailSection("Timeline", [
        { label: "Last updated", value: formatEventTime(payload.match.updatedAt) },
        { label: "Invitation sent", value: payload.match.invitationSentAt ? formatEventTime(payload.match.invitationSentAt) : "" },
        { label: "Candidate reply", value: payload.match.candidateRespondedAt ? formatEventTime(payload.match.candidateRespondedAt) : "" },
        { label: "Manager decision", value: payload.match.managerDecisionAt ? formatEventTime(payload.match.managerDecisionAt) : "" }
      ])}
      ${hasDecisionSupport ? renderDetailSection("Decision support", [
        { label: "Interview state", value: payload.interview.stateLabel || "Not started" },
        { label: "Recommendation", value: payload.evaluation.recommendation || "N/A" },
        { label: "Interview summary", value: payload.evaluation.interviewSummary || "Interview feedback will appear here after the session.", full: true },
        { label: "Strengths", value: listChips(payload.evaluation.strengths || []), raw: true, full: true },
        { label: "Risks", value: listChips(payload.evaluation.risks || []), raw: true, full: true }
      ]) : ""}
      ${renderTextPanel(
        "Summary",
        firstNonEmpty(
          payload.candidate.summary && payload.candidate.summary.approvalSummaryText,
          payload.candidate.summary && payload.candidate.summary.experienceExcerpt
        ),
        "Helly is still preparing the candidate summary."
      )}
      ${renderChipPanel("Skills", payload.candidate.fullHardSkills || (payload.candidate.summary || {}).skills || [], "")}
      ${renderDetailSection("Answers", [
        { label: "Salary", value: payload.candidate.answers && payload.candidate.answers.salaryExpectation ? payload.candidate.answers.salaryExpectation : payload.candidate.salaryExpectation || "Not specified" },
        { label: "Location", value: payload.candidate.answers && payload.candidate.answers.location ? payload.candidate.answers.location : payload.candidate.location || "Not specified" },
        { label: "Country", value: payload.candidate.answers && payload.candidate.answers.countryCode ? payload.candidate.answers.countryCode : payload.candidate.countryCode || "" },
        { label: "City", value: payload.candidate.answers && payload.candidate.answers.city ? payload.candidate.answers.city : payload.candidate.city || "" },
        { label: "Work format", value: payload.candidate.answers && payload.candidate.answers.workFormat ? payload.candidate.answers.workFormat : payload.candidate.workFormat || "Not specified" },
        { label: "English", value: payload.candidate.answers && payload.candidate.answers.englishLevel ? payload.candidate.answers.englishLevel : "Not specified" },
        { label: "Preferred domains", value: formatJoinedValues(payload.candidate.answers && payload.candidate.answers.preferredDomains), full: true },
        { label: "Take-home roles", value: formatBooleanChoice(payload.candidate.answers && payload.candidate.answers.showTakeHomeTaskRoles, { yes: "Show", no: "Hide" }) || "Not set" },
        { label: "Live coding roles", value: formatBooleanChoice(payload.candidate.answers && payload.candidate.answers.showLiveCodingRoles, { yes: "Show", no: "Hide" }) || "Not set" },
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

  function bindViewControls() {
    Array.from(document.querySelectorAll("[data-view-scope]")).forEach((node) => {
      node.addEventListener("click", () => {
        const scope = node.getAttribute("data-view-scope");
        const key = node.getAttribute("data-view-key");
        const value = node.getAttribute("data-view-value");
        const scopeId = node.getAttribute("data-view-id");
        if (!scope || !key || !value) return;
        tapFeedback();
        updateViewState(scope, key, value, scopeId);
        if (scope === "manager-home") {
          if (state.managerHomePayload) {
            renderManagerHomeScreen(state.managerHomePayload);
            return;
          }
          renderRoute();
          return;
        }
        if (scope === "manager-vacancy" && scopeId) {
          const cachedPayload = state.managerVacancyPayloads[scopeId];
          if (cachedPayload) {
            renderManagerVacancyScreen(scopeId, cachedPayload.detail, cachedPayload.matchesPayload);
            return;
          }
        }
        renderRoute();
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
        const copy = homeLoadingCopy();
        renderLoadingState(copy.title, copy.body);
        await renderHome();
        return;
      }

      const parts = currentRoute.split(":");
      if (currentRoute === "candidate-profile") {
        renderLoadingState("Opening your profile", "Loading your latest summary, skills, and answers.");
        const payload = await api("/webapp/api/candidate/profile");
        renderCandidateProfileHome(payload.profile || {});
        return;
      }
      if (parts.length !== 2) {
        const copy = homeLoadingCopy();
        renderLoadingState(copy.title, copy.body);
        await renderHome();
        return;
      }
      const route = parts[0];
      const id = parts[1];
      if (route === "candidate-profile-section") {
        renderLoadingState("Opening your profile", "Loading your latest summary, skills, and answers.");
        const payload = await api("/webapp/api/candidate/profile");
        return renderCandidateProfileSection(payload.profile || {}, id);
      }
      if (route === "candidate-vacancy") {
        renderLoadingState("Opening role details", "Loading the latest status, summary, and role context.");
        return await renderCandidateVacancy(id);
      }
      if (route === "manager-vacancy") {
        renderLoadingState("Opening vacancy", "Loading the latest vacancy data and candidate pipeline.");
        return await renderManagerVacancy(id);
      }
      if (route === "manager-candidate") {
        renderLoadingState("Opening candidate", "Loading the latest candidate summary and decision signals.");
        return await renderManagerCandidate(id);
      }
      const copy = homeLoadingCopy();
      renderLoadingState(copy.title, copy.body);
      await renderHome();
    } catch (error) {
      renderError("Unable to load this screen", error.message || "Please try again in a moment.");
    }
  }

  async function boot() {
    try {
      initializeTheme();
      bindTelegramRuntime();
      renderRoleCheck("Checking your Telegram access and opening the right workspace.");
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
      renderError("Unable to open Helly", error.message || "Unknown error.");
    }
  }

  boot();
})();
