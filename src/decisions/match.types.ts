import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import {
  MatchBreakdownV2,
  MatchReasonsV2,
  MatchingExplanationV1,
} from "../shared/types/matching.types";
import { MatchingDecisionV1 } from "../shared/types/matching-decision.types";

export type CandidateDecision = "pending" | "applied" | "rejected";
export type ManagerDecision = "pending" | "accepted" | "rejected";
export type MatchStatus =
  | "suggested"
  | "candidate_pending"
  | "manager_pending"
  | "contact_shared"
  | "closed";

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
