import { buildAlwaysOnRouterV1Prompt } from "../ai/prompts/router/always-on-router.v1.prompt";
import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { Logger } from "../config/logger";
import { AlwaysOnRouterDecision } from "../shared/types/always-on-router.types";
import { UserRole, UserState } from "../shared/types/state.types";

interface AlwaysOnRouterInput {
  updateId: number;
  telegramUserId: number;
  currentState: UserState;
  userRole?: UserRole;
  hasText: boolean;
  textEnglish: string | null;
  hasDocument: boolean;
  hasVoice: boolean;
  currentQuestion: string | null;
  lastBotMessage: string | null;
  knownUserName?: string | null;
  userRagContext?: string | null;
}

export class AlwaysOnRouterService {
  private readonly debugMode = (process.env.DEBUG_MODE ?? "false").toLowerCase() === "true";

  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: AlwaysOnRouterInput): Promise<AlwaysOnRouterDecision> {
    const startedAt = Date.now();
    this.logger.debug("router called", {
      updateId: input.updateId,
      telegramUserId: input.telegramUserId,
      currentState: input.currentState,
      promptName: "always_on_router_v1",
      modelName: this.llmClient.getModelName(),
    });

    const prompt = buildAlwaysOnRouterV1Prompt({
      currentState: input.currentState,
      userRole: input.userRole ?? "unknown",
      hasText: input.hasText,
      textEnglish: input.textEnglish,
      hasDocument: input.hasDocument,
      hasVoice: input.hasVoice,
      currentQuestion: input.currentQuestion,
      lastBotMessage: input.lastBotMessage,
      knownUserName: input.knownUserName ?? null,
      userRagContext: input.userRagContext ?? null,
    });

    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 280,
        promptName: "always_on_router_v1",
        schemaHint:
          "Always-on router JSON with route, conversation_intent, meta_type, control_type, matching_intent, reply, should_advance, should_process_text_as_document.",
      });
      if (!safe.ok) {
        throw new Error(`always_on_router_v1_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      const parsed = parseAlwaysOnRouterDecision(raw);
      if (this.debugMode) {
        this.logger.debug("router.output.always_on", {
          updateId: input.updateId,
          telegramUserId: input.telegramUserId,
          output: parsed,
        });
      }
      this.logger.info("router.parse.completed", {
        updateId: input.updateId,
        telegramUserId: input.telegramUserId,
        currentState: input.currentState,
        route: parsed.route,
        promptName: "always_on_router_v1",
        modelName: this.llmClient.getModelName(),
        latencyMs: Date.now() - startedAt,
        parseSuccess: true,
      });
      return parsed;
    } catch (error) {
      this.logger.warn("router.parse.failed", {
        updateId: input.updateId,
        telegramUserId: input.telegramUserId,
        currentState: input.currentState,
        promptName: "always_on_router_v1",
        modelName: this.llmClient.getModelName(),
        latencyMs: Date.now() - startedAt,
        parseSuccess: false,
        error_code: error instanceof Error ? error.message : "unknown_error",
      });
      throw error;
    }
  }
}

function parseAlwaysOnRouterDecision(raw: string): AlwaysOnRouterDecision {
  const parsed = parseJsonObject(raw);
  const route = normalizeRoute(parsed.route);
  const conversationIntent = normalizeConversationIntent(parsed.conversation_intent, route);
  const metaType = normalizeMetaType(parsed.meta_type, route);
  const controlType = normalizeControlType(parsed.control_type, route);
  const matchingIntent = normalizeMatchingIntent(parsed.matching_intent, route);
  const reply = toText(parsed.reply);
  if (!reply) {
    throw new Error("always-on router output is invalid: reply is required");
  }
  if (typeof parsed.should_advance !== "boolean") {
    throw new Error("always-on router output is invalid: should_advance must be boolean");
  }
  if (typeof parsed.should_process_text_as_document !== "boolean") {
    throw new Error(
      "always-on router output is invalid: should_process_text_as_document must be boolean",
    );
  }

  const shouldProcessTextAsDocument =
    (route === "JD_TEXT" || route === "RESUME_TEXT") && parsed.should_process_text_as_document;

  return {
    route,
    conversation_intent: conversationIntent,
    meta_type: metaType,
    control_type: controlType,
    matching_intent: matchingIntent,
    reply,
    should_advance: parsed.should_advance,
    should_process_text_as_document: shouldProcessTextAsDocument,
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("always-on router output is not valid JSON");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeRoute(value: unknown): AlwaysOnRouterDecision["route"] {
  const normalized = toText(value).toUpperCase();
  if (
    normalized === "DOC" ||
    normalized === "VOICE" ||
    normalized === "JD_TEXT" ||
    normalized === "RESUME_TEXT" ||
    normalized === "INTERVIEW_ANSWER" ||
    normalized === "META" ||
    normalized === "CONTROL" ||
    normalized === "MATCHING_COMMAND" ||
    normalized === "OFFTOPIC" ||
    normalized === "OTHER"
  ) {
    return normalized;
  }
  throw new Error("always-on router output is invalid: route is not supported");
}

function normalizeConversationIntent(
  value: unknown,
  route: AlwaysOnRouterDecision["route"],
): AlwaysOnRouterDecision["conversation_intent"] {
  const normalized = toText(value).toUpperCase();
  if (
    normalized === "ANSWER" ||
    normalized === "CLARIFY" ||
    normalized === "COMMAND" ||
    normalized === "MATCHING" ||
    normalized === "COMPLAINT" ||
    normalized === "SMALLTALK" ||
    normalized === "OTHER"
  ) {
    return normalized;
  }

  if (route === "INTERVIEW_ANSWER") {
    return "ANSWER";
  }
  if (route === "MATCHING_COMMAND") {
    return "MATCHING";
  }
  if (route === "CONTROL") {
    return "COMMAND";
  }
  if (route === "META") {
    return "CLARIFY";
  }
  return "OTHER";
}

function normalizeMetaType(
  value: unknown,
  route: AlwaysOnRouterDecision["route"],
): AlwaysOnRouterDecision["meta_type"] {
  if (route !== "META") {
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
  return "other";
}

function normalizeControlType(
  value: unknown,
  route: AlwaysOnRouterDecision["route"],
): AlwaysOnRouterDecision["control_type"] {
  if (route !== "CONTROL") {
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
  return "help";
}

function normalizeMatchingIntent(
  value: unknown,
  route: AlwaysOnRouterDecision["route"],
): AlwaysOnRouterDecision["matching_intent"] {
  if (route !== "MATCHING_COMMAND") {
    return null;
  }
  const normalized = toText(value).toLowerCase();
  if (
    normalized === "run" ||
    normalized === "show" ||
    normalized === "pause" ||
    normalized === "resume" ||
    normalized === "help"
  ) {
    return normalized;
  }
  return "help";
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
