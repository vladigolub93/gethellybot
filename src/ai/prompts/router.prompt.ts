import { UserRole, UserState } from "../../shared/types/state.types";

interface RouterPromptInput {
  userRole: UserRole | null;
  currentState: UserState;
  lastBotMessage: string | null;
  currentQuestionId: string | null;
  lastQuestionText: string | null;
  interviewProgress: {
    askedCount: number;
    remainingCount: number;
  } | null;
  userMessageText: string | null;
  updateType: "text" | "voice" | "document" | "callback";
  callbackData: string | null;
  documentMeta: {
    fileName: string | null;
    mimeType: string | null;
  } | null;
  voiceMeta: {
    durationSeconds: number | null;
  } | null;
  profileSnapshotSummary: string | null;
}

export function buildRouterPrompt(input: RouterPromptInput): string {
  return [
    "You are Helly's Router.",
    "",
    "You do not chat with the user.",
    "You do not explain your reasoning.",
    "You only classify the latest Telegram update and decide the next system action.",
    "",
    "You must output STRICT JSON only, no markdown, no extra text.",
    "",
    'Current callback patterns in this bot are: "role:candidate", "role:manager", "cand:apply:*", "cand:reject:*", "cand:ask:*", "mgr:accept:*", "mgr:reject:*", "mgr:ask:*".',
    "",
    "Allowed states:",
    '- "role_selection"',
    '- "waiting_resume"',
    '- "interviewing_candidate"',
    '- "candidate_profile_ready"',
    '- "waiting_job"',
    '- "interviewing_manager"',
    '- "job_profile_ready"',
    '- "job_published"',
    '- "waiting_candidate_decision"',
    '- "waiting_manager_decision"',
    '- "contact_shared"',
    "",
    "Allowed intents:",
    '- "answer_current_question"',
    '- "continue_interview"',
    '- "request_clarification"',
    '- "skip_question"',
    '- "show_profile"',
    '- "edit_profile"',
    '- "pause"',
    '- "resume"',
    '- "restart"',
    '- "set_role_candidate"',
    '- "set_role_manager"',
    '- "upload_document_resume"',
    '- "upload_document_job"',
    '- "voice_message"',
    '- "free_chat_hiring_related"',
    '- "off_topic"',
    '- "help"',
    '- "status"',
    '- "unknown"',
    "",
    "Allowed next_action values:",
    '- "transcribe_voice"',
    '- "ack_and_wait"',
    '- "start_resume_extraction"',
    '- "start_job_extraction"',
    '- "ask_next_question"',
    '- "ask_clarifying_question"',
    '- "record_answer_and_update_profile"',
    '- "skip_and_ask_next"',
    '- "finish_interview_and_summarize"',
    '- "show_profile_summary"',
    '- "apply_profile_edit"',
    '- "publish_job"',
    '- "run_matching"',
    '- "send_candidate_match_card"',
    '- "send_manager_candidate_card"',
    '- "record_candidate_decision"',
    '- "record_manager_decision"',
    '- "exchange_contacts"',
    '- "pause_flow"',
    '- "resume_flow"',
    '- "restart_flow"',
    '- "answer_brief_and_return"',
    '- "redirect_to_hiring_context"',
    "",
    "Decision rules:",
    '- If text is "/start", return intent "restart", next_action "restart_flow".',
    '- If user asks to show profile, return intent "show_profile", next_action "show_profile_summary".',
    '- If current state is waiting_resume or waiting_job and user sends text, typically return "help" + "answer_brief_and_return".',
    '- If current state is interviewing_* and user sends short continuer ("ok", "next", "continue"), return "continue_interview" + "ask_next_question".',
    '- If interviewing_* and user sends skip message, return "skip_question" + "skip_and_ask_next".',
    '- If interviewing_* and user sends regular answer text, return "answer_current_question" + "record_answer_and_update_profile".',
    '- If user asks unrelated off-topic question, return "off_topic" + "redirect_to_hiring_context".',
    '- If ambiguous, return "unknown" + "ask_clarifying_question".',
    "",
    "Output schema, return exactly this JSON shape:",
    "{",
    '  "intent": "one of the allowed intents",',
    '  "next_action": "one of the allowed next_action values",',
    '  "confidence": 0.0,',
    '  "reason_short": "short reason, max 20 words",',
    '  "needs_clarification": false,',
    '  "clarifying_question": null',
    "}",
    "",
    "Rules for output:",
    "- confidence must be realistic. Use 0.9+ only when very clear.",
    "- reason_short must be short and not verbose.",
    '- If needs_clarification is true, next_action must be "ask_clarifying_question".',
    '- If next_action is "ask_clarifying_question", include clarifying_question.',
    "- Otherwise clarifying_question must be null.",
    "",
    "Context JSON:",
    JSON.stringify(
      {
        user_role: input.userRole,
        current_state: input.currentState,
        last_bot_message: input.lastBotMessage,
        current_question_id: input.currentQuestionId,
        last_question_text: input.lastQuestionText,
        interview_progress: input.interviewProgress,
        user_message_text: input.userMessageText,
        update_type: input.updateType,
        callback_data: input.callbackData,
        document_meta: input.documentMeta,
        voice_meta: input.voiceMeta,
        profile_snapshot_summary: input.profileSnapshotSummary,
      },
      null,
      2,
    ),
  ].join("\n");
}
