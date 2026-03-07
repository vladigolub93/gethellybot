export type InterviewIntent = "ANSWER" | "META" | "CLARIFY" | "CONTROL" | "OFFTOPIC";

export type InterviewMetaType = "timing" | "language" | "format" | "privacy" | "other" | null;

export type InterviewControlType = "pause" | "resume" | "restart" | "help" | "stop" | null;

export interface InterviewIntentDecisionV1 {
  intent: InterviewIntent;
  meta_type: InterviewMetaType;
  control_type: InterviewControlType;
  reply: string;
  should_advance: boolean;
}
