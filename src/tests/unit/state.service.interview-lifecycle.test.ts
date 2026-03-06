import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { InterviewLifecycleService } from "../../core/matching/interview-lifecycle.service";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { StateService } from "../../state/state.service";

class LoggerMock implements Logger {
  public readonly debugCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];
  public readonly warnCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];

  debug(message: string, meta?: Record<string, unknown>): void {
    this.debugCalls.push({ message, meta });
  }

  info(): void {
    return;
  }

  warn(message: string, meta?: Record<string, unknown>): void {
    this.warnCalls.push({ message, meta });
  }

  error(): void {
    return;
  }
}

class FailingInterviewLifecycleService extends InterviewLifecycleService {
  override startInterview(): never {
    throw new Error("forced lifecycle start failure");
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

function testInterviewStartPathStillWorks(): void {
  const logger = new LoggerMock();
  const stateService = new StateService(logger);
  const userId = 911;
  const chatId = 922;

  const session = stateService.getOrCreate(userId, chatId);
  session.state = "waiting_resume";

  const started = stateService.markInterviewStarted(userId, "pdf", "2026-03-06T12:00:00.000Z");

  assert.equal(started.documentType, "pdf");
  assert.equal(started.interviewStartedAt, "2026-03-06T12:00:00.000Z");
}

function testCanonicalStartTransitionComputedCorrectly(): void {
  const logger = new LoggerMock();
  const stateService = new StateService(logger);
  const userId = 933;
  const chatId = 944;

  const session = stateService.getOrCreate(userId, chatId);
  session.state = "waiting_job";

  stateService.markInterviewStarted(userId, "docx", "2026-03-06T12:05:00.000Z");

  const logs = findDebug(logger, "interview_lifecycle.start.transition");
  assert.equal(logs.length, 1);
  assert.equal(logs[0]?.meta?.canonicalFrom, INTERVIEW_STATUSES.INVITED);
  assert.equal(logs[0]?.meta?.canonicalTo, INTERVIEW_STATUSES.STARTED);
  assert.equal(logs[0]?.meta?.currentState, "waiting_job");
}

function testLifecycleFailureDoesNotBreakLegacyFlow(): void {
  const logger = new LoggerMock();
  const stateService = new StateService(
    logger,
    new FailingInterviewLifecycleService(),
  );
  const userId = 955;
  const chatId = 966;

  const session = stateService.getOrCreate(userId, chatId);
  session.state = "waiting_resume";

  const started = stateService.markInterviewStarted(userId, "unknown", "2026-03-06T12:10:00.000Z");

  assert.equal(started.documentType, "unknown");
  assert.equal(started.interviewStartedAt, "2026-03-06T12:10:00.000Z");

  const failures = findWarn(logger, "interview_lifecycle.transition_failed");
  assert.equal(failures.length, 1);
  assert.equal(failures[0]?.meta?.action, "start_interview");
}

function run(): void {
  testInterviewStartPathStillWorks();
  testCanonicalStartTransitionComputedCorrectly();
  testLifecycleFailureDoesNotBreakLegacyFlow();
  process.stdout.write("state.service.interview-lifecycle tests passed.\n");
}

run();
