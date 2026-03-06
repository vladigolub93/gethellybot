import assert from "node:assert/strict";
import { Logger } from "../../config/logger";
import { InterviewLifecycleService } from "../../core/matching/interview-lifecycle.service";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { InterviewEngine } from "../../interviews/interview.engine";
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
  override completeInterview(): never {
    throw new Error("forced interview lifecycle failure");
  }
}

function buildInterviewEngineHarness(options?: {
  lifecycleService?: InterviewLifecycleService;
}): {
  engine: InterviewEngine;
  stateService: StateService;
  logger: LoggerMock;
  storageSaves: number;
  supabaseSaves: number;
  savedSupabaseRecords: Array<{ canonicalInterviewStatus?: string | null }>;
} {
  const stateService = new StateService();
  const logger = new LoggerMock();
  let storageSaves = 0;
  let supabaseSaves = 0;
  const savedSupabaseRecords: Array<{ canonicalInterviewStatus?: string | null }> = [];

  const engine = new InterviewEngine(
    {} as never,
    stateService,
    {
      async generateArtifact() {
        throw new Error("artifact generation is stubbed");
      },
    } as never,
    {
      async save() {
        storageSaves += 1;
      },
    } as never,
    {
      async saveCompletedInterview(record: { canonicalInterviewStatus?: string | null }) {
        supabaseSaves += 1;
        savedSupabaseRecords.push({
          canonicalInterviewStatus: record.canonicalInterviewStatus,
        });
      },
    } as never,
    {} as never,
    {} as never,
    {
      async createEmbedding() {
        return [];
      },
    } as never,
    {
      async getCandidateResumeAnalysis() {
        return null;
      },
      async saveCandidateTechnicalSummary() {},
      async upsertCandidateProfile() {},
      async upsertJobProfile() {},
    } as never,
    {
      async saveJobTechnicalSummary() {},
      async upsertManagerJob() {},
    } as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    logger,
    undefined,
    undefined,
    options?.lifecycleService,
  );

  return {
    engine,
    stateService,
    logger,
    get storageSaves() {
      return storageSaves;
    },
    get supabaseSaves() {
      return supabaseSaves;
    },
    get savedSupabaseRecords() {
      return savedSupabaseRecords;
    },
  };
}

function setupCandidateInterviewSession(stateService: StateService, withAnswer: boolean): void {
  const userId = 70001;
  const chatId = 80001;
  const session = stateService.getOrCreate(userId, chatId);
  session.state = "interviewing_candidate";

  stateService.setInterviewPlan(userId, {
    summary: "Candidate interview",
    questions: [
      {
        id: "q1",
        question: "Tell me about your production ownership.",
        goal: "ownership",
        gapToClarify: "details",
      },
    ],
  });
  stateService.setCandidateResumeText(userId, "Senior backend engineer with production ownership");
  stateService.markInterviewStarted(userId, "pdf", "2026-03-06T10:00:00.000Z");

  if (withAnswer) {
    stateService.upsertAnswer(userId, {
      questionIndex: 0,
      questionId: "q1",
      questionText: "Tell me about your production ownership.",
      answerText: "I owned incident response and platform reliability.",
      inputType: "text",
      answeredAt: "2026-03-06T10:05:00.000Z",
      status: "final",
    });
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

async function testInterviewCompletionPathStillWorksAndCanonicalComputed(): Promise<void> {
  const harness = buildInterviewEngineHarness();
  setupCandidateInterviewSession(harness.stateService, true);
  const session = harness.stateService.getSession(70001);
  if (!session) {
    throw new Error("Session not initialized");
  }

  const result = await harness.engine.finishInterviewNow(session);

  assert.equal(result.kind, "completed");
  assert.equal(result.completedState, "candidate_profile_ready");
  assert.equal(harness.storageSaves, 1);
  assert.equal(harness.supabaseSaves, 1);
  assert.equal(
    harness.savedSupabaseRecords[0]?.canonicalInterviewStatus,
    INTERVIEW_STATUSES.COMPLETED,
  );

  const transitions = findDebug(harness.logger, "interview_lifecycle.complete.transition");
  assert.equal(transitions.length, 1);
  assert.equal(transitions[0]?.meta?.canonicalFrom, INTERVIEW_STATUSES.IN_PROGRESS);
  assert.equal(transitions[0]?.meta?.canonicalTo, INTERVIEW_STATUSES.COMPLETED);
}

async function testFailedCanonicalCompletionDoesNotBreakLegacyFlow(): Promise<void> {
  const harness = buildInterviewEngineHarness({
    lifecycleService: new FailingInterviewLifecycleService(),
  });
  setupCandidateInterviewSession(harness.stateService, true);
  const session = harness.stateService.getSession(70001);
  if (!session) {
    throw new Error("Session not initialized");
  }

  const result = await harness.engine.finishInterviewNow(session);

  assert.equal(result.kind, "completed");
  assert.equal(result.completedState, "candidate_profile_ready");
  assert.equal(harness.storageSaves, 1);
  assert.equal(harness.supabaseSaves, 1);
  assert.equal(harness.savedSupabaseRecords[0]?.canonicalInterviewStatus, null);

  const failures = findWarn(harness.logger, "interview_lifecycle.transition_failed");
  assert.equal(failures.length, 1);
  assert.equal(failures[0]?.meta?.action, "complete_interview");
}

async function run(): Promise<void> {
  await testInterviewCompletionPathStillWorksAndCanonicalComputed();
  await testFailedCanonicalCompletionDoesNotBreakLegacyFlow();
  process.stdout.write("interview.engine.lifecycle.integration tests passed.\n");
}

void run();
