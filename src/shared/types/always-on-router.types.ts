export type AlwaysOnRouterRoute =
  | "DOC"
  | "VOICE"
  | "JD_TEXT"
  | "RESUME_TEXT"
  | "INTERVIEW_ANSWER"
  | "META"
  | "CONTROL"
  | "MATCHING_COMMAND"
  | "OFFTOPIC"
  | "OTHER";

export type AlwaysOnMetaType = "timing" | "language" | "format" | "privacy" | "other" | null;
export type AlwaysOnControlType = "pause" | "resume" | "restart" | "help" | "stop" | null;
export type AlwaysOnMatchingIntent = "run" | "show" | "pause" | "resume" | "help" | null;

export interface AlwaysOnRouterDecision {
  route: AlwaysOnRouterRoute;
  meta_type: AlwaysOnMetaType;
  control_type: AlwaysOnControlType;
  matching_intent: AlwaysOnMatchingIntent;
  reply: string;
  should_advance: boolean;
  should_process_text_as_document: boolean;
}
