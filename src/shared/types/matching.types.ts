export interface MatchBreakdownV2 {
  coreTechDepth: number;
  domainAlignment: number;
  ownershipAlignment: number;
  architectureScaleAlignment: number;
  challengeAlignment: number;
}

export interface MatchReasonsV2 {
  topMatches: string[];
  topGaps: string[];
  risks: string[];
}

export interface MatchScoreV2 {
  totalScore: number;
  passHardFilters: boolean;
  hardFilterFailures: string[];
  breakdown: MatchBreakdownV2;
  reasons: MatchReasonsV2;
}

export interface MatchingExplanationV1 {
  message_for_candidate: string;
  message_for_manager: string;
  one_suggested_live_question: string;
}
