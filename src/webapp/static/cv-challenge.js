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
    streak: 0,
    maxStreak: 0,
    multiplier: 1,
    stageStartedAt: 0,
    stageEndsAt: 0,
    lastSpawnAt: 0,
    missedCorrect: new Set(),
    correctTapCount: 0,
    wrongTapCount: 0,
    bonusTapCount: 0,
    shieldTapCount: 0,
    trapHitCount: 0,
    totalMistakes: 0,
    startedAt: 0,
    stageBannerEl: null,
    hudScoreEl: null,
    hudLivesEl: null,
    hudStageEl: null,
    progressSaveInFlight: false,
    lastProgressSavedAt: 0,
    recentCorrectTexts: [],
    recentWrongTexts: [],
    bannerText: "",
    bannerUntil: 0,
    latestRunIsBest: false,
    rngState: 0,
    practiceMode: false,
  };
  const TERMINAL_THEME = "terminal";

  function setAppMode(mode) {
    appEl.className = mode ? `app-mode-${mode}` : "";
  }

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

  function bindPress(element, handler) {
    if (!element || typeof handler !== "function") return;
    let touchHandled = false;
    const run = (event) => {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      handler();
    };
    element.addEventListener("click", (event) => {
      if (touchHandled) {
        touchHandled = false;
        return;
      }
      run(event);
    });
    element.addEventListener("touchend", (event) => {
      touchHandled = true;
      run(event);
    }, { passive: false });
  }

  function openDashboard() {
    const targetUrl = withCurrentTheme("/webapp");
    try {
      window.location.href = targetUrl;
    } catch (_) {
      window.location.assign(targetUrl);
    }
  }

  function currentAttemptId() {
    return state.bootstrap && state.bootstrap.attempt ? state.bootstrap.attempt.id : null;
  }

  function integerOr(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.round(parsed) : fallback;
  }

  function resultPayload(result) {
    return result && typeof result.result === "object" && result.result ? result.result : {};
  }

  function resultMistakes(result) {
    return integerOr(resultPayload(result).totalMistakes, 10 ** 6);
  }

  function compareResults(left, right) {
    if (!left && !right) return 0;
    if (left && !right) return 1;
    if (!left && right) return -1;

    const leftScore = integerOr(left.score, 0);
    const rightScore = integerOr(right.score, 0);
    if (leftScore !== rightScore) return leftScore > rightScore ? 1 : -1;

    const leftStage = integerOr(left.stageReached, 1);
    const rightStage = integerOr(right.stageReached, 1);
    if (leftStage !== rightStage) return leftStage > rightStage ? 1 : -1;

    const leftMistakes = resultMistakes(left);
    const rightMistakes = resultMistakes(right);
    if (leftMistakes !== rightMistakes) return leftMistakes < rightMistakes ? 1 : -1;

    return 0;
  }

  function isSameResult(left, right) {
    if (!left || !right) return false;
    if (left.id && right.id) return left.id === right.id;
    return compareResults(left, right) === 0;
  }

  function comboMultiplier(streak) {
    if (streak >= 6) return 3;
    if (streak >= 3) return 2;
    return 1;
  }

  function scoreValueForItem(item) {
    return item && item.kind === "bonus" ? 2 : 1;
  }

  function damageValueForItem(item) {
    return item && item.kind === "trap" ? 2 : 1;
  }

  function canSpawnShieldToken() {
    const totalLives = integerOr(state.bootstrap && state.bootstrap.challenge && state.bootstrap.challenge.totalLives, 3);
    return state.livesLeft < totalLives;
  }

  function currentStageNumber() {
    return integerOr(state.stageIndex, 0) + 1;
  }

  function defaultBannerText() {
    const comboText = isTerminalTheme() ? `combo_x${state.multiplier}` : `Combo x${state.multiplier}`;
    const stageText = state.practiceMode
      ? (isTerminalTheme()
        ? `endless_${String(currentStageNumber()).padStart(2, "0")}`
        : `Endless ${currentStageNumber()}`)
      : (isTerminalTheme()
        ? `stage_${String(currentStageNumber()).padStart(2, "0")}`
        : (currentStageConfig() && currentStageConfig().label) || `Stage ${currentStageNumber()}`);
    return isTerminalTheme() ? `[ ${stageText} | ${comboText} ]` : `${stageText} • ${comboText}`;
  }

  function setBannerMessage(text, durationMs) {
    state.bannerText = text;
    state.bannerUntil = performance.now() + durationMs;
    updateHud();
  }

  function hashSeedString(value) {
    let hash = 2166136261;
    const text = String(value || "helly");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function seedRandom(seedValue) {
    state.rngState = hashSeedString(seedValue) || 1;
  }

  function nextRandom() {
    let t = (state.rngState += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    const result = ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    state.rngState = t >>> 0;
    return result;
  }

  function dailyRunData() {
    return state.bootstrap && state.bootstrap.challenge ? state.bootstrap.challenge.dailyRun || null : null;
  }

  function formatDailyLabel(dailyRun) {
    if (!dailyRun || !dailyRun.dateLabel) return "";
    return `Daily run · ${dailyRun.dateLabel}`;
  }

  function accuracyPercentFromCounts(correctTapCount, wrongTapCount, missedCount) {
    const total = integerOr(correctTapCount, 0) + integerOr(wrongTapCount, 0) + integerOr(missedCount, 0);
    if (total <= 0) return 100;
    return Math.round((integerOr(correctTapCount, 0) / total) * 100);
  }

  function currentAccuracyPercent() {
    return accuracyPercentFromCounts(
      state.correctTapCount,
      state.wrongTapCount,
      state.missedCorrect.size
    );
  }

  function dailyGoals() {
    const dailyRun = dailyRunData();
    return dailyRun && Array.isArray(dailyRun.goals) ? dailyRun.goals : [];
  }

  function renderGoalList(goals, completedKeys) {
    const items = goals || [];
    if (!items.length) return "";
    const done = new Set(completedKeys || []);
    return `
      <div class="goal-list">
        ${items.map((goal) => `
          <span class="goal-item" data-complete="${done.has(goal.type) ? "true" : "false"}">${escapeHtml(goal.label)}</span>
        `).join("")}
      </div>
    `;
  }

  function evaluateDailyGoal(goal, metrics) {
    if (!goal || !metrics) return false;
    const data = metrics.result || {};
    if (goal.type === "accuracy_min") return integerOr(data.accuracyPercent, 0) >= integerOr(goal.target, 0);
    if (goal.type === "lives_left_min") return integerOr(metrics.livesLeft, 0) >= integerOr(goal.target, 0);
    if (goal.type === "max_streak_min") return integerOr(data.maxStreak, 0) >= integerOr(goal.target, 0);
    if (goal.type === "bonus_taps_min") return integerOr(data.bonusTapCount, 0) >= integerOr(goal.target, 0);
    if (goal.type === "mistakes_max") return integerOr(data.totalMistakes, 0) <= integerOr(goal.target, 0);
    if (goal.type === "shield_taps_min") return integerOr(data.shieldTapCount, 0) >= integerOr(goal.target, 0);
    if (goal.type === "score_min") return integerOr(metrics.score, 0) >= integerOr(goal.target, 0);
    return false;
  }

  function completedGoalTypes(metrics) {
    return dailyGoals()
      .filter((goal) => evaluateDailyGoal(goal, metrics))
      .map((goal) => goal.type);
  }

  function buildAchievements(metrics) {
    const data = metrics.result || {};
    const achievements = [];
    if (integerOr(data.maxStreak, 0) >= 6) achievements.push("Combo x3");
    if (integerOr(data.accuracyPercent, 0) >= 85) achievements.push("Sharp Eye");
    if (integerOr(data.totalMistakes, 0) === 0) achievements.push("Clean Run");
    if ((data.missedSkills || []).length === 0 && integerOr(metrics.stageReached, 1) >= baseStageCount()) achievements.push("No Misses");
    if (integerOr(data.bonusTapCount, 0) >= 2) achievements.push("Bonus Hunter");
    if (integerOr(data.shieldTapCount, 0) >= 1) achievements.push("Shield Keeper");
    if (integerOr(data.trapHitCount, 0) >= 1 && integerOr(metrics.livesLeft, 0) > 0) achievements.push("Trap Survivor");
    if (state.practiceMode && integerOr(metrics.stageReached, 1) >= baseStageCount() + 2) achievements.push("Endless Push");
    if (completedGoalTypes(metrics).length === dailyGoals().length && dailyGoals().length) achievements.push("Daily Goals");
    return achievements.slice(0, 8);
  }

  function rememberRecent(array, value) {
    if (!value) return;
    array.push(value);
    while (array.length > 2) {
      array.shift();
    }
  }

  function pickRandomAvoidRecent(list, recentValues) {
    if (!list || !list.length) return null;
    if (list.length === 1) return list[0];
    const recentSet = new Set(recentValues || []);
    const filtered = list.filter((item) => !recentSet.has(item));
    return pickRandom(filtered.length ? filtered : list);
  }

  function buildTokenLabel(text, kind) {
    return isTerminalTheme() ? `[ ${text} ]` : text;
  }

  function buildCurrentAttemptResult(won) {
    const accuracyPercent = currentAccuracyPercent();
    return {
      score: state.score,
      livesLeft: state.livesLeft,
      stageReached: currentStageNumber(),
      won: Boolean(won),
      result: {
        correctTapCount: state.correctTapCount,
        wrongTapCount: state.wrongTapCount,
        bonusTapCount: state.bonusTapCount,
        shieldTapCount: state.shieldTapCount,
        trapHitCount: state.trapHitCount,
        maxStreak: state.maxStreak,
        totalMistakes: state.totalMistakes,
        missedSkills: Array.from(state.missedCorrect),
        durationMs: Math.max(Date.now() - state.startedAt, 0),
        accuracyPercent,
        mode: state.practiceMode ? "endless_practice" : "challenge",
      },
    };
  }

  function renderAttemptMetrics(result, options) {
    if (!result) return "";
    const resultData = resultPayload(result);
    const accuracyPercent = resultData.accuracyPercent !== undefined
      ? integerOr(resultData.accuracyPercent, 0)
      : accuracyPercentFromCounts(
        integerOr(resultData.correctTapCount, 0),
        integerOr(resultData.wrongTapCount, 0),
        Array.isArray(resultData.missedSkills) ? resultData.missedSkills.length : 0
      );
    return `
      <div class="result-meta">
        <article class="result-meta-card">
          <span class="result-meta-value">${escapeHtml(integerOr(result.score, 0))}</span>
          <span class="result-meta-label">${isTerminalTheme() ? "score" : "Score"}</span>
        </article>
        <article class="result-meta-card">
          <span class="result-meta-value">${escapeHtml(integerOr(result.stageReached, 1))}</span>
          <span class="result-meta-label">${isTerminalTheme() ? "stage_reached" : "Stage reached"}</span>
        </article>
        <article class="result-meta-card">
          <span class="result-meta-value">${escapeHtml(integerOr(resultData.maxStreak, 0))}</span>
          <span class="result-meta-label">${isTerminalTheme() ? "max_streak" : "Max streak"}</span>
        </article>
        <article class="result-meta-card">
          <span class="result-meta-value">${escapeHtml(accuracyPercent)}%</span>
          <span class="result-meta-label">${isTerminalTheme() ? "accuracy" : "Accuracy"}</span>
        </article>
      </div>
      ${options && options.note ? `<p class="history-note">${escapeHtml(options.note)}</p>` : ""}
    `;
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
    setAppMode("panel");
    appEl.innerHTML = `
      <section class="screen-card">
        <p class="eyebrow">${isTerminalTheme() ? "boot_sequence" : "Loading"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(title)}</p>
        <p>${escapeHtml(body)}</p>
      </section>
    `;
  }

  function renderLocked(title, body) {
    setAppMode("panel");
    appEl.innerHTML = `
      <section class="locked-card">
        <p class="eyebrow">${isTerminalTheme() ? "access_denied" : "Challenge locked"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(title)}</p>
        <p>${escapeHtml(body)}</p>
        <div class="action-row">
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Open dashboard"}</button>
          <button id="close-app" class="button" type="button">${isTerminalTheme() ? "exit" : "Close"}</button>
        </div>
      </section>
    `;
    bindPress(document.getElementById("open-dashboard"), openDashboard);
    bindPress(document.getElementById("close-app"), () => {
      if (tg && typeof tg.close === "function") {
        tg.close();
      }
    });
  }

  function renderStartScreen() {
    setAppMode("panel");
    const challenge = state.bootstrap.challenge;
    const attempt = state.bootstrap.attempt || null;
    const lastResult = state.bootstrap.lastResult || null;
    const bestResult = state.bootstrap.bestResult || lastResult || null;
    const dailyRun = dailyRunData();
    const canResume = Boolean(attempt && attempt.resumable && attempt.progress);
    const historyNote = lastResult && bestResult && !isSameResult(lastResult, bestResult)
      ? `Last run: ${integerOr(lastResult.score, 0)} points, stage ${integerOr(lastResult.stageReached, 1)}.`
      : "";
    appEl.innerHTML = `
      <section class="screen-card">
        <p class="eyebrow">${isTerminalTheme() ? "cv_challenge_runtime" : "CV Challenge"}</p>
        <h1><span class="brand-angle">&gt;</span>helly<span class="brand-tail">_</span></h1>
        <p class="copy">${escapeHtml(challenge.subtitle)}</p>
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
        ${dailyRun ? `
          <div class="result-history">
            <p class="eyebrow">${escapeHtml(formatDailyLabel(dailyRun))}</p>
            ${renderGoalList(dailyGoals(), [])}
          </div>
        ` : ""}
        ${bestResult ? `
          <div class="result-history">
            <p class="eyebrow">${isTerminalTheme() ? "best_run" : "Best result"}</p>
            ${renderAttemptMetrics(bestResult, { note: historyNote })}
          </div>
        ` : ""}
        <div class="action-row">
          <button id="start-challenge" class="button" type="button">${canResume ? (isTerminalTheme() ? "resume run" : "Resume challenge") : (isTerminalTheme() ? "run challenge" : "Start challenge")}</button>
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Back to dashboard"}</button>
        </div>
      </section>
    `;
    bindPress(document.getElementById("start-challenge"), () => {
      if (canResume) {
        startGame(attempt.progress || {});
        return;
      }
      startGame();
    });
    bindPress(document.getElementById("open-dashboard"), openDashboard);
  }

  function renderGameShell() {
    setAppMode("game");
    appEl.innerHTML = `
      <section class="game-shell">
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
          <div id="stage-banner" class="stage-banner"></div>
          <canvas id="game-canvas" class="game-canvas"></canvas>
        </section>
        <footer class="game-footer" aria-label="How to play">
          <span class="game-footer-chip">${isTerminalTheme() ? "tap cv skills" : "Tap CV skills"}</span>
          <span class="game-footer-chip">${isTerminalTheme() ? "combo = more score" : "Combo = more score"}</span>
          <span class="game-footer-chip">${isTerminalTheme() ? "+2 token = bonus" : "+2 token = bonus"}</span>
          <span class="game-footer-chip">${isTerminalTheme() ? "+1 token = restore life" : "+1 token = restore life"}</span>
          <span class="game-footer-chip">${isTerminalTheme() ? "trap = -2 lives" : "Trap = -2 lives"}</span>
          <span class="game-footer-chip">${isTerminalTheme() ? "missed real skill = -1 life" : "Missed real skill = -1 life"}</span>
        </footer>
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
    setAppMode("panel");
    const missed = Array.from(state.missedCorrect).slice(0, 12);
    const currentResult = buildCurrentAttemptResult(won);
    const bestResult = state.bootstrap && state.bootstrap.bestResult ? state.bootstrap.bestResult : currentResult;
    const isNewBest = Boolean(state.latestRunIsBest);
    const resultData = resultPayload(currentResult);
    const completedGoals = completedGoalTypes(currentResult);
    const achievements = buildAchievements(currentResult);
    const showEndlessButton = Boolean(won && !state.practiceMode);
    appEl.innerHTML = `
      <section class="result-card">
        <p class="eyebrow">${won ? (isTerminalTheme() ? "run_complete" : "Challenge complete") : (isTerminalTheme() ? "run_failed" : "Game over")}</p>
        <h2>${state.practiceMode ? "Endless mode complete." : (won ? "You know your CV well." : "You missed some skills from your CV.")}</h2>
        <p class="result-copy">${isNewBest ? "New best run saved." : (state.practiceMode ? "Practice run finished. Your saved challenge result stayed untouched." : (won ? "Nice run. Helly is still matching you in the background." : "Try again and tap only the technologies that really appear in your profile."))}</p>
        <div class="result-meta">
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.score)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "score" : "Score"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(integerOr(bestResult.score, state.score))}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "best_score" : "Best score"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(currentStageNumber())}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "stage_reached" : "Stage reached"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.maxStreak)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "max_streak" : "Max streak"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(integerOr(resultData.accuracyPercent, 0))}%</span>
            <span class="result-meta-label">${isTerminalTheme() ? "accuracy" : "Accuracy"}</span>
          </article>
          <article class="result-meta-card">
            <span class="result-meta-value">${escapeHtml(state.totalMistakes)}</span>
            <span class="result-meta-label">${isTerminalTheme() ? "mistakes" : "Mistakes"}</span>
          </article>
        </div>
        ${dailyGoals().length ? `
          <div class="result-history">
            <p class="eyebrow">${isTerminalTheme() ? "daily_goals" : "Daily goals"}</p>
            ${renderGoalList(dailyGoals(), completedGoals)}
          </div>
        ` : ""}
        ${achievements.length ? `
          <div class="result-history">
            <p class="eyebrow">${isTerminalTheme() ? "achievements" : "Achievements"}</p>
            <div class="goal-list">
              ${achievements.map((item) => `<span class="goal-item" data-complete="true">${escapeHtml(item)}</span>`).join("")}
            </div>
          </div>
        ` : ""}
        ${missed.length ? `
          <div class="missed-list">
            ${missed.map((skill) => `<span class="missed-item">${escapeHtml(isTerminalTheme() ? `[ ${skill} ]` : skill)}</span>`).join("")}
          </div>
        ` : ""}
        <div class="action-row">
          ${showEndlessButton ? `<button id="continue-endless" class="ghost-button" type="button">${isTerminalTheme() ? "continue endless" : "Continue endless"}</button>` : ""}
          <button id="try-again" class="button" type="button">${isTerminalTheme() ? "rerun" : "Try again"}</button>
          <button id="open-dashboard" class="ghost-button" type="button">${isTerminalTheme() ? "cd /dashboard" : "Open dashboard"}</button>
        </div>
      </section>
    `;
    bindPress(document.getElementById("continue-endless"), () => {
      startEndlessPractice();
    });
    bindPress(document.getElementById("try-again"), async () => {
      await refreshBootstrap();
      startGame();
    });
    bindPress(document.getElementById("open-dashboard"), openDashboard);
  }

  function buildProgressSnapshot() {
    const now = performance.now();
    const stageConfig = currentStageConfig();
    const stageRemainingMs = state.stageEndsAt ? Math.max(Math.round(state.stageEndsAt - now), 0) : stageConfig.durationMs;
    const nextSpawnRemainingMs = state.lastSpawnAt
      ? Math.max(Math.round((state.lastSpawnAt + stageConfig.spawnIntervalMs) - now), 0)
      : stageConfig.spawnIntervalMs;
    return {
      score: state.score,
      livesLeft: state.livesLeft,
      stageIndex: state.stageIndex,
      stageReached: state.stageIndex + 1,
      streak: state.streak,
      maxStreak: state.maxStreak,
      multiplier: state.multiplier,
      stageRemainingMs,
      nextSpawnRemainingMs,
      elapsedMs: Math.max(Date.now() - state.startedAt, 0),
      missedSkills: Array.from(state.missedCorrect),
      correctTapCount: state.correctTapCount,
      wrongTapCount: state.wrongTapCount,
      bonusTapCount: state.bonusTapCount,
      shieldTapCount: state.shieldTapCount,
      trapHitCount: state.trapHitCount,
      totalMistakes: state.totalMistakes,
      recentCorrectTexts: state.recentCorrectTexts.slice(),
      recentWrongTexts: state.recentWrongTexts.slice(),
      rngState: state.rngState,
      practiceMode: state.practiceMode,
      objects: state.objects.map((item) => ({
        text: item.text,
        displayText: item.displayText,
        correct: Boolean(item.correct),
        kind: item.kind || (item.correct ? "correct" : "wrong"),
        width: item.width,
        height: item.height,
        x: item.x,
        y: item.y,
        speed: item.speed,
      })),
    };
  }

  async function saveProgressSnapshot(force) {
    if (!state.running || state.finishSubmitted || state.progressSaveInFlight || state.practiceMode) return;
    const attemptId = currentAttemptId();
    if (!attemptId) return;
    const now = performance.now();
    if (!force && now - state.lastProgressSavedAt < 1800) return;
    state.progressSaveInFlight = true;
    try {
      const snapshot = buildProgressSnapshot();
      await api("/webapp/api/candidate/cv-challenge/progress", {
        method: "POST",
        body: JSON.stringify({
          attemptId,
          score: state.score,
          livesLeft: state.livesLeft,
          stageReached: state.stageIndex + 1,
          progress: snapshot,
        }),
      });
      state.lastProgressSavedAt = performance.now();
    } catch (_) {
      state.lastProgressSavedAt = now;
    } finally {
      state.progressSaveInFlight = false;
    }
  }

  function restoreProgressSnapshot(snapshot) {
    const currentStage = stageConfigForIndex(Math.max(integerOr(snapshot.stageIndex, 0), 0));
    state.objects = (snapshot.objects || []).map((item) => ({
      id: state.nextId++,
      text: item.text,
      displayText: item.displayText || item.text,
      correct: Boolean(item.correct),
      kind: item.kind || (item.correct ? "correct" : "wrong"),
      width: item.width,
      height: item.height,
      x: item.x,
      y: item.y,
      speed: item.speed,
    }));
    state.score = Number(snapshot.score || 0);
    state.livesLeft = Number(snapshot.livesLeft || state.bootstrap.challenge.totalLives);
    state.stageIndex = Math.max(integerOr(snapshot.stageIndex, 0), 0);
    state.streak = integerOr(snapshot.streak, 0);
    state.maxStreak = integerOr(snapshot.maxStreak, 0);
    state.multiplier = integerOr(snapshot.multiplier, comboMultiplier(state.streak));
    state.missedCorrect = new Set(snapshot.missedSkills || []);
    state.correctTapCount = Number(snapshot.correctTapCount || 0);
    state.wrongTapCount = Number(snapshot.wrongTapCount || 0);
    state.bonusTapCount = Number(snapshot.bonusTapCount || 0);
    state.shieldTapCount = Number(snapshot.shieldTapCount || 0);
    state.trapHitCount = Number(snapshot.trapHitCount || 0);
    state.totalMistakes = Number(snapshot.totalMistakes || 0);
    state.recentCorrectTexts = Array.isArray(snapshot.recentCorrectTexts) ? snapshot.recentCorrectTexts.slice(-2) : [];
    state.recentWrongTexts = Array.isArray(snapshot.recentWrongTexts) ? snapshot.recentWrongTexts.slice(-2) : [];
    state.rngState = integerOr(snapshot.rngState, state.rngState || 1);
    state.practiceMode = Boolean(snapshot.practiceMode);
    state.startedAt = Date.now() - Math.max(Number(snapshot.elapsedMs || 0), 0);
    const now = performance.now();
    const stageRemainingMs = Math.max(Number(snapshot.stageRemainingMs || currentStage.durationMs), 0);
    const nextSpawnRemainingMs = Math.max(Number(snapshot.nextSpawnRemainingMs || currentStage.spawnIntervalMs), 0);
    state.stageStartedAt = now - Math.max(currentStage.durationMs - stageRemainingMs, 0);
    state.stageEndsAt = now + stageRemainingMs;
    state.lastSpawnAt = now - Math.max(currentStage.spawnIntervalMs - nextSpawnRemainingMs, 0);
    state.lastFrameTime = now;
  }

  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function resizeCanvas() {
    if (!state.canvas) return;
    const host = state.canvas.parentElement || state.canvas;
    const rect = host.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    state.canvas.style.width = `${Math.max(Math.floor(rect.width), 320)}px`;
    state.canvas.style.height = `${Math.max(Math.floor(rect.height), 320)}px`;
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
          state.correctTapCount += 1;
          state.streak += 1;
          state.maxStreak = Math.max(state.maxStreak, state.streak);
          state.multiplier = comboMultiplier(state.streak);
          state.score += scoreValueForItem(item) * state.multiplier;
          if (item.kind === "bonus") {
            state.bonusTapCount += 1;
            setBannerMessage(isTerminalTheme() ? `[ bonus +${2 * state.multiplier} ]` : `Bonus +${2 * state.multiplier}`, 1100);
          } else if (item.kind === "shield") {
            state.shieldTapCount += 1;
            state.livesLeft = Math.min(
              state.livesLeft + 1,
              integerOr(state.bootstrap && state.bootstrap.challenge && state.bootstrap.challenge.totalLives, 3)
            );
            setBannerMessage(isTerminalTheme() ? "[ shield +1 life ]" : "Shield +1 life", 1100);
          } else if (state.multiplier > 1) {
            setBannerMessage(
              isTerminalTheme() ? `[ combo_x${state.multiplier} ]` : `Combo x${state.multiplier}`,
              900
            );
          }
          tapFeedback("success");
        } else {
          state.wrongTapCount += 1;
          registerMistake({
            damage: damageValueForItem(item),
            reason: item.kind || "wrong",
          });
          tapFeedback("error");
        }
        updateHud();
        return;
      }
    }
  }

  function registerMistake(options) {
    const damage = Math.max(integerOr(options && options.damage, 1), 1);
    state.totalMistakes += 1;
    state.streak = 0;
    state.multiplier = 1;
    state.livesLeft = Math.max(state.livesLeft - damage, 0);
    if (options && options.missedSkill) {
      state.missedCorrect.add(options.missedSkill);
      setBannerMessage(
        isTerminalTheme() ? `[ missed ${options.missedSkill} ]` : `Missed ${options.missedSkill}`,
        1200
      );
    } else if (options && options.reason === "trap") {
      state.trapHitCount += 1;
      setBannerMessage(isTerminalTheme() ? "[ trap -2 lives ]" : "Trap -2 lives", 1200);
    } else {
      setBannerMessage(isTerminalTheme() ? "[ -1 life ]" : "Wrong tap -1 life", 900);
    }
    if (state.livesLeft <= 0) {
      finishGame(false);
    }
  }

  function baseStageCount() {
    return state.bootstrap && state.bootstrap.challenge && Array.isArray(state.bootstrap.challenge.stages)
      ? state.bootstrap.challenge.stages.length
      : 0;
  }

  function stageConfigForIndex(index) {
    const stages = state.bootstrap && state.bootstrap.challenge ? state.bootstrap.challenge.stages || [] : [];
    if (!stages.length) {
      return {
        index: integerOr(index, 0) + 1,
        label: `Stage ${integerOr(index, 0) + 1}`,
        durationMs: 18000,
        spawnIntervalMs: 900,
        speedMin: 90,
        speedMax: 120,
        correctChance: 0.5,
        bonusChance: 0.12,
        shieldChance: 0.05,
        trapChance: 0.1,
      };
    }
    if (index < stages.length) return stages[index];

    const last = stages[stages.length - 1];
    const extra = index - stages.length + 1;
    return {
      index: index + 1,
      label: `Stage ${index + 1}`,
      durationMs: Math.max(integerOr(last.durationMs, 18000) - (extra * 350), 13000),
      spawnIntervalMs: Math.max(integerOr(last.spawnIntervalMs, 640) - (extra * 45), 300),
      speedMin: integerOr(last.speedMin, 134) + (extra * 16),
      speedMax: integerOr(last.speedMax, 168) + (extra * 20),
      correctChance: Math.max(Number(last.correctChance || 0.38) - (extra * 0.025), 0.22),
      bonusChance: Math.min(Number(last.bonusChance || 0.16) + (extra * 0.015), 0.28),
      shieldChance: Math.max(Number(last.shieldChance || 0.04) - (extra * 0.004), 0.01),
      trapChance: Math.min(Number(last.trapChance || 0.14) + (extra * 0.018), 0.3),
    };
  }

  function currentStageConfig() {
    return stageConfigForIndex(Math.max(integerOr(state.stageIndex, 0), 0));
  }

  function effectiveStageConfig() {
    const base = currentStageConfig();
    let spawnFactor = 1;
    let speedFactor = 1;
    const accuracy = currentAccuracyPercent();
    const actionCount = state.correctTapCount + state.wrongTapCount + state.missedCorrect.size;

    if (actionCount >= 6 && accuracy >= 82) {
      spawnFactor *= 0.9;
      speedFactor *= 1.12;
    } else if (actionCount >= 5 && accuracy <= 58) {
      spawnFactor *= 1.12;
      speedFactor *= 0.9;
    }

    if (state.streak >= 6) {
      spawnFactor *= 0.92;
      speedFactor *= 1.08;
    }

    if (state.livesLeft <= 1) {
      spawnFactor *= 1.14;
      speedFactor *= 0.88;
    }

    return {
      ...base,
      spawnIntervalMs: Math.max(Math.round(integerOr(base.spawnIntervalMs, 900) * spawnFactor), 260),
      speedMin: Math.max(Math.round(integerOr(base.speedMin, 90) * speedFactor), 50),
      speedMax: Math.max(Math.round(integerOr(base.speedMax, 120) * speedFactor), 70),
    };
  }

  function pickRandom(list) {
    return list[Math.floor(nextRandom() * list.length)];
  }

  function spawnItem() {
    const challenge = state.bootstrap.challenge;
    const stage = effectiveStageConfig();
    const correctChance = Number(stage && stage.correctChance);
    const correct = nextRandom() < (Number.isFinite(correctChance) ? correctChance : 0.5);
    const sourceList = correct ? challenge.correctSkills : challenge.distractorSkills;
    const text = pickRandomAvoidRecent(sourceList, correct ? state.recentCorrectTexts : state.recentWrongTexts);
    if (!text) return;
    let kind = correct ? "correct" : "wrong";
    if (correct) {
      const shieldChance = canSpawnShieldToken() ? Number(stage && stage.shieldChance) : 0;
      const bonusChance = Number(stage && stage.bonusChance);
      const roll = nextRandom();
      if (roll < (Number.isFinite(shieldChance) ? shieldChance : 0)) {
        kind = "shield";
      } else if (roll < (Number.isFinite(shieldChance) ? shieldChance : 0) + (Number.isFinite(bonusChance) ? bonusChance : 0.12)) {
        kind = "bonus";
      }
    } else if (nextRandom() < (Number.isFinite(Number(stage && stage.trapChance)) ? Number(stage.trapChance) : 0.1)) {
      kind = "trap";
    }

    state.ctx.font = cssVar("--canvas-font", "700 18px system-ui, sans-serif");
    const displayText = buildTokenLabel(text, kind);
    const textWidth = state.ctx.measureText(displayText).width;
    const width = Math.min(state.canvas.clientWidth - 24, textWidth + 28);
    const height = 46;
    const maxX = Math.max(state.canvas.clientWidth - width - 12, 12);
    state.objects.push({
      id: state.nextId++,
      text,
      displayText,
      correct,
      kind,
      width,
      height,
      x: 12 + nextRandom() * Math.max(maxX - 12, 1),
      y: -height - 12,
      speed: stage.speedMin + nextRandom() * (stage.speedMax - stage.speedMin),
    });
    rememberRecent(correct ? state.recentCorrectTexts : state.recentWrongTexts, text);
  }

  function updateHud() {
    if (state.hudScoreEl) state.hudScoreEl.textContent = String(state.score);
    if (state.hudLivesEl) state.hudLivesEl.textContent = isTerminalTheme() ? "■".repeat(state.livesLeft) : String(state.livesLeft);
    if (state.hudStageEl) {
      state.hudStageEl.textContent = state.practiceMode
        ? (isTerminalTheme()
          ? `endless_${String(currentStageNumber()).padStart(2, "0")}`
          : `${currentStageNumber()} / ∞`)
        : (isTerminalTheme()
          ? `stage_${String(currentStageNumber()).padStart(2, "0")}`
          : `${currentStageNumber()} / ${baseStageCount()}`);
    }
    if (state.stageBannerEl) {
      if (state.bannerText && performance.now() < state.bannerUntil) {
        state.stageBannerEl.textContent = state.bannerText;
      } else {
        state.bannerText = "";
        state.bannerUntil = 0;
        state.stageBannerEl.textContent = defaultBannerText();
      }
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
    const currentResult = buildCurrentAttemptResult(won);
    if (state.bootstrap && !state.practiceMode) {
      const previousBest = state.bootstrap.bestResult || null;
      state.latestRunIsBest = !previousBest || compareResults(currentResult, previousBest) > 0;
      state.bootstrap.lastResult = currentResult;
      if (compareResults(currentResult, state.bootstrap.bestResult) >= 0) {
        state.bootstrap.bestResult = currentResult;
      }
    }
    submitResult(won).finally(() => {
      renderResult(won);
    });
  }

  async function submitResult(won) {
    if (state.finishSubmitted || !state.bootstrap || !state.bootstrap.attempt || state.practiceMode) return;
    state.finishSubmitted = true;
    const currentResult = buildCurrentAttemptResult(won);
    const result = resultPayload(currentResult);
    try {
      await api("/webapp/api/candidate/cv-challenge/finish", {
        method: "POST",
        body: JSON.stringify({
          attemptId: state.bootstrap.attempt.id,
          score: state.score,
          livesLeft: state.livesLeft,
          stageReached: currentStageNumber(),
          won,
          result,
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
      if (!state.practiceMode && state.stageIndex >= baseStageCount() - 1) {
        finishGame(true);
        return;
      }
      state.stageIndex += 1;
      state.stageStartedAt = now;
      state.stageEndsAt = now + currentStageConfig().durationMs;
      state.lastSpawnAt = now;
      setBannerMessage(
        state.practiceMode
          ? (isTerminalTheme() ? `[ endless_${String(currentStageNumber()).padStart(2, "0")} ]` : `Endless ${currentStageNumber()}`)
          : (isTerminalTheme() ? `[ ${currentStageConfig().label.toLowerCase().replace(/\s+/g, "_")} ]` : currentStageConfig().label),
        1200
      );
      updateHud();
    }

    if (now - state.lastSpawnAt >= effectiveStageConfig().spawnIntervalMs) {
      spawnItem();
      state.lastSpawnAt = now;
    }

    const deltaSeconds = Math.min((state.lastFrameTime ? now - state.lastFrameTime : 16) / 1000, 0.05);
    state.lastFrameTime = now;

    state.objects = state.objects.filter((item) => {
      item.y += item.speed * deltaSeconds;
      if (item.y > state.canvas.clientHeight + item.height) {
        if (item.correct) {
          registerMistake({
            damage: 1,
            missedSkill: item.text,
            reason: item.kind || "correct",
          });
        }
        return false;
      }
      return true;
    });

    updateHud();
    draw();
    saveProgressSnapshot(false);
    if (state.running) {
      state.frameId = window.requestAnimationFrame(frame);
    }
  }

  function startGame(resumeSnapshot) {
    renderGameShell();
    state.running = true;
    state.finishSubmitted = false;
    state.practiceMode = false;
    state.objects = [];
    state.nextId = 1;
    state.score = 0;
    state.livesLeft = state.bootstrap.challenge.totalLives;
    state.stageIndex = 0;
    state.streak = 0;
    state.maxStreak = 0;
    state.multiplier = 1;
    state.stageStartedAt = 0;
    state.stageEndsAt = 0;
    state.lastSpawnAt = 0;
    state.lastFrameTime = 0;
    state.missedCorrect = new Set();
    state.correctTapCount = 0;
    state.wrongTapCount = 0;
    state.bonusTapCount = 0;
    state.shieldTapCount = 0;
    state.trapHitCount = 0;
    state.totalMistakes = 0;
    state.startedAt = Date.now();
    state.progressSaveInFlight = false;
    state.lastProgressSavedAt = 0;
    state.recentCorrectTexts = [];
    state.recentWrongTexts = [];
    state.bannerText = "";
    state.bannerUntil = 0;
    state.latestRunIsBest = false;
    seedRandom((dailyRunData() && dailyRunData().seed) || currentAttemptId() || "helly");
    if (resumeSnapshot && Object.keys(resumeSnapshot).length) {
      restoreProgressSnapshot(resumeSnapshot);
    }
    updateHud();
    state.frameId = window.requestAnimationFrame(frame);
  }

  function startEndlessPractice() {
    const snapshot = {
      score: state.score,
      livesLeft: Math.max(state.livesLeft, 1),
      stageIndex: baseStageCount(),
      stageReached: baseStageCount() + 1,
      streak: state.streak,
      maxStreak: state.maxStreak,
      multiplier: state.multiplier,
      stageRemainingMs: stageConfigForIndex(baseStageCount()).durationMs,
      nextSpawnRemainingMs: 0,
      elapsedMs: Math.max(Date.now() - state.startedAt, 0),
      missedSkills: Array.from(state.missedCorrect),
      correctTapCount: state.correctTapCount,
      wrongTapCount: state.wrongTapCount,
      bonusTapCount: state.bonusTapCount,
      shieldTapCount: state.shieldTapCount,
      trapHitCount: state.trapHitCount,
      totalMistakes: state.totalMistakes,
      recentCorrectTexts: state.recentCorrectTexts.slice(),
      recentWrongTexts: state.recentWrongTexts.slice(),
      rngState: state.rngState,
      practiceMode: true,
      objects: [],
    };
    startGame(snapshot);
  }

  async function refreshBootstrap() {
    const bootstrap = await api("/webapp/api/candidate/cv-challenge/bootstrap");
    state.bootstrap = bootstrap;
    return bootstrap;
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
      const bootstrap = await refreshBootstrap();
      if (!bootstrap.eligible) {
        renderLocked(bootstrap.title || "Challenge unavailable", bootstrap.body || "The challenge is not available right now.");
        return;
      }

      renderStartScreen();
    } catch (error) {
      renderLocked("Unable to open CV Challenge", error.message || "Unknown error.");
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      saveProgressSnapshot(true);
    }
  });
  window.addEventListener("pagehide", () => {
    saveProgressSnapshot(true);
  });

  boot();
})();
