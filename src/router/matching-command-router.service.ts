import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { MATCHING_COMMAND_ROUTER_V1_PROMPT } from "../ai/prompts/router/matching-command-router.v1.prompt";
import { Logger } from "../config/logger";
import { UserRole, UserState } from "../shared/types/state.types";

export type MatchingCommandIntent =
  | "RUN_MATCHING"
  | "SHOW_MATCHES"
  | "PAUSE_MATCHING"
  | "RESUME_MATCHING"
  | "HELP"
  | "OTHER";

export type MatchingCommandTarget = "roles" | "candidates" | "unknown";
export type MatchingCommandConfidence = "low" | "medium" | "high";

export interface MatchingCommandDecision {
  intent: MatchingCommandIntent;
  target: MatchingCommandTarget;
  confidence: MatchingCommandConfidence;
  reply: string;
}

export class MatchingCommandRouterService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: {
    userRole?: UserRole;
    currentState: UserState;
    userMessageEnglish: string;
  }): Promise<MatchingCommandDecision> {
    const prompt = buildMatchingCommandRouterPrompt(input);
    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 220,
        promptName: "matching_command_router_v1",
        schemaHint: "Matching command router JSON with intent, target, confidence, reply.",
      });
      if (!safe.ok) {
        throw new Error(`matching_command_router_v1_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      return parseDecision(raw);
    } catch (error) {
      this.logger.warn("Matching command router failed, using fallback", {
        state: input.currentState,
        role: input.userRole ?? "unknown",
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return fallbackDecision(input.userMessageEnglish);
    }
  }
}

function buildMatchingCommandRouterPrompt(input: {
  userRole?: UserRole;
  currentState: UserState;
  userMessageEnglish: string;
}): string {
  return [
    MATCHING_COMMAND_ROUTER_V1_PROMPT,
    "",
    "Runtime context JSON:",
    JSON.stringify(
      {
        user_role: input.userRole ?? null,
        current_state: input.currentState,
        user_message_english: input.userMessageEnglish,
      },
      null,
      2,
    ),
  ].join("\n");
}

function parseDecision(raw: string): MatchingCommandDecision {
  const parsed = parseJsonObject(raw);
  const intent = normalizeIntent(parsed.intent);
  const target = normalizeTarget(parsed.target);
  const confidence = normalizeConfidence(parsed.confidence);
  const reply = toText(parsed.reply);
  if (!reply) {
    throw new Error("matching command router output is invalid: reply is required");
  }

  return {
    intent,
    target,
    confidence,
    reply,
  };
}

function fallbackDecision(userMessageEnglish: string): MatchingCommandDecision {
  const normalized = userMessageEnglish.trim().toLowerCase();
  if (!normalized) {
    return {
      intent: "OTHER",
      target: "unknown",
      confidence: "low",
      reply: "Please share what you want to do.",
    };
  }

  if (
    normalized.includes("help") ||
    normalized.includes("how it works")
  ) {
    return {
      intent: "HELP",
      target: "unknown",
      confidence: "medium",
      reply: "I can run matching, show latest matches, pause or resume matching alerts.",
    };
  }

  if (
    normalized.includes("pause") ||
    normalized.includes("stop") ||
    normalized.includes("disable alerts")
  ) {
    return {
      intent: "PAUSE_MATCHING",
      target: "unknown",
      confidence: "high",
      reply: "Matching alerts are paused.",
    };
  }

  if (
    normalized.includes("resume") ||
    normalized.includes("enable")
  ) {
    return {
      intent: "RESUME_MATCHING",
      target: "unknown",
      confidence: "high",
      reply: "Matching is resumed.",
    };
  }

  if (
    normalized.includes("show matches") ||
    normalized.includes("show results")
  ) {
    return {
      intent: "SHOW_MATCHES",
      target: inferTarget(normalized),
      confidence: "medium",
      reply: "I will show your latest matching results.",
    };
  }

  if (
    normalized.includes("find roles") ||
    normalized.includes("find jobs") ||
    normalized.includes("vacancies")
  ) {
    return {
      intent: "RUN_MATCHING",
      target: "roles",
      confidence: "high",
      reply: "I will look for matching roles now.",
    };
  }

  if (
    normalized.includes("find candidates") ||
    normalized.includes("find engineers") ||
    normalized.includes("find people")
  ) {
    return {
      intent: "RUN_MATCHING",
      target: "candidates",
      confidence: "high",
      reply: "I will look for matching candidates now.",
    };
  }

  return {
    intent: "OTHER",
    target: "unknown",
    confidence: "low",
    reply: "Please tell me if you want to run matching, show matches, pause, or resume.",
  };
}

function inferTarget(text: string): MatchingCommandTarget {
  if (text.includes("candidate") || text.includes("engineer") || text.includes("people")) {
    return "candidates";
  }
  if (text.includes("role") || text.includes("job") || text.includes("vacanc")) {
    return "roles";
  }
  return "unknown";
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("matching command router output is not valid JSON");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeIntent(value: unknown): MatchingCommandIntent {
  const normalized = toText(value).toUpperCase();
  if (
    normalized === "RUN_MATCHING" ||
    normalized === "SHOW_MATCHES" ||
    normalized === "PAUSE_MATCHING" ||
    normalized === "RESUME_MATCHING" ||
    normalized === "HELP" ||
    normalized === "OTHER"
  ) {
    return normalized;
  }
  throw new Error("matching command router output has invalid intent");
}

function normalizeTarget(value: unknown): MatchingCommandTarget {
  const normalized = toText(value).toLowerCase();
  if (normalized === "roles" || normalized === "candidates" || normalized === "unknown") {
    return normalized;
  }
  return "unknown";
}

function normalizeConfidence(value: unknown): MatchingCommandConfidence {
  const normalized = toText(value).toLowerCase();
  if (normalized === "low" || normalized === "medium" || normalized === "high") {
    return normalized;
  }
  return "low";
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
