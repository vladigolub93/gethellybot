import {
  buildCandidatePackageForManagerReview,
  CandidatePackageForManagerReview,
} from "./candidate-package.builder";
import { EvaluationStatus } from "./evaluation-statuses";
import { InterviewStatus } from "./interview-statuses";
import {
  LegacyEvaluationInput,
  LegacyInterviewLifecycleInput,
  LegacyMatchLifecycleInput,
} from "./lifecycle-normalizers";
import { MatchStatus } from "./match-statuses";

export interface ManagerReviewReadModelInput {
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

export interface ManagerReviewReadModel {
  candidateSummary: string;
  normalizedPackage: CandidatePackageForManagerReview;
  matchStatus: MatchStatus | null;
  interviewStatus: InterviewStatus | null;
  evaluationStatus: EvaluationStatus | null;
  isCandidateSentToManager: boolean;
  notes: string[];
  risks: string[];
  legacy: {
    candidateSummary: string;
    score: number | null;
    explanation: string | null;
    status: string | null;
    candidateDecision: string | null;
    managerDecision: string | null;
    contactShared: boolean | null;
  };
}

/**
 * Shared pure manager-facing review read-model builder.
 *
 * This function is read-only and deterministic:
 * - no writes
 * - no routing/state side effects
 * - no business decision changes
 */
export function buildManagerReviewReadModel(
  input: ManagerReviewReadModelInput,
): ManagerReviewReadModel {
  const normalizedPackage = buildCandidatePackageForManagerReview({
    candidate: input.candidate,
    match: input.match,
    interview: input.interview,
    evaluation: input.evaluation,
    verification: input.verification,
  });

  const legacyCandidateSummary =
    normalizeText(input.candidate?.summary) ??
    normalizeText(input.match?.candidateSummary) ??
    "";

  return {
    candidateSummary: normalizedPackage.candidateSummary || legacyCandidateSummary,
    normalizedPackage,
    matchStatus: normalizedPackage.matchStatus,
    interviewStatus: normalizedPackage.interviewStatus,
    evaluationStatus: normalizedPackage.evaluationStatus,
    isCandidateSentToManager: normalizedPackage.isCandidateSentToManager,
    notes: normalizedPackage.notes,
    risks: normalizedPackage.risks,
    legacy: {
      candidateSummary: legacyCandidateSummary,
      score: toFiniteNumber(input.match?.score),
      explanation: normalizeText(input.match?.explanation),
      status: normalizeText(input.match?.status),
      candidateDecision: normalizeText(input.match?.candidateDecision),
      managerDecision: normalizeText(input.match?.managerDecision),
      contactShared:
        typeof input.match?.contactShared === "boolean"
          ? input.match.contactShared
          : null,
    },
  };
}

function normalizeText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toFiniteNumber(value: number | null | undefined): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}
