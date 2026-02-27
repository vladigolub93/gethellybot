export type RouterIntent =
  | "answer_current_question"
  | "continue_interview"
  | "request_clarification"
  | "skip_question"
  | "show_profile"
  | "edit_profile"
  | "pause"
  | "resume"
  | "restart"
  | "set_role_candidate"
  | "set_role_manager"
  | "upload_document_resume"
  | "upload_document_job"
  | "voice_message"
  | "free_chat_hiring_related"
  | "off_topic"
  | "help"
  | "status"
  | "unknown";

export type RouterNextAction =
  | "transcribe_voice"
  | "ack_and_wait"
  | "start_resume_extraction"
  | "start_job_extraction"
  | "ask_next_question"
  | "ask_clarifying_question"
  | "record_answer_and_update_profile"
  | "skip_and_ask_next"
  | "finish_interview_and_summarize"
  | "show_profile_summary"
  | "apply_profile_edit"
  | "publish_job"
  | "run_matching"
  | "send_candidate_match_card"
  | "send_manager_candidate_card"
  | "record_candidate_decision"
  | "record_manager_decision"
  | "exchange_contacts"
  | "pause_flow"
  | "resume_flow"
  | "restart_flow"
  | "answer_brief_and_return"
  | "redirect_to_hiring_context";

export interface RouterDecision {
  intent: RouterIntent;
  next_action: RouterNextAction;
  confidence: number;
  reason_short: string;
  needs_clarification: boolean;
  clarifying_question: string | null;
}

const ALLOWED_INTENTS = new Set<RouterIntent>([
  "answer_current_question",
  "continue_interview",
  "request_clarification",
  "skip_question",
  "show_profile",
  "edit_profile",
  "pause",
  "resume",
  "restart",
  "set_role_candidate",
  "set_role_manager",
  "upload_document_resume",
  "upload_document_job",
  "voice_message",
  "free_chat_hiring_related",
  "off_topic",
  "help",
  "status",
  "unknown",
]);

const ALLOWED_ACTIONS = new Set<RouterNextAction>([
  "transcribe_voice",
  "ack_and_wait",
  "start_resume_extraction",
  "start_job_extraction",
  "ask_next_question",
  "ask_clarifying_question",
  "record_answer_and_update_profile",
  "skip_and_ask_next",
  "finish_interview_and_summarize",
  "show_profile_summary",
  "apply_profile_edit",
  "publish_job",
  "run_matching",
  "send_candidate_match_card",
  "send_manager_candidate_card",
  "record_candidate_decision",
  "record_manager_decision",
  "exchange_contacts",
  "pause_flow",
  "resume_flow",
  "restart_flow",
  "answer_brief_and_return",
  "redirect_to_hiring_context",
]);

export function parseRouterDecision(raw: string): RouterDecision {
  const parsed = parseJson(raw);
  const intent = readAllowedIntent(parsed.intent);
  const nextAction = readAllowedAction(parsed.next_action);
  const confidence = readConfidence(parsed.confidence);
  const reasonShort = readShortReason(parsed.reason_short);
  const needsClarification = Boolean(parsed.needs_clarification);
  const clarifyingQuestion = readClarifyingQuestion(parsed.clarifying_question);

  if (needsClarification && nextAction !== "ask_clarifying_question") {
    throw new Error("Router output invalid: clarification requires ask_clarifying_question action.");
  }

  if (!needsClarification && clarifyingQuestion !== null) {
    throw new Error("Router output invalid: clarifying_question must be null when clarification is not needed.");
  }

  if (nextAction === "ask_clarifying_question" && !clarifyingQuestion) {
    throw new Error("Router output invalid: missing clarifying_question.");
  }

  return {
    intent,
    next_action: nextAction,
    confidence,
    reason_short: reasonShort,
    needs_clarification: needsClarification,
    clarifying_question: clarifyingQuestion,
  };
}

function parseJson(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Router output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function readAllowedIntent(value: unknown): RouterIntent {
  if (typeof value === "string" && ALLOWED_INTENTS.has(value as RouterIntent)) {
    return value as RouterIntent;
  }
  throw new Error("Router output invalid intent.");
}

function readAllowedAction(value: unknown): RouterNextAction {
  if (typeof value === "string" && ALLOWED_ACTIONS.has(value as RouterNextAction)) {
    return value as RouterNextAction;
  }
  throw new Error("Router output invalid next_action.");
}

function readConfidence(value: unknown): number {
  const confidence = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(confidence)) {
    throw new Error("Router output invalid confidence.");
  }
  if (confidence < 0 || confidence > 1) {
    throw new Error("Router confidence must be between 0 and 1.");
  }
  return Number(confidence.toFixed(3));
}

function readShortReason(value: unknown): string {
  if (typeof value !== "string") {
    throw new Error("Router output invalid reason_short.");
  }
  const compact = value.replace(/\s+/g, " ").trim();
  if (!compact) {
    throw new Error("Router output empty reason_short.");
  }
  return compact.slice(0, 120);
}

function readClarifyingQuestion(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    throw new Error("Router output invalid clarifying_question.");
  }
  const compact = value.replace(/\s+/g, " ").trim();
  return compact ? compact.slice(0, 300) : null;
}
