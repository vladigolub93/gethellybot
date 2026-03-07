import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { StatesRepository } from "../../db/repositories/states.repo";
import { UserSessionState } from "../../shared/types/state.types";

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
    if (this.options?.failCanonicalOnce && "canonical_interview_status" in payload) {
      this.options.failCanonicalOnce = false;
      throw new Error("column user_states.canonical_interview_status does not exist");
    }
  }
}

function makeStartedSession(overrides: Partial<UserSessionState> = {}): UserSessionState {
  return {
    userId: 12001,
    chatId: 13001,
    state: "interviewing_candidate",
    documentType: "pdf",
    interviewStartedAt: "2026-03-06T14:00:00.000Z",
    canonicalInterviewStatus: INTERVIEW_STATUSES.STARTED,
    ...overrides,
  };
}

function findDebug(
  logger: LoggerMock,
  message: string,
): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(
  logger: LoggerMock,
  message: string,
): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

async function testCanonicalInterviewStatusPersistedOnStart(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock();
  const repository = new StatesRepository(logger, supabase as never);

  await repository.saveSession(makeStartedSession());

  assert.equal(supabase.upsertCalls.length, 1);
  assert.equal(
    supabase.upsertCalls[0]?.payload.canonical_interview_status,
    INTERVIEW_STATUSES.STARTED,
  );
  const payload = supabase.upsertCalls[0]?.payload.state_payload as Record<string, unknown>;
  assert.equal(payload.documentType, "pdf");
  assert.equal(payload.interviewStartedAt, "2026-03-06T14:00:00.000Z");

  const persistedLogs = findDebug(logger, "interview_lifecycle.canonical_persisted");
  assert.equal(persistedLogs.length, 1);
}

async function testCanonicalPersistenceFailureFallsBackAndLegacyStartPersists(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock({ failCanonicalOnce: true });
  const repository = new StatesRepository(logger, supabase as never);

  await repository.saveSession(makeStartedSession());

  assert.equal(supabase.upsertCalls.length, 2);
  assert.equal(
    supabase.upsertCalls[0]?.payload.canonical_interview_status,
    INTERVIEW_STATUSES.STARTED,
  );
  assert.equal(
    "canonical_interview_status" in (supabase.upsertCalls[1]?.payload ?? {}),
    false,
  );
  const fallbackPayload = supabase.upsertCalls[1]?.payload.state_payload as Record<string, unknown>;
  assert.equal(fallbackPayload.documentType, "pdf");
  assert.equal(fallbackPayload.interviewStartedAt, "2026-03-06T14:00:00.000Z");
  assert.equal(fallbackPayload.canonicalInterviewStatus, INTERVIEW_STATUSES.STARTED);

  const failedLogs = findWarn(logger, "interview_lifecycle.canonical_persist_failed");
  assert.equal(failedLogs.length, 1);
}

async function run(): Promise<void> {
  await testCanonicalInterviewStatusPersistedOnStart();
  await testCanonicalPersistenceFailureFallsBackAndLegacyStartPersists();
  process.stdout.write("states.repository.canonical-interview-persistence tests passed.\n");
}

void run();

