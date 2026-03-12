(function () {
  const state = {
    sessionToken: null,
    session: null,
    apiCache: new Map(),
    backButtonHandlerBound: false,
  };

  const appEl = document.getElementById("app");
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const HOME_ROUTE = "home";

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function truncateText(value, maxLength) {
    const text = String(value || "").trim();
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

  function humanize(value) {
    if (!value) return "";
    return String(value)
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/\b\w/g, (character) => character.toUpperCase());
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
    const backgroundColor = "#f4efe7";
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
        tg.setBottomBarColor(backgroundColor);
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

  function tapFeedback() {
    try {
      if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.impactOccurred === "function") {
        tg.HapticFeedback.impactOccurred("light");
      }
    } catch (_) {}
  }

  function badgeTone(value) {
    const text = String(value || "").toLowerCase();
    if (text.includes("approved") || text.includes("completed") || text.includes("shared")) return "good";
    if (text.includes("reject") || text.includes("declined") || text.includes("expired") || text.includes("closed")) return "bad";
    if (text.includes("waiting") || text.includes("review") || text.includes("queued") || text.includes("pending")) return "warn";
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

  function sanitizeRoute(route) {
    return route && route !== "#" ? String(route).replace(/^#/, "") : HOME_ROUTE;
  }

  function splitRoute(route) {
    const normalized = sanitizeRoute(route);
    const separatorIndex = normalized.indexOf(":");
    if (separatorIndex === -1) {
      return { name: normalized, param: null };
    }
    return {
      name: normalized.slice(0, separatorIndex),
      param: normalized.slice(separatorIndex + 1),
    };
  }

  function getCurrentRoute() {
    return sanitizeRoute((window.history.state && window.history.state.route) || HOME_ROUTE);
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

  function handleTelegramBack() {
    if (getCurrentRoute() === HOME_ROUTE) {
      if (tg && typeof tg.close === "function") {
        tg.close();
      }
      return;
    }
    window.history.back();
  }

  function updateBackButton() {
    if (!tg || !tg.BackButton) return;
    if (getCurrentRoute() === HOME_ROUTE) {
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

  function renderStatusScreen(title, note, options) {
    const compact = options && options.compact;
    const titleMarkup = title && String(title).trim()
      ? `<h1 class="status-title">${escapeHtml(title)}</h1>`
      : "";
    appEl.innerHTML = `
      <section class="${compact ? "loading-shell" : "status-shell"}">
        <div class="brand-mark">Helly</div>
        ${titleMarkup}
        <p class="status-note">${escapeHtml(note)}</p>
      </section>
    `;
  }

  function renderLoading(note) {
    renderStatusScreen("", note || "Checking access and loading your screen.", { compact: true });
  }

  function renderBlocked(title, note) {
    renderStatusScreen(title, note, { compact: false });
  }

  function renderError(title, note) {
    renderStatusScreen(title, note, { compact: false });
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

  function renderBadge(value) {
    if (!value) return "";
    return `<span class="badge" data-tone="${badgeTone(value)}">${escapeHtml(value)}</span>`;
  }

  function renderStatsGrid(items) {
    const visibleItems = (items || []).filter((item) => item && item.value !== null && item.value !== undefined && item.value !== "");
    if (!visibleItems.length) return "";
    return `
      <section class="stats-grid">
        ${visibleItems.map((item) => `
          <article class="metric-card">
            <span class="metric-value">${escapeHtml(String(item.value))}</span>
            <span class="metric-label">${escapeHtml(item.label)}</span>
          </article>
        `).join("")}
      </section>
    `;
  }

  function renderMetaStrip(items) {
    const visibleItems = (items || []).filter((item) => item && String(item).trim());
    if (!visibleItems.length) return "";
    return `
      <div class="meta-strip">
        ${visibleItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
      </div>
    `;
  }

  function renderPills(values) {
    const items = (values || []).filter((value) => value && String(value).trim());
    if (!items.length) return "";
    return `
      <div class="pill-list">
        ${items.map((value) => `<span class="pill">${escapeHtml(value)}</span>`).join("")}
      </div>
    `;
  }

  function renderPageHeader(title, note) {
    const safeTitle = escapeHtml(title || "Untitled");
    const safeNote = note ? `<p class="page-note">${escapeHtml(note)}</p>` : "";
    return `
      <header class="page-header">
        <h1>${safeTitle}</h1>
        ${safeNote}
      </header>
    `;
  }

  function renderSectionBar(title, count) {
    const countMarkup = count === null || count === undefined ? "" : `<span class="section-count">${escapeHtml(String(count))}</span>`;
    return `
      <div class="section-bar">
        <h2>${escapeHtml(title)}</h2>
        ${countMarkup}
      </div>
    `;
  }

  function renderEmptyState(message) {
    return `<div class="empty-state">${escapeHtml(message)}</div>`;
  }

  function renderPreviewMetrics(items) {
    const visibleItems = (items || []).filter((item) => item && item.value && String(item.value).trim());
    if (!visibleItems.length) return "";
    return `
      <div class="mini-metrics">
        ${visibleItems.map((item) => `
          <span class="mini-metric">
            <span class="mini-metric-label">${escapeHtml(item.label)}</span>
            <span class="mini-metric-value">${escapeHtml(item.value)}</span>
          </span>
        `).join("")}
      </div>
    `;
  }

  function renderNavCard(options) {
    const actionAttr = options.route
      ? `data-route="${escapeHtml(options.route)}"`
      : `data-open-url="${escapeHtml(options.openUrl)}"`;
    return `
      <article class="nav-card" ${actionAttr}>
        <div class="card-head">
          <div class="card-head-copy">
            <span class="card-label">${escapeHtml(options.label || "")}</span>
            <h3 class="card-title">${escapeHtml(options.title || "Open")}</h3>
          </div>
          ${renderBadge(options.badge)}
        </div>
        ${options.note ? `<p class="card-note">${escapeHtml(options.note)}</p>` : ""}
        ${renderPreviewMetrics(options.metrics)}
      </article>
    `;
  }

  function renderInfoCard(title, rows) {
    const visibleRows = (rows || []).filter((row) => row && row.value !== null && row.value !== undefined && row.value !== "");
    if (!visibleRows.length) return "";
    return `
      <section class="detail-card">
        <h2 class="detail-title">${escapeHtml(title)}</h2>
        <dl class="detail-list">
          ${visibleRows.map((row) => `
            <div class="detail-row">
              <dt>${escapeHtml(row.label)}</dt>
              <dd>${row.raw ? row.value : escapeHtml(row.value)}</dd>
            </div>
          `).join("")}
        </dl>
      </section>
    `;
  }

  function renderTextCard(title, text, emptyText) {
    const content = String(firstNonEmpty(text, emptyText)).trim();
    if (!content) return "";
    return `
      <section class="detail-card">
        <h2 class="detail-title">${escapeHtml(title)}</h2>
        <div class="text-block">${escapeHtml(content).replace(/\n/g, "<br />")}</div>
      </section>
    `;
  }

  function renderSkillCard(title, skills) {
    const pills = renderPills(skills);
    if (!pills) return "";
    return `
      <section class="detail-card">
        <h2 class="detail-title">${escapeHtml(title)}</h2>
        ${pills}
      </section>
    `;
  }

  function renderCandidateVacancyCard(item) {
    return `
      <article class="entity-card" data-route="candidate-vacancy:${escapeHtml(item.id)}">
        <div class="card-head">
          <div class="card-head-copy">
            <h3 class="card-title">${escapeHtml(item.roleTitle || "Vacancy")}</h3>
          </div>
          ${renderBadge(item.stageLabel || humanize(item.stage))}
        </div>
        ${renderMetaStrip([
          item.budget || "Budget not set",
          item.workFormat ? humanize(item.workFormat) : "Format not set",
          item.updatedAt ? `Updated ${formatRelativeTime(item.updatedAt)}` : "",
        ])}
      </article>
    `;
  }

  function renderManagerVacancyCard(item) {
    return `
      <article class="entity-card" data-route="manager-vacancy:${escapeHtml(item.id)}">
        <div class="card-head">
          <div class="card-head-copy">
            <h3 class="card-title">${escapeHtml(item.roleTitle || "Vacancy")}</h3>
          </div>
          ${renderBadge(humanize(item.state))}
        </div>
        ${renderPreviewMetrics([
          { label: "Candidates", value: String(item.candidateCount || 0) },
          { label: "Pipeline", value: String(item.activePipelineCount || 0) },
          { label: "Connected", value: String(item.connectedCount || 0) },
        ])}
        ${renderMetaStrip([
          item.budget || "Budget not set",
          item.updatedAt ? `Updated ${formatRelativeTime(item.updatedAt)}` : "",
        ])}
      </article>
    `;
  }

  function renderManagerCandidateCard(item) {
    return `
      <article class="entity-card" data-route="manager-candidate:${escapeHtml(item.id)}">
        <div class="card-head">
          <div class="card-head-copy">
            <h3 class="card-title">${escapeHtml(item.candidateName || "Candidate")}</h3>
          </div>
          ${renderBadge(item.stageLabel || humanize(item.stage))}
        </div>
        ${item.summary && item.summary.approvalSummaryText
          ? `<p class="card-note">${escapeHtml(truncateText(item.summary.approvalSummaryText, 140))}</p>`
          : ""}
        ${renderMetaStrip([
          item.location || "Location not set",
          item.salaryExpectation || "Salary not set",
          item.workFormat ? humanize(item.workFormat) : "",
        ])}
      </article>
    `;
  }

  function renderReviewCard(interview, evaluation) {
    const hasInterviewInfo = Boolean(interview && (interview.stateLabel || interview.completedAt || interview.acceptedAt));
    const hasEvaluationInfo = Boolean(
      evaluation && (
        evaluation.interviewSummary ||
        evaluation.recommendation ||
        (evaluation.strengths || []).length ||
        (evaluation.risks || []).length
      )
    );
    if (!hasInterviewInfo && !hasEvaluationInfo) return "";
    const summaryText = evaluation && evaluation.interviewSummary
      ? `
        <div class="detail-card-embedded">
          <h3 class="detail-subtitle">Interview summary</h3>
          <div class="text-block">${escapeHtml(evaluation.interviewSummary).replace(/\n/g, "<br />")}</div>
        </div>
      `
      : "";
    const strengthsMarkup = (evaluation && evaluation.strengths && evaluation.strengths.length)
      ? `
        <div class="detail-card-embedded">
          <h3 class="detail-subtitle">Strengths</h3>
          ${renderPills(evaluation.strengths)}
        </div>
      `
      : "";
    const risksMarkup = (evaluation && evaluation.risks && evaluation.risks.length)
      ? `
        <div class="detail-card-embedded">
          <h3 class="detail-subtitle">Risks</h3>
          ${renderPills(evaluation.risks)}
        </div>
      `
      : "";
    return `
      <section class="detail-card">
        <h2 class="detail-title">Review</h2>
        ${renderInfoCard("Status", [
          { label: "Interview", value: interview && interview.stateLabel ? interview.stateLabel : "" },
          { label: "Recommendation", value: evaluation && evaluation.recommendation ? evaluation.recommendation : "" },
        ]).replace('<section class="detail-card">', '<div class="detail-card-embedded">').replace("</section>", "</div>")}
        ${summaryText}
        ${strengthsMarkup}
        ${risksMarkup}
      </section>
    `;
  }

  function buildAnswerPreview(answers) {
    return [
      answers && answers.salaryExpectation,
      answers && answers.location,
      answers && answers.workFormat ? humanize(answers.workFormat) : "",
    ].filter((value) => value && String(value).trim()).join(" • ");
  }

  function normalizeProfileAnswers(profile) {
    return profile && profile.answers ? profile.answers : {
      salaryExpectation: profile && profile.salaryExpectation,
      location: profile && profile.location,
      countryCode: profile && profile.countryCode,
      city: profile && profile.city,
      workFormat: profile && profile.workFormat,
    };
  }

  function renderCandidateHome(payload) {
    const items = payload.items || [];
    const profile = payload.profile || {};
    const waitingCount = items.filter((item) =>
      ["manager_decision_pending", "candidate_decision_pending", "candidate_applied", "manager_interview_requested"].includes(item.stage)
    ).length;
    const connectedCount = items.filter((item) => item.stage === "approved").length;
    const challenge = payload.cvChallenge || {};

    appEl.innerHTML = `
      <div class="page">
        ${renderStatsGrid([
          { label: "Vacancies", value: String(items.length) },
          { label: "Waiting", value: String(waitingCount) },
          { label: "Connected", value: String(connectedCount) },
        ])}
        <section class="hero-grid">
          ${challenge.eligible && challenge.launchUrl ? renderNavCard({
            label: "Game",
            title: challenge.title || "CV Challenge",
            note: truncateText(challenge.body || "Open the game.", 120),
            openUrl: challenge.launchUrl,
          }) : ""}
          ${renderNavCard({
            label: "Profile",
            title: firstNonEmpty(profile.targetRole, profile.headline, "Open profile"),
            note: truncateText(firstNonEmpty(
              profile.summary && profile.summary.approvalSummaryText,
              buildAnswerPreview(normalizeProfileAnswers(profile)),
              "Open your profile details."
            ), 140),
            route: "candidate-profile",
            metrics: [
              { label: "Location", value: profile.location || "" },
              { label: "Format", value: profile.workFormat ? humanize(profile.workFormat) : "" },
              { label: "Salary", value: profile.salaryExpectation || "" },
            ],
          })}
        </section>
        <section class="stack">
          ${renderSectionBar("Vacancies", items.length)}
          ${items.length ? items.map(renderCandidateVacancyCard).join("") : renderEmptyState("No vacancies yet.")}
        </section>
      </div>
    `;
    bindInteractiveNodes();
  }

  function renderCandidateProfile(profile) {
    const answers = normalizeProfileAnswers(profile);
    appEl.innerHTML = `
      <div class="page">
        ${renderPageHeader("Profile", firstNonEmpty(profile.targetRole, profile.headline, profile.name))}
        ${renderStatsGrid([
          { label: "Location", value: profile.location || "Not set" },
          { label: "Format", value: profile.workFormat ? humanize(profile.workFormat) : "Not set" },
          { label: "Salary", value: profile.salaryExpectation || "Not set" },
        ])}
        <section class="stack">
          ${renderNavCard({
            label: "Summary",
            title: "Saved summary",
            note: truncateText(firstNonEmpty(
              profile.summary && profile.summary.approvalSummaryText,
              profile.summary && profile.summary.experienceExcerpt,
              "No summary yet."
            ), 180),
            route: "candidate-profile-section:summary",
          })}
          ${renderNavCard({
            label: "CV",
            title: "CV text",
            note: truncateText(firstNonEmpty(profile.source && profile.source.text, "No CV text yet."), 180),
            route: "candidate-profile-section:cv",
          })}
          ${renderNavCard({
            label: "Answers",
            title: "Question answers",
            note: truncateText(firstNonEmpty(buildAnswerPreview(answers), "No saved answers yet."), 180),
            route: "candidate-profile-section:answers",
          })}
        </section>
      </div>
    `;
    bindInteractiveNodes();
  }

  function renderCandidateProfileSection(profile, sectionKey) {
    const answers = normalizeProfileAnswers(profile);
    if (sectionKey === "summary") {
      appEl.innerHTML = `
        <div class="page">
          ${renderPageHeader("Summary", firstNonEmpty(profile.targetRole, profile.headline, profile.name))}
          ${renderTextCard("Summary", firstNonEmpty(
            profile.summary && profile.summary.approvalSummaryText,
            profile.summary && profile.summary.experienceExcerpt
          ), "No summary yet.")}
          <div class="panel-grid">
            ${renderInfoCard("Profile", [
              { label: "Headline", value: profile.summary && profile.summary.headline ? profile.summary.headline : "" },
              { label: "Target role", value: profile.summary && profile.summary.targetRole ? profile.summary.targetRole : "" },
              { label: "Experience", value: profile.summary && profile.summary.yearsExperience ? `${profile.summary.yearsExperience}+ years` : "" },
            ])}
            ${renderSkillCard("Skills", profile.summary && profile.summary.skills)}
          </div>
        </div>
      `;
      return;
    }

    if (sectionKey === "cv") {
      appEl.innerHTML = `
        <div class="page">
          ${renderPageHeader("CV text", profile.name || "Profile")}
          ${renderTextCard("Saved CV text", profile.source && profile.source.text, "No CV text yet.")}
        </div>
      `;
      return;
    }

    appEl.innerHTML = `
      <div class="page">
        ${renderPageHeader("Question answers", profile.name || "Profile")}
        ${renderInfoCard("Answers", [
          { label: "Salary", value: answers.salaryExpectation || "Not set" },
          { label: "Location", value: answers.location || "Not set" },
          { label: "Country", value: answers.countryCode || "" },
          { label: "City", value: answers.city || "" },
          { label: "Work format", value: answers.workFormat ? humanize(answers.workFormat) : "Not set" },
        ])}
      </div>
    `;
  }

  function renderCandidateVacancy(payload) {
    const vacancy = payload.vacancy || {};
    const match = payload.match || {};
    appEl.innerHTML = `
      <div class="page">
        ${renderPageHeader(vacancy.roleTitle || "Vacancy", match.statusLabel || "")}
        ${renderStatsGrid([
          { label: "Stage", value: match.statusLabel || "Unknown" },
          { label: "Budget", value: vacancy.budget || "Not set" },
          { label: "Format", value: vacancy.workFormat ? humanize(vacancy.workFormat) : "Not set" },
          { label: "Updated", value: match.updatedAt ? formatRelativeTime(match.updatedAt) : "Unknown" },
        ])}
        <div class="panel-grid">
          ${renderTextCard("Summary", firstNonEmpty(
            vacancy.summary && vacancy.summary.approvalSummaryText,
            vacancy.summary && vacancy.summary.projectDescriptionExcerpt,
            vacancy.projectDescription
          ), "No summary yet.")}
          ${renderInfoCard("Details", [
            { label: "Seniority", value: vacancy.seniority ? humanize(vacancy.seniority) : "" },
            { label: "Countries", value: (vacancy.countriesAllowed || []).join(", ") || "" },
            { label: "Team size", value: vacancy.teamSize || "" },
          ])}
        </div>
        ${renderSkillCard("Tech stack", vacancy.primaryTechStack)}
        ${renderTextCard("Job description", vacancy.source && vacancy.source.text, "")}
      </div>
    `;
  }

  function renderManagerHome(payload) {
    const items = payload.items || [];
    const totalCandidates = items.reduce((sum, item) => sum + Number(item.candidateCount || 0), 0);
    const totalPipeline = items.reduce((sum, item) => sum + Number(item.activePipelineCount || 0), 0);
    const totalConnected = items.reduce((sum, item) => sum + Number(item.connectedCount || 0), 0);
    appEl.innerHTML = `
      <div class="page">
        ${renderStatsGrid([
          { label: "Vacancies", value: String(items.length) },
          { label: "Candidates", value: String(totalCandidates) },
          { label: "Pipeline", value: String(totalPipeline) },
          { label: "Connected", value: String(totalConnected) },
        ])}
        <section class="stack">
          ${renderSectionBar("Vacancies", items.length)}
          ${items.length ? items.map(renderManagerVacancyCard).join("") : renderEmptyState("No vacancies yet.")}
        </section>
      </div>
    `;
    bindInteractiveNodes();
  }

  function renderManagerVacancy(detail, matchesPayload) {
    const vacancy = detail.vacancy || {};
    const stats = detail.stats || {};
    const items = matchesPayload.items || [];
    appEl.innerHTML = `
      <div class="page">
        ${renderPageHeader(vacancy.roleTitle || "Vacancy", humanize(vacancy.state))}
        ${renderStatsGrid([
          { label: "Candidates", value: String(stats.candidateCount || 0) },
          { label: "Pipeline", value: String(stats.activePipelineCount || 0) },
          { label: "Connected", value: String(stats.connectedCount || 0) },
          { label: "Budget", value: vacancy.budget || "Not set" },
        ])}
        <div class="panel-grid">
          ${renderTextCard("Summary", firstNonEmpty(
            vacancy.summary && vacancy.summary.approvalSummaryText,
            vacancy.summary && vacancy.summary.projectDescriptionExcerpt,
            vacancy.projectDescription
          ), "No summary yet.")}
          ${renderInfoCard("Details", [
            { label: "Work format", value: vacancy.workFormat ? humanize(vacancy.workFormat) : "" },
            { label: "Countries", value: (vacancy.countriesAllowed || []).join(", ") || "" },
            { label: "Team size", value: vacancy.teamSize || "" },
            { label: "Opened", value: vacancy.openedAt ? formatRelativeTime(vacancy.openedAt) : "" },
          ])}
        </div>
        ${renderSkillCard("Tech stack", vacancy.primaryTechStack)}
        ${renderTextCard("Job description", vacancy.source && vacancy.source.text, "")}
        <section class="stack">
          ${renderSectionBar("Candidates", items.length)}
          ${items.length ? items.map(renderManagerCandidateCard).join("") : renderEmptyState("No candidates yet.")}
        </section>
      </div>
    `;
    bindInteractiveNodes();
  }

  function renderManagerCandidate(payload) {
    const candidate = payload.candidate || {};
    const answers = normalizeProfileAnswers(candidate);
    const summary = candidate.summary || {};
    appEl.innerHTML = `
      <div class="page">
        ${renderPageHeader(candidate.name || "Candidate", payload.vacancy && payload.vacancy.roleTitle ? payload.vacancy.roleTitle : "")}
        ${renderStatsGrid([
          { label: "Stage", value: payload.match && payload.match.statusLabel ? payload.match.statusLabel : "Unknown" },
          { label: "Salary", value: candidate.salaryExpectation || "Not set" },
          { label: "Format", value: candidate.workFormat ? humanize(candidate.workFormat) : "Not set" },
          { label: "Location", value: candidate.location || "Not set" },
        ])}
        <div class="panel-grid">
          ${renderTextCard("Summary", firstNonEmpty(
            summary.approvalSummaryText,
            summary.experienceExcerpt
          ), "No summary yet.")}
          ${renderInfoCard("Answers", [
            { label: "Location", value: answers.location || "Not set" },
            { label: "Country", value: answers.countryCode || "" },
            { label: "City", value: answers.city || "" },
            { label: "Work format", value: answers.workFormat ? humanize(answers.workFormat) : "Not set" },
          ])}
        </div>
        ${renderSkillCard("Skills", summary.skills)}
        ${renderTextCard("CV text", candidate.source && candidate.source.text, "")}
        ${renderReviewCard(payload.interview || {}, payload.evaluation || {})}
      </div>
    `;
  }

  function bindInteractiveNodes() {
    Array.from(document.querySelectorAll("[data-route], [data-open-url]")).forEach((node) => {
      const route = node.getAttribute("data-route");
      const openUrl = node.getAttribute("data-open-url");
      const isButton = node.tagName === "BUTTON";
      if (!isButton) {
        node.setAttribute("tabindex", "0");
        node.setAttribute("role", "button");
      }
      const activate = () => {
        tapFeedback();
        if (route) {
          pushRoute(route);
          return;
        }
        if (openUrl) {
          window.location.assign(openUrl);
        }
      };
      node.addEventListener("click", activate);
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
    });
  }

  async function renderHome() {
    if (!state.session) return;
    if (state.session.role === "candidate") {
      const payload = await api("/webapp/api/candidate/opportunities");
      renderCandidateHome(payload);
      return;
    }
    if (state.session.role === "hiring_manager") {
      const payload = await api("/webapp/api/hiring-manager/vacancies");
      renderManagerHome(payload);
      return;
    }
    renderBlocked(
      "Screen unavailable",
      "This WebApp now supports candidate and manager screens only."
    );
  }

  async function renderRoute() {
    if (!state.session) return;
    updateBackButton();
    try {
      const route = splitRoute(getCurrentRoute());
      if (route.name === HOME_ROUTE) {
        await renderHome();
        return;
      }

      if (route.name === "candidate-profile") {
        const payload = await api("/webapp/api/candidate/profile");
        renderCandidateProfile(payload.profile || {});
        return;
      }

      if (route.name === "candidate-profile-section") {
        const payload = await api("/webapp/api/candidate/profile");
        renderCandidateProfileSection(payload.profile || {}, route.param || "summary");
        return;
      }

      if (route.name === "candidate-vacancy" && route.param) {
        const payload = await api(`/webapp/api/candidate/opportunities/${route.param}`);
        renderCandidateVacancy(payload);
        return;
      }

      if (route.name === "manager-vacancy" && route.param) {
        const [detail, matchesPayload] = await Promise.all([
          api(`/webapp/api/hiring-manager/vacancies/${route.param}`),
          api(`/webapp/api/hiring-manager/vacancies/${route.param}/matches`),
        ]);
        renderManagerVacancy(detail, matchesPayload);
        return;
      }

      if (route.name === "manager-candidate" && route.param) {
        const payload = await api(`/webapp/api/hiring-manager/matches/${route.param}`);
        renderManagerCandidate(payload);
        return;
      }

      await renderHome();
    } catch (error) {
      renderError("Unable to load screen", error.message || "Unknown error.");
    }
  }

  async function boot() {
    try {
      bindTelegramRuntime();
      renderLoading("Checking access and loading your screen.");
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
          "This WebApp requires Telegram Mini App authentication."
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

      const initialRoute = sanitizeRoute(window.location.hash || HOME_ROUTE);
      window.history.replaceState({ route: initialRoute }, "", window.location.pathname + window.location.search);
      await renderRoute();
      window.addEventListener("popstate", renderRoute);
    } catch (error) {
      renderError("Unable to open Helly", error.message || "Unknown error.");
    }
  }

  boot();
})();
