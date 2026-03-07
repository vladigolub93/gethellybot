import { LlmClient } from "./llm.client";
import { callTextPromptSafe } from "./llm.safe";
import { Logger } from "../config/logger";
import { buildOutboundComposeV1Prompt } from "./prompts/outbound/outbound-compose.v1.prompt";
import { isHardSystemSource } from "../shared/utils/message-source";

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
    if (isHardSystemSource(input.source)) {
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
    if (!isComposedMessageSafe(trimmed, candidate)) {
      this.logger.debug("outbound.message.compose.rejected_by_guard", {
        source: input.source,
        chatId: input.chatId,
      });
      return input.text;
    }
    return candidate;
  }
}

const KEYWORD_ANCHORS = [
  "pdf",
  "docx",
  "resume",
  "job description",
  "contact",
  "share my contact",
  "skip for now",
  "candidate",
  "hiring",
  "apply",
  "reject",
];

const COMMAND_ANCHORS = ["/start", "/help", "/delete"];

function isComposedMessageSafe(original: string, candidate: string): boolean {
  const o = normalizeForGuard(original);
  const c = normalizeForGuard(candidate);
  if (!c) {
    return false;
  }

  for (const command of COMMAND_ANCHORS) {
    if (o.includes(command) && !c.includes(command)) {
      return false;
    }
  }

  for (const keyword of KEYWORD_ANCHORS) {
    if (o.includes(keyword) && !c.includes(keyword)) {
      return false;
    }
  }

  if (containsLikelyPhone(original) && !containsLikelyPhone(candidate)) {
    return false;
  }

  if (original.length >= 80) {
    const minLength = Math.floor(original.length * 0.5);
    if (candidate.length < minLength) {
      return false;
    }
  }

  return true;
}

function normalizeForGuard(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

function containsLikelyPhone(text: string): boolean {
  return /(\+?\d[\d\s\-()]{7,}\d)/.test(text);
}
