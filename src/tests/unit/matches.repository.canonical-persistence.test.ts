import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";
import { MatchRecord } from "../../decisions/match.types";
import { MatchesRepository } from "../../db/repositories/matches.repo";

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

class SupabaseClientMock {
  public readonly upsertCalls: Array<{
    table: string;
    payload: Record<string, unknown>;
    options: { onConflict: string };
  }> = [];

  constructor(private readonly options?: { failCanonicalOnce?: boolean }) {}

  async upsert(
    table: string,
    payload: Record<string, unknown>,
    options: { onConflict: string },
  ): Promise<void> {
    this.upsertCalls.push({ table, payload, options });
    if (this.options?.failCanonicalOnce && "canonical_match_status" in payload) {
      this.options.failCanonicalOnce = false;
      throw new Error("column matches.canonical_match_status does not exist");
    }
  }
}

function makeMatch(overrides: Partial<MatchRecord> = {}): MatchRecord {
  return {
    id: "match_repo_1",
    managerUserId: 1111,
    candidateUserId: 2222,
    jobId: null,
    candidateId: null,
    jobSummary: "Job",
    candidateSummary: "Candidate",
    score: 0.92,
    explanation: "fit",
    candidateDecision: "applied",
    managerDecision: "accepted",
    status: "manager_accepted",
    createdAt: "2026-03-06T12:00:00.000Z",
    updatedAt: "2026-03-06T12:01:00.000Z",
    ...overrides,
  };
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

async function testCanonicalStatusPersistedAlongsideLegacyPayload(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock();
  const repository = new MatchesRepository(logger, supabase as unknown as never);

  await repository.upsertMatch(
    makeMatch({ canonicalMatchStatus: MATCH_STATUSES.APPROVED }),
  );

  assert.equal(supabase.upsertCalls.length, 1);
  assert.equal(
    supabase.upsertCalls[0]?.payload.canonical_match_status,
    MATCH_STATUSES.APPROVED,
  );
  const persistedLogs = findDebug(logger, "match_lifecycle.canonical_persisted");
  assert.equal(persistedLogs.length, 1);
}

async function testCanonicalPersistenceFailureFallsBackToLegacyPayload(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock({ failCanonicalOnce: true });
  const repository = new MatchesRepository(logger, supabase as unknown as never);

  await repository.upsertMatch(
    makeMatch({ canonicalMatchStatus: MATCH_STATUSES.REJECTED }),
  );

  assert.equal(supabase.upsertCalls.length, 2);
  assert.equal(
    supabase.upsertCalls[0]?.payload.canonical_match_status,
    MATCH_STATUSES.REJECTED,
  );
  assert.equal(
    "canonical_match_status" in (supabase.upsertCalls[1]?.payload ?? {}),
    false,
  );
  const failedLogs = findWarn(logger, "match_lifecycle.canonical_persist_failed");
  assert.equal(failedLogs.length, 1);
  const persistedLogs = findDebug(logger, "Match persisted to Supabase");
  assert.equal(persistedLogs.length, 1);
}

async function run(): Promise<void> {
  await testCanonicalStatusPersistedAlongsideLegacyPayload();
  await testCanonicalPersistenceFailureFallsBackToLegacyPayload();
  process.stdout.write("matches.repository.canonical-persistence tests passed.\n");
}

void run();

