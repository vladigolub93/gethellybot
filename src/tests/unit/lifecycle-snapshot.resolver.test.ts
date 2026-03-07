import assert from "node:assert/strict";
import { EVALUATION_STATUSES } from "../../core/matching/evaluation-statuses";
import { INTERVIEW_STATUSES } from "../../core/matching/interview-statuses";
import { resolveLifecycleSnapshot } from "../../core/matching/lifecycle-snapshot.resolver";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";

function testCleanAllStatusSnapshot(): void {
  const snapshot = resolveLifecycleSnapshot({
    match: {
      id: "m_1",
      status: "candidate_applied",
      candidateDecision: "applied",
      managerDecision: "pending",
    },
    interview: {
      interviewRunStatus: "completed",
      interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
      hasInterviewRunRow: true,
    },
    evaluation: {
      interviewConfidenceLevel: "high",
    },
    exposure: {
      managerVisible: true,
      source: "notification_push",
    },
  });

  assert.equal(snapshot.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(snapshot.interviewStatus, INTERVIEW_STATUSES.COMPLETED);
  assert.equal(snapshot.evaluationStatus, EVALUATION_STATUSES.STRONG);
  assert.equal(snapshot.raw.matchId, "m_1");
  assert.equal(snapshot.notes.includes("LEGACY_CANDIDATE_APPLIED_OVERLOADED"), true);
}

function testAmbiguousMatchStatus(): void {
  const snapshot = resolveLifecycleSnapshot({
    match: {
      status: "unknown_status",
      candidateDecision: "rejected",
      managerDecision: "accepted",
    },
  });

  assert.equal(snapshot.matchStatus, null);
  assert.equal(snapshot.notes.includes("MATCH_STATUS_UNCLEAR"), true);
}

function testAmbiguousInterviewStatus(): void {
  const snapshot = resolveLifecycleSnapshot({
    interview: {
      interviewRunStatus: "abandoned",
      interviewRunCompletedAt: "2026-03-06T10:00:00.000Z",
    },
  });

  assert.equal(snapshot.interviewStatus, null);
  assert.equal(snapshot.notes.includes("INTERVIEW_STATUS_UNCLEAR"), true);
}

function testMissingEvaluationStatus(): void {
  const snapshot = resolveLifecycleSnapshot({
    match: {
      status: "candidate_applied",
      candidateDecision: "applied",
      managerDecision: "pending",
    },
    interview: {
      interviewRunStatus: "completed",
    },
    evaluation: {},
  });

  assert.equal(snapshot.evaluationStatus, null);
  assert.equal(snapshot.notes.includes("EVALUATION_STATUS_UNCLEAR"), true);
  assert.equal(snapshot.notes.includes("INTERVIEW_COMPLETED_WITHOUT_EVALUATION"), true);
}

function testOverloadedLegacyValuesCandidateAppliedAndApplyAlias(): void {
  const snapshot = resolveLifecycleSnapshot({
    match: {
      status: "candidate_applied",
      candidateDecision: "apply",
      managerDecision: "pending",
    },
  });

  assert.equal(snapshot.matchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(snapshot.notes.includes("LEGACY_CANDIDATE_APPLIED_OVERLOADED"), true);
  assert.equal(snapshot.notes.includes("LEGACY_APPLY_ALIAS_USED"), true);
}

function testRejectedNonTechnicalCase(): void {
  const snapshot = resolveLifecycleSnapshot({
    evaluation: {
      profileStatus: "rejected_non_technical",
    },
  });

  assert.equal(snapshot.evaluationStatus, EVALUATION_STATUSES.WEAK);
  assert.equal(snapshot.risks.includes("PROFILE_REJECTED_NON_TECHNICAL"), true);
}

function run(): void {
  testCleanAllStatusSnapshot();
  testAmbiguousMatchStatus();
  testAmbiguousInterviewStatus();
  testMissingEvaluationStatus();
  testOverloadedLegacyValuesCandidateAppliedAndApplyAlias();
  testRejectedNonTechnicalCase();
  process.stdout.write("lifecycle-snapshot.resolver tests passed.\n");
}

run();
