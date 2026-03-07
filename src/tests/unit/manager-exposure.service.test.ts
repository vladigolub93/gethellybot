import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { MatchLifecycleService } from "../../core/matching/match-lifecycle.service";
import { ManagerExposureService } from "../../core/matching/manager-exposure.service";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

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

class FailingMatchLifecycleService extends MatchLifecycleService {
  override sendToManager(): never {
    throw new Error("forced send-to-manager failure");
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

function testManagerExposurePathStillWorks(): void {
  const logger = new LoggerMock();
  const service = new ManagerExposureService(logger);

  const result = service.exposeCandidateToManager({
    matchId: "match_1",
    candidateUserId: 101,
    managerUserId: 202,
    legacyStatus: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    source: "notification_push",
  });

  assert.equal(result.partialCoverage, true);
  assert.equal(result.canonicalObserved, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(result.canonicalFrom, MATCH_STATUSES.INTERVIEW_COMPLETED);
  assert.equal(result.canonicalTo, MATCH_STATUSES.SENT_TO_MANAGER);
}

function testCanonicalTransitionComputedCorrectly(): void {
  const logger = new LoggerMock();
  const service = new ManagerExposureService(logger);

  service.exposeCandidateToManager({
    matchId: "match_2",
    candidateUserId: 103,
    managerUserId: 204,
    legacyStatus: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    source: "notification_push",
  });

  const transitionLogs = findDebug(logger, "match_lifecycle.send_to_manager.transition");
  assert.equal(transitionLogs.length, 1);
  assert.equal(transitionLogs[0]?.meta?.canonicalFrom, MATCH_STATUSES.INTERVIEW_COMPLETED);
  assert.equal(transitionLogs[0]?.meta?.canonicalTo, MATCH_STATUSES.SENT_TO_MANAGER);

  const exposedLogs = findDebug(logger, "manager_exposure.exposed");
  assert.equal(exposedLogs.length, 1);

  const coverageLogs = findDebug(logger, "manager_exposure.partial_coverage");
  assert.equal(coverageLogs.length, 1);
  assert.equal(coverageLogs[0]?.meta?.missingSource, "state_router.showTopMatchesWithActions");
}

function testFailureDoesNotBreakExposureFlow(): void {
  const logger = new LoggerMock();
  const service = new ManagerExposureService(
    logger,
    new FailingMatchLifecycleService(),
  );

  const result = service.exposeCandidateToManager({
    matchId: "match_3",
    candidateUserId: 105,
    managerUserId: 206,
    legacyStatus: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    source: "notification_push",
  });

  assert.equal(result.canonicalObserved, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(result.canonicalFrom, MATCH_STATUSES.INTERVIEW_COMPLETED);
  assert.equal(result.canonicalTo, null);

  const failures = findWarn(logger, "match_lifecycle.transition_failed");
  assert.equal(failures.length, 1);
  assert.equal(failures[0]?.meta?.action, "send_to_manager");

  const exposedLogs = findDebug(logger, "manager_exposure.exposed");
  assert.equal(exposedLogs.length, 1);
}

function testPartialCoverageExplicitForPushSeam(): void {
  const logger = new LoggerMock();
  const service = new ManagerExposureService(logger);

  const result = service.exposeCandidateToManager({
    matchId: "match_4",
    candidateUserId: 107,
    managerUserId: 208,
    legacyStatus: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    source: "notification_push",
  });

  assert.equal(result.partialCoverage, true);

  const coverageLogs = findDebug(logger, "manager_exposure.partial_coverage");
  assert.equal(coverageLogs.length, 1);
  assert.equal(coverageLogs[0]?.meta?.coveredSource, "notification_push");
  assert.equal(coverageLogs[0]?.meta?.missingSource, "state_router.showTopMatchesWithActions");
}

function testPullSourceLogsPullPathUsage(): void {
  const logger = new LoggerMock();
  const service = new ManagerExposureService(logger);

  const result = service.exposeCandidateToManager({
    matchId: "match_5",
    candidateUserId: 109,
    managerUserId: 210,
    legacyStatus: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    source: "match_card_pull",
  });

  assert.equal(result.partialCoverage, true);
  const pullLogs = findDebug(logger, "manager_exposure.pull_path_used");
  assert.equal(pullLogs.length, 1);
  assert.equal(pullLogs[0]?.meta?.matchId, "match_5");
}

function run(): void {
  testManagerExposurePathStillWorks();
  testCanonicalTransitionComputedCorrectly();
  testFailureDoesNotBreakExposureFlow();
  testPartialCoverageExplicitForPushSeam();
  testPullSourceLogsPullPathUsage();
  process.stdout.write("manager-exposure.service tests passed.\n");
}

run();
