import { LlmClient } from "./llm.client";
import { callTextPromptSafe } from "./llm.safe";
import { Logger } from "../config/logger";
import { buildOutboundComposeV1Prompt } from "./prompts/outbound/outbound-compose.v1.prompt";

interface ComposeInput {
  source: string;
  chatId: number;
  text: string;
}

export class OutboundMessageComposerService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async compose(input: ComposeInput): Promise<string> {
    const trimmed = input.text.trim();
    if (!trimmed) {
      return input.text;
    }

    const prompt = buildOutboundComposeV1Prompt({
      source: input.source,
      message: trimmed,
      nonce: `${Date.now()}_${Math.abs(input.chatId) % 97}`,
    });

    const safe = await callTextPromptSafe({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 220,
      promptName: "outbound_message_compose_v1",
      timeoutMs: 25_000,
    });

    if (!safe.ok) {
      this.logger.warn("outbound.message.compose.failed", {
        source: input.source,
        chatId: input.chatId,
        errorCode: safe.error_code,
      });
      return input.text;
    }

    const candidate = safe.text.trim();
    if (!candidate) {
      return input.text;
    }
    return candidate;
  }
}
