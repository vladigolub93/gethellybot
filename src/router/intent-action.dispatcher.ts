import { AlwaysOnRouterDecision } from "../shared/types/always-on-router.types";
import { UserSessionState } from "../shared/types/state.types";

export type RouterDispatchAction =
  | "process_document"
  | "transcribe_voice"
  | "process_pasted_text"
  | "process_interview_answer"
  | "interview_clarify"
  | "matching_command"
  | "control"
  | "meta_reply"
  | "complaint_reply"
  | "smalltalk_reply"
  | "other_reply";

export function resolveRouterDispatchAction(
  decision: AlwaysOnRouterDecision,
  session: UserSessionState,
): RouterDispatchAction {
  if (decision.route === "DOC") {
    return "process_document";
  }
  if (decision.route === "VOICE") {
    return "transcribe_voice";
  }
  if (decision.route === "JD_TEXT" || decision.route === "RESUME_TEXT") {
    return "process_pasted_text";
  }
  if (decision.route === "INTERVIEW_ANSWER") {
    return "process_interview_answer";
  }
  if (decision.route === "MATCHING_COMMAND") {
    return "matching_command";
  }
  if (decision.route === "CONTROL") {
    return "control";
  }
  if (decision.route === "META") {
    return "meta_reply";
  }
  if (decision.route === "OFFTOPIC") {
    return "other_reply";
  }

  if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
    if (decision.conversation_intent === "CLARIFY") {
      return "interview_clarify";
    }
    if (decision.conversation_intent === "COMPLAINT") {
      return "complaint_reply";
    }
  }

  if (decision.conversation_intent === "SMALLTALK") {
    return "smalltalk_reply";
  }
  if (decision.conversation_intent === "COMPLAINT") {
    return "complaint_reply";
  }
  return "other_reply";
}
