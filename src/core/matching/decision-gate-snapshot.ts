import { normalizeLegacyMatchStatus } from "./lifecycle-normalizers";
import { MATCH_STATUSES, MatchStatus } from "./match-statuses";

export interface DecisionGateSnapshotInput {
  status?: string | null;
  candidateDecision?: string | null;
  managerDecision?: string | null;
  contactShared?: boolean | null;
  canonicalMatchStatus?: MatchStatus | null;
  hints?: {
    managerVisible?: boolean | null;
    interviewCompleted?: boolean | null;
  };
}

export interface DecisionGateSnapshot {
  canonicalMatchStatus: MatchStatus | null;
  legacyGateState: string | null;
  candidateMayAccept: boolean;
  candidateMayReject: boolean;
  managerMayApprove: boolean;
  managerMayReject: boolean;
  divergenceNotes: string[];
  risks: string[];
}

/**
 * Read-only snapshot of current legacy decision gates vs canonical lifecycle implications.
 *
 * This helper intentionally does not mutate anything and is not wired into runtime gates yet.
 */
export function resolveDecisionGateSnapshot(
  input: DecisionGateSnapshotInput,
): DecisionGateSnapshot {
  const normalizedStatus = normalizeText(input.status);
  const normalizedCandidateDecision = normalizeCandidateDecision(input.candidateDecision);
  const normalizedManagerDecision = normalizeManagerDecision(input.managerDecision);

  const canonicalPersisted = normalizeCanonicalMatchStatus(input.canonicalMatchStatus);
  const canonicalFromLegacy = normalizeLegacyMatchStatus({
    status: input.status ?? null,
    candidateDecision: input.candidateDecision ?? null,
    managerDecision: input.managerDecision ?? null,
    contactShared: normalizeContactShared(input),
  });
  const canonicalMatchStatus = canonicalPersisted ?? canonicalFromLegacy;

  const legacyGateState = resolveLegacyGateState({
    status: normalizedStatus,
    contactShared: normalizeContactShared(input),
  });

  const candidatePending = normalizedCandidateDecision === "pending";
  const managerPending = normalizedManagerDecision === "pending";
  const candidateApplied = normalizedCandidateDecision === "applied";

  const candidateGateOpen = normalizedStatus === "proposed";
  const managerGateOpen = normalizedStatus === "candidate_applied";

  const candidateMayAccept = candidateGateOpen && candidatePending;
  const candidateMayReject = candidateGateOpen && candidatePending;
  const managerMayApprove = managerGateOpen && managerPending && candidateApplied;
  const managerMayReject = managerGateOpen && managerPending && candidateApplied;

  const canonicalCandidateGateOpen = canonicalMatchStatus === MATCH_STATUSES.INVITED;
  const canonicalManagerGateOpen = canonicalMatchStatus === MATCH_STATUSES.SENT_TO_MANAGER;

  const divergenceNotes: string[] = [];
  const risks: string[] = [];

  if (candidateMayAccept !== canonicalCandidateGateOpen) {
    divergenceNotes.push("CANDIDATE_GATE_DIVERGES_FROM_CANONICAL");
  }
  if (managerMayApprove !== canonicalManagerGateOpen) {
    divergenceNotes.push("MANAGER_GATE_DIVERGES_FROM_CANONICAL");
  }

  if (
    canonicalPersisted &&
    canonicalFromLegacy &&
    canonicalPersisted !== canonicalFromLegacy
  ) {
    divergenceNotes.push("CANONICAL_PERSISTED_DIFFERS_FROM_LEGACY_NORMALIZED");
  }

  if (normalizedStatus === "candidate_applied") {
    risks.push("LEGACY_STATUS_OVERLOADED_CANDIDATE_APPLIED");
  }

  if (managerGateOpen && !candidateApplied) {
    risks.push("LEGACY_MANAGER_GATE_WITHOUT_APPLIED_CANDIDATE_DECISION");
  }

  if (!canonicalMatchStatus) {
    risks.push("CANONICAL_STATUS_UNRESOLVED");
  }

  if (
    input.hints?.managerVisible === true &&
    canonicalMatchStatus !== MATCH_STATUSES.SENT_TO_MANAGER &&
    canonicalMatchStatus !== MATCH_STATUSES.APPROVED
  ) {
    risks.push("MANAGER_VISIBLE_HINT_CONFLICT");
  }

  if (
    input.hints?.interviewCompleted === true &&
    canonicalMatchStatus === MATCH_STATUSES.INTERVIEW_STARTED
  ) {
    risks.push("INTERVIEW_COMPLETED_HINT_CONFLICT");
  }

  if (!legacyGateState) {
    risks.push("LEGACY_GATE_STATE_UNRESOLVED");
  }

  return {
    canonicalMatchStatus,
    legacyGateState,
    candidateMayAccept,
    candidateMayReject,
    managerMayApprove,
    managerMayReject,
    divergenceNotes,
    risks,
  };
}

function resolveLegacyGateState(input: {
  status: string | null;
  contactShared: boolean | null;
}): string | null {
  if (input.status === "proposed") {
    return "CANDIDATE_DECISION_OPEN";
  }
  if (input.status === "candidate_applied") {
    return "MANAGER_DECISION_OPEN";
  }
  if (input.status === "manager_accepted" && input.contactShared !== true) {
    return "CONTACT_SHARE_PENDING";
  }
  if (input.status === "contact_shared" || input.contactShared === true) {
    return "CONTACT_SHARED";
  }
  if (input.status) {
    return "NON_ACTIONABLE";
  }
  return null;
}

function normalizeCanonicalMatchStatus(value: MatchStatus | null | undefined): MatchStatus | null {
  if (!value) {
    return null;
  }
  const values = new Set<string>(Object.values(MATCH_STATUSES));
  return values.has(value) ? value : null;
}

function normalizeContactShared(input: DecisionGateSnapshotInput): boolean | null {
  if (typeof input.contactShared === "boolean") {
    return input.contactShared;
  }
  const status = normalizeText(input.status);
  if (status === "contact_shared") {
    return true;
  }
  return null;
}

function normalizeCandidateDecision(
  value: string | null | undefined,
): "pending" | "applied" | "rejected" | null {
  const normalized = normalizeText(value);
  if (!normalized) {
    return null;
  }
  if (normalized === "pending") {
    return "pending";
  }
  if (normalized === "applied" || normalized === "apply") {
    return "applied";
  }
  if (normalized === "rejected" || normalized === "reject" || normalized === "declined") {
    return "rejected";
  }
  return null;
}

function normalizeManagerDecision(
  value: string | null | undefined,
): "pending" | "accepted" | "rejected" | null {
  const normalized = normalizeText(value);
  if (!normalized) {
    return null;
  }
  if (normalized === "pending") {
    return "pending";
  }
  if (normalized === "accepted" || normalized === "accept" || normalized === "approved") {
    return "accepted";
  }
  if (normalized === "rejected" || normalized === "reject" || normalized === "declined") {
    return "rejected";
  }
  return null;
}

function normalizeText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim().toLowerCase();
  return trimmed || null;
}

