import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildInterviewIntentRouterV1Prompt } from "../ai/prompts/router/interview-intent-router.v1.prompt";
import { Logger } from "../config/logger";
import { InterviewIntentDecisionV1 } from "../shared/types/interview-intent.types";

interface InterviewIntentInput {
  currentState: "interviewing_candidate" | "interviewing_manager";
  userRole: "candidate" | "manager";
  currentQuestion: string;
  userMessageEnglish: string;
  lastBotMessage: string | null;
  knownUserName?: string | null;
  userRagContext?: string | null;
}

const FORMAT_FALLBACK_REPLY =
  "Please answer the current question. A short practical answer is enough, text or voice.";
const OFFTOPIC_FALLBACK_REPLY =
  "Let us keep this focused on your interview. Please answer the current question to continue.";

export class InterviewIntentRouterService {
  private readonly debugMode = (process.env.DEBUG_MODE ?? "false").toLowerCase() === "true";

  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: InterviewIntentInput): Promise<InterviewIntentDecisionV1> {
    const prompt = buildInterviewIntentRouterV1Prompt(input);
    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 280,
        promptName: "interview_intent_router_v1",
        schemaHint:
          "Interview intent JSON with intent, meta_type, control_type, reply, should_advance.",
      });
      if (!safe.ok) {
        throw new Error(`interview_intent_router_v1_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      const parsed = parseDecision(raw);
      if (this.debugMode) {
        this.logger.debug("router.output.interview_intent", {
          state: input.currentState,
          role: input.userRole,
          output: parsed,
        });
      }
      return normalizeSubstantiveAnswerGuard(parsed, input.userMessageEnglish);
    } catch (error) {
      this.logger.warn("Interview intent router failed, using fallback", {
        state: input.currentState,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return fallbackDecision(input.userMessageEnglish, input.knownUserName ?? null);
    }
  }
}

function parseDecision(raw: string): InterviewIntentDecisionV1 {
  const parsed = parseJsonObject(raw);
  const intent = toText(parsed.intent).toUpperCase();
  if (
    intent !== "ANSWER" &&
    intent !== "META" &&
    intent !== "CLARIFY" &&
    intent !== "CONTROL" &&
    intent !== "OFFTOPIC"
  ) {
    throw new Error("Invalid interview intent.");
  }

  const metaTypeRaw = parsed.meta_type;
  const controlTypeRaw = parsed.control_type;
  const reply = toText(parsed.reply);
  if (!reply) {
    throw new Error("Invalid interview intent: reply is required.");
  }
  if (typeof parsed.should_advance !== "boolean") {
    throw new Error("Invalid interview intent: should_advance must be boolean.");
  }

  const metaType = normalizeMetaType(metaTypeRaw);
  const controlType = normalizeControlType(controlTypeRaw);

  return {
    intent,
    meta_type: metaType,
    control_type: controlType,
    reply,
    should_advance: parsed.should_advance,
  };
}

function normalizeSubstantiveAnswerGuard(
  decision: InterviewIntentDecisionV1,
  userMessage: string,
): InterviewIntentDecisionV1 {
  if (decision.intent !== "ANSWER") {
    return decision;
  }
  if (!isNonAnswerFiller(userMessage)) {
    return decision;
  }
  return {
    intent: "META",
    meta_type: "format",
    control_type: null,
    reply: FORMAT_FALLBACK_REPLY,
    should_advance: false,
  };
}

function fallbackDecision(
  userMessage: string,
  knownUserName: string | null,
): InterviewIntentDecisionV1 {
  const normalized = userMessage.trim().toLowerCase();
  if (!normalized || normalized === "ok" || normalized === "sure" || normalized === "yes") {
    return {
      intent: "META",
      meta_type: "format",
      control_type: null,
      reply: FORMAT_FALLBACK_REPLY,
      should_advance: false,
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
      reply:
        "Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.",
      should_advance: false,
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
      reply:
        "Yes, you can answer by voice in Russian or Ukrainian. I will transcribe it and continue. Please be detailed and use real examples.",
      should_advance: false,
    };
  }

  if (
    normalized.includes("can you ask in russian") ||
    normalized.includes("can you ask in ukrainian") ||
    normalized.includes("ask in russian") ||
    normalized.includes("ask in ukrainian") ||
    normalized.includes("на русском вопрос") ||
    normalized.includes("на русском задать вопрос") ||
    normalized.includes("українською поставити питання")
  ) {
    return {
      intent: "META",
      meta_type: "language",
      control_type: null,
      reply: "Yes. I can ask questions in your preferred language. Please answer the current question and I will continue accordingly.",
      should_advance: false,
    };
  }

  if (
    normalized.includes("what is my name") ||
    normalized.includes("my name") ||
    normalized.includes("как меня зовут") ||
    normalized.includes("як мене звати")
  ) {
    return {
      intent: "META",
      meta_type: "other",
      control_type: null,
      reply: knownUserName?.trim()
        ? `I saved your name as ${knownUserName.trim()}.`
        : "I do not have your name yet, but we can continue with the current interview question.",
      should_advance: false,
    };
  }

  if (
    normalized.includes("what do you mean") ||
    normalized.includes("which project") ||
    normalized.includes("give me an example") ||
    normalized.includes("what level of detail") ||
    normalized.includes("clarify")
  ) {
    return {
      intent: "CLARIFY",
      meta_type: null,
      control_type: null,
      reply:
        "By this, I need one concrete example. Use: context, what you did, decisions, trade offs, and result.",
      should_advance: false,
    };
  }

  if (normalized.includes("help") || normalized.includes("what to do")) {
    return {
      intent: "CONTROL",
      meta_type: null,
      control_type: "help",
      reply: FORMAT_FALLBACK_REPLY,
      should_advance: false,
    };
  }

  if (isNonAnswerFiller(normalized)) {
    return {
      intent: "META",
      meta_type: "format",
      control_type: null,
      reply: FORMAT_FALLBACK_REPLY,
      should_advance: false,
    };
  }

  return {
    intent: "ANSWER",
    meta_type: null,
    control_type: null,
    reply: OFFTOPIC_FALLBACK_REPLY,
    should_advance: true,
  };
}

function isNonAnswerFiller(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const directMatches = new Set([
    "ok",
    "okay",
    "sure",
    "yes",
    "yep",
    "no",
    "next",
    "continue",
    "go on",
    "k",
    "kk",
    "понятно",
    "ок",
    "да",
    "нет",
    "дальше",
    "продолжай",
  ]);
  if (directMatches.has(normalized)) {
    return true;
  }
  if (normalized.length <= 3 && /^[\d.,]+$/.test(normalized)) {
    return true;
  }
  return false;
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
