import assert from "node:assert/strict";
import { LlmClient } from "../../ai/llm.client";
import { Logger } from "../../config/logger";
import { ManagerExposureService } from "../../core/matching/manager-exposure.service";
import { MatchRecord } from "../../decisions/match.types";
import { MatchCardComposerService } from "../../matching/match-card-composer.service";
import { CandidateTechnicalSummaryV1 } from "../../shared/types/candidate-summary.types";

class LlmClientMock {
  public readonly prompts: string[] = [];

  constructor(private readonly response: string) {}

  async generateStructuredJson(prompt: string): Promise<string> {
    this.prompts.push(prompt);
    return this.response;
  }

  getModelName(): string {
    return "mock-llm";
  }
}

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

class ThrowingManagerExposureService {
  exposeCandidateToManager(): never {
    throw new Error("forced pull exposure failure");
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function makeTechnicalSummary(overrides: Partial<CandidateTechnicalSummaryV1> = {}): CandidateTechnicalSummaryV1 {
  return {
    headline: "Senior Backend Engineer",
    technical_depth_summary: "Built resilient APIs in Node.js",
    architecture_and_scale: "Scaled to 2M MAU",
    domain_expertise: "Fintech",
    ownership_and_authority: "Owned platform migration",
    strength_highlights: ["system design"],
    risk_flags: [],
    interview_confidence_level: "high",
    overall_assessment: "Strong",
    ...overrides,
  };
}

function makeMatch(overrides: Partial<MatchRecord> = {}): MatchRecord {
  return {
    id: "match_001",
    managerUserId: 2001,
    candidateUserId: 1001,
    jobSummary: "Senior backend role",
    jobTechnicalSummary: null,
    candidateSummary: "Legacy summary",
    candidateTechnicalSummary: makeTechnicalSummary(),
    score: 89,
    explanation: "Strong fit for backend role",
    explanationJson: {
      message_for_candidate: "Candidate-side explanation",
      message_for_manager: "Manager-side explanation",
      one_suggested_live_question: "Tell me about your architecture decisions.",
    },
    candidateDecision: "applied",
    managerDecision: "pending",
    status: "candidate_applied",
    createdAt: "2026-03-06T12:00:00.000Z",
    updatedAt: "2026-03-06T12:00:00.000Z",
    ...overrides,
  };
}

async function testCleanNormalizedCardPath(): Promise<void> {
  const llm = new LlmClientMock(
    JSON.stringify({
      title: "Manager Card",
      body: "Candidate looks relevant.",
      keyFacts: { ok: "yes" },
    }),
  );
  const logger = new LoggerMock();
  const service = new MatchCardComposerService(llm as unknown as LlmClient, logger);

  const result = await service.composeForManager(
    makeMatch({ candidateSummary: "  Strong normalized candidate summary  " }),
    "en",
  );

  assert.match(result.text, /Manager Card/);
  assert.equal(llm.prompts.length > 0, true);
  assert.match(llm.prompts[0] ?? "", /"candidateSummary": "Strong normalized candidate summary"/);

  const builtLogs = findDebug(logger, "manager_card.normalized_built");
  assert.equal(builtLogs.length, 1);
  assert.equal(builtLogs[0]?.meta?.matchStatus, "SENT_TO_MANAGER");
  assert.equal(builtLogs[0]?.meta?.evaluationStatus, "STRONG");
  const lifecycleLogs = findDebug(logger, "match_lifecycle.send_to_manager.transition");
  assert.equal(lifecycleLogs.length, 1);
  const pullPathLogs = findDebug(logger, "manager_exposure.pull_path_used");
  assert.equal(pullPathLogs.length, 1);
}

async function testAmbiguousNormalizationStillRendersSafely(): Promise<void> {
  const llm = new LlmClientMock(
    JSON.stringify({
      title: "Manager Card",
      body: "Safe render path.",
      keyFacts: { ok: "yes" },
    }),
  );
  const logger = new LoggerMock();
  const service = new MatchCardComposerService(llm as unknown as LlmClient, logger);

  await service.composeForManager(
    makeMatch({
      status: "legacy_unknown" as unknown as MatchRecord["status"],
      candidateDecision: "rejected",
      managerDecision: "accepted",
    }),
    "en",
  );

  const builtLogs = findDebug(logger, "manager_card.normalized_built");
  assert.equal(builtLogs.length, 1);
  assert.equal(builtLogs[0]?.meta?.matchStatus, null);

  const notesLogs = findDebug(logger, "manager_card.normalization_notes");
  assert.equal(notesLogs.length, 1);
  const notes = (notesLogs[0]?.meta?.notes ?? []) as string[];
  assert.equal(notes.includes("MATCH_STATUS_UNCLEAR"), true);
}

async function testMissingEvaluationStillSafe(): Promise<void> {
  const llm = new LlmClientMock(
    JSON.stringify({
      title: "Manager Card",
      body: "No eval details but still safe.",
      keyFacts: { ok: "yes" },
    }),
  );
  const logger = new LoggerMock();
  const service = new MatchCardComposerService(llm as unknown as LlmClient, logger);

  const result = await service.composeForManager(
    makeMatch({
      candidateTechnicalSummary: null,
      score: Number.NaN,
    }),
    "en",
  );

  assert.match(result.text, /Manager Card/);

  const builtLogs = findDebug(logger, "manager_card.normalized_built");
  assert.equal(builtLogs.length, 1);
  assert.equal(builtLogs[0]?.meta?.evaluationStatus, null);

  const notesLogs = findDebug(logger, "manager_card.normalization_notes");
  assert.equal(notesLogs.length, 1);
  const notes = (notesLogs[0]?.meta?.notes ?? []) as string[];
  assert.equal(notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
}

async function testSentToManagerCaseStillWorks(): Promise<void> {
  const llm = new LlmClientMock(
    JSON.stringify({
      title: "Manager Card",
      body: "Sent to manager path.",
      keyFacts: { ok: "yes" },
    }),
  );
  const logger = new LoggerMock();
  const service = new MatchCardComposerService(llm as unknown as LlmClient, logger);

  const result = await service.composeForManager(
    makeMatch({
      candidateDecision: "apply" as unknown as MatchRecord["candidateDecision"],
      status: "legacy_unknown" as unknown as MatchRecord["status"],
    }),
    "en",
  );

  assert.match(result.text, /Manager Card/);

  const builtLogs = findDebug(logger, "manager_card.normalized_built");
  assert.equal(builtLogs.length, 1);
  assert.equal(builtLogs[0]?.meta?.isCandidateSentToManager, true);
}

async function testPullExposureFailureDoesNotBreakCardFlow(): Promise<void> {
  const llm = new LlmClientMock(
    JSON.stringify({
      title: "Manager Card",
      body: "Safe fallback despite exposure sidecar failure.",
      keyFacts: { ok: "yes" },
    }),
  );
  const logger = new LoggerMock();
  const service = new MatchCardComposerService(
    llm as unknown as LlmClient,
    logger,
    new ThrowingManagerExposureService() as unknown as ManagerExposureService,
  );

  const result = await service.composeForManager(makeMatch(), "en");
  assert.match(result.text, /Manager Card/);

  const failures = logger.warnCalls.filter((entry) => entry.message === "manager_exposure.failed");
  assert.equal(failures.length, 1);
}

async function run(): Promise<void> {
  await testCleanNormalizedCardPath();
  await testAmbiguousNormalizationStillRendersSafely();
  await testMissingEvaluationStillSafe();
  await testSentToManagerCaseStillWorks();
  await testPullExposureFailureDoesNotBreakCardFlow();
  process.stdout.write("match-card-composer.manager-normalized tests passed.\n");
}

void run();
