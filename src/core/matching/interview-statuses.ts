/**
 * Canonical interview lifecycle statuses for Helly domain orchestration.
 *
 * This is a contract-only layer. Runtime wiring is intentionally not added yet.
 */
export const INTERVIEW_STATUSES = {
  INVITED: "INVITED",
  STARTED: "STARTED",
  IN_PROGRESS: "IN_PROGRESS",
  COMPLETED: "COMPLETED",
  DROPPED: "DROPPED",
  DECLINED: "DECLINED",
  CANCELLED_BY_MANAGER: "CANCELLED_BY_MANAGER",
  CANCELLED_BY_CANDIDATE: "CANCELLED_BY_CANDIDATE",
} as const;

export type InterviewStatus = (typeof INTERVIEW_STATUSES)[keyof typeof INTERVIEW_STATUSES];

