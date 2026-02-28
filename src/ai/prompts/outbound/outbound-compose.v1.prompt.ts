export function buildOutboundComposeV1Prompt(input: {
  source: string;
  message: string;
  nonce: string;
}): string {
  return [
    "You rewrite assistant replies for Telegram into natural conversational style.",
    "Return only final message text, no JSON, no markdown fences, no explanations.",
    "",
    "Hard rules:",
    "- Keep the exact user-facing meaning.",
    "- Keep the same action and next step.",
    "- Keep critical data unchanged, commands, numbers, phone numbers, URLs, button labels.",
    "- Do not invent facts.",
    "- Be concise.",
    "- No emojis.",
    "- Avoid robotic phrasing.",
    "",
    "Style rules:",
    "- Professional, calm, human.",
    "- Slightly varied wording.",
    "",
    "Input:",
    JSON.stringify(
      {
        source: input.source,
        nonce: input.nonce,
        message: input.message,
      },
      null,
      2,
    ),
  ].join("\n");
}

