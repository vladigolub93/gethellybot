import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { ManagerExposureService } from "../../core/matching/manager-exposure.service";
import { MatchRecord } from "../../decisions/match.types";
import { NotificationEngine } from "../../notifications/notification.engine";
import { StateService } from "../../state/state.service";

class LoggerMock implements Logger {
  public readonly debugCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];
  public readonly warnCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];
  public readonly infoCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];

  debug(message: string, meta?: Record<string, unknown>): void {
    this.debugCalls.push({ message, meta });
  }

  info(message: string, meta?: Record<string, unknown>): void {
    this.infoCalls.push({ message, meta });
  }

  warn(message: string, meta?: Record<string, unknown>): void {
    this.warnCalls.push({ message, meta });
  }

  error(): void {
    return;
  }
}

class ManagerNotifierMock {
  public calls = 0;

  async notifyCandidateApplied(): Promise<void> {
    this.calls += 1;
  }
}

class ThrowingManagerExposureService {
  exposeCandidateToManager(): never {
    throw new Error("forced manager exposure failure");
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

function makeMatch(overrides: Partial<MatchRecord> = {}): MatchRecord {
  return {
    id: "match_1",
    managerUserId: 501,
    candidateUserId: 601,
    jobSummary: "Backend role",
    candidateSummary: "Candidate summary",
    score: 88,
    explanation: "Good fit",
    candidateDecision: "applied",
    managerDecision: "pending",
    status: "candidate_applied",
    createdAt: "2026-03-06T10:00:00.000Z",
    updatedAt: "2026-03-06T10:00:00.000Z",
    ...overrides,
  };
}

function buildEngineHarness(options?: {
  managerExposureService?: ManagerExposureService;
}): {
  engine: NotificationEngine;
  stateService: StateService;
  managerNotifier: ManagerNotifierMock;
  logger: LoggerMock;
} {
  const logger = new LoggerMock();
  const stateService = new StateService(logger);
  const managerNotifier = new ManagerNotifierMock();

  const engine = new NotificationEngine(
    stateService,
    {
      async persistSession() {},
    } as never,
    {
      async sendUserMessage() {},
    } as never,
    {} as never,
    managerNotifier as unknown as never,
    {
      async checkAndConsumeCandidateNotification() {
        return { allowed: true };
      },
      async checkAndConsumeManagerNotification() {
        return { allowed: true };
      },
    } as never,
    {
      async getManagerJobStatus() {
        return "active";
      },
    } as never,
    {
      async getUserFlags() {
        return { autoNotifyEnabled: true, firstMatchExplained: true };
      },
      async markFirstMatchExplained() {},
    } as never,
    logger,
    options?.managerExposureService,
  );

  return {
    engine,
    stateService,
    managerNotifier,
    logger,
  };
}

async function testManagerExposurePathStillWorksAndCanonicalComputed(): Promise<void> {
  const harness = buildEngineHarness();
  const session = harness.stateService.getOrCreate(501, 777);
  session.state = "job_published";
  session.role = "manager";
  session.firstMatchExplained = true;

  const match = makeMatch();
  await harness.engine.notifyManagerCandidateApplied(match);

  assert.equal(harness.managerNotifier.calls, 1);
  const transitionLogs = findDebug(harness.logger, "match_lifecycle.send_to_manager.transition");
  assert.equal(transitionLogs.length, 1);
  const coverageLogs = findDebug(harness.logger, "manager_exposure.partial_coverage");
  assert.equal(coverageLogs.length, 1);
}

async function testFailureDoesNotBreakLegacyFlow(): Promise<void> {
  const harness = buildEngineHarness({
    managerExposureService: new ThrowingManagerExposureService() as unknown as ManagerExposureService,
  });
  const session = harness.stateService.getOrCreate(501, 778);
  session.state = "job_published";
  session.role = "manager";
  session.firstMatchExplained = true;

  const match = makeMatch({ id: "match_fail" });
  await harness.engine.notifyManagerCandidateApplied(match);

  assert.equal(harness.managerNotifier.calls, 1);
  const failures = findWarn(harness.logger, "manager_exposure.failed");
  assert.equal(failures.length, 1);
}

async function run(): Promise<void> {
  await testManagerExposurePathStillWorksAndCanonicalComputed();
  await testFailureDoesNotBreakLegacyFlow();
  process.stdout.write("notification.engine.manager-exposure tests passed.\n");
}

void run();
