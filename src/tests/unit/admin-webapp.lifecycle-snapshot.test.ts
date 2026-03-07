import assert from "node:assert/strict";
import { AdminWebappService } from "../../admin/admin-webapp.service";
import { Logger } from "../../config/logger";

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

type SupabaseDataByTable = Record<string, unknown[]>;

class SupabaseClientMock {
  constructor(private readonly dataByTable: SupabaseDataByTable) {}

  async selectMany<T>(table: string): Promise<T[]> {
    return (this.dataByTable[table] ?? []) as T[];
  }
}

function makeBaseData(overrides?: {
  matches?: unknown[];
  profiles?: unknown[];
  users?: unknown[];
  interviews?: unknown[];
  userStates?: unknown[];
}): SupabaseDataByTable {
  return {
    users: overrides?.users ?? [
      {
        telegram_user_id: 2001,
        telegram_username: "manager_one",
        first_name: "M",
        last_name: "One",
        role: "manager",
        preferred_language: "en",
        contact_shared: true,
        candidate_profile_complete: false,
        created_at: "2026-03-06T10:00:00.000Z",
        updated_at: "2026-03-06T12:00:00.000Z",
      },
      {
        telegram_user_id: 1001,
        telegram_username: "candidate_one",
        first_name: "C",
        last_name: "One",
        role: "candidate",
        preferred_language: "en",
        contact_shared: false,
        candidate_profile_complete: true,
        created_at: "2026-03-06T10:00:00.000Z",
        updated_at: "2026-03-06T12:00:00.000Z",
      },
    ],
    profiles: overrides?.profiles ?? [],
    jobs: [],
    matches: overrides?.matches ?? [],
    quality_flags: [],
    data_deletion_requests: [],
    interview_runs: overrides?.interviews ?? [],
    user_states: overrides?.userStates ?? [],
  };
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

async function testCleanSnapshotPath(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_clean",
            job_id: "job_1",
            candidate_id: "cand_1",
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: 92,
            status: "candidate_applied",
            candidate_decision: "applied",
            manager_decision: "pending",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        profiles: [
          {
            telegram_user_id: 1001,
            kind: "candidate",
            profile_status: "analysis_ready",
            technical_summary_json: {
              interview_confidence_level: "high",
            },
            raw_resume_analysis_json: null,
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        interviews: [
          {
            telegram_user_id: 1001,
            role: "candidate",
            completed_at: "2026-03-06T11:59:00.000Z",
          },
        ],
        userStates: [
          {
            telegram_user_id: 1001,
            state: "candidate_profile_ready",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.status, "candidate_applied");
  assert.equal(data.matches[0]?.candidateDecision, "applied");
  assert.equal(data.matches[0]?.lifecycleSnapshot?.matchStatus, "SENT_TO_MANAGER");
  assert.equal(data.matches[0]?.lifecycleSnapshot?.interviewStatus, "COMPLETED");
  assert.equal(data.matches[0]?.lifecycleSnapshot?.evaluationStatus, "STRONG");
  assert.equal(data.matches[0]?.normalizedLifecycle?.matchStatus, "SENT_TO_MANAGER");
  assert.equal(data.matches[0]?.normalizedLifecycle?.interviewStatus, "COMPLETED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.evaluationStatus, "STRONG");
  assert.equal(data.matches[0]?.normalizedLifecycle?.fallbackUsed, false);
  assert.equal(data.matches[0]?.decisionGateSnapshot?.legacyGateState, "MANAGER_DECISION_OPEN");
  assert.equal(data.matches[0]?.decisionGateSnapshot?.managerMayApprove, true);
  assert.equal(data.matches[0]?.decisionGateSnapshot?.managerMayReject, true);
  assert.equal(data.matches[0]?.decisionGateSnapshot?.divergenceNotes.length, 0);
  assert.equal(data.decisionGateSummary.total, 1);
  assert.equal(data.decisionGateSummary.aligned, 1);
  assert.equal(data.decisionGateSummary.diverged, 0);
  assert.equal(data.decisionGateSummary.unresolved, 0);
  assert.equal(data.decisionGateSummary.overloadedLegacy, 1);
  assert.equal(data.decisionGateSummary.canonicalMismatch, 0);
  assert.equal(data.decisionGateObservability.total, 1);
  assert.equal(data.decisionGateObservability.canonicalGateEligible, 1);
  assert.equal(data.decisionGateObservability.canonicalGateUsed, 1);
  assert.equal(data.decisionGateObservability.legacyFallbackUsed, 0);
  assert.equal(data.decisionGateObservability.divergenceDetected, 0);
  assert.equal(data.decisionGateObservability.canonicalMissing, 0);
  assert.equal(data.decisionGateObservability.unresolved, 0);

  const resolvedLogs = findDebug(logger, "lifecycle_snapshot.resolved");
  assert.equal(resolvedLogs.length, 1);
  const gateLogs = findDebug(logger, "decision_gate_snapshot.resolved");
  assert.equal(gateLogs.length, 1);
}

async function testAmbiguousLifecyclePathStillRendersSafely(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_ambiguous",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: null,
            status: "legacy_unknown",
            candidate_decision: "rejected",
            manager_decision: "accepted",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.id, "match_ambiguous");
  assert.equal(data.matches[0]?.lifecycleSnapshot?.matchStatus, null);
  assert.equal(data.matches[0]?.normalizedLifecycle?.fallbackUsed, true);
  assert.equal(data.matches[0]?.normalizedLifecycle?.matchStatus, "DECLINED");
  assert.equal(data.decisionGateSummary.total, 1);
  assert.equal(data.decisionGateSummary.aligned, 1);
  assert.equal(data.decisionGateSummary.diverged, 0);
  assert.equal(data.decisionGateSummary.unresolved, 1);
  assert.equal(data.decisionGateObservability.total, 1);
  assert.equal(data.decisionGateObservability.canonicalGateEligible, 0);
  assert.equal(data.decisionGateObservability.canonicalGateUsed, 0);
  assert.equal(data.decisionGateObservability.legacyFallbackUsed, 1);
  assert.equal(data.decisionGateObservability.divergenceDetected, 0);
  assert.equal(data.decisionGateObservability.canonicalMissing, 1);
  assert.equal(data.decisionGateObservability.unresolved, 1);
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("MATCH_STATUS_UNCLEAR"),
    true,
  );

  const notesLogs = findDebug(logger, "lifecycle_snapshot.notes");
  assert.equal(notesLogs.length >= 1, true);
  const fallbackLogs = findDebug(logger, "lifecycle_snapshot.fallback");
  assert.equal(fallbackLogs.length >= 1, true);
}

async function testMissingEvaluationStillSafe(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_missing_eval",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: null,
            status: "candidate_applied",
            candidate_decision: "applied",
            manager_decision: "pending",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        interviews: [
          {
            telegram_user_id: 1001,
            role: "candidate",
            completed_at: "2026-03-06T11:59:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.evaluationStatus, null);
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("EVALUATION_STATUS_UNCLEAR"),
    true,
  );
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("INTERVIEW_COMPLETED_WITHOUT_EVALUATION"),
    true,
  );
  assert.equal(data.matches[0]?.normalizedLifecycle?.fallbackUsed, true);
  assert.equal(data.matches[0]?.normalizedLifecycle?.evaluationStatus, null);
  assert.equal(
    data.matches[0]?.normalizedLifecycle?.fallbackReasons.includes("EVALUATION_STATUS_SNAPSHOT_NULL"),
    true,
  );
}

async function testOverloadedLegacyValuePathStillSafe(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_overloaded",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: null,
            status: "candidate_applied",
            candidate_decision: "apply",
            manager_decision: "pending",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.status, "candidate_applied");
  assert.equal(data.matches[0]?.candidateDecision, "apply");
  assert.equal(data.matches[0]?.lifecycleSnapshot?.matchStatus, "SENT_TO_MANAGER");
  assert.equal(data.matches[0]?.normalizedLifecycle?.matchStatus, "SENT_TO_MANAGER");
  assert.equal(data.matches[0]?.decisionGateSnapshot?.managerMayApprove, true);
  assert.equal(
    data.matches[0]?.decisionGateSnapshot?.risks.includes(
      "LEGACY_STATUS_OVERLOADED_CANDIDATE_APPLIED",
    ),
    true,
  );
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("LEGACY_CANDIDATE_APPLIED_OVERLOADED"),
    true,
  );
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("LEGACY_APPLY_ALIAS_USED"),
    true,
  );
  assert.equal(data.decisionGateSummary.total, 1);
  assert.equal(data.decisionGateSummary.overloadedLegacy, 1);
  assert.equal(data.decisionGateSummary.diverged, 0);
}

async function testAdminOutputShapeBackwardCompatible(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_shape",
            job_id: "job_shape",
            candidate_id: "cand_shape",
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: 60,
            status: "candidate_applied",
            candidate_decision: "applied",
            manager_decision: "pending",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  const match = data.matches[0];
  assert.ok(match);
  assert.equal(match?.id, "match_shape");
  assert.equal(match?.status, "candidate_applied");
  assert.equal(match?.candidateDecision, "applied");
  assert.equal(match?.managerDecision, "pending");
  assert.ok(match?.lifecycleSnapshot);
  assert.ok(match?.normalizedLifecycle);
  assert.ok(match?.decisionGateSnapshot);
  assert.ok(data.decisionGateSummary);
  assert.ok(data.decisionGateObservability);
  assert.equal(typeof data.decisionGateSummary.total, "number");
  assert.equal(typeof data.decisionGateSummary.aligned, "number");
  assert.equal(typeof data.decisionGateSummary.diverged, "number");
  assert.equal(typeof data.decisionGateObservability.total, "number");
  assert.equal(typeof data.decisionGateObservability.canonicalGateEligible, "number");
  assert.equal(typeof data.decisionGateObservability.canonicalGateUsed, "number");
  assert.equal(typeof data.decisionGateObservability.legacyFallbackUsed, "number");
}

async function testCanonicalPersistedMatchStatusOverridesLegacyInference(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_canonical_match",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: 50,
            status: "candidate_rejected",
            candidate_decision: "rejected",
            manager_decision: "pending",
            canonical_match_status: "APPROVED",
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.matchStatus, "APPROVED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.matchStatus, "APPROVED");
  assert.equal(data.matches[0]?.decisionGateSnapshot?.canonicalMatchStatus, "APPROVED");
  assert.equal(
    data.matches[0]?.decisionGateSnapshot?.divergenceNotes.includes(
      "CANONICAL_PERSISTED_DIFFERS_FROM_LEGACY_NORMALIZED",
    ),
    true,
  );
  assert.equal(data.decisionGateSummary.total, 1);
  assert.equal(data.decisionGateSummary.diverged, 1);
  assert.equal(data.decisionGateSummary.canonicalMismatch, 1);
  assert.equal(data.decisionGateSummary.aligned, 0);
  assert.equal(data.decisionGateObservability.total, 1);
  assert.equal(data.decisionGateObservability.canonicalGateEligible, 1);
  assert.equal(data.decisionGateObservability.canonicalGateUsed, 0);
  assert.equal(data.decisionGateObservability.legacyFallbackUsed, 1);
  assert.equal(data.decisionGateObservability.divergenceDetected, 1);
  assert.equal(data.decisionGateObservability.canonicalMissing, 0);
  assert.equal(data.decisionGateObservability.unresolved, 0);
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("MATCH_STATUS_CANONICAL_OVERRIDE_LEGACY"),
    true,
  );
  const divergenceLogs = findDebug(logger, "decision_gate_snapshot.divergence");
  assert.equal(divergenceLogs.length >= 1, true);
}

async function testCanonicalPersistedInterviewStatusOverridesLegacyInference(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_canonical_interview",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: null,
            status: "candidate_applied",
            candidate_decision: "applied",
            manager_decision: "pending",
            canonical_match_status: null,
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        userStates: [
          {
            telegram_user_id: 1001,
            state: "interviewing_candidate",
            canonical_interview_status: "COMPLETED",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.interviewStatus, "COMPLETED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.interviewStatus, "COMPLETED");
  assert.equal(
    data.matches[0]?.lifecycleSnapshot?.notes.includes("INTERVIEW_STATUS_CANONICAL_OVERRIDE_LEGACY"),
    true,
  );
  const resolvedLogs = findDebug(logger, "lifecycle_snapshot.resolved");
  assert.equal(resolvedLogs.length, 1);
  assert.equal(
    resolvedLogs[0]?.meta?.canonicalInterviewStatusSource,
    "active_session_or_run",
  );
}

async function testCompletedInterviewRunCanonicalOverridesStaleUserStateCanonical(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_completed_run_precedence",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: 80,
            status: "candidate_applied",
            candidate_decision: "applied",
            manager_decision: "pending",
            canonical_match_status: null,
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        interviews: [
          {
            telegram_user_id: 1001,
            role: "candidate",
            canonical_interview_status: "COMPLETED",
            completed_at: "2026-03-06T11:59:00.000Z",
          },
        ],
        userStates: [
          {
            telegram_user_id: 1001,
            state: "interviewing_candidate",
            canonical_interview_status: "STARTED",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.interviewStatus, "COMPLETED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.interviewStatus, "COMPLETED");

  const resolvedLogs = findDebug(logger, "lifecycle_snapshot.resolved");
  assert.equal(resolvedLogs.length, 1);
  assert.equal(
    resolvedLogs[0]?.meta?.canonicalInterviewStatusSource,
    "completed_interview_run",
  );
}

async function testLegacyFallbackStillWorksWhenCanonicalAbsent(): Promise<void> {
  const logger = new LoggerMock();
  const service = new AdminWebappService(
    logger,
    {
      async requestDeletion() {
        return { requested: true, confirmationMessage: "ok" };
      },
    } as never,
    new SupabaseClientMock(
      makeBaseData({
        matches: [
          {
            id: "match_legacy_fallback",
            job_id: null,
            candidate_id: null,
            manager_telegram_user_id: 2001,
            candidate_telegram_user_id: 1001,
            total_score: null,
            status: "manager_rejected",
            candidate_decision: "applied",
            manager_decision: "rejected",
            canonical_match_status: null,
            created_at: "2026-03-06T12:00:00.000Z",
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
        userStates: [
          {
            telegram_user_id: 1001,
            state: "candidate_profile_ready",
            canonical_interview_status: null,
            updated_at: "2026-03-06T12:00:00.000Z",
          },
        ],
      }),
    ) as never,
  );

  const data = await service.getDashboardData();
  assert.equal(data.matches.length, 1);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.matchStatus, "REJECTED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.matchStatus, "REJECTED");
  assert.equal(data.matches[0]?.normalizedLifecycle?.fallbackUsed, true);
  assert.equal(data.matches[0]?.lifecycleSnapshot?.interviewStatus, null);
}

async function run(): Promise<void> {
  await testCleanSnapshotPath();
  await testAmbiguousLifecyclePathStillRendersSafely();
  await testMissingEvaluationStillSafe();
  await testOverloadedLegacyValuePathStillSafe();
  await testCanonicalPersistedMatchStatusOverridesLegacyInference();
  await testCanonicalPersistedInterviewStatusOverridesLegacyInference();
  await testCompletedInterviewRunCanonicalOverridesStaleUserStateCanonical();
  await testLegacyFallbackStillWorksWhenCanonicalAbsent();
  await testAdminOutputShapeBackwardCompatible();
  process.stdout.write("admin-webapp.lifecycle-snapshot tests passed.\n");
}

void run();
