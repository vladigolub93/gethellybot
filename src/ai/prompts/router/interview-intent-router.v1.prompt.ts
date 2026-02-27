interface BuildInterviewIntentRouterPromptInput {
  currentState: "interviewing_candidate" | "interviewing_manager";
  currentQuestionText: string;
  userMessage: string;
}

export function buildInterviewIntentRouterV1Prompt(
  input: BuildInterviewIntentRouterPromptInput,
): string {
  return [
    "You are Helly interview intent router.",
    "Classify the user message during an active interview step.",
    "Return STRICT JSON only. No markdown. No explanation.",
    "",
    "Output schema:",
    "{",
    '  "intent": "ANSWER | META | CONTROL | OFFTOPIC",',
    '  "meta_type": "timing | language | format | privacy | other | null",',
    '  "control_type": "pause | resume | restart | help | stop | null",',
    '  "suggested_reply": "string",',
    '  "should_advance_interview": false',
    "}",
    "",
    "Rules:",
    "- If user asks how long, timing, when, return intent META and meta_type timing.",
    "- If user asks about language, voice, Russian, Ukrainian, return intent META and meta_type language.",
    "- If user asks help, what to do, return intent CONTROL and control_type help.",
    "- If message is very short like ok, sure, yes, return intent META and meta_type format.",
    "- If user asks about privacy or data sharing, return intent META and meta_type privacy.",
    "- If message contains substantive technical details relevant to current question, return intent ANSWER.",
    "- If unrelated to hiring interview context, return intent OFFTOPIC.",
    "- For META, CONTROL, OFFTOPIC set should_advance_interview to false.",
    "- For ANSWER set should_advance_interview to true.",
    "",
    "Suggested reply guidance:",
    "- timing: Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.",
    "- language: Yes, you can answer by voice in Russian or Ukrainian. I will transcribe it and continue. Please be detailed and use real examples.",
    "- format: You can answer in text or voice. Detailed answers help me build an accurate profile.",
    "- privacy: Your profile is only shared after you apply, and contacts are shared only after mutual approval.",
    "",
    "Runtime context JSON:",
    JSON.stringify(
      {
        current_state: input.currentState,
        current_question_text: input.currentQuestionText,
        user_message: input.userMessage,
      },
      null,
      2,
    ),
  ].join("\n");
}
