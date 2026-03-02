/**
 * Intent router v2 — classify user message for dialogue orchestrator.
 * Supports: answer, clarify_question, skip, pause, resume, restart, switch_role, request_matching, smalltalk, other.
 */

export type IntentRouterV2Language = "en" | "ru" | "uk";

export interface IntentRouterV2Input {
  userMessage: string;
  role: "candidate" | "manager";
  phase: string;
  currentQuestionText?: string | null;
}

const INTENT_ROUTER_V2_SYSTEM = `You classify one user message in a recruitment Telegram bot.
Return STRICT JSON only. No markdown. No commentary.

Intent values:
- answer: user is answering the current prescreen question (substantive reply)
- clarify_question: user asks a clarifying question (why/how/what/что/чому/як/как etc.)
- skip: user wants to skip current step or question
- pause: user wants to pause or take a break
- resume: user wants to continue after pause
- restart: user wants to start over (/start or equivalent)
- switch_role: user wants to switch role (candidate <-> manager)
- request_matching: user asks to find jobs, candidates, vacancies ("дай вакансии", "ищи работу", "покажи кандидатов", "match me", "find jobs")
- match_apply: user says they want to apply / accept current match ("apply", "хочу", "приймаю", "accept", "да", "так")
- match_reject: user says skip/reject/next for current match ("reject", "skip", "next", "пропустити", "ні", "нет", "next one")
- smalltalk: greeting or chitchat ("hi", "how are you") -> respond briefly then steer back
- other: none of the above

Rules:
- If message ends with ? or starts with why/how/what/что/чому/як/зачем/как, likely clarify_question.
- request_matching: any clear request for jobs list, candidates list, or matching.
- match_apply / match_reject: short replies about the last shown match (apply/accept/reject/skip/next). Prefer when message is very short and could refer to the match cards.
- language: detect from message (en|ru|uk).
- userQuestion: if intent is clarify_question, the user's question in their words (for answering); else null.`;

export const INTENT_ROUTER_V2_OUTPUT_SCHEMA = `
Output JSON:
{
  "intent": "answer|clarify_question|skip|pause|resume|restart|switch_role|request_matching|match_apply|match_reject|smalltalk|other",
  "language": "en|ru|uk",
  "confidence": 0-1,
  "userQuestion": "string" | null
}`;

export function buildIntentRouterV2Prompt(input: IntentRouterV2Input): string {
  return [
    INTENT_ROUTER_V2_SYSTEM,
    "",
    INTENT_ROUTER_V2_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        user_message: input.userMessage,
        role: input.role,
        phase: input.phase,
        current_question_text: input.currentQuestionText ?? null,
      },
      null,
      2,
    ),
  ].join("\n");
}
