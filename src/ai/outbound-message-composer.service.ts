import { LlmClient } from "./llm.client";
import { callTextPromptSafe } from "./llm.safe";
import { Logger } from "../config/logger";

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

    const prompt = [
      "Rewrite the assistant message into a natural conversational message.",
      "Keep the same meaning, same action, and same constraints.",
      "Do not remove critical details like numbers, phone numbers, links, commands, or button labels.",
      "Do not add new promises.",
      "Do not add emojis.",
      "Keep it concise.",
      "If the message is already natural, return it with minimal changes.",
      "",
      "Output only the final assistant message text.",
      "",
      "Input JSON:",
      JSON.stringify(
        {
          source: input.source,
          chat_id: input.chatId,
          message: trimmed,
        },
        null,
        2,
      ),
    ].join("\n");

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

