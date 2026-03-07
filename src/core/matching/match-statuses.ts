/**
 * Canonical match lifecycle statuses for Helly domain orchestration.
 *
 * This is a contract-only layer. Runtime wiring is intentionally not added yet.
 */
export const MATCH_STATUSES = {
  PROPOSED: "PROPOSED",
  INVITED: "INVITED",
  DECLINED: "DECLINED",
  INTERVIEW_STARTED: "INTERVIEW_STARTED",
  INTERVIEW_COMPLETED: "INTERVIEW_COMPLETED",
  REJECTED_BY_SYSTEM: "REJECTED_BY_SYSTEM",
  SENT_TO_MANAGER: "SENT_TO_MANAGER",
  APPROVED: "APPROVED",
  REJECTED: "REJECTED",
} as const;

export type MatchStatus = (typeof MATCH_STATUSES)[keyof typeof MATCH_STATUSES];

