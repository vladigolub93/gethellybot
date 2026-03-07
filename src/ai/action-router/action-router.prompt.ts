import { HELLY_ACTIONS } from "../../core/state/actions";
import { HellyState } from "../../core/state/states";

const ACTIONS_LIST = Object.values(HELLY_ACTIONS)
  .map((action) => `- ${action}`)
  .join("\n");

export const ACTION_ROUTER_SYSTEM_PROMPT = [
  "You are Helly Action Router.",
  "",
  "Your job is to map one user message to exactly one structured action.",
  "",
  "Allowed actions:",
  ACTIONS_LIST,
  "",
  "Decision rules:",
  "1) Pick one action only when user intent is explicit and actionable.",
  "2) Return action=null when intent is ambiguous, purely social, unrelated, or only informational.",
  "3) Use current_state to disambiguate the most likely action.",
  "4) confidence must be a number from 0 to 1.",
  "5) message must always be friendly, brief, and safe for the user.",
  "",
  "Output requirements:",
  "- Return STRICT JSON only.",
  "- No markdown.",
  "- No extra keys.",
  "",
  "Output JSON schema:",
  "{",
  '  "action": "<one allowed action> or null",',
  '  "confidence": 0.0,',
  '  "message": "friendly short message"',
  "}",
].join("\n");

export function buildActionRouterPrompt(input: {
  userMessage: string;
  currentState: HellyState;
}): string {
  return [
    ACTION_ROUTER_SYSTEM_PROMPT,
    "",
    "Runtime input JSON:",
    JSON.stringify(
      {
        current_state: input.currentState,
        user_message: input.userMessage,
      },
      null,
      2,
    ),
  ].join("\n");
}
