export type OutboundComposeV2Language = "en" | "ru" | "uk";

export interface OutboundComposeV2Input {
  userRole: "candidate" | "manager";
  userLanguage: OutboundComposeV2Language;
  currentState: string;
  nextQuestionText?: string | null;
  lastUserMessage: string;
  profileSummaryFacts: string[];
  safetyRules: string[];
  lastBotMessage?: string | null;
  /** Avoid repeating this exact phrasing */
  avoidPhrase?: string | null;
}

export function buildOutboundComposeV2Prompt(input: OutboundComposeV2Input): string {
  const parts = [
    "You are a friendly hiring assistant in a Telegram bot. Compose ONE short, natural reply.",
    "Return STRICT JSON only. No markdown fences, no commentary.",
    "",
    "Rules:",
    "- Message must be short and natural (1-3 sentences).",
    "- Use the user's language for the message (user_language: en|ru|uk).",
    "- Use reaction sparingly: only when it fits (e.g. after a good answer). Allowed: 👍, 🤝, 👀, ✅, ❓, or null.",
    "- Include buttons only when needed: e.g. Apply/Reject, Share contact, Skip. Empty array [] if no buttons.",
    "- Never produce repeated boilerplate like 'Please answer the current interview question'.",
    "- No harassment, no aggressive tone. Keep it hiring-related.",
    "- If user goes off-topic, respond briefly but steer back to hiring.",
    "- If next_question_text is provided, you may include it in the message or acknowledge and ask it naturally.",
  ];

  if (input.avoidPhrase?.trim()) {
    parts.push(`- Do NOT repeat or closely paraphrase: "${input.avoidPhrase.trim()}"`);
  }

  parts.push(
    "",
    "Output JSON schema:",
    `{
  "message": "string (required, in user language)",
  "reaction": "👍" | "🤝" | "👀" | "✅" | "❓" | null,
  "buttons": [{"text": "string", "data": "string"}] | []
}`,
    "",
    "Input:",
    JSON.stringify(
      {
        user_role: input.userRole,
        user_language: input.userLanguage,
        current_state: input.currentState,
        next_question_text: input.nextQuestionText ?? null,
        last_user_message: input.lastUserMessage,
        profile_summary_facts: input.profileSummaryFacts,
        safety_rules: input.safetyRules,
        last_bot_message: input.lastBotMessage ?? null,
      },
      null,
      2,
    ),
  );

  return parts.join("\n");
}
