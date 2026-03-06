import { type EvaluationStatus } from "./evaluation-statuses";
import { type InterviewStatus, INTERVIEW_STATUSES } from "./interview-statuses";
import {
  type LegacyEvaluationInput,
  type LegacyInterviewLifecycleInput,
  type LegacyMatchLifecycleInput,
  normalizeLegacyEvaluationStatus,
  normalizeLegacyInterviewStatus,
  normalizeLegacyMatchStatus,
} from "./lifecycle-normalizers";
import { type MatchStatus, MATCH_STATUSES } from "./match-statuses";

export interface LifecycleSnapshotResolverInput {
  match?: LegacyMatchLifecycleInput & {
    id?: string | null;
  };
  interview?: LegacyInterviewLifecycleInput;
  evaluation?: LegacyEvaluationInput;
  exposure?: {
    managerVisible?: boolean | null;
    source?: string | null;
  };
}

export interface LifecycleSnapshotRawSummary {
  matchId: string | null;
  status: string | null;
  candidateDecision: string | null;
  managerDecision: string | null;
  interviewSessionState: string | null;
  interviewRunStatus: string | null;
  profileStatus: string | null;
  interviewConfidenceLevel: string | null;
  recommendation: string | null;
  managerVisibleHint: boolean | null;
  exposureSource: string | null;
}

export interface LifecycleSnapshot {
  matchStatus: MatchStatus | null;
  interviewStatus: InterviewStatus | null;
  evaluationStatus: EvaluationStatus | null;
  notes: string[];
  risks: string[];
  raw: LifecycleSnapshotRawSummary;
}

/**
 * Unified read-only lifecycle snapshot resolver.
 *
 * Purpose:
 * - One place to normalize mixed legacy lifecycle fields for read paths.
 * - No writes, no side effects, no runtime state transitions.
 */
export function resolveLifecycleSnapshot(
  input: LifecycleSnapshotResolverInput,
): LifecycleSnapshot {
  const raw = buildRawSummary(input);

  const matchStatus = normalizeLegacyMatchStatus({
    status: raw.status,
    candidateDecision: raw.candidateDecision,
    managerDecision: raw.managerDecision,
    contactShared: input.match?.contactShared ?? null,
  });

  const interviewStatus = normalizeLegacyInterviewStatus({
    sessionState: raw.interviewSessionState,
    interviewRunStatus: raw.interviewRunStatus,
    hasInterviewRunRow: input.interview?.hasInterviewRunRow,
    interviewRunCompletedAt: input.interview?.interviewRunCompletedAt,
    interviewStartedAt: input.interview?.interviewStartedAt,
    interviewCompletedAt: input.interview?.interviewCompletedAt,
    hasInterviewPlan: input.interview?.hasInterviewPlan,
    answerCount: input.interview?.answerCount,
    currentQuestionIndex: input.interview?.currentQuestionIndex,
  });

  const evaluationStatus = normalizeLegacyEvaluationStatus({
    profileStatus: raw.profileStatus,
    interviewConfidenceLevel: raw.interviewConfidenceLevel,
    recommendation: raw.recommendation,
    matchScore: input.evaluation?.matchScore,
    shouldRequestReanswer: input.evaluation?.shouldRequestReanswer,
    aiAssistedLikelihood: input.evaluation?.aiAssistedLikelihood,
    aiAssistedConfidence: input.evaluation?.aiAssistedConfidence,
  });

  const notes: string[] = [];
  const risks: string[] = [];

  if (matchStatus === null) {
    notes.push("MATCH_STATUS_UNCLEAR");
  }
  if (interviewStatus === null) {
    notes.push("INTERVIEW_STATUS_UNCLEAR");
  }
  if (evaluationStatus === null) {
    notes.push("EVALUATION_STATUS_UNCLEAR");
  }

  if (raw.status === "candidate_applied") {
    notes.push("LEGACY_CANDIDATE_APPLIED_OVERLOADED");
  }
  if (raw.candidateDecision === "apply") {
    notes.push("LEGACY_APPLY_ALIAS_USED");
  }

  if (
    matchStatus === MATCH_STATUSES.SENT_TO_MANAGER &&
    interviewStatus !== INTERVIEW_STATUSES.COMPLETED
  ) {
    risks.push("SENT_TO_MANAGER_WITHOUT_COMPLETED_INTERVIEW_SIGNAL");
  }

  if (
    interviewStatus === INTERVIEW_STATUSES.COMPLETED &&
    evaluationStatus === null
  ) {
    notes.push("INTERVIEW_COMPLETED_WITHOUT_EVALUATION");
  }

  if (raw.profileStatus === "rejected_non_technical") {
    risks.push("PROFILE_REJECTED_NON_TECHNICAL");
  }

  if (raw.managerVisibleHint === true && matchStatus !== MATCH_STATUSES.SENT_TO_MANAGER) {
    notes.push("EXPOSURE_HINT_CONFLICT");
  }

  return {
    matchStatus,
    interviewStatus,
    evaluationStatus,
    notes,
    risks,
    raw,
  };
}

function buildRawSummary(input: LifecycleSnapshotResolverInput): LifecycleSnapshotRawSummary {
  return {
    matchId: normalizeText(input.match?.id),
    status: normalizeText(input.match?.status),
    candidateDecision: normalizeText(input.match?.candidateDecision),
    managerDecision: normalizeText(input.match?.managerDecision),
    interviewSessionState: normalizeText(input.interview?.sessionState),
    interviewRunStatus: normalizeText(input.interview?.interviewRunStatus),
    profileStatus: normalizeText(input.evaluation?.profileStatus),
    interviewConfidenceLevel: normalizeText(input.evaluation?.interviewConfidenceLevel),
    recommendation: normalizeText(input.evaluation?.recommendation),
    managerVisibleHint:
      typeof input.exposure?.managerVisible === "boolean" ? input.exposure.managerVisible : null,
    exposureSource: normalizeText(input.exposure?.source),
  };
}

function normalizeText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim().toLowerCase();
  return trimmed ? trimmed : null;
}
