import assert from "node:assert/strict";
import { EVALUATION_STATUSES } from "../../core/matching/evaluation-statuses";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import {
  normalizeLegacyEvaluationStatus,
  normalizeLegacyInterviewStatus,
  normalizeLegacyMatchStatus,
} from "../../core/matching/lifecycle-normalizers";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

function testMatchStatusFromLegacyField(): void {
  const normalized = normalizeLegacyMatchStatus({
    status: "candidate_applied",
  });
  assert.equal(normalized, MATCH_STATUSES.SENT_TO_MANAGER);
}

function testMatchStatusFromCandidateDecisionApplied(): void {
  const normalized = normalizeLegacyMatchStatus({
    candidateDecision: "applied",
  });
  assert.equal(normalized, MATCH_STATUSES.SENT_TO_MANAGER);
}

function testMatchStatusFromAdminDriftApply(): void {
  const normalized = normalizeLegacyMatchStatus({
    candidateDecision: "apply",
  });
  assert.equal(normalized, MATCH_STATUSES.SENT_TO_MANAGER);
}

function testMatchStatusAmbiguousConflictReturnsNull(): void {
  const normalized = normalizeLegacyMatchStatus({
    candidateDecision: "rejected",
    managerDecision: "accepted",
  });
  assert.equal(normalized, null);
}

function testInterviewStatusInterviewingCandidateStarted(): void {
  const normalized = normalizeLegacyInterviewStatus({
    sessionState: "interviewing_candidate",
    hasInterviewPlan: true,
    answerCount: 0,
  });
  assert.equal(normalized, INTERVIEW_STATUSES.STARTED);
}

function testInterviewStatusInterviewingManagerInProgress(): void {
  const normalized = normalizeLegacyInterviewStatus({
    sessionState: "interviewing_manager",
    answerCount: 2,
    currentQuestionIndex: 1,
  });
  assert.equal(normalized, INTERVIEW_STATUSES.IN_PROGRESS);
}

function testInterviewStatusCompletedFromRunRow(): void {
  const normalized = normalizeLegacyInterviewStatus({
    hasInterviewRunRow: true,
  });
  assert.equal(normalized, INTERVIEW_STATUSES.COMPLETED);
}

function testInterviewStatusCompletedFromRunTimestamp(): void {
  const normalized = normalizeLegacyInterviewStatus({
    interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
  });
  assert.equal(normalized, INTERVIEW_STATUSES.COMPLETED);
}

function testInterviewStatusConflictCompletedVsAbandonedReturnsNull(): void {
  const normalized = normalizeLegacyInterviewStatus({
    interviewRunStatus: "abandoned",
    interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
  });
  assert.equal(normalized, null);
}

function testInterviewStatusUnknownReturnsNull(): void {
  const normalized = normalizeLegacyInterviewStatus({
    sessionState: "candidate_profile_ready",
  });
  assert.equal(normalized, null);
}

function testEvaluationFromProfileStatusRejectedNonTechnical(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    profileStatus: "rejected_non_technical",
  });
  assert.equal(normalized, EVALUATION_STATUSES.WEAK);
}

function testEvaluationFromConfidenceHigh(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    interviewConfidenceLevel: "high",
  });
  assert.equal(normalized, EVALUATION_STATUSES.STRONG);
}

function testEvaluationProfileAndConfidencePrefersConfidence(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    profileStatus: "analysis_ready",
    interviewConfidenceLevel: "medium",
  });
  assert.equal(normalized, EVALUATION_STATUSES.POSSIBLE);
}

function testEvaluationFromRecommendation(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    recommendation: "weak",
  });
  assert.equal(normalized, EVALUATION_STATUSES.WEAK);
}

function testEvaluationFromEvaluatorSignals(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    shouldRequestReanswer: true,
    aiAssistedLikelihood: "high",
    aiAssistedConfidence: 0.82,
  });
  assert.equal(normalized, EVALUATION_STATUSES.WEAK);
}

function testEvaluationFromScoreFallback(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    matchScore: 90,
  });
  assert.equal(normalized, EVALUATION_STATUSES.STRONG);
}

function testEvaluationConflictRejectedProfileVsStrongRecommendationReturnsNull(): void {
  const normalized = normalizeLegacyEvaluationStatus({
    profileStatus: "rejected_non_technical",
    recommendation: "strong",
  });
  assert.equal(normalized, null);
}

function testEvaluationUnknownReturnsNull(): void {
  const normalized = normalizeLegacyEvaluationStatus({});
  assert.equal(normalized, null);
}

function run(): void {
  testMatchStatusFromLegacyField();
  testMatchStatusFromCandidateDecisionApplied();
  testMatchStatusFromAdminDriftApply();
  testMatchStatusAmbiguousConflictReturnsNull();
  testInterviewStatusInterviewingCandidateStarted();
  testInterviewStatusInterviewingManagerInProgress();
  testInterviewStatusCompletedFromRunRow();
  testInterviewStatusCompletedFromRunTimestamp();
  testInterviewStatusConflictCompletedVsAbandonedReturnsNull();
  testInterviewStatusUnknownReturnsNull();
  testEvaluationFromProfileStatusRejectedNonTechnical();
  testEvaluationFromConfidenceHigh();
  testEvaluationProfileAndConfidencePrefersConfidence();
  testEvaluationFromRecommendation();
  testEvaluationFromEvaluatorSignals();
  testEvaluationFromScoreFallback();
  testEvaluationConflictRejectedProfileVsStrongRecommendationReturnsNull();
  testEvaluationUnknownReturnsNull();
  process.stdout.write("lifecycle-normalizers tests passed.\n");
}

run();
