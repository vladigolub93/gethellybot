import type { OutboundComposeV2Language } from "./outbound_message_compose_v2.prompt";

export interface OutboundComposeV3Input {
  userRole: "candidate" | "manager";
  userLanguage: OutboundComposeV2Language;
  currentState: string;
  nextQuestionText?: string | null;
  lastUserMessage: string;
  profileSummaryFacts: string[];
  lastBotMessage?: string | null;
  avoidPhrase?: string | null;
  /** User seems frustrated or asked to skip/stop */
  userFrustrated?: boolean;
}

export function buildOutboundComposeV3Prompt(input: OutboundComposeV3Input): string {
  const parts = [
    "You are Helly, a friendly recruiter in a Telegram bot. Compose ONE short, warm reply.",
    "Return STRICT JSON only. No markdown, no commentary.",
    "",
    "Style: short, warm. No repetitive boilerplate. Never say 'Please answer the current interview question'.",
    "If the user is frustrated or asked to skip/stop: de-escalate and offer skip or pause.",
    "User language for message: " + input.userLanguage + " (en|ru|uk).",
    "Reaction: use sparingly. Allowed: 👍, 🤝, 👀, ✅, ❓, or null.",
    "Buttons: only when needed (Apply, Reject, Share contact, Skip). Otherwise [].",
  ];

  if (input.avoidPhrase?.trim()) {
    parts.push(`Do NOT repeat or paraphrase: "${input.avoidPhrase.trim()}"`);
  }

  parts.push(
    "",
    "Output JSON:",
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
        last_bot_message: input.lastBotMessage ?? null,
        user_frustrated: input.userFrustrated ?? false,
      },
      null,
      2,
    ),
  );

  return parts.join("\n");
}
