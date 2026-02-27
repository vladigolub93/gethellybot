import { UserRole, UserState } from "../../shared/types/state.types";

interface ConversationReplyPromptInput {
  role?: UserRole;
  state: UserState;
  userText: string;
  nextStep: string;
  profileReady: boolean;
}

export function buildConversationReplyPrompt(input: ConversationReplyPromptInput): string {
  return [
    "Task: provide a short conversational reply for the current bot context.",
    "Return plain text only.",
    "",
    "Rules:",
    "- Keep reply concise, maximum 2 short sentences.",
    "- Stay within recruitment context.",
    "- If user asks unrelated question, answer briefly and redirect.",
    "- Include the next step clearly.",
    "- Do not use markdown or emojis.",
    "",
    "Runtime context:",
    `Role: ${input.role ?? "unknown"}`,
    `State: ${input.state}`,
    `Profile ready: ${input.profileReady ? "yes" : "no"}`,
    `Required next step: ${input.nextStep}`,
    "",
    `User message: ${input.userText}`,
  ].join("\n");
}
