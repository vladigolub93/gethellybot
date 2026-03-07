import { AdminDashboardData } from "./admin-webapp.service";

export function renderAdminWebappOpenPage(data: AdminDashboardData): string {
  const now = escapeHtml(data.generatedAt || new Date().toISOString());

  const statCards = [
    ["Users", data.stats.usersTotal],
    ["Candidates", data.stats.candidatesTotal],
    ["Managers", data.stats.managersTotal],
    ["Jobs", data.stats.jobsTotal],
    ["Active jobs", data.stats.jobsActive],
    ["Matches", data.stats.matchesTotal],
    ["Contact shared", data.stats.matchesContactShared],
    ["Flags 24h", data.stats.qualityFlags24h],
    ["Candidate done", data.stats.candidateInterviewsCompleted],
    ["Candidate in progress", data.stats.candidateInterviewsInProgress],
    ["Manager done", data.stats.managerInterviewsCompleted],
    ["Manager in progress", data.stats.managerInterviewsInProgress],
  ]
    .map(
      ([label, value]) =>
        `<div class="stat"><div class="k">${escapeHtml(String(label))}</div><div class="v">${escapeHtml(String(value))}</div></div>`,
    )
    .join("");

  const jobs = data.jobs
    .slice(0, 40)
    .map(
      (job) => `
      <article class="item">
        <div class="title">${escapeHtml(job.title)}</div>
        <div class="meta">ID ${escapeHtml(job.id)}, ${escapeHtml(job.status)}, ${escapeHtml(job.workFormat)}</div>
        <div class="meta">Manager ${escapeHtml(String(job.managerTelegramUserId))}, interview ${escapeHtml(job.managerInterviewStatus || "not_started")}</div>
      </article>`,
    )
    .join("");

  const candidates = data.candidates
    .slice(0, 40)
    .map(
      (candidate) => `
      <article class="item">
        <div class="title">${escapeHtml(candidate.fullName || String(candidate.telegramUserId))}</div>
        <div class="meta">ID ${escapeHtml(String(candidate.telegramUserId))}, ${escapeHtml(candidate.profileStatus)}</div>
        <div class="meta">Interview ${escapeHtml(candidate.interviewStatus || "not_started")}, complete ${candidate.candidateProfileComplete ? "yes" : "no"}</div>
      </article>`,
    )
    .join("");

  const matches = data.matches
    .slice(0, 60)
    .map(
      (match) => `
      <article class="item">
        <div class="title">Match ${escapeHtml(match.id)}</div>
        <div class="meta">Candidate ${escapeHtml(String(match.candidateTelegramUserId))}, Manager ${escapeHtml(String(match.managerTelegramUserId))}</div>
        <div class="meta">Score ${escapeHtml(String(match.totalScore ?? "-"))}, status ${escapeHtml(match.status)}</div>
      </article>`,
    )
    .join("");

  const flags = data.qualityFlags
    .slice(0, 80)
    .map(
      (flag) => `
      <article class="item">
        <div class="title">${escapeHtml(flag.flag)}</div>
        <div class="meta">${escapeHtml(flag.entityType)}:${escapeHtml(flag.entityId)}</div>
        <div class="meta">${escapeHtml(flag.createdAt || "-")}</div>
      </article>`,
    )
    .join("");

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover" />
  <title>Helly Admin</title>
  <style>
    :root {
      --bg: #0a0a0d;
      --text: #f4f4f7;
      --muted: #9ca0ad;
      --accent: #7b2cff;
      --border: rgba(255, 255, 255, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at 12% -18%, #211239 0%, #0a0a0d 56%);
      color: var(--text);
      font-family: "SF Pro Text", "Inter", "Segoe UI", sans-serif;
      padding: 12px;
    }
    .app { max-width: 960px; margin: 0 auto; display: grid; gap: 12px; }
    .card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.02);
    }
    .logo { font-size: 30px; font-weight: 700; }
    .logo .mark { color: var(--accent); }
    .muted { color: var(--muted); font-size: 13px; }
    .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .stat { border: 1px solid var(--border); border-radius: 10px; padding: 10px; }
    .k { color: var(--muted); font-size: 12px; }
    .v { font-size: 22px; font-weight: 700; margin-top: 4px; }
    .section-title { margin: 0 0 8px; font-size: 16px; }
    .list { display: grid; gap: 8px; }
    .item { border: 1px solid var(--border); border-radius: 10px; padding: 10px; }
    .title { font-weight: 650; line-height: 1.3; }
    .meta { color: var(--muted); font-size: 13px; margin-top: 3px; line-height: 1.35; }
  </style>
</head>
<body>
  <div class="app">
    <section class="card">
      <div class="logo"><span class="mark">&gt;</span>helly<span class="mark">_</span></div>
      <div class="muted">Open access mode for testing, no login required.</div>
      <div class="muted">Snapshot: ${now}</div>
    </section>
    <section class="card">
      <h2 class="section-title">Stats</h2>
      <div class="stats">${statCards}</div>
    </section>
    <section class="card">
      <h2 class="section-title">Jobs</h2>
      <div class="list">${jobs || '<div class="muted">No jobs</div>'}</div>
    </section>
    <section class="card">
      <h2 class="section-title">Candidates</h2>
      <div class="list">${candidates || '<div class="muted">No candidates</div>'}</div>
    </section>
    <section class="card">
      <h2 class="section-title">Matches</h2>
      <div class="list">${matches || '<div class="muted">No matches</div>'}</div>
    </section>
    <section class="card">
      <h2 class="section-title">Quality Flags</h2>
      <div class="list">${flags || '<div class="muted">No flags</div>'}</div>
    </section>
  </div>
</body>
</html>`;
}

function escapeHtml(value: string): string {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
