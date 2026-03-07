import { Logger } from "../../config/logger";
import { UserState } from "../../shared/types/state.types";
import { TelegramClient } from "../telegram.client";

export type SafeReaction = "👍" | "✅" | "💡";
export type AnswerQualityHint = "low" | "medium" | "high";

export interface MaybeReactContext {
  telegramClient: TelegramClient;
  logger: Logger;
  userId: number;
  chatId: number;
  messageId?: number;
  state: UserState;
  answerText: string;
}

export interface MaybeReactOptions {
  enabled: boolean;
  probability: number;
  reactionMessagesSinceLast?: number;
  lastReactionEmoji?: string;
  answerQualityHint?: AnswerQualityHint;
}

export interface MaybeReactResult {
  reacted: boolean;
  reactionEmoji?: SafeReaction;
  nextMessagesSinceLast: number;
  lastReactionAt?: string;
}

const SAFE_REACTIONS: SafeReaction[] = ["👍", "✅", "💡"];

export async function maybeReact(
  ctx: MaybeReactContext,
  options: MaybeReactOptions,
): Promise<MaybeReactResult> {
  const previousCount = normalizeMessagesCount(options.reactionMessagesSinceLast);
  const incrementedCount = previousCount + 1;

  if (!options.enabled) {
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }

  if (!isInterviewingState(ctx.state) || !ctx.messageId) {
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }

  const answerText = ctx.answerText.trim();
  if (!isMeaningfulAnswer(answerText) || containsSensitiveContent(answerText)) {
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }

  if (incrementedCount < 3) {
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }

  const normalizedProbability = clampProbability(options.probability);
  if (Math.random() > normalizedProbability) {
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }

  const chosen = chooseReaction(answerText, options.answerQualityHint, options.lastReactionEmoji);
  try {
    await ctx.telegramClient.setMessageReaction(ctx.chatId, ctx.messageId, chosen);
    return {
      reacted: true,
      reactionEmoji: chosen,
      nextMessagesSinceLast: 0,
      lastReactionAt: new Date().toISOString(),
    };
  } catch (error) {
    ctx.logger.debug("Reaction was skipped after Telegram API fallback", {
      userId: ctx.userId,
      error: error instanceof Error ? error.message : "unknown_error",
    });
    return { reacted: false, nextMessagesSinceLast: incrementedCount };
  }
}

function isInterviewingState(state: UserState): boolean {
  return state === "interviewing_candidate" || state === "interviewing_manager";
}

function clampProbability(value: number): number {
  if (!Number.isFinite(value)) {
    return 0.12;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

function normalizeMessagesCount(value?: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 3;
  }
  return Math.max(0, Math.floor(value));
}

function isMeaningfulAnswer(text: string): boolean {
  if (!text) {
    return false;
  }
  const words = text.split(/\s+/).filter(Boolean);
  return text.length >= 20 && words.length >= 4;
}

function containsSensitiveContent(text: string): boolean {
  const lowered = text.toLowerCase();
  const sensitivePatterns = [
    "passport",
    "social security",
    "ssn",
    "medical",
    "diagnosis",
    "disease",
    "religion",
    "politics",
    "home address",
    "phone number",
  ];
  return sensitivePatterns.some((pattern) => lowered.includes(pattern));
}

function chooseReaction(
  answerText: string,
  qualityHint: AnswerQualityHint | undefined,
  previousEmoji: string | undefined,
): SafeReaction {
  let candidate: SafeReaction;

  if (qualityHint === "high") {
    candidate = Math.random() < 0.5 ? "👍" : "✅";
  } else if (hasConcreteDetails(answerText)) {
    candidate = "💡";
  } else {
    candidate = "👍";
  }

  if (candidate !== previousEmoji) {
    return candidate;
  }

  return SAFE_REACTIONS.find((item) => item !== previousEmoji) ?? "✅";
}

function hasConcreteDetails(text: string): boolean {
  const lowered = text.toLowerCase();
  return (
    /\d/.test(lowered) ||
    lowered.includes("for example") ||
    lowered.includes("because") ||
    lowered.includes("architecture") ||
    lowered.includes("latency") ||
    lowered.includes("throughput")
  );
}
