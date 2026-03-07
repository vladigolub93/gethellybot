import assert from "node:assert/strict";
import { MATCH_STATUSES } from "../../core/matching/match-statuses";
import { resolveDecisionGateSnapshot } from "../../core/matching/decision-gate-snapshot";

function testCleanAlignedLegacyAndCanonicalCase(): void {
  const snapshot = resolveDecisionGateSnapshot({
    status: "candidate_applied",
    candidateDecision: "applied",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.SENT_TO_MANAGER,
  });

  assert.equal(snapshot.canonicalMatchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(snapshot.legacyGateState, "MANAGER_DECISION_OPEN");
  assert.equal(snapshot.candidateMayAccept, false);
  assert.equal(snapshot.candidateMayReject, false);
  assert.equal(snapshot.managerMayApprove, true);
  assert.equal(snapshot.managerMayReject, true);
  assert.equal(snapshot.divergenceNotes.length, 0);
}

function testOverloadedCandidateAppliedCase(): void {
  const snapshot = resolveDecisionGateSnapshot({
    status: "candidate_applied",
    candidateDecision: "apply",
    managerDecision: "pending",
    canonicalMatchStatus: null,
  });

  assert.equal(snapshot.canonicalMatchStatus, MATCH_STATUSES.SENT_TO_MANAGER);
  assert.equal(snapshot.legacyGateState, "MANAGER_DECISION_OPEN");
  assert.equal(snapshot.managerMayApprove, true);
  assert.equal(snapshot.risks.includes("LEGACY_STATUS_OVERLOADED_CANDIDATE_APPLIED"), true);
}

function testCanonicalAndLegacyDivergenceCase(): void {
  const snapshot = resolveDecisionGateSnapshot({
    status: "proposed",
    candidateDecision: "pending",
    managerDecision: "pending",
    canonicalMatchStatus: MATCH_STATUSES.SENT_TO_MANAGER,
  });

  assert.equal(snapshot.candidateMayAccept, true);
  assert.equal(snapshot.managerMayApprove, false);
  assert.equal(snapshot.divergenceNotes.includes("CANDIDATE_GATE_DIVERGES_FROM_CANONICAL"), true);
  assert.equal(snapshot.divergenceNotes.includes("MANAGER_GATE_DIVERGES_FROM_CANONICAL"), true);
  assert.equal(
    snapshot.divergenceNotes.includes("CANONICAL_PERSISTED_DIFFERS_FROM_LEGACY_NORMALIZED"),
    true,
  );
}

function testAlreadyApprovedAndRejectedCases(): void {
  const approvedSnapshot = resolveDecisionGateSnapshot({
    status: "manager_accepted",
    candidateDecision: "applied",
    managerDecision: "accepted",
    canonicalMatchStatus: MATCH_STATUSES.APPROVED,
    contactShared: false,
  });
  assert.equal(approvedSnapshot.legacyGateState, "CONTACT_SHARE_PENDING");
  assert.equal(approvedSnapshot.candidateMayAccept, false);
  assert.equal(approvedSnapshot.managerMayApprove, false);
  assert.equal(approvedSnapshot.divergenceNotes.length, 0);

  const rejectedSnapshot = resolveDecisionGateSnapshot({
    status: "manager_rejected",
    candidateDecision: "applied",
    managerDecision: "rejected",
    canonicalMatchStatus: MATCH_STATUSES.REJECTED,
  });
  assert.equal(rejectedSnapshot.legacyGateState, "NON_ACTIONABLE");
  assert.equal(rejectedSnapshot.candidateMayReject, false);
  assert.equal(rejectedSnapshot.managerMayReject, false);
}

function testAmbiguousNoStatusCase(): void {
  const snapshot = resolveDecisionGateSnapshot({
    status: null,
    candidateDecision: null,
    managerDecision: null,
    canonicalMatchStatus: null,
  });

  assert.equal(snapshot.canonicalMatchStatus, null);
  assert.equal(snapshot.legacyGateState, null);
  assert.equal(snapshot.candidateMayAccept, false);
  assert.equal(snapshot.candidateMayReject, false);
  assert.equal(snapshot.managerMayApprove, false);
  assert.equal(snapshot.managerMayReject, false);
  assert.equal(snapshot.risks.includes("CANONICAL_STATUS_UNRESOLVED"), true);
  assert.equal(snapshot.risks.includes("LEGACY_GATE_STATE_UNRESOLVED"), true);
}

function run(): void {
  testCleanAlignedLegacyAndCanonicalCase();
  testOverloadedCandidateAppliedCase();
  testCanonicalAndLegacyDivergenceCase();
  testAlreadyApprovedAndRejectedCases();
  testAmbiguousNoStatusCase();
  process.stdout.write("decision-gate-snapshot tests passed.\n");
}

run();

