import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { MatchLifecycleService } from "../../core/matching/match-lifecycle.service";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";
import { DecisionService } from "../../decisions/decision.service";
import { MatchRecord } from "../../decisions/match.types";

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

class MatchStorageMock {
  public readonly candidateDecisions: Array<{
    matchId: string;
    decision: "applied" | "rejected";
    canonicalMatchStatus?: MatchRecord["canonicalMatchStatus"];
  }> = [];
  public readonly managerDecisions: Array<{
    matchId: string;
    decision: "accepted" | "rejected";
    canonicalMatchStatus?: MatchRecord["canonicalMatchStatus"];
  }> = [];

  constructor(private readonly match: MatchRecord) {}

  async getById(matchId: string): Promise<MatchRecord | null> {
    return matchId === this.match.id ? this.match : null;
  }

  async applyCandidateDecision(
    matchId: string,
    decision: "applied" | "rejected",
    options?: {
      canonicalMatchStatus?: MatchRecord["canonicalMatchStatus"];
    },
  ): Promise<MatchRecord | null> {
    if (matchId !== this.match.id) {
      return null;
    }
    this.candidateDecisions.push({
      matchId,
      decision,
      canonicalMatchStatus: options?.canonicalMatchStatus,
    });

    return {
      ...this.match,
      candidateDecision: decision,
      status: decision === "applied" ? "candidate_applied" : "candidate_rejected",
      canonicalMatchStatus: options?.canonicalMatchStatus ?? null,
      updatedAt: "2026-03-06T20:00:00.000Z",
    };
  }

  async applyManagerDecision(
    matchId: string,
    decision: "accepted" | "rejected",
    options?: {
      canonicalMatchStatus?: MatchRecord["canonicalMatchStatus"];
    },
  ): Promise<MatchRecord | null> {
    if (matchId !== this.match.id) {
      return null;
    }
    this.managerDecisions.push({
      matchId,
      decision,
      canonicalMatchStatus: options?.canonicalMatchStatus,
    });

    return {
      ...this.match,
      managerDecision: decision,
      status: decision === "accepted" ? "manager_accepted" : "manager_rejected",
      canonicalMatchStatus: options?.canonicalMatchStatus ?? null,
      updatedAt: "2026-03-06T20:00:00.000Z",
    };
  }
}

class JobsRepoMock {
  constructor(private readonly status: string | null = "active") {}

  async getManagerJobStatus(): Promise<string | null> {
    return this.status;
  }
}

class FailingLifecycleService extends MatchLifecycleService {
  override candidateAcceptsMatch(): never {
    throw new Error("forced lifecycle failure");
  }
}

class FailingManagerLifecycleService extends MatchLifecycleService {
  override managerApprovesCandidate(): never {
    throw new Error("forced manager lifecycle failure");
  }
}


function makeMatch(overrides: Partial<MatchRecord> = {}): MatchRecord {
  return {
    id: "match_1",
    managerUserId: 7001,
    candidateUserId: 8001,
    jobSummary: "Backend role",
    candidateSummary: "Candidate summary",
    score: 86,
    explanation: "Good overlap",
    candidateDecision: "pending",
    managerDecision: "pending",
    status: "proposed",
    createdAt: "2026-03-06T10:00:00.000Z",
    updatedAt: "2026-03-06T10:00:00.000Z",
    ...overrides,
  };
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

async function testCandidateAcceptPathStillWorks(): Promise<void> {
  const initial = makeMatch();
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.candidateApply(initial.id, initial.candidateUserId);

  assert.equal(updated.candidateDecision, "applied");
  assert.equal(updated.status, "candidate_applied");
  assert.equal(updated.canonicalMatchStatus, MATCH_STATUSES.INTERVIEW_STARTED);
  assert.equal(storage.candidateDecisions.length, 1);
  assert.equal(storage.candidateDecisions[0]?.decision, "applied");
  assert.equal(
    storage.candidateDecisions[0]?.canonicalMatchStatus,
    MATCH_STATUSES.INTERVIEW_STARTED,
  );
}

async function testCandidateDeclinePathStillWorks(): Promise<void> {
  const initial = makeMatch();
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.candidateReject(initial.id, initial.candidateUserId);

  assert.equal(updated.candidateDecision, "rejected");
  assert.equal(updated.status, "candidate_rejected");
  assert.equal(updated.canonicalMatchStatus, MATCH_STATUSES.DECLINED);
  assert.equal(storage.candidateDecisions.length, 1);
  assert.equal(storage.candidateDecisions[0]?.decision, "rejected");
  assert.equal(storage.candidateDecisions[0]?.canonicalMatchStatus, MATCH_STATUSES.DECLINED);
}

async function testCanonicalTransitionComputedCorrectly(): Promise<void> {
  const initial = makeMatch();
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  await service.candidateApply(initial.id, initial.candidateUserId);
  await service.candidateReject(initial.id, initial.candidateUserId);

  const acceptLogs = findDebug(logger, "match_lifecycle.candidate_accept.transition");
  const declineLogs = findDebug(logger, "match_lifecycle.candidate_decline.transition");

  assert.equal(acceptLogs.length, 1);
  assert.equal(declineLogs.length, 1);

  assert.equal(acceptLogs[0]?.meta?.canonicalFrom, MATCH_STATUSES.INVITED);
  assert.equal(acceptLogs[0]?.meta?.canonicalTo, MATCH_STATUSES.INTERVIEW_STARTED);

  assert.equal(declineLogs[0]?.meta?.canonicalFrom, MATCH_STATUSES.INVITED);
  assert.equal(declineLogs[0]?.meta?.canonicalTo, MATCH_STATUSES.DECLINED);
}

async function testFailedCanonicalTransitionDoesNotBreakLegacyFlow(): Promise<void> {
  const initial = makeMatch();
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new FailingLifecycleService(),
  );

  const updated = await service.candidateApply(initial.id, initial.candidateUserId);

  assert.equal(updated.candidateDecision, "applied");
  assert.equal(updated.status, "candidate_applied");
  assert.equal(storage.candidateDecisions.length, 1);
  assert.equal(storage.candidateDecisions[0]?.canonicalMatchStatus, undefined);

  const failures = findWarn(logger, "match_lifecycle.transition_failed");
  assert.equal(failures.length, 1);
  assert.equal(failures[0]?.meta?.action, "candidate_accept");
}

async function testManagerApprovePathStillWorks(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);

  assert.equal(updated.managerDecision, "accepted");
  assert.equal(updated.status, "manager_accepted");
  assert.equal(updated.canonicalMatchStatus, MATCH_STATUSES.APPROVED);
  assert.equal(storage.managerDecisions.length, 1);
  assert.equal(storage.managerDecisions[0]?.decision, "accepted");
  assert.equal(storage.managerDecisions[0]?.canonicalMatchStatus, MATCH_STATUSES.APPROVED);
}

async function testManagerRejectPathStillWorks(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.managerReject(initial.id, initial.managerUserId);

  assert.equal(updated.managerDecision, "rejected");
  assert.equal(updated.status, "manager_rejected");
  assert.equal(updated.canonicalMatchStatus, MATCH_STATUSES.REJECTED);
  assert.equal(storage.managerDecisions.length, 1);
  assert.equal(storage.managerDecisions[0]?.decision, "rejected");
  assert.equal(storage.managerDecisions[0]?.canonicalMatchStatus, MATCH_STATUSES.REJECTED);
}

async function testManagerCanonicalTransitionComputedCorrectly(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  await service.managerAccept(initial.id, initial.managerUserId);
  await service.managerReject(initial.id, initial.managerUserId);

  const approveLogs = findDebug(logger, "match_lifecycle.manager_approve.transition");
  const rejectLogs = findDebug(logger, "match_lifecycle.manager_reject.transition");

  assert.equal(approveLogs.length, 1);
  assert.equal(rejectLogs.length, 1);

  assert.equal(approveLogs[0]?.meta?.canonicalFrom, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(approveLogs[0]?.meta?.canonicalTo, MATCH_STATUSES.APPROVED);

  assert.equal(rejectLogs[0]?.meta?.canonicalFrom, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(rejectLogs[0]?.meta?.canonicalTo, MATCH_STATUSES.REJECTED);
}

async function testFailedManagerCanonicalTransitionDoesNotBreakLegacyFlow(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new FailingManagerLifecycleService(),
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);

  assert.equal(updated.managerDecision, "accepted");
  assert.equal(updated.status, "manager_accepted");
  assert.equal(storage.managerDecisions.length, 1);
  assert.equal(storage.managerDecisions[0]?.canonicalMatchStatus, undefined);

  const failures = findWarn(logger, "match_lifecycle.transition_failed");
  assert.equal(failures.length, 1);
  assert.equal(failures[0]?.meta?.action, "manager_approve");
}

async function testManagerDecisionPathDoesNotOwnSendToManagerTransitionYet(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  await service.managerAccept(initial.id, initial.managerUserId);

  const sendLogs = findDebug(logger, "match_lifecycle.send_to_manager.transition");
  assert.equal(sendLogs.length, 0);
}

async function testCandidateRejectFlagOffKeepsLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.REJECTED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.candidateReject(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_rejected");
  assert.equal(updated.candidateDecision, "rejected");

  const gateLogs = findDebug(logger, "decision_gate.candidate_reject.canonical_used");
  assert.equal(gateLogs.length, 0);
}

async function testCandidateRejectUsesCanonicalGateWhenEnabledAndValid(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.INVITED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    true,
  );

  const updated = await service.candidateReject(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_rejected");

  const canonicalUsed = findDebug(logger, "decision_gate.candidate_reject.canonical_used");
  const fallbackLogs = findDebug(logger, "decision_gate.candidate_reject.legacy_fallback");
  assert.equal(canonicalUsed.length, 1);
  assert.equal(fallbackLogs.length, 0);
}

async function testCandidateRejectFallsBackWhenCanonicalMissing(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: null,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    true,
  );

  const updated = await service.candidateReject(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_rejected");
  assert.equal(storage.candidateDecisions.length, 1);

  const fallbackLogs = findDebug(logger, "decision_gate.candidate_reject.legacy_fallback");
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "CANONICAL_STATUS_UNAVAILABLE");
}

async function testCandidateRejectDivergenceFallsBackToLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.INVITED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    true,
  );

  await assert.rejects(
    () => service.candidateReject(initial.id, initial.candidateUserId),
    /no longer available/,
  );

  const divergenceLogs = findWarn(logger, "decision_gate.candidate_reject.divergence");
  const fallbackLogs = findDebug(logger, "decision_gate.candidate_reject.legacy_fallback");
  assert.equal(divergenceLogs.length, 1);
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "DIVERGENCE_FALLBACK_TO_LEGACY");
  assert.equal(storage.candidateDecisions.length, 0);
}

async function testCandidateAcceptFlagOffKeepsLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.REJECTED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.candidateApply(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_applied");
  assert.equal(updated.candidateDecision, "applied");

  const gateLogs = findDebug(logger, "decision_gate.candidate_accept.canonical_used");
  assert.equal(gateLogs.length, 0);
}

async function testCandidateAcceptUsesCanonicalGateWhenEnabledAndValid(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.INVITED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    true,
  );

  const updated = await service.candidateApply(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_applied");

  const canonicalUsed = findDebug(logger, "decision_gate.candidate_accept.canonical_used");
  const fallbackLogs = findDebug(logger, "decision_gate.candidate_accept.legacy_fallback");
  assert.equal(canonicalUsed.length, 1);
  assert.equal(fallbackLogs.length, 0);
}

async function testCandidateAcceptFallsBackWhenCanonicalMissing(): Promise<void> {
  const initial = makeMatch({
    status: "proposed",
    candidateDecision: "pending",
    canonicalMatchStatus: null,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    true,
  );

  const updated = await service.candidateApply(initial.id, initial.candidateUserId);
  assert.equal(updated.status, "candidate_applied");
  assert.equal(storage.candidateDecisions.length, 1);

  const fallbackLogs = findDebug(logger, "decision_gate.candidate_accept.legacy_fallback");
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "CANONICAL_STATUS_UNAVAILABLE");
}

async function testCandidateAcceptDivergenceFallsBackToLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.INVITED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    true,
  );

  await assert.rejects(
    () => service.candidateApply(initial.id, initial.candidateUserId),
    /no longer available/,
  );

  const divergenceLogs = findWarn(logger, "decision_gate.candidate_accept.divergence");
  const fallbackLogs = findDebug(logger, "decision_gate.candidate_accept.legacy_fallback");
  assert.equal(divergenceLogs.length, 1);
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "DIVERGENCE_FALLBACK_TO_LEGACY");
  assert.equal(storage.candidateDecisions.length, 0);
}

async function testManagerRejectFlagOffKeepsLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.APPROVED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.managerReject(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_rejected");
  assert.equal(updated.managerDecision, "rejected");

  const gateLogs = findDebug(logger, "decision_gate.manager_reject.canonical_used");
  assert.equal(gateLogs.length, 0);
}

async function testManagerRejectUsesCanonicalGateWhenEnabledAndValid(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.SENT_TO_MANAGER,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    true,
    false,
  );

  const updated = await service.managerReject(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_rejected");

  const canonicalUsed = findDebug(logger, "decision_gate.manager_reject.canonical_used");
  const fallbackLogs = findDebug(logger, "decision_gate.manager_reject.legacy_fallback");
  assert.equal(canonicalUsed.length, 1);
  assert.equal(fallbackLogs.length, 0);
}

async function testManagerRejectFallsBackWhenCanonicalMissing(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: null,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    true,
    false,
  );

  const updated = await service.managerReject(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_rejected");
  assert.equal(storage.managerDecisions.length, 1);

  const fallbackLogs = findDebug(logger, "decision_gate.manager_reject.legacy_fallback");
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "CANONICAL_STATUS_UNAVAILABLE");
}

async function testManagerRejectDivergenceFallsBackToLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.APPROVED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    true,
    false,
  );

  const updated = await service.managerReject(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_rejected");
  assert.equal(storage.managerDecisions.length, 1);

  const divergenceLogs = findWarn(logger, "decision_gate.manager_reject.divergence");
  const fallbackLogs = findDebug(logger, "decision_gate.manager_reject.legacy_fallback");
  assert.equal(divergenceLogs.length, 1);
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "DIVERGENCE_FALLBACK_TO_LEGACY");
}

async function testManagerAcceptFlagOffKeepsLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.REJECTED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_accepted");
  assert.equal(updated.managerDecision, "accepted");

  const gateLogs = findDebug(logger, "decision_gate.manager_accept.canonical_used");
  assert.equal(gateLogs.length, 0);
}

async function testManagerAcceptUsesCanonicalGateWhenEnabledAndValid(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.SENT_TO_MANAGER,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    false,
    true,
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_accepted");

  const canonicalUsed = findDebug(logger, "decision_gate.manager_accept.canonical_used");
  const fallbackLogs = findDebug(logger, "decision_gate.manager_accept.legacy_fallback");
  assert.equal(canonicalUsed.length, 1);
  assert.equal(fallbackLogs.length, 0);
}

async function testManagerAcceptFallsBackWhenCanonicalMissing(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: null,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    false,
    true,
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_accepted");
  assert.equal(storage.managerDecisions.length, 1);

  const fallbackLogs = findDebug(logger, "decision_gate.manager_accept.legacy_fallback");
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "CANONICAL_STATUS_UNAVAILABLE");
}

async function testManagerAcceptDivergenceFallsBackToLegacyGate(): Promise<void> {
  const initial = makeMatch({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.REJECTED,
  });
  const storage = new MatchStorageMock(initial);
  const logger = new LoggerMock();
  const service = new DecisionService(
    storage as unknown as never,
    new JobsRepoMock() as unknown as never,
    logger,
    new MatchLifecycleService(),
    false,
    false,
    false,
    true,
  );

  const updated = await service.managerAccept(initial.id, initial.managerUserId);
  assert.equal(updated.status, "manager_accepted");
  assert.equal(storage.managerDecisions.length, 1);

  const divergenceLogs = findWarn(logger, "decision_gate.manager_accept.divergence");
  const fallbackLogs = findDebug(logger, "decision_gate.manager_accept.legacy_fallback");
  assert.equal(divergenceLogs.length, 1);
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.reason, "DIVERGENCE_FALLBACK_TO_LEGACY");
}

async function run(): Promise<void> {
  await testCandidateAcceptPathStillWorks();
  await testCandidateDeclinePathStillWorks();
  await testCanonicalTransitionComputedCorrectly();
  await testFailedCanonicalTransitionDoesNotBreakLegacyFlow();
  await testManagerApprovePathStillWorks();
  await testManagerRejectPathStillWorks();
  await testManagerCanonicalTransitionComputedCorrectly();
  await testFailedManagerCanonicalTransitionDoesNotBreakLegacyFlow();
  await testManagerDecisionPathDoesNotOwnSendToManagerTransitionYet();
  await testCandidateRejectFlagOffKeepsLegacyGate();
  await testCandidateRejectUsesCanonicalGateWhenEnabledAndValid();
  await testCandidateRejectFallsBackWhenCanonicalMissing();
  await testCandidateRejectDivergenceFallsBackToLegacyGate();
  await testCandidateAcceptFlagOffKeepsLegacyGate();
  await testCandidateAcceptUsesCanonicalGateWhenEnabledAndValid();
  await testCandidateAcceptFallsBackWhenCanonicalMissing();
  await testCandidateAcceptDivergenceFallsBackToLegacyGate();
  await testManagerRejectFlagOffKeepsLegacyGate();
  await testManagerRejectUsesCanonicalGateWhenEnabledAndValid();
  await testManagerRejectFallsBackWhenCanonicalMissing();
  await testManagerRejectDivergenceFallsBackToLegacyGate();
  await testManagerAcceptFlagOffKeepsLegacyGate();
  await testManagerAcceptUsesCanonicalGateWhenEnabledAndValid();
  await testManagerAcceptFallsBackWhenCanonicalMissing();
  await testManagerAcceptDivergenceFallsBackToLegacyGate();
  process.stdout.write("decision.service.match-lifecycle tests passed.\n");
}

void run();
