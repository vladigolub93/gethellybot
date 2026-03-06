import { EVALUATION_STATUSES, type EvaluationStatus } from "./evaluation-statuses";
import { INTERVIEW_STATUSES, type InterviewStatus } from "./interview-statuses";
import {
  LEGACY_INTERVIEW_DB_STATUSES,
  LEGACY_INTERVIEW_DB_STATUS_TO_CANONICAL,
  LEGACY_MATCH_SCORE_BANDS_TO_EVALUATION,
  LEGACY_MATCH_STATUS_TO_CANONICAL,
  LEGACY_PROFILE_STATUS,
  LEGACY_PROFILE_STATUS_TO_EVALUATION,
  type LegacyInterviewDbStatus,
  type LegacyMatchStatus,
  type LegacyProfileStatus,
} from "./legacy-matching-compat";
import { MATCH_STATUSES, type MatchStatus } from "./match-statuses";

export interface LegacyMatchLifecycleInput {
  status?: string | null;
  candidateDecision?: string | null;
  managerDecision?: string | null;
  contactShared?: boolean | null;
}

export interface LegacyInterviewLifecycleInput {
  sessionState?: string | null;
  interviewRunStatus?: string | null;
  hasInterviewRunRow?: boolean | null;
  interviewRunCompletedAt?: string | null;
  interviewStartedAt?: string | null;
  interviewCompletedAt?: string | null;
  hasInterviewPlan?: boolean | null;
  answerCount?: number | null;
  currentQuestionIndex?: number | null;
}

export interface LegacyEvaluationInput {
  profileStatus?: string | null;
  interviewConfidenceLevel?: string | null;
  recommendation?: string | null;
  matchScore?: number | null;
  shouldRequestReanswer?: boolean | null;
  aiAssistedLikelihood?: string | null;
  aiAssistedConfidence?: number | null;
}

/**
 * Maps legacy match lifecycle shape to canonical MatchStatus.
 * Returns null when signals conflict or are insufficient.
 */
export function normalizeLegacyMatchStatus(
  input: LegacyMatchLifecycleInput,
): MatchStatus | null {
  const legacyStatus = toLegacyMatchStatus(input.status);
  if (legacyStatus) {
    return LEGACY_MATCH_STATUS_TO_CANONICAL[legacyStatus];
  }

  const normalizedCandidateDecision = normalizeCandidateDecision(input.candidateDecision);
  const normalizedManagerDecision = normalizeManagerDecision(input.managerDecision);

  const derived: MatchStatus[] = [];

  if (input.contactShared === true) {
    derived.push(MATCH_STATUSES.APPROVED);
  }

  if (normalizedManagerDecision === "rejected") {
    derived.push(MATCH_STATUSES.REJECTED);
  }
  if (normalizedManagerDecision === "accepted") {
    derived.push(MATCH_STATUSES.APPROVED);
  }

  if (normalizedCandidateDecision === "rejected") {
    derived.push(MATCH_STATUSES.DECLINED);
  }
  if (normalizedCandidateDecision === "applied") {
    derived.push(MATCH_STATUSES.SENT_TO_MANAGER);
  }

  if (
    normalizedCandidateDecision === "pending" &&
    normalizedManagerDecision === "pending" &&
    input.contactShared !== true
  ) {
    derived.push(MATCH_STATUSES.PROPOSED);
  }

  return resolveSingleStatus(derived);
}

/**
 * Maps legacy interview lifecycle shape to canonical InterviewStatus.
 * Returns null when signals are conflicting or too weak.
 */
export function normalizeLegacyInterviewStatus(
  input: LegacyInterviewLifecycleInput,
): InterviewStatus | null {
  const hasCompletedEvidence =
    hasIsoLikeValue(input.interviewCompletedAt) ||
    hasIsoLikeValue(input.interviewRunCompletedAt) ||
    input.hasInterviewRunRow === true;

  const legacyDbStatus = toLegacyInterviewDbStatus(input.interviewRunStatus);
  if (legacyDbStatus) {
    const mapped = LEGACY_INTERVIEW_DB_STATUS_TO_CANONICAL[legacyDbStatus];
    // Explicit conflict: a completed run timestamp and abandoned/active row should not co-exist.
    if (hasCompletedEvidence && mapped !== INTERVIEW_STATUSES.COMPLETED) {
      return null;
    }
    return hasCompletedEvidence ? INTERVIEW_STATUSES.COMPLETED : mapped;
  }

  if (hasCompletedEvidence) {
    return INTERVIEW_STATUSES.COMPLETED;
  }

  const sessionState = normalizeText(input.sessionState);
  const isInterviewingSession =
    sessionState === "interviewing_candidate" || sessionState === "interviewing_manager";

  if (!isInterviewingSession) {
    return null;
  }

  const answerCount = toNonNegativeInteger(input.answerCount);
  const questionIndex = toNonNegativeInteger(input.currentQuestionIndex);

  if ((answerCount ?? 0) > 0 || (questionIndex ?? 0) > 0) {
    return INTERVIEW_STATUSES.IN_PROGRESS;
  }

  if (hasIsoLikeValue(input.interviewStartedAt) || input.hasInterviewPlan === true) {
    return INTERVIEW_STATUSES.STARTED;
  }

  // Interviewing state itself means interview has already been started,
  // but we keep it distinct from IN_PROGRESS when no answer evidence exists yet.
  return INTERVIEW_STATUSES.STARTED;
}

/**
 * Maps legacy evaluation shape to canonical EvaluationStatus.
 * Returns null when mapping is ambiguous.
 */
export function normalizeLegacyEvaluationStatus(
  input: LegacyEvaluationInput,
): EvaluationStatus | null {
  const recommendation = normalizeRecommendation(input.recommendation);
  const profileStatus = toLegacyProfileStatus(input.profileStatus);
  const confidence = normalizeConfidence(input.interviewConfidenceLevel);

  if (profileStatus === LEGACY_PROFILE_STATUS.REJECTED_NON_TECHNICAL) {
    // Hard gate: non-technical profile cannot become strong/possible.
    if (
      recommendation &&
      recommendation !== EVALUATION_STATUSES.WEAK
    ) {
      return null;
    }
    return EVALUATION_STATUSES.WEAK;
  }

  if (recommendation) {
    return recommendation;
  }

  if (confidence) {
    if (confidence === "high") {
      return EVALUATION_STATUSES.STRONG;
    }
    if (confidence === "medium") {
      return EVALUATION_STATUSES.POSSIBLE;
    }
    return EVALUATION_STATUSES.WEAK;
  }

  if (profileStatus) {
    return LEGACY_PROFILE_STATUS_TO_EVALUATION[profileStatus];
  }

  if (
    input.shouldRequestReanswer === true &&
    normalizeText(input.aiAssistedLikelihood) === "high" &&
    isHighConfidence(input.aiAssistedConfidence)
  ) {
    return EVALUATION_STATUSES.WEAK;
  }

  const numericScore = toNumber(input.matchScore);
  if (numericScore !== null) {
    if (numericScore >= LEGACY_MATCH_SCORE_BANDS_TO_EVALUATION.strongMin) {
      return EVALUATION_STATUSES.STRONG;
    }
    if (numericScore >= LEGACY_MATCH_SCORE_BANDS_TO_EVALUATION.possibleMin) {
      return EVALUATION_STATUSES.POSSIBLE;
    }
    return EVALUATION_STATUSES.WEAK;
  }

  return null;
}

function resolveSingleStatus<T>(values: readonly T[]): T | null {
  const unique = Array.from(new Set(values));
  if (unique.length === 1) {
    return unique[0];
  }
  return null;
}

function toLegacyMatchStatus(value: string | null | undefined): LegacyMatchStatus | null {
  const normalized = normalizeText(value);
  if (!normalized) {
    return null;
  }

  const values = Object.values(LEGACY_MATCH_STATUS_TO_CANONICAL)
    ? Object.keys(LEGACY_MATCH_STATUS_TO_CANONICAL)
    : [];
  for (const key of values) {
    if (normalized === key) {
      return key as LegacyMatchStatus;
    }
  }
  return null;
}

function toLegacyInterviewDbStatus(
  value: string | null | undefined,
): LegacyInterviewDbStatus | null {
  const normalized = normalizeText(value);
  if (
    normalized === LEGACY_INTERVIEW_DB_STATUSES.ACTIVE ||
    normalized === LEGACY_INTERVIEW_DB_STATUSES.COMPLETED ||
    normalized === LEGACY_INTERVIEW_DB_STATUSES.ABANDONED
  ) {
    return normalized;
  }
  return null;
}

function toLegacyProfileStatus(
  value: string | null | undefined,
): LegacyProfileStatus | null {
  const normalized = normalizeText(value);
  if (
    normalized === LEGACY_PROFILE_STATUS.ANALYSIS_READY ||
    normalized === LEGACY_PROFILE_STATUS.REJECTED_NON_TECHNICAL
  ) {
    return normalized;
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
  // Handles known drift case from admin/analytics vocabulary.
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

function normalizeRecommendation(
  value: string | null | undefined,
): EvaluationStatus | null {
  const normalized = normalizeText(value);
  if (!normalized) {
    return null;
  }

  if (normalized === "strong" || normalized === "evaluation_strong") {
    return EVALUATION_STATUSES.STRONG;
  }
  if (normalized === "possible" || normalized === "evaluation_possible") {
    return EVALUATION_STATUSES.POSSIBLE;
  }
  if (normalized === "weak" || normalized === "evaluation_weak") {
    return EVALUATION_STATUSES.WEAK;
  }

  return null;
}

function normalizeConfidence(
  value: string | null | undefined,
): "low" | "medium" | "high" | null {
  const normalized = normalizeText(value);
  if (normalized === "low" || normalized === "medium" || normalized === "high") {
    return normalized;
  }
  return null;
}

function hasIsoLikeValue(value: string | null | undefined): boolean {
  return Boolean(normalizeText(value));
}

function toNonNegativeInteger(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return Math.floor(value);
}

function isHighConfidence(value: number | null | undefined): boolean {
  const numeric = toNumber(value);
  return numeric !== null && numeric >= 0.55;
}

function toNumber(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function normalizeText(value: string | null | undefined): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim().toLowerCase();
}
