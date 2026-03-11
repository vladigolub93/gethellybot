(function () {
  const state = {
    sessionToken: null,
    session: null,
  };

  const appEl = document.getElementById("app");
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

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

  function renderDetailSection(title, rows) {
    return `
      <section class="detail-panel">
        <h3 class="section-title">${escapeHtml(title)}</h3>
        <dl class="detail-grid">
          ${rows
            .filter((row) => row.value !== null && row.value !== undefined && row.value !== "")
            .map((row) => `
              <div class="${row.full ? "span-full" : ""}">
                <dt>${escapeHtml(row.label)}</dt>
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
    if (!location.hash || location.hash === "#home") {
      tg.BackButton.hide();
      return;
    }
    tg.BackButton.show();
  }

  function pushRoute(route) {
    location.hash = route;
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
      appEl.innerHTML = `
        <section class="screen-header">
          <p class="eyebrow">Candidate view</p>
          <h2>My Opportunities</h2>
          <p>Your current matches, interview progress and saved profile context.</p>
        </section>
        <section class="detail-panel">
          <h3 class="section-title">Profile Snapshot</h3>
          <dl class="detail-grid">
            <div><dt>Location</dt><dd>${escapeHtml(payload.profile.location || "Not set")}</dd></div>
            <div><dt>Work format</dt><dd>${escapeHtml(payload.profile.workFormat || "Not set")}</dd></div>
            <div><dt>Salary</dt><dd>${escapeHtml(payload.profile.salaryExpectation || "Not set")}</dd></div>
            <div class="span-full"><dt>Summary</dt><dd>${escapeHtml((payload.profile.summary || {}).approvalSummaryText || "No summary yet.")}</dd></div>
          </dl>
        </section>
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card" data-route="candidate-match:${item.id}">
              <div class="card-head">
                <div>
                  <p class="eyebrow">Opportunity</p>
                  <h3>${escapeHtml(item.roleTitle || "Untitled role")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.stageLabel)}">${escapeHtml(item.stageLabel || "Unknown")}</span>
              </div>
              <div class="meta-stack">
                <p class="meta-line">Budget: ${escapeHtml(item.budget || "Not specified")}</p>
                <p class="meta-line">Interview: ${escapeHtml(item.interviewStateLabel || "Not started")}</p>
                <p class="meta-line">Updated: ${escapeHtml(formatRelativeTime(item.updatedAt))}</p>
              </div>
            </article>
          `).join("") : `<div class="empty-state">No opportunities yet. Once Helly creates matches for you, they will appear here.</div>`}
        </section>
        <p class="footer-note">Read-only mode. Apply, skip and interview actions still happen in the bot chat.</p>
      `;
      bindCards();
      return;
    }

    if (role === "hiring_manager") {
      const payload = await api("/webapp/api/hiring-manager/vacancies");
      const items = payload.items || [];
      appEl.innerHTML = `
        <section class="screen-header">
          <p class="eyebrow">Manager view</p>
          <h2>My Vacancies</h2>
          <p>One clean view of your live candidate pipeline and interview progress.</p>
        </section>
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card" data-route="manager-vacancy:${item.id}">
              <div class="card-head">
                <div>
                  <p class="eyebrow">Vacancy</p>
                  <h3>${escapeHtml(item.roleTitle || "Untitled vacancy")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.state)}">${escapeHtml(item.state || "Unknown")}</span>
              </div>
              <div class="meta-stack">
                <p class="meta-line">Candidates: ${escapeHtml(item.candidateCount)}</p>
                <p class="meta-line">Active pipeline: ${escapeHtml(item.activePipelineCount)}</p>
                <p class="meta-line">Completed interviews: ${escapeHtml(item.completedInterviewCount)}</p>
                <p class="meta-line">Updated: ${escapeHtml(formatRelativeTime(item.updatedAt))}</p>
              </div>
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
      appEl.innerHTML = `
        <section class="screen-header">
          <p class="eyebrow">Admin view</p>
          <h2>All Vacancies</h2>
          <p>Read-only visibility across the full Helly production pipeline.</p>
        </section>
        <section class="list">
          ${items.length ? items.map((item) => `
            <article class="card" data-route="admin-vacancy:${item.id}">
              <div class="card-head">
                <div>
                  <p class="eyebrow">Vacancy</p>
                  <h3>${escapeHtml(item.roleTitle || "Untitled vacancy")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.state)}">${escapeHtml(item.state || "Unknown")}</span>
              </div>
              <div class="meta-stack">
                <p class="meta-line">Manager: ${escapeHtml(item.managerName || "Unknown")}</p>
                <p class="meta-line">Candidates: ${escapeHtml(item.candidateCount)}</p>
                <p class="meta-line">Completed interviews: ${escapeHtml(item.completedInterviewCount)}</p>
                <p class="meta-line">Updated: ${escapeHtml(formatRelativeTime(item.updatedAt))}</p>
              </div>
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
      <section class="screen-header">
        <p class="eyebrow">Opportunity detail</p>
        <h2>${escapeHtml(payload.vacancy.roleTitle || "Opportunity")}</h2>
        <p>${escapeHtml(payload.match.statusLabel || "Unknown stage")}</p>
      </section>
      ${renderDetailSection("Match", [
        { label: "Stage", value: payload.match.statusLabel || "Unknown" },
        { label: "Updated", value: formatRelativeTime(payload.match.updatedAt) },
        { label: "Interview", value: payload.interview.stateLabel || "Not started" },
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
        { label: "Interview state", value: payload.interview.stateLabel || "Not started" },
        { label: "Summary", value: payload.evaluation.interviewSummary || "No interview summary yet.", full: true },
        { label: "Recommendation", value: payload.evaluation.recommendation || "Not available" },
        { label: "Final score", value: payload.evaluation.finalScore == null ? "Not available" : String(payload.evaluation.finalScore) },
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
      <section class="screen-header">
        <p class="eyebrow">${escapeHtml(rolePrefix)} vacancy</p>
        <h2>${escapeHtml(vacancy.roleTitle || "Vacancy")}</h2>
        <p>${escapeHtml(vacancy.state || "Unknown")} • ${escapeHtml(stats.candidateCount)} candidates</p>
      </section>
      ${renderDetailSection("Vacancy snapshot", [
        { label: "Budget", value: vacancy.budget || "Not specified" },
        { label: "Work format", value: vacancy.workFormat || "Not specified" },
        { label: "Allowed countries", value: (vacancy.countriesAllowed || []).join(", ") || "Not specified", full: true },
        { label: "Tech stack", value: (vacancy.primaryTechStack || []).join(", ") || "Not specified", full: true },
        { label: "Project", value: vacancy.projectDescription || "Not specified", full: true },
        { label: "Summary", value: (vacancy.summary || {}).approvalSummaryText || "No stored summary.", full: true }
      ])}
      <section class="detail-panel">
        <h3 class="section-title">Candidate pipeline</h3>
        <div class="list">
          ${items.length ? items.map((item) => `
            <article class="card" data-route="${rolePrefix}-match:${item.id}">
              <div class="card-head">
                <div>
                  <p class="eyebrow">Candidate</p>
                  <h3>${escapeHtml(item.candidateName || "Candidate")}</h3>
                </div>
                <span class="badge" data-tone="${badgeTone(item.stageLabel)}">${escapeHtml(item.stageLabel || "Unknown")}</span>
              </div>
              <div class="meta-stack">
                <p class="meta-line">Location: ${escapeHtml(item.location || "Not specified")}</p>
                <p class="meta-line">Salary: ${escapeHtml(item.salaryExpectation || "Not specified")}</p>
                <p class="meta-line">Interview: ${escapeHtml(item.interviewStateLabel || "Not started")}</p>
                <p class="meta-line">Summary: ${escapeHtml(truncateText(((item.summary || {}).approvalSummaryText) || "No summary yet.", 110))}</p>
              </div>
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
      <section class="screen-header">
        <p class="eyebrow">Match detail</p>
        <h2>${escapeHtml(payload.candidate.name || "Candidate")}</h2>
        <p>${escapeHtml(payload.vacancy.roleTitle || "Vacancy")} • ${escapeHtml(payload.match.statusLabel || "Unknown stage")}</p>
      </section>
      ${renderDetailSection("Candidate", [
        { label: "Location", value: payload.candidate.location || "Not specified" },
        { label: "Work format", value: payload.candidate.workFormat || "Not specified" },
        { label: "Salary", value: payload.candidate.salaryExpectation || "Not specified" },
        { label: "Summary", value: (payload.candidate.summary || {}).approvalSummaryText || "No saved summary.", full: true },
        { label: "Skills", value: listChips((payload.candidate.summary || {}).skills || []), raw: true, full: true }
      ])}
      ${renderDetailSection("Interview", [
        { label: "State", value: payload.interview.stateLabel || "Not started" },
        { label: "Summary", value: payload.evaluation.interviewSummary || "No interview summary yet.", full: true },
        { label: "Recommendation", value: payload.evaluation.recommendation || "Not available" },
        { label: "Final score", value: payload.evaluation.finalScore == null ? "Not available" : String(payload.evaluation.finalScore) },
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
      node.addEventListener("click", () => pushRoute(route));
      node.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          pushRoute(route);
        }
      });
    });
  }

  async function renderRoute() {
    updateBackButton();
    const hash = (location.hash || "#home").replace(/^#/, "");
    if (!state.session) return;
    try {
      if (hash === "home") {
        await renderHome();
        return;
      }

      const parts = hash.split(":");
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
      if (tg) {
        tg.ready();
        tg.expand();
        if (tg.BackButton) {
          tg.BackButton.onClick(() => window.history.back());
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
      if (!location.hash) {
        location.hash = "home";
      }
      await renderRoute();
      window.addEventListener("hashchange", renderRoute);
    } catch (error) {
      renderError("Unable to open Helly Dashboard", error.message || "Unknown error.");
    }
  }

  boot();
})();
