import { Logger } from "../../config/logger";
import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import {
  buildOutboundComposeV2Prompt,
  type OutboundComposeV2Input,
} from "../../ai/prompts/outbound/outbound_message_compose_v2.prompt";
import { buildOutboundComposeV3Prompt } from "../../ai/prompts/outbound/outbound_message_compose_v3.prompt";
import type { DialogueLanguage } from "./language.service";
import type { UserRole } from "../../shared/types/state.types";

export type ComposerReaction = "👍" | "🤝" | "👀" | "✅" | "❓" | null;

export interface ComposerButton {
  text: string;
  data: string;
}

export interface ReplyComposeV2Result {
  message: string;
  reaction: ComposerReaction;
  buttons: ComposerButton[];
}

const ALLOWED_REACTIONS: ComposerReaction[] = ["👍", "🤝", "👀", "✅", "❓"];

function parseReaction(value: unknown): ComposerReaction {
  if (value === null || value === undefined) {
    return null;
  }
  const s = String(value).trim();
  if (ALLOWED_REACTIONS.includes(s as ComposerReaction)) {
    return s as ComposerReaction;
  }
  return null;
}

function parseButtons(value: unknown): ComposerButton[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      text: typeof item.text === "string" ? item.text.trim().slice(0, 64) : "",
      data: typeof item.data === "string" ? item.data.trim().slice(0, 64) : "",
    }))
    .filter((b) => b.text && b.data)
    .slice(0, 8);
}

function parseComposeResult(raw: Record<string, unknown>): ReplyComposeV2Result | null {
  const message = typeof raw.message === "string" ? raw.message.trim() : "";
  if (!message) {
    return null;
  }
  return {
    message,
    reaction: parseReaction(raw.reaction),
    buttons: parseButtons(raw.buttons),
  };
}

export interface ReplyComposerV2Input {
  userRole: UserRole;
  userLanguage: DialogueLanguage;
  currentState: string;
  nextQuestionText?: string | null;
  lastUserMessage: string;
  profileSummaryFacts?: string[];
  lastBotMessage?: string | null;
  /** If set, avoid repeating this phrase (e.g. for loop prevention) */
  avoidPhrase?: string | null;
  /** User seems frustrated or asked to skip/stop — use v3 de-escalation when useV3Prompt */
  userFrustrated?: boolean;
}

const DEFAULT_SAFETY_RULES = [
  "No harassment or aggressive tone.",
  "Keep replies hiring-related and professional.",
];

export class ReplyComposerV2 {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly useV3Prompt = false,
  ) {}

  async compose(input: ReplyComposerV2Input): Promise<ReplyComposeV2Result | null> {
    const promptName = this.useV3Prompt ? "outbound_message_compose_v3" : "outbound_message_compose_v2";
    let prompt: string;

    if (this.useV3Prompt) {
      prompt = buildOutboundComposeV3Prompt({
        userRole: input.userRole === "manager" ? "manager" : "candidate",
        userLanguage: input.userLanguage,
        currentState: input.currentState,
        nextQuestionText: input.nextQuestionText,
        lastUserMessage: input.lastUserMessage,
        profileSummaryFacts: input.profileSummaryFacts ?? [],
        lastBotMessage: input.lastBotMessage,
        avoidPhrase: input.avoidPhrase,
        userFrustrated: input.userFrustrated ?? false,
      });
    } else {
      const promptInput: OutboundComposeV2Input = {
        userRole: input.userRole === "manager" ? "manager" : "candidate",
        userLanguage: input.userLanguage,
        currentState: input.currentState,
        nextQuestionText: input.nextQuestionText,
        lastUserMessage: input.lastUserMessage,
        profileSummaryFacts: input.profileSummaryFacts ?? [],
        safetyRules: DEFAULT_SAFETY_RULES,
        lastBotMessage: input.lastBotMessage,
        avoidPhrase: input.avoidPhrase,
      };
      prompt = buildOutboundComposeV2Prompt(promptInput);
    }

    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 380,
      timeoutMs: 20_000,
      promptName,
      schemaHint: "Reply compose JSON with message, reaction, buttons.",
      validate: (v): v is Record<string, unknown> =>
        typeof v === "object" && v !== null && !Array.isArray(v),
    });

    if (!safe.ok) {
      this.logger.warn("reply.composer.v2.failed", {
        errorCode: safe.error_code,
      });
      return null;
    }

    const result = parseComposeResult(safe.data);
    if (!result) {
      this.logger.warn("reply.composer.v2.invalid_output");
      return null;
    }

    this.logger.debug("reply.composer.v2.composed", {
      messageLength: result.message.length,
      hasReaction: result.reaction !== null,
      buttonsCount: result.buttons.length,
    });
    return result;
  }
}
