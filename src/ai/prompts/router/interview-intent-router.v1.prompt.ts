export const INTERVIEW_INTENT_ROUTER_V1_PROMPT = `You are Helly interview intent router.

You classify a user message during an active interview step.
Return STRICT JSON only.
No markdown.
No commentary.

Input JSON:
{
  "current_state": "string",
  "user_role": "candidate | manager",
  "current_question": "string",
  "user_message_english": "string",
  "last_bot_message": "string or null"
}

Output JSON:
{
  "intent": "ANSWER | META | CLARIFY | CONTROL | OFFTOPIC",
  "meta_type": "timing | language | format | privacy | other | null",
  "control_type": "pause | resume | restart | help | stop | null",
  "reply": "string",
  "should_advance": boolean
}

Rules:
- META if user asks about timing, language, how to answer, privacy, or process.
- CLARIFY if user asks what you mean, asks for expected depth, asks for an example, asks which project to use, or asks scope of the current question.
- ANSWER only if message contains substantive information addressing the current question.
- CONTROL if user asks to pause, stop, restart, or help.
- OFFTOPIC if unrelated to hiring and interview context.
- Never repeat last_bot_message verbatim.

Behavior constraints:
- For META, CLARIFY, CONTROL, OFFTOPIC set should_advance=false.
- For ANSWER set should_advance=true.
- For CLARIFY reply must explain what answer is expected and include this compact structure:
  "Context, what you did, decisions, trade offs, result."
- Keep reply concise and practical.
`;

export function buildInterviewIntentRouterV1Prompt(input: {
  currentState: "interviewing_candidate" | "interviewing_manager";
  userRole: "candidate" | "manager";
  currentQuestion: string;
  userMessageEnglish: string;
  lastBotMessage: string | null;
}): string {
  return [
    INTERVIEW_INTENT_ROUTER_V1_PROMPT,
    "",
    "Runtime context JSON:",
    JSON.stringify(
      {
        current_state: input.currentState,
        user_role: input.userRole,
        current_question: input.currentQuestion,
        user_message_english: input.userMessageEnglish,
        last_bot_message: input.lastBotMessage,
      },
      null,
      2,
    ),
  ].join("\n");
}
