import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import {
  MatchBreakdownV2,
  MatchReasonsV2,
  MatchingExplanationV1,
} from "../shared/types/matching.types";
import { MatchingDecisionV1 } from "../shared/types/matching-decision.types";
import { MatchStatus as CanonicalMatchStatus } from "../core/matching/match-statuses";

export type CandidateDecision = "pending" | "applied" | "rejected";
export type ManagerDecision = "pending" | "accepted" | "rejected";
/**
 * Stage 10: legacy persisted statuses for matching + consent flow.
 *
 * Legacy lifecycle caveats:
 * - `candidate_applied` is overloaded in current runtime:
 *   it means both candidate accepted and candidate is now visible to manager.
 * - `contact_pending` is a legacy placeholder, currently not part of active runtime transitions.
 * - `closed` is a legacy placeholder, currently not part of active runtime transitions.
 *
 * Do not expand this legacy vocabulary in new flows.
 * New lifecycle ownership should move toward canonical statuses in `src/core/matching/`.
 */
export type MatchStatus =
  | "proposed"
  // Legacy overloaded value: currently used as manager-review visibility proxy.
  | "candidate_applied"
  | "candidate_rejected"
  | "manager_accepted"
  | "manager_rejected"
  // Legacy placeholder (deprecated in cleanup plan; keep for backward compatibility only).
  | "contact_pending"
  | "contact_shared"
  // Legacy placeholder (deprecated in cleanup plan; keep for backward compatibility only).
  | "closed";

/**
 * @deprecated Legacy placeholders kept for backward compatibility only.
 * Do not use these in new write paths.
 */
export const LEGACY_DEPRECATED_MATCH_STATUSES = [
  "contact_pending",
  "closed",
] as const satisfies ReadonlyArray<MatchStatus>;

/**
 * Legacy overloaded status values.
 * `candidate_applied` should eventually be replaced by explicit lifecycle ownership
 * of the manager-exposure moment.
 */
export const LEGACY_OVERLOADED_MATCH_STATUSES = [
  "candidate_applied",
] as const satisfies ReadonlyArray<MatchStatus>;

export interface MatchRecord {
  id: string;
  managerUserId: number;
  candidateUserId: number;
  jobId?: string | null;
  candidateId?: string | null;
  jobSummary: string;
  jobTechnicalSummary?: JobTechnicalSummaryV2 | null;
  candidateSummary: string;
  candidateTechnicalSummary?: CandidateTechnicalSummaryV1 | null;
  score: number;
  breakdown?: MatchBreakdownV2;
  reasons?: MatchReasonsV2;
  explanationJson?: MatchingExplanationV1 | null;
  matchingDecision?: MatchingDecisionV1 | null;
  explanation: string;
  candidateDecision: CandidateDecision;
  managerDecision: ManagerDecision;
  status: MatchStatus;
  canonicalMatchStatus?: CanonicalMatchStatus | null;
  createdAt: string;
  updatedAt: string;
}

export interface MatchCandidateInput {
  candidateUserId: number;
  jobId?: string | null;
  candidateId?: string | null;
  candidateSummary: string;
  jobTechnicalSummary?: JobTechnicalSummaryV2 | null;
  candidateTechnicalSummary?: CandidateTechnicalSummaryV1 | null;
  score: number;
  breakdown?: MatchBreakdownV2;
  reasons?: MatchReasonsV2;
  explanationJson?: MatchingExplanationV1 | null;
  matchingDecision?: MatchingDecisionV1 | null;
  explanation: string;
}
