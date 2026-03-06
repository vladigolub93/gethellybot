import assert from "node:assert/strict";
import { buildCandidatePackageForManagerReview } from "../../core/matching/candidate-package.builder";
import { EVALUATION_STATUSES } from "../../core/matching/evaluation-statuses";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

function testCleanFullyNormalizedPackage(): void {
  const pkg = buildCandidatePackageForManagerReview({
    candidate: {
      summary: "Senior backend engineer",
      profile: { location: "Ukraine" },
      technicalSummary: { confidence: "high" },
    },
    match: {
      status: "candidate_applied",
      candidateDecision: "applied",
      managerDecision: "pending",
      contactShared: false,
      score: 88,
    },
    interview: {
      sessionState: "interviewing_candidate",
      hasInterviewPlan: true,
      answerCount: 2,
      currentQuestionIndex: 1,
    },
    evaluation: {
      interviewConfidenceLevel: "high",
    },
    verification: {
      videoVerified: true,
      identityVerified: true,
      notes: ["voice verified"],
    },
  });

  assert.equal(pkg.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(pkg.interviewStatus, INTERVIEW_STATUSES.IN_PROGRESS);
  assert.equal(pkg.evaluationStatus, EVALUATION_STATUSES.STRONG);
  assert.equal(pkg.isCandidateSentToManager, true);
  assert.deepEqual(pkg.notes, []);
  assert.deepEqual(pkg.risks, []);
  assert.equal(pkg.verificationSummary?.videoVerified, true);
}

function testAmbiguousStatusesBecomeNullWithNotes(): void {
  const pkg = buildCandidatePackageForManagerReview({
    candidate: {
      summary: "Candidate",
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

  assert.equal(pkg.matchStatus, null);
  assert.equal(pkg.interviewStatus, null);
  assert.equal(pkg.evaluationStatus, null);
  assert.equal(pkg.notes.includes("MATCH_STATUS_UNCLEAR"), true);
  assert.equal(pkg.notes.includes("INTERVIEW_STATUS_UNCLEAR"), true);
  assert.equal(pkg.notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
}

function testInterviewCompletedButEvaluationMissing(): void {
  const pkg = buildCandidatePackageForManagerReview({
    candidate: {
      summary: "Candidate",
    },
    match: {
      status: "manager_accepted",
    },
    interview: {
      hasInterviewRunRow: true,
    },
    evaluation: {},
  });

  assert.equal(pkg.matchStatus, MATCH_STATUSES.APPROVED);
  assert.equal(pkg.interviewStatus, INTERVIEW_STATUSES.COMPLETED);
  assert.equal(pkg.evaluationStatus, null);
  assert.equal(pkg.notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
  assert.equal(pkg.notes.includes("INTERVIEW_COMPLETED_WITHOUT_EVALUATION"), true);
}

function testCandidateSentToManagerCaseFromDriftDecision(): void {
  const pkg = buildCandidatePackageForManagerReview({
    candidate: {
      summary: "Candidate",
    },
    match: {
      candidateDecision: "apply",
      managerDecision: "pending",
    },
  });

  assert.equal(pkg.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(pkg.isCandidateSentToManager, true);
}

function testRejectedNonTechnicalCase(): void {
  const pkg = buildCandidatePackageForManagerReview({
    candidate: {
      summary: "Candidate",
    },
    match: {
      status: "candidate_rejected",
    },
    evaluation: {
      profileStatus: "rejected_non_technical",
    },
  });

  assert.equal(pkg.matchStatus, MATCH_STATUSES.DECLINED);
  assert.equal(pkg.evaluationStatus, EVALUATION_STATUSES.WEAK);
  assert.equal(pkg.risks.includes("PROFILE_REJECTED_NON_TECHNICAL"), true);
}

function run(): void {
  testCleanFullyNormalizedPackage();
  testAmbiguousStatusesBecomeNullWithNotes();
  testInterviewCompletedButEvaluationMissing();
  testCandidateSentToManagerCaseFromDriftDecision();
  testRejectedNonTechnicalCase();
  process.stdout.write("candidate-package.builder tests passed.\n");
}

run();
