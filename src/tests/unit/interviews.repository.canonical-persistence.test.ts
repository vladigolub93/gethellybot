import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { InterviewsRepository } from "../../db/repositories/interviews.repo";
import { PersistedInterviewRecord } from "../../storage/interview-storage.service";

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

class SupabaseClientMock {
  public readonly insertCalls: Array<{ table: string; payload: Record<string, unknown> }> = [];

  constructor(private readonly options?: { failCanonicalOnce?: boolean }) {}

  async insert(table: string, payload: Record<string, unknown>): Promise<void> {
    this.insertCalls.push({ table, payload });
    if (this.options?.failCanonicalOnce && "canonical_interview_status" in payload) {
      this.options.failCanonicalOnce = false;
      throw new Error("column interview_runs.canonical_interview_status does not exist");
    }
  }
}

function makeRecord(
  overrides: Partial<PersistedInterviewRecord> = {},
): PersistedInterviewRecord {
  return {
    role: "candidate",
    telegramUserId: 9001,
    startedAt: "2026-03-06T10:00:00.000Z",
    completedAt: "2026-03-06T10:15:00.000Z",
    documentType: "pdf",
    extractedText: "resume text",
    planQuestions: [{ id: "q1", question: "Tell me about production incidents." }],
    answers: [
      {
        questionIndex: 0,
        questionId: "q1",
        questionText: "Tell me about production incidents.",
        answerText: "I handled incidents and led postmortems.",
        inputType: "text",
        answeredAt: "2026-03-06T10:05:00.000Z",
        status: "final",
      },
    ],
    finalArtifact: null,
    canonicalInterviewStatus: INTERVIEW_STATUSES.COMPLETED,
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

async function testCanonicalInterviewStatusPersistedOnCompletion(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock();
  const repository = new InterviewsRepository(logger, supabase as never);

  await repository.saveCompletedInterview(makeRecord());

  assert.equal(supabase.insertCalls.length, 1);
  assert.equal(
    supabase.insertCalls[0]?.payload.canonical_interview_status,
    INTERVIEW_STATUSES.COMPLETED,
  );
  const persistedLogs = findDebug(logger, "interview_lifecycle.canonical_persisted");
  assert.equal(persistedLogs.length, 1);
}

async function testCanonicalPersistenceFailureDoesNotBreakLegacyFlow(): Promise<void> {
  const logger = new LoggerMock();
  const supabase = new SupabaseClientMock({ failCanonicalOnce: true });
  const repository = new InterviewsRepository(logger, supabase as never);

  await repository.saveCompletedInterview(makeRecord());

  assert.equal(supabase.insertCalls.length, 2);
  assert.equal(
    supabase.insertCalls[0]?.payload.canonical_interview_status,
    INTERVIEW_STATUSES.COMPLETED,
  );
  assert.equal(
    "canonical_interview_status" in (supabase.insertCalls[1]?.payload ?? {}),
    false,
  );
  const failedLogs = findWarn(logger, "interview_lifecycle.canonical_persist_failed");
  assert.equal(failedLogs.length, 1);
}

async function run(): Promise<void> {
  await testCanonicalInterviewStatusPersistedOnCompletion();
  await testCanonicalPersistenceFailureDoesNotBreakLegacyFlow();
  process.stdout.write("interviews.repository.canonical-persistence tests passed.\n");
}

void run();

