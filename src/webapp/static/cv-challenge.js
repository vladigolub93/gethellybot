(function () {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  const appEl = document.getElementById("app");
  const state = {
    sessionToken: null,
    bootstrap: null,
    theme: "terminal",
    running: false,
    finishSubmitted: false,
    frameId: null,
    canvas: null,
    ctx: null,
    objects: [],
    nextId: 1,
    score: 0,
    livesLeft: 3,
    stageIndex: 0,
    stageStartedAt: 0,
    stageEndsAt: 0,
    lastSpawnAt: 0,
    missedCorrect: new Set(),
    correctTapCount: 0,
    wrongTapCount: 0,
    totalMistakes: 0,
    startedAt: 0,
    stageBannerEl: null,
    hudScoreEl: null,
    hudLivesEl: null,
    hudStageEl: null,
  };
  const TERMINAL_THEME = "terminal";

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
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
      if (typeof tg.setHeaderColor === "function") tg.setHeaderColor(backgroundColor);
    } catch (_) {}
    try {
      if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor(backgroundColor);
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
    window.history.replaceState(window.history.state || {}, "", `${currentUrl.pathname}${currentUrl.search}`);
  }

  function withCurrentTheme(url) {
    const nextUrl = new URL(url, window.location.origin);
    nextUrl.searchParams.delete("theme");
    return nextUrl.toString();
  }

  function setTheme(theme) {
    state.theme = normalizeTheme(theme);
    document.documentElement.setAttribute("data-theme", state.theme);
    syncThemeInUrl();
    applyTelegramChrome();
    if (state.running && state.canvas && state.ctx) {
      draw();
    }
  }

  function initializeTheme() {
    setTheme(TERMINAL_THEME);
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

  function renderTerminalConsole(title, rows) {
    if (!isTerminalTheme()) return "";
    const visibleRows = (rows || []).filter((row) => row && row.value !== null && row.value !== undefined && row.value !== "");
    if (!visibleRows.length) return "";
    return `
      <section class="terminal-console">
        <div class="terminal-console-head">
          <span class="terminal-title">${escapeHtml(title)}</span>
        </div>
        <div class="terminal-console-body">
          ${visibleRows.map((row) => `
            <div class="terminal-line">
              <span class="terminal-key">${escapeHtml(terminalToken(row.key || row.label))}</span>
              <span class="terminal-separator">::</span>
              <span class="terminal-value">${escapeHtml(row.value)}</span>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  }

  function tapFeedback(kind) {
    try {
      if (!tg || !tg.HapticFeedback) return;
      if (kind === "error" && typeof tg.HapticFeedback.notificationOccurred === "function") {
        tg.HapticFeedback.notificationOccurred("error");
        return;
      }
      if (typeof tg.HapticFeedback.impactOccurred === "function") {
        tg.HapticFeedback.impactOccurred(kind === "success" ? "light" : "soft");
      }
    } catch (_) {}
  }

  async function api(path, options) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(state.sessionToken ? { Authorization: `Bearer ${state.sessionToken}` } : {}),
        ...((options && options.headers) || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || "Request failed.");
    }
    return data;
  }

  function renderLoading(title, body) {
    appEl.innerHTML = `
      <section class="screen-card">
        <p class="eyebrow">${isTerminalTheme() ? "boot_sequence" : "Loading"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(title)}</p>
        <p>${escapeHtml(body)}</p>
        ${renderTerminalConsole("helly@cv-challenge:~ % boot", [
          { label: "runtime", key: "runtime", value: "telegram_webapp" },
          { label: "profile_sync", key: "profile", value: "pending" },
        ])}
      </section>
    `;
  }

  function renderLocked(title, body) {
    appEl.innerHTML = `
      <section class="locked-card">
        <p class="eyebrow">${isTerminalTheme() ? "access_denied" : "Challenge locked"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(title)}</p>
        <p>${escapeHtml(body)}</p>
        ${renderTerminalConsole("helly@cv-challenge:~ % access", [
          { label: "status", key: "status", value: "locked" },
          { label: "hint", key: "hint", value: "return_to_dashboard" },
        ])}
        <div class="action-row">
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Open dashboard"}</button>
          <button id="close-app" class="button" type="button">${isTerminalTheme() ? "exit" : "Close"}</button>
        </div>
      </section>
    `;
    document.getElementById("open-dashboard").addEventListener("click", () => {
      window.location.assign(withCurrentTheme("/webapp"));
    });
    document.getElementById("close-app").addEventListener("click", () => {
      if (tg && typeof tg.close === "function") {
        tg.close();
      }
    });
  }

  function renderStartScreen() {
    const challenge = state.bootstrap.challenge;
    appEl.innerHTML = `
      <section class="screen-card">
        <p class="eyebrow">${isTerminalTheme() ? "cv_challenge_runtime" : "CV Challenge"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(challenge.subtitle)}</p>
        ${renderTerminalConsole("helly@cv-challenge:~ % cat challenge.txt", [
          { label: "correct skills", key: "correct", value: String(challenge.correctSkills.length) },
          { label: "distractors", key: "wrong_pool", value: String(challenge.distractorSkills.length) },
          { label: "stages", key: "stages", value: String(challenge.stages.length) },
          { label: "lives", key: "lives", value: String(challenge.totalLives) },
        ])}
        <div class="meta-strip">
          <article class="meta-card">
            <span class="meta-value">${escapeHtml(challenge.correctSkills.length)}</span>
            <span class="meta-label">${isTerminalTheme() ? "cv_skills" : "CV skills"}</span>
          </article>
          <article class="meta-card">
            <span class="meta-value">${escapeHtml(challenge.totalLives)}</span>
            <span class="meta-label">${isTerminalTheme() ? "lives" : "Lives"}</span>
          </article>
          <article class="meta-card">
            <span class="meta-value">${escapeHtml(challenge.stages.length)}</span>
            <span class="meta-label">${isTerminalTheme() ? "stages" : "Stages"}</span>
          </article>
        </div>
        <div class="action-row">
          <button id="start-challenge" class="button" type="button">${isTerminalTheme() ? "run challenge" : "Start challenge"}</button>
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Back to dashboard"}</button>
        </div>
      </section>
    `;
    document.getElementById("start-challenge").addEventListener("click", startGame);
    document.getElementById("open-dashboard").addEventListener("click", () => {
      window.location.assign(withCurrentTheme("/webapp"));
    });
  }

  function renderGameShell() {
    appEl.innerHTML = `
      <section class="game-shell">
        ${renderTerminalConsole("helly@cv-challenge:~ % ./run", [
          { label: "mode", key: "mode", value: "live" },
          { label: "rule", key: "rule", value: "tap_valid_tokens_only" },
        ])}
        <header class="hud">
          <article class="hud-card">
            <span id="hud-score" class="hud-value">0</span>
            <span class="hud-label">${isTerminalTheme() ? "score" : "Score"}</span>
          </article>
          <article class="hud-card">
            <span id="hud-lives" class="hud-value">3</span>
            <span class="hud-label">${isTerminalTheme() ? "lives" : "Lives"}</span>
          </article>
          <article class="hud-card">
            <span id="hud-stage" class="hud-value">1 / 3</span>
            <span class="hud-label">${isTerminalTheme() ? "stage" : "Stage"}</span>
          </article>
        </header>
        <section class="canvas-wrap">
          <div id="stage-banner" class="stage-banner">${isTerminalTheme() ? "[ stage_01 ]" : "Stage 1"}</div>
          <canvas id="game-canvas" class="game-canvas"></canvas>
        </section>
        <p class="canvas-hint">${isTerminalTheme() ? "tap tokens from your real cv. ignore foreign tokens. missing a valid one costs 1 life." : "Tap only the technologies that truly appear in your CV. Missing a real one also costs a life."}</p>
      </section>
    `;
    state.canvas = document.getElementById("game-canvas");
    state.ctx = state.canvas.getContext("2d");
    state.stageBannerEl = document.getElementById("stage-banner");
    state.hudScoreEl = document.getElementById("hud-score");
    state.hudLivesEl = document.getElementById("hud-lives");
    state.hudStageEl = document.getElementById("hud-stage");
    bindCanvas();
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
  }

  function renderResult(won) {
    const missed = Array.from(state.missedCorrect).slice(0, 12);
    appEl.innerHTML = `
      <section class="result-card">
        <p class="eyebrow">${won ? (isTerminalTheme() ? "run_complete" : "Challenge complete") : (isTerminalTheme() ? "run_failed" : "Game over")}</p>
        <h2>${won ? "You know your CV well." : "You missed some skills from your CV."}</h2>
        <p class="result-copy">${won ? "Nice run. Helly is still matching you in the background." : "Try again and tap only the technologies that really appear in your profile."}</p>
        ${renderTerminalConsole("helly@cv-challenge:~ % cat result.txt", [
          { label: "score", key: "score", value: String(state.score) },
          { label: "stage reached", key: "stage", value: String(state.stageIndex + 1) },
          { label: "mistakes", key: "mistakes", value: String(state.totalMistakes) },
          { label: "status", key: "status", value: won ? "complete" : "failed" },
        ])}
        <div class="result-meta">
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.score)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "score" : "Score"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.stageIndex + 1)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "stage_reached" : "Stage reached"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.correctTapCount)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "correct_taps" : "Correct taps"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.totalMistakes)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "mistakes" : "Mistakes"}</span>
          </article>
        </div>
        ${missed.length ? `
          <div class="missed-list">
            ${missed.map((skill) => `<span class="missed-item">${escapeHtml(isTerminalTheme() ? `[ ${skill} ]` : skill)}</span>`).join("")}
          </div>
        ` : ""}
        <div class="action-row">
          <button id="try-again" class="button" type="button">${isTerminalTheme() ? "rerun" : "Try again"}</button>
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Open dashboard"}</button>
        </div>
      </section>
    `;
    document.getElementById("try-again").addEventListener("click", () => window.location.reload());
    document.getElementById("open-dashboard").addEventListener("click", () => {
      window.location.assign(withCurrentTheme("/webapp"));
    });
  }

  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function resizeCanvas() {
    if (!state.canvas) return;
    const rect = state.canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    state.canvas.width = Math.max(Math.floor(rect.width * ratio), 320);
    state.canvas.height = Math.max(Math.floor(rect.height * ratio), 440);
    state.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function bindCanvas() {
    state.canvas.addEventListener("pointerdown", onPointerDown);
  }

  function onPointerDown(event) {
    if (!state.running) return;
    const rect = state.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    for (let index = state.objects.length - 1; index >= 0; index -= 1) {
      const item = state.objects[index];
      if (x >= item.x && x <= item.x + item.width && y >= item.y && y <= item.y + item.height) {
        state.objects.splice(index, 1);
        if (item.correct) {
          state.score += 1;
          state.correctTapCount += 1;
          tapFeedback("success");
        } else {
          state.wrongTapCount += 1;
          registerMistake();
          tapFeedback("error");
        }
        updateHud();
        return;
      }
    }
  }

  function registerMistake(missedSkill) {
    state.totalMistakes += 1;
    state.livesLeft = Math.max(state.livesLeft - 1, 0);
    if (missedSkill) {
      state.missedCorrect.add(missedSkill);
    }
    if (state.livesLeft <= 0) {
      finishGame(false);
    }
  }

  function currentStageConfig() {
    return state.bootstrap.challenge.stages[Math.min(state.stageIndex, state.bootstrap.challenge.stages.length - 1)];
  }

  function pickRandom(list) {
    return list[Math.floor(Math.random() * list.length)];
  }

  function spawnItem() {
    const challenge = state.bootstrap.challenge;
    const stage = currentStageConfig();
    const correct = Math.random() >= 0.5;
    const text = pickRandom(correct ? challenge.correctSkills : challenge.distractorSkills);
    if (!text) return;
    state.ctx.font = cssVar("--canvas-font", "700 18px system-ui, sans-serif");
    const displayText = isTerminalTheme() ? `[ ${text} ]` : text;
    const textWidth = state.ctx.measureText(displayText).width;
    const width = Math.min(state.canvas.clientWidth - 24, textWidth + 28);
    const height = 46;
    const maxX = Math.max(state.canvas.clientWidth - width - 12, 12);
    state.objects.push({
      id: state.nextId++,
      text,
      displayText,
      correct,
      width,
      height,
      x: 12 + Math.random() * Math.max(maxX - 12, 1),
      y: -height - 12,
      speed: stage.speedMin + Math.random() * (stage.speedMax - stage.speedMin),
    });
  }

  function updateHud() {
    if (state.hudScoreEl) state.hudScoreEl.textContent = String(state.score);
    if (state.hudLivesEl) state.hudLivesEl.textContent = isTerminalTheme() ? "■".repeat(state.livesLeft) : String(state.livesLeft);
    if (state.hudStageEl) {
      state.hudStageEl.textContent = isTerminalTheme()
        ? `stage_${String(state.stageIndex + 1).padStart(2, "0")}`
        : `${state.stageIndex + 1} / ${state.bootstrap.challenge.stages.length}`;
    }
    if (state.stageBannerEl) {
      state.stageBannerEl.textContent = isTerminalTheme()
        ? `[ stage_${String(state.stageIndex + 1).padStart(2, "0")} ]`
        : currentStageConfig().label;
    }
  }

  function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }

  function draw() {
    const width = state.canvas.clientWidth;
    const height = state.canvas.clientHeight;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, width, height);

    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, cssVar("--canvas-bg-start", "#11111a"));
    gradient.addColorStop(1, cssVar("--canvas-bg-end", "#09090d"));
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = cssVar("--canvas-glow", "rgba(140,40,255,0.14)");
    ctx.beginPath();
    ctx.arc(width * 0.18, height * 0.12, Math.min(width, height) * 0.16, 0, Math.PI * 2);
    ctx.fill();

    const gridColor = cssVar("--canvas-grid", "rgba(255,255,255,0.04)");
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    for (let y = 20; y < height; y += 28) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    state.objects.forEach((item) => {
      roundRect(ctx, item.x, item.y, item.width, item.height, 16);
      ctx.fillStyle = item.correct
        ? cssVar("--token-fill-correct", "rgba(12,12,18,0.92)")
        : cssVar("--token-fill-wrong", "rgba(12,12,18,0.92)");
      ctx.fill();
      ctx.strokeStyle = item.correct
        ? cssVar("--token-stroke-correct", "rgba(255,255,255,0.08)")
        : cssVar("--token-stroke-wrong", "rgba(255,255,255,0.08)");
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.font = cssVar("--canvas-font", "700 18px system-ui, sans-serif");
      ctx.fillStyle = cssVar("--token-text", "#f8f8fb");
      ctx.textBaseline = "middle";
      ctx.fillText(item.displayText || item.text, item.x + 14, item.y + item.height / 2);
    });
  }

  function finishGame(won) {
    if (!state.running) return;
    state.running = false;
    if (state.frameId) {
      window.cancelAnimationFrame(state.frameId);
      state.frameId = null;
    }
    submitResult(won).finally(() => {
      renderResult(won);
    });
  }

  async function submitResult(won) {
    if (state.finishSubmitted || !state.bootstrap || !state.bootstrap.attempt) return;
    state.finishSubmitted = true;
    try {
      await api("/webapp/api/candidate/cv-challenge/finish", {
        method: "POST",
        body: JSON.stringify({
          attemptId: state.bootstrap.attempt.id,
          score: state.score,
          livesLeft: state.livesLeft,
          stageReached: state.stageIndex + 1,
          won,
          result: {
            correctTapCount: state.correctTapCount,
            wrongTapCount: state.wrongTapCount,
            totalMistakes: state.totalMistakes,
            missedSkills: Array.from(state.missedCorrect),
            durationMs: Date.now() - state.startedAt,
          },
        }),
      });
    } catch (_) {}
  }

  function frame(now) {
    if (!state.running) return;
    const stage = currentStageConfig();

    if (!state.stageStartedAt) {
      state.stageStartedAt = now;
      state.stageEndsAt = now + stage.durationMs;
      state.lastSpawnAt = now;
    }

    if (now >= state.stageEndsAt) {
      if (state.stageIndex >= state.bootstrap.challenge.stages.length - 1) {
        finishGame(true);
        return;
      }
      state.stageIndex += 1;
      state.stageStartedAt = now;
      state.stageEndsAt = now + currentStageConfig().durationMs;
      state.lastSpawnAt = now;
      updateHud();
    }

    if (now - state.lastSpawnAt >= currentStageConfig().spawnIntervalMs) {
      spawnItem();
      state.lastSpawnAt = now;
    }

    const deltaSeconds = Math.min((state.lastFrameTime ? now - state.lastFrameTime : 16) / 1000, 0.05);
    state.lastFrameTime = now;

    state.objects = state.objects.filter((item) => {
      item.y += item.speed * deltaSeconds;
      if (item.y > state.canvas.clientHeight + item.height) {
        if (item.correct) {
          registerMistake(item.text);
        }
        return false;
      }
      return true;
    });

    updateHud();
    draw();
    if (state.running) {
      state.frameId = window.requestAnimationFrame(frame);
    }
  }

  function startGame() {
    renderGameShell();
    state.running = true;
    state.finishSubmitted = false;
    state.objects = [];
    state.nextId = 1;
    state.score = 0;
    state.livesLeft = state.bootstrap.challenge.totalLives;
    state.stageIndex = 0;
    state.stageStartedAt = 0;
    state.stageEndsAt = 0;
    state.lastSpawnAt = 0;
    state.lastFrameTime = 0;
    state.missedCorrect = new Set();
    state.correctTapCount = 0;
    state.wrongTapCount = 0;
    state.totalMistakes = 0;
    state.startedAt = Date.now();
    updateHud();
    state.frameId = window.requestAnimationFrame(frame);
  }

  async function boot() {
    try {
      initializeTheme();
      bindTelegramRuntime();
      if (tg) {
        if (typeof tg.ready === "function") tg.ready();
        if (typeof tg.expand === "function") tg.expand();
        if (typeof tg.enableVerticalSwipes === "function") tg.enableVerticalSwipes();
        if (tg.BackButton && typeof tg.BackButton.hide === "function") tg.BackButton.hide();
      }

      const initDataFromQuery = new URLSearchParams(window.location.search).get("initData");
      const initData = (tg && tg.initData) || initDataFromQuery;
      if (!initData) {
        renderLocked(
          "Open this challenge from Helly",
          "This screen needs Telegram Mini App auth. Open it from the Helly bot button inside Telegram."
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

      renderLoading("Syncing your candidate profile", "Preparing the skills Helly extracted from your CV.");
      const bootstrap = await api("/webapp/api/candidate/cv-challenge/bootstrap");
      state.bootstrap = bootstrap;
      if (!bootstrap.eligible) {
        renderLocked(bootstrap.title || "Challenge unavailable", bootstrap.body || "The challenge is not available right now.");
        return;
      }

      renderStartScreen();
    } catch (error) {
      renderLocked("Unable to open CV Challenge", error.message || "Unknown error.");
    }
  }

  boot();
})();
