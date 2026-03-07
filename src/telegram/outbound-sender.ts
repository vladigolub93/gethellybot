/**
 * Stage 11: Centralize outbound sending with duplicate prevention (TTL cache).
 * sendOnce ensures the same (chatId, updateId, textHash) is not sent twice within TTL.
 */

import { createHash } from "node:crypto";
import { Logger } from "../config/logger";

const TTL_MS = 30_000;
const MAX_ENTRIES = 5000;

interface CacheEntry {
  at: number;
}

const sentCache = new Map<string, CacheEntry>();
let evictTimer: ReturnType<typeof setImmediate> | null = null;

function cacheKey(chatId: number, updateId: number, textHash: string): string {
  return `${chatId}:${updateId}:${textHash}`;
}

function evictStale(): void {
  const now = Date.now();
  for (const [key, entry] of sentCache.entries()) {
    if (now - entry.at > TTL_MS) sentCache.delete(key);
  }
  if (sentCache.size > MAX_ENTRIES) {
    const entries = [...sentCache.entries()].sort((a, b) => a[1].at - b[1].at);
    const toDelete = entries.slice(0, Math.floor(MAX_ENTRIES / 2)).map(([k]) => k);
    toDelete.forEach((k) => sentCache.delete(k));
  }
  evictTimer = null;
}

function scheduleEvict(): void {
  if (evictTimer) return;
  evictTimer = setImmediate(() => {
    evictTimer = null;
    evictStale();
  });
}

export function hashOutboundText(text: string): string {
  return createHash("sha256").update(text.trim()).digest("hex").slice(0, 16);
}

export interface SendOncePayload {
  chatId: number;
  text: string;
  replyMarkup?: unknown;
  source?: string;
}

export interface SendOnceInput {
  chatId: number;
  updateId: number;
  textHash: string;
  payload: SendOncePayload;
  send: (payload: SendOncePayload) => Promise<void>;
  logger?: Logger;
}

/**
 * If (chatId, updateId, textHash) was already sent within TTL, skip. Otherwise send and record.
 */
export async function sendOnce(input: SendOnceInput): Promise<{ sent: boolean }> {
  const key = cacheKey(input.chatId, input.updateId, input.textHash);
  const now = Date.now();
  const existing = sentCache.get(key);
  if (existing && now - existing.at < TTL_MS) {
    input.logger?.debug("outbound_sender.duplicate_skipped", {
      chatId: input.chatId,
      updateId: input.updateId,
      source: input.payload.source,
    });
    return { sent: false };
  }
  sentCache.set(key, { at: now });
  scheduleEvict();
  await input.send(input.payload);
  return { sent: true };
}
