import { LlmClient } from "../llm.client";
import { callJsonPromptSafe } from "../llm.safe";
import { Logger } from "../../config/logger";
import { buildActionRouterPrompt } from "./action-router.prompt";
import {
  ACTION_ROUTER_RESULT_JSON_SCHEMA,
  isActionRouterResult,
  normalizeActionRouterResult,
} from "./action-router.schema";
import { ActionRouterInput, ActionRouterResult } from "./action-router.types";

const FALLBACK_RESULT: ActionRouterResult = {
  action: null,
  confidence: 0,
  message: "Please continue when you are ready.",
};

export class ActionRouterService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: ActionRouterInput): Promise<ActionRouterResult> {
    const userMessage = input.userMessage.trim();
    if (!userMessage) {
      return FALLBACK_RESULT;
    }

    const prompt = buildActionRouterPrompt({
      userMessage,
      currentState: input.currentState,
    });

    const safe = await callJsonPromptSafe<ActionRouterResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 160,
      timeoutMs: 20_000,
      promptName: "action_router_v1",
      schemaHint: JSON.stringify(ACTION_ROUTER_RESULT_JSON_SCHEMA),
      validate: isActionRouterResult,
    });

    if (!safe.ok) {
      this.logger.warn("action.router.failed", {
        errorCode: safe.error_code,
        state: input.currentState,
      });
      return FALLBACK_RESULT;
    }

    const normalized = normalizeActionRouterResult(safe.data);
    this.logger.debug("action.router.classified", {
      action: normalized.action,
      confidence: normalized.confidence,
      state: input.currentState,
    });
    return normalized;
  }
}
