import { type EvaluationStatus } from "./evaluation-statuses";
import { INTERVIEW_STATUSES, type InterviewStatus } from "./interview-statuses";
import {
  type LegacyEvaluationInput,
  type LegacyInterviewLifecycleInput,
  type LegacyMatchLifecycleInput,
  normalizeLegacyEvaluationStatus,
  normalizeLegacyInterviewStatus,
  normalizeLegacyMatchStatus,
} from "./lifecycle-normalizers";
import { MATCH_STATUSES, type MatchStatus } from "./match-statuses";

export interface CandidatePackageBuilderInput {
  candidate?: {
    summary?: string | null;
    profile?: Record<string, unknown> | null;
    technicalSummary?: Record<string, unknown> | null;
  };
  match?: {
    id?: string | null;
    candidateSummary?: string | null;
    score?: number | null;
    explanation?: string | null;
  } & LegacyMatchLifecycleInput;
  interview?: LegacyInterviewLifecycleInput;
  evaluation?: LegacyEvaluationInput;
  verification?: {
    videoVerified?: boolean | null;
    contactShared?: boolean | null;
    identityVerified?: boolean | null;
    notes?: string[] | null;
  };
}

export interface CandidatePackageRawEvaluationSignals {
  profileStatus: string | null;
  interviewConfidenceLevel: string | null;
  recommendation: string | null;
  matchScore: number | null;
  shouldRequestReanswer: boolean | null;
  aiAssistedLikelihood: string | null;
  aiAssistedConfidence: number | null;
}

export interface CandidatePackageVerificationSummary {
  videoVerified: boolean | null;
  contactShared: boolean | null;
  identityVerified: boolean | null;
  notes: string[];
}

export interface CandidatePackageForManagerReview {
  candidateSummary: string;
  candidateProfile: Record<string, unknown> | null;
  candidateTechnicalSummary: Record<string, unknown> | null;
  matchStatus: MatchStatus | null;
  interviewStatus: InterviewStatus | null;
  evaluationStatus: EvaluationStatus | null;
  rawEvaluationSignals: CandidatePackageRawEvaluationSignals;
  verificationSummary: CandidatePackageVerificationSummary | null;
  isCandidateSentToManager: boolean;
  risks: string[];
  notes: string[];
}

/**
 * Pure candidate-package builder for manager review screens.
 *
 * This is normalization-only infrastructure:
 * - no writes
 * - no routing side effects
 * - no business decision changes
 */
export function buildCandidatePackageForManagerReview(
  input: CandidatePackageBuilderInput,
): CandidatePackageForManagerReview {
  const candidateSummary =
    normalizeText(input.candidate?.summary) ??
    normalizeText(input.match?.candidateSummary) ??
    "";

  const matchStatus = normalizeLegacyMatchStatus({
    status: input.match?.status,
    candidateDecision: input.match?.candidateDecision,
    managerDecision: input.match?.managerDecision,
    contactShared: input.match?.contactShared,
  });

  const interviewStatus = normalizeLegacyInterviewStatus({
    sessionState: input.interview?.sessionState,
    interviewRunStatus: input.interview?.interviewRunStatus,
    hasInterviewRunRow: input.interview?.hasInterviewRunRow,
    interviewRunCompletedAt: input.interview?.interviewRunCompletedAt,
    interviewStartedAt: input.interview?.interviewStartedAt,
    interviewCompletedAt: input.interview?.interviewCompletedAt,
    hasInterviewPlan: input.interview?.hasInterviewPlan,
    answerCount: input.interview?.answerCount,
    currentQuestionIndex: input.interview?.currentQuestionIndex,
  });

  const rawEvaluationSignals: CandidatePackageRawEvaluationSignals = {
    profileStatus: normalizeText(input.evaluation?.profileStatus) ?? null,
    interviewConfidenceLevel: normalizeText(input.evaluation?.interviewConfidenceLevel) ?? null,
    recommendation: normalizeText(input.evaluation?.recommendation) ?? null,
    matchScore:
      typeof input.evaluation?.matchScore === "number" && Number.isFinite(input.evaluation.matchScore)
        ? input.evaluation.matchScore
        : typeof input.match?.score === "number" && Number.isFinite(input.match.score)
        ? input.match.score
        : null,
    shouldRequestReanswer:
      typeof input.evaluation?.shouldRequestReanswer === "boolean"
        ? input.evaluation.shouldRequestReanswer
        : null,
    aiAssistedLikelihood: normalizeText(input.evaluation?.aiAssistedLikelihood) ?? null,
    aiAssistedConfidence:
      typeof input.evaluation?.aiAssistedConfidence === "number" &&
      Number.isFinite(input.evaluation.aiAssistedConfidence)
        ? input.evaluation.aiAssistedConfidence
        : null,
  };

  const evaluationStatus = normalizeLegacyEvaluationStatus({
    profileStatus: rawEvaluationSignals.profileStatus,
    interviewConfidenceLevel: rawEvaluationSignals.interviewConfidenceLevel,
    recommendation: rawEvaluationSignals.recommendation,
    matchScore: rawEvaluationSignals.matchScore,
    shouldRequestReanswer: rawEvaluationSignals.shouldRequestReanswer,
    aiAssistedLikelihood: rawEvaluationSignals.aiAssistedLikelihood,
    aiAssistedConfidence: rawEvaluationSignals.aiAssistedConfidence,
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

  if (
    interviewStatus === INTERVIEW_STATUSES.COMPLETED &&
    evaluationStatus === null
  ) {
    notes.push("INTERVIEW_COMPLETED_WITHOUT_EVALUATION");
  }

  if (rawEvaluationSignals.profileStatus === "rejected_non_technical") {
    risks.push("PROFILE_REJECTED_NON_TECHNICAL");
  }

  const verificationSummary = buildVerificationSummary(input);

  return {
    candidateSummary,
    candidateProfile: input.candidate?.profile ?? null,
    candidateTechnicalSummary: input.candidate?.technicalSummary ?? null,
    matchStatus,
    interviewStatus,
    evaluationStatus,
    rawEvaluationSignals,
    verificationSummary,
    isCandidateSentToManager: isCandidateSentToManager(input, matchStatus),
    risks,
    notes,
  };
}

function isCandidateSentToManager(
  input: CandidatePackageBuilderInput,
  matchStatus: MatchStatus | null,
): boolean {
  if (matchStatus === MATCH_STATUSES.SENT_TO_MANAGER) {
    return true;
  }

  const decision = normalizeText(input.match?.candidateDecision);
  return decision === "applied" || decision === "apply";
}

function buildVerificationSummary(
  input: CandidatePackageBuilderInput,
): CandidatePackageVerificationSummary | null {
  const videoVerified =
    typeof input.verification?.videoVerified === "boolean"
      ? input.verification.videoVerified
      : null;

  const verificationContact =
    typeof input.verification?.contactShared === "boolean"
      ? input.verification.contactShared
      : null;

  const matchContact =
    typeof input.match?.contactShared === "boolean"
      ? input.match.contactShared
      : null;

  const contactShared = verificationContact ?? matchContact;

  const identityVerified =
    typeof input.verification?.identityVerified === "boolean"
      ? input.verification.identityVerified
      : null;

  const notes = toStringArray(input.verification?.notes);

  const hasAnyData =
    videoVerified !== null ||
    contactShared !== null ||
    identityVerified !== null ||
    notes.length > 0;

  if (!hasAnyData) {
    return null;
  }

  return {
    videoVerified,
    contactShared,
    identityVerified,
    notes,
  };
}

function normalizeText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toStringArray(value: string[] | null | undefined): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}
