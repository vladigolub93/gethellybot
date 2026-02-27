import { LlmClient } from "../ai/llm.client";
import { buildInterviewIntentRouterV1Prompt } from "../ai/prompts/router/interview-intent-router.v1.prompt";
import { Logger } from "../config/logger";
import { InterviewIntentDecisionV1 } from "../shared/types/interview-intent.types";

interface InterviewIntentInput {
  currentState: "interviewing_candidate" | "interviewing_manager";
  currentQuestionText: string;
  userMessage: string;
}

const FORMAT_FALLBACK_REPLY =
  "You can answer in text or voice. Detailed answers help me build an accurate profile.";
const OFFTOPIC_FALLBACK_REPLY =
  "Let us keep this focused on your interview. Please answer the current question to continue.";

export class InterviewIntentRouterService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: InterviewIntentInput): Promise<InterviewIntentDecisionV1> {
    const prompt = buildInterviewIntentRouterV1Prompt(input);
    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 280, {
        promptName: "interview_intent_router_v1",
      });
      const parsed = parseDecision(raw);
      return normalizeSubstantiveAnswerGuard(parsed, input.userMessage);
    } catch (error) {
      this.logger.warn("Interview intent router failed, using fallback", {
        state: input.currentState,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return fallbackDecision(input.userMessage);
    }
  }
}

function parseDecision(raw: string): InterviewIntentDecisionV1 {
  const parsed = parseJsonObject(raw);
  const intent = toText(parsed.intent).toUpperCase();
  if (intent !== "ANSWER" && intent !== "META" && intent !== "CONTROL" && intent !== "OFFTOPIC") {
    throw new Error("Invalid interview intent.");
  }

  const metaTypeRaw = parsed.meta_type;
  const controlTypeRaw = parsed.control_type;
  const suggestedReply = toText(parsed.suggested_reply);
  if (!suggestedReply) {
    throw new Error("Invalid interview intent: suggested_reply is required.");
  }
  if (typeof parsed.should_advance_interview !== "boolean") {
    throw new Error("Invalid interview intent: should_advance_interview must be boolean.");
  }

  const metaType = normalizeMetaType(metaTypeRaw);
  const controlType = normalizeControlType(controlTypeRaw);

  return {
    intent,
    meta_type: metaType,
    control_type: controlType,
    suggested_reply: suggestedReply,
    should_advance_interview: parsed.should_advance_interview,
  };
}

function normalizeSubstantiveAnswerGuard(
  decision: InterviewIntentDecisionV1,
  userMessage: string,
): InterviewIntentDecisionV1 {
  if (decision.intent !== "ANSWER") {
    return decision;
  }

  const words = userMessage
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  const hasSubstantiveLength = userMessage.trim().length >= 20 || words.length >= 5;
  if (hasSubstantiveLength) {
    return decision;
  }

  return {
    intent: "META",
    meta_type: "format",
    control_type: null,
    suggested_reply: FORMAT_FALLBACK_REPLY,
    should_advance_interview: false,
  };
}

function fallbackDecision(userMessage: string): InterviewIntentDecisionV1 {
  const normalized = userMessage.trim().toLowerCase();
  if (!normalized || normalized === "ok" || normalized === "sure" || normalized === "yes") {
    return {
      intent: "META",
      meta_type: "format",
      control_type: null,
      suggested_reply: FORMAT_FALLBACK_REPLY,
      should_advance_interview: false,
    };
  }

  if (
    normalized.includes("how long") ||
    normalized.includes("when") ||
    normalized.includes("сколько") ||
    normalized.includes("когда")
  ) {
    return {
      intent: "META",
      meta_type: "timing",
      control_type: null,
      suggested_reply:
        "Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.",
      should_advance_interview: false,
    };
  }

  if (
    normalized.includes("voice") ||
    normalized.includes("language") ||
    normalized.includes("russian") ||
    normalized.includes("ukrainian") ||
    normalized.includes("рус") ||
    normalized.includes("укра")
  ) {
    return {
      intent: "META",
      meta_type: "language",
      control_type: null,
      suggested_reply:
        "Yes, you can answer by voice in Russian or Ukrainian. I will transcribe it and continue. Please be detailed and use real examples.",
      should_advance_interview: false,
    };
  }

  if (normalized.includes("help") || normalized.includes("what to do")) {
    return {
      intent: "CONTROL",
      meta_type: null,
      control_type: "help",
      suggested_reply: FORMAT_FALLBACK_REPLY,
      should_advance_interview: false,
    };
  }

  const words = normalized.split(/\s+/).filter(Boolean);
  if (words.length < 4) {
    return {
      intent: "META",
      meta_type: "format",
      control_type: null,
      suggested_reply: FORMAT_FALLBACK_REPLY,
      should_advance_interview: false,
    };
  }

  return {
    intent: "ANSWER",
    meta_type: null,
    control_type: null,
    suggested_reply: OFFTOPIC_FALLBACK_REPLY,
    should_advance_interview: true,
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Interview intent output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeMetaType(value: unknown): InterviewIntentDecisionV1["meta_type"] {
  if (value === null) {
    return null;
  }
  const normalized = toText(value).toLowerCase();
  if (
    normalized === "timing" ||
    normalized === "language" ||
    normalized === "format" ||
    normalized === "privacy" ||
    normalized === "other"
  ) {
    return normalized;
  }
  return null;
}

function normalizeControlType(value: unknown): InterviewIntentDecisionV1["control_type"] {
  if (value === null) {
    return null;
  }
  const normalized = toText(value).toLowerCase();
  if (
    normalized === "pause" ||
    normalized === "resume" ||
    normalized === "restart" ||
    normalized === "help" ||
    normalized === "stop"
  ) {
    return normalized;
  }
  return null;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
