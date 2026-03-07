/**
 * Domain invariants for matching + interview orchestration.
 *
 * These constants are intentionally declarative. They document non-negotiable
 * business constraints and will be enforced by future gatekeepers/state engines.
 */
export const MATCHING_INVARIANTS = {
  /**
   * A single candidate can have multiple matches, but at most one active interview.
   */
  CANDIDATE_MAX_ACTIVE_INTERVIEWS: 1,

  /**
   * A vacancy can have multiple active invites in parallel, controlled by wave logic.
   */
  VACANCY_SUPPORTS_WAVE_INVITES: true,

  /**
   * Match and interview lifecycle transitions must remain internally consistent.
   * Example: INTERVIEW_COMPLETED cannot exist without INTERVIEW_STARTED.
   */
  REQUIRE_LIFECYCLE_CONSISTENCY: true,

  /**
   * Final evaluation is valid only after interview completion.
   */
  EVALUATION_REQUIRES_COMPLETED_INTERVIEW: true,
} as const;

