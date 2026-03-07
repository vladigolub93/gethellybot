export type MatchingDecisionPriority = "low" | "normal" | "high";

export type MatchingDecisionMessageLength = "short" | "standard";

export interface MatchingDecisionV1 {
  notify_candidate: boolean;
  notify_manager: boolean;
  priority: MatchingDecisionPriority;
  message_length: MatchingDecisionMessageLength;
  cooldown_hours_candidate: number;
  cooldown_hours_manager: number;
  reason: string;
}
