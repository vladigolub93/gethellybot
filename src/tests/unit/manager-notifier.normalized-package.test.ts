import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { ManagerNotifier } from "../../notifications/manager-notifier";
import { TelegramClient } from "../../telegram/telegram.client";

interface SentMessage {
  source: string;
  chatId: number;
  text: string;
  replyMarkup?: unknown;
  kind?: unknown;
}

class TelegramClientMock {
  public readonly sent: SentMessage[] = [];

  async sendUserMessage(input: SentMessage): Promise<void> {
    this.sent.push(input);
  }
}

class LoggerMock implements Logger {
  public readonly debugCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];

  debug(message: string, meta?: Record<string, unknown>): void {
    this.debugCalls.push({ message, meta });
  }

  info(): void {
    return;
  }

  warn(): void {
    return;
  }

  error(): void {
    return;
  }
}

type NotifyParams = Parameters<ManagerNotifier["notifyCandidateApplied"]>[0];

function makeParams(overrides: Partial<NotifyParams> = {}): NotifyParams {
  return {
    chatId: 11001,
    matchId: "match_001",
    candidateUserId: 99001,
    score: 87,
    candidateSummary: "Legacy candidate summary",
    candidateTechnicalSummary: null,
    explanationMessage: "Legacy explanation",
    ...overrides,
  };
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function testCleanPackagePath(): Promise<void> {
  const telegram = new TelegramClientMock();
  const logger = new LoggerMock();
  const notifier = new ManagerNotifier(telegram as unknown as TelegramClient, logger);

  return notifier.notifyCandidateApplied(
    makeParams({
      candidateSummary: "  Clean normalized summary  ",
      matchLifecycle: {
        status: "candidate_applied",
        candidateDecision: "applied",
        managerDecision: "pending",
        contactShared: false,
      },
      interviewLifecycle: {
        sessionState: "interviewing_candidate",
        hasInterviewPlan: true,
        answerCount: 2,
        currentQuestionIndex: 1,
      },
      evaluation: {
        interviewConfidenceLevel: "high",
      },
    }),
  ).then(() => {
    assert.equal(telegram.sent.length, 1);
    assert.equal(telegram.sent[0]?.source, "manager_notifier.candidate_applied");
    assert.match(telegram.sent[0]?.text ?? "", /Candidate applied to your role/);
    assert.match(telegram.sent[0]?.text ?? "", /Technical depth: Clean normalized summary/);

    const builtLogs = findDebug(logger, "manager_package.normalized_built");
    assert.equal(builtLogs.length, 1);
    assert.equal(builtLogs[0]?.meta?.matchStatus, "SENT_TO_MANAGER");
    assert.equal(builtLogs[0]?.meta?.interviewStatus, "IN_PROGRESS");
    assert.equal(builtLogs[0]?.meta?.evaluationStatus, "STRONG");
    assert.equal(builtLogs[0]?.meta?.isCandidateSentToManager, true);

    const noteLogs = findDebug(logger, "manager_package.normalization_notes");
    assert.equal(noteLogs.length, 0);
  });
}

function testAmbiguousNormalizationStillRendersSafely(): Promise<void> {
  const telegram = new TelegramClientMock();
  const logger = new LoggerMock();
  const notifier = new ManagerNotifier(telegram as unknown as TelegramClient, logger);

  return notifier.notifyCandidateApplied(
    makeParams({
      candidateSummary: "Ambiguous fallback summary",
      matchLifecycle: {
        candidateDecision: "rejected",
        managerDecision: "accepted",
      },
      interviewLifecycle: {
        interviewRunStatus: "abandoned",
        interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
      },
      evaluation: {
        profileStatus: "rejected_non_technical",
        recommendation: "strong",
      },
    }),
  ).then(() => {
    assert.equal(telegram.sent.length, 1);
    assert.match(telegram.sent[0]?.text ?? "", /Technical depth: Ambiguous fallback summary/);

    const builtLogs = findDebug(logger, "manager_package.normalized_built");
    assert.equal(builtLogs.length, 1);
    assert.equal(builtLogs[0]?.meta?.matchStatus, null);
    assert.equal(builtLogs[0]?.meta?.interviewStatus, null);
    assert.equal(builtLogs[0]?.meta?.evaluationStatus, null);

    const noteLogs = findDebug(logger, "manager_package.normalization_notes");
    assert.equal(noteLogs.length, 1);
    const notes = (noteLogs[0]?.meta?.notes ?? []) as string[];
    const risks = (noteLogs[0]?.meta?.risks ?? []) as string[];
    assert.equal(notes.includes("MATCH_STATUS_UNCLEAR"), true);
    assert.equal(notes.includes("INTERVIEW_STATUS_UNCLEAR"), true);
    assert.equal(notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
    assert.equal(risks.includes("PROFILE_REJECTED_NON_TECHNICAL"), true);
  });
}

function testMissingEvaluationStaysSafe(): Promise<void> {
  const telegram = new TelegramClientMock();
  const logger = new LoggerMock();
  const notifier = new ManagerNotifier(telegram as unknown as TelegramClient, logger);

  return notifier.notifyCandidateApplied(
    makeParams({
      matchLifecycle: {
        status: "manager_accepted",
      },
      interviewLifecycle: {
        hasInterviewRunRow: true,
      },
      evaluation: {},
    }),
  ).then(() => {
    assert.equal(telegram.sent.length, 1);
    assert.match(telegram.sent[0]?.text ?? "", /Candidate applied to your role/);

    const builtLogs = findDebug(logger, "manager_package.normalized_built");
    assert.equal(builtLogs.length, 1);
    assert.equal(builtLogs[0]?.meta?.matchStatus, "APPROVED");
    assert.equal(builtLogs[0]?.meta?.interviewStatus, "COMPLETED");
    // Missing explicit evaluation falls back to score-based normalization.
    assert.equal(builtLogs[0]?.meta?.evaluationStatus, "STRONG");

    const noteLogs = findDebug(logger, "manager_package.normalization_notes");
    assert.equal(noteLogs.length, 0);
  });
}

function testSentToManagerDriftPathStillWorks(): Promise<void> {
  const telegram = new TelegramClientMock();
  const logger = new LoggerMock();
  const notifier = new ManagerNotifier(telegram as unknown as TelegramClient, logger);

  return notifier.notifyCandidateApplied(
    makeParams({
      matchLifecycle: {
        candidateDecision: "apply",
        managerDecision: "pending",
      },
    }),
  ).then(() => {
    assert.equal(telegram.sent.length, 1);
    assert.match(telegram.sent[0]?.text ?? "", /Candidate: #99001/);

    const builtLogs = findDebug(logger, "manager_package.normalized_built");
    assert.equal(builtLogs.length, 1);
    assert.equal(builtLogs[0]?.meta?.matchStatus, "SENT_TO_MANAGER");
    assert.equal(builtLogs[0]?.meta?.isCandidateSentToManager, true);
  });
}

async function run(): Promise<void> {
  await testCleanPackagePath();
  await testAmbiguousNormalizationStillRendersSafely();
  await testMissingEvaluationStaysSafe();
  await testSentToManagerDriftPathStillWorks();
  process.stdout.write("manager-notifier.normalized-package tests passed.\n");
}

void run();
