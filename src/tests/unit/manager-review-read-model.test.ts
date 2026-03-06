import assert from "node:assert/strict";
import { EVALUATION_STATUSES } from "../../core/matching/evaluation-statuses";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { buildManagerReviewReadModel } from "../../core/matching/manager-review-read-model";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

function testCleanNormalizedReadModel(): void {
  const model = buildManagerReviewReadModel({
    candidate: {
      summary: "  Senior backend engineer  ",
      technicalSummary: { interview_confidence_level: "high" },
    },
    match: {
      status: "candidate_applied",
      candidateDecision: "applied",
      managerDecision: "pending",
      contactShared: false,
      score: 92,
      explanation: "Strong overlap",
    },
    interview: {
      sessionState: "interviewing_candidate",
      hasInterviewPlan: true,
      answerCount: 1,
      currentQuestionIndex: 1,
    },
    evaluation: {
      interviewConfidenceLevel: "high",
    },
  });

  assert.equal(model.candidateSummary, "Senior backend engineer");
  assert.equal(model.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(model.interviewStatus, INTERVIEW_STATUSES.IN_PROGRESS);
  assert.equal(model.evaluationStatus, EVALUATION_STATUSES.STRONG);
  assert.equal(model.isCandidateSentToManager, true);
  assert.deepEqual(model.notes, []);
}

function testAmbiguousNormalizationStillSafe(): void {
  const model = buildManagerReviewReadModel({
    candidate: {
      summary: "Legacy fallback summary",
    },
    match: {
      candidateDecision: "rejected",
      managerDecision: "accepted",
    },
    interview: {
      interviewRunStatus: "abandoned",
      interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
    },
    evaluation: {
      profileStatus: "rejected_non_technical",
      recommendation: "strong",
    },
  });

  assert.equal(model.candidateSummary, "Legacy fallback summary");
  assert.equal(model.matchStatus, null);
  assert.equal(model.interviewStatus, null);
  assert.equal(model.evaluationStatus, null);
  assert.equal(model.notes.includes("MATCH_STATUS_UNCLEAR"), true);
  assert.equal(model.notes.includes("INTERVIEW_STATUS_UNCLEAR"), true);
  assert.equal(model.notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
  assert.equal(model.risks.includes("PROFILE_REJECTED_NON_TECHNICAL"), true);
}

function testMissingEvaluationStillSafe(): void {
  const model = buildManagerReviewReadModel({
    candidate: {
      summary: "Candidate",
    },
    match: {
      status: "manager_accepted",
      score: Number.NaN,
    },
    interview: {
      hasInterviewRunRow: true,
    },
    evaluation: {},
  });

  assert.equal(model.matchStatus, MATCH_STATUSES.APPROVED);
  assert.equal(model.interviewStatus, INTERVIEW_STATUSES.COMPLETED);
  assert.equal(model.evaluationStatus, null);
  assert.equal(model.notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
  assert.equal(model.notes.includes("INTERVIEW_COMPLETED_WITHOUT_EVALUATION"), true);
  assert.equal(model.legacy.score, null);
}

function testSentToManagerCaseStillWorks(): void {
  const model = buildManagerReviewReadModel({
    candidate: {
      summary: "Candidate",
    },
    match: {
      candidateDecision: "apply",
      managerDecision: "pending",
    },
  });

  assert.equal(model.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(model.isCandidateSentToManager, true);
  assert.equal(model.legacy.candidateDecision, "apply");
}

function run(): void {
  testCleanNormalizedReadModel();
  testAmbiguousNormalizationStillSafe();
  testMissingEvaluationStillSafe();
  testSentToManagerCaseStillWorks();
  process.stdout.write("manager-review-read-model tests passed.\n");
}

run();
