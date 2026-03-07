import { Logger } from "../config/logger";
import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildIntentRouterV2Prompt, type IntentRouterV2Input } from "../ai/prompts/intent_router_v2.prompt";
import {
  type IntentRouterV2Schema,
  isIntentRouterV2Schema,
} from "../ai/schemas/llm-json-schemas";

export type { IntentRouterV2Schema };

const FALLBACK: IntentRouterV2Schema = {
  intent: "other",
  language: "en",
  confidence: 0.3,
  userQuestion: null,
};

export class IntentRouterV2Service {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async detect(input: IntentRouterV2Input): Promise<IntentRouterV2Schema> {
    const prompt = buildIntentRouterV2Prompt(input);
    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 120,
      timeoutMs: 15_000,
      promptName: "intent_router_v2",
      schemaHint: "Intent router v2 JSON with intent, language, confidence, userQuestion.",
      validate: (v): v is Record<string, unknown> =>
        typeof v === "object" && v !== null && !Array.isArray(v),
    });

    if (!safe.ok) {
      this.logger.warn("intent_router_v2.failed", { errorCode: safe.error_code });
      return FALLBACK;
    }

    const intent = normalizeIntent(safe.data.intent);
    const language = normalizeLanguage(safe.data.language);
    const confidence = typeof safe.data.confidence === "number" ? Math.max(0, Math.min(1, safe.data.confidence)) : 0.5;
    const userQuestion =
      safe.data.userQuestion != null && typeof safe.data.userQuestion === "string"
        ? safe.data.userQuestion.trim() || null
        : null;

    const result: IntentRouterV2Schema = {
      intent: intent ?? "other",
      language: language ?? "en",
      confidence,
      userQuestion,
    };

    if (!isIntentRouterV2Schema(result)) {
      return FALLBACK;
    }

    this.logger.debug("intent_router_v2.result", {
      intent: result.intent,
      language: result.language,
      confidence: result.confidence,
    });
    return result;
  }
}

function normalizeIntent(value: unknown): IntentRouterV2Schema["intent"] | null {
  const s = typeof value === "string" ? value.trim().toLowerCase() : "";
  const intents: IntentRouterV2Schema["intent"][] = [
    "answer", "clarify_question", "skip", "pause", "resume", "restart",
    "switch_role", "request_matching", "match_apply", "match_reject", "smalltalk", "other",
  ];
  return intents.includes(s as IntentRouterV2Schema["intent"]) ? (s as IntentRouterV2Schema["intent"]) : null;
}

function normalizeLanguage(value: unknown): "en" | "ru" | "uk" | null {
  const s = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (s === "en" || s === "ru" || s === "uk") return s;
  return null;
}
