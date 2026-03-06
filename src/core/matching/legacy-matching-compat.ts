import { EVALUATION_STATUSES, type EvaluationStatus } from "./evaluation-statuses";
import { INTERVIEW_STATUSES, type InterviewStatus } from "./interview-statuses";
import { MATCH_STATUSES, type MatchStatus } from "./match-statuses";

/**
 * Legacy -> canonical compatibility inventory for gradual migration.
 *
 * This file is intentionally read-only:
 * - no runtime wiring
 * - no mutation helpers
 * - no behavior changes
 */

export const LEGACY_MATCH_STATUSES = {
  PROPOSED: "proposed",
  CANDIDATE_APPLIED: "candidate_applied",
  CANDIDATE_REJECTED: "candidate_rejected",
  MANAGER_ACCEPTED: "manager_accepted",
  MANAGER_REJECTED: "manager_rejected",
  CONTACT_PENDING: "contact_pending",
  CONTACT_SHARED: "contact_shared",
  CLOSED: "closed",
} as const;

export type LegacyMatchStatus = (typeof LEGACY_MATCH_STATUSES)[keyof typeof LEGACY_MATCH_STATUSES];

/**
 * Proposed mapping based on current observed behavior.
 *
 * Notes:
 * - `proposed` is used both before and after notification send, so it maps to PROPOSED.
 * - `candidate_applied` is the stage where manager review is expected.
 * - `contact_pending` and `closed` exist in legacy vocabulary, but are not actively used now.
 */
export const LEGACY_MATCH_STATUS_TO_CANONICAL: Record<LegacyMatchStatus, MatchStatus> = {
  [LEGACY_MATCH_STATUSES.PROPOSED]: MATCH_STATUSES.PROPOSED,
  [LEGACY_MATCH_STATUSES.CANDIDATE_APPLIED]: MATCH_STATUSES.SENT_TO_MANAGER,
  [LEGACY_MATCH_STATUSES.CANDIDATE_REJECTED]: MATCH_STATUSES.DECLINED,
  [LEGACY_MATCH_STATUSES.MANAGER_ACCEPTED]: MATCH_STATUSES.APPROVED,
  [LEGACY_MATCH_STATUSES.MANAGER_REJECTED]: MATCH_STATUSES.REJECTED,
  [LEGACY_MATCH_STATUSES.CONTACT_PENDING]: MATCH_STATUSES.APPROVED,
  [LEGACY_MATCH_STATUSES.CONTACT_SHARED]: MATCH_STATUSES.APPROVED,
  [LEGACY_MATCH_STATUSES.CLOSED]: MATCH_STATUSES.REJECTED_BY_SYSTEM,
};

/**
 * @deprecated Legacy match statuses that are currently placeholders/drift-only.
 * Keep only for backward compatibility during migration.
 */
export const LEGACY_DEPRECATED_MATCH_STATUSES = [
  LEGACY_MATCH_STATUSES.CONTACT_PENDING,
  LEGACY_MATCH_STATUSES.CLOSED,
] as const;

/**
 * Legacy overloaded status values that currently represent more than one lifecycle meaning.
 * `candidate_applied` is used as both candidate decision and manager exposure proxy.
 */
export const LEGACY_OVERLOADED_MATCH_STATUSES = [
  LEGACY_MATCH_STATUSES.CANDIDATE_APPLIED,
] as const;

export const LEGACY_INTERVIEW_DB_STATUSES = {
  ACTIVE: "active",
  COMPLETED: "completed",
  ABANDONED: "abandoned",
} as const;

export type LegacyInterviewDbStatus =
  (typeof LEGACY_INTERVIEW_DB_STATUSES)[keyof typeof LEGACY_INTERVIEW_DB_STATUSES];

/**
 * Mapping for legacy `public.interviews.status` vocabulary from migration 019.
 * Current runtime writes interview_runs, but this preserves compatibility intent.
 */
export const LEGACY_INTERVIEW_DB_STATUS_TO_CANONICAL: Record<
  LegacyInterviewDbStatus,
  InterviewStatus
> = {
  [LEGACY_INTERVIEW_DB_STATUSES.ACTIVE]: INTERVIEW_STATUSES.IN_PROGRESS,
  [LEGACY_INTERVIEW_DB_STATUSES.COMPLETED]: INTERVIEW_STATUSES.COMPLETED,
  [LEGACY_INTERVIEW_DB_STATUSES.ABANDONED]: INTERVIEW_STATUSES.DROPPED,
};

export const LEGACY_PROFILE_STATUS = {
  ANALYSIS_READY: "analysis_ready",
  REJECTED_NON_TECHNICAL: "rejected_non_technical",
} as const;

export type LegacyProfileStatus =
  (typeof LEGACY_PROFILE_STATUS)[keyof typeof LEGACY_PROFILE_STATUS];

export const LEGACY_PROFILE_STATUS_TO_EVALUATION: Record<
  LegacyProfileStatus,
  EvaluationStatus
> = {
  [LEGACY_PROFILE_STATUS.ANALYSIS_READY]: EVALUATION_STATUSES.POSSIBLE,
  [LEGACY_PROFILE_STATUS.REJECTED_NON_TECHNICAL]: EVALUATION_STATUSES.WEAK,
};

export const LEGACY_INTERVIEW_CONFIDENCE_TO_EVALUATION: Record<
  "low" | "medium" | "high",
  EvaluationStatus
> = {
  low: EVALUATION_STATUSES.WEAK,
  medium: EVALUATION_STATUSES.POSSIBLE,
  high: EVALUATION_STATUSES.STRONG,
};

/**
 * Numeric fallback when confidence-level is absent.
 * Based on existing matching thresholds (70/85) used by legacy flow.
 */
export const LEGACY_MATCH_SCORE_BANDS_TO_EVALUATION = {
  strongMin: 85,
  possibleMin: 70,
} as const;
