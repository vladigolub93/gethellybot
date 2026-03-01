import { AsyncLocalStorage } from "node:async_hooks";

export type ReplyKind = "primary" | "secondary";

interface UpdateReplyContext {
  updateId: number;
  telegramUserId: number;
  primarySent: boolean;
  secondarySent: boolean;
}

const storage = new AsyncLocalStorage<UpdateReplyContext>();

export function beginUpdateContext(updateId: number, telegramUserId: number): void {
  storage.enterWith({
    updateId,
    telegramUserId,
    primarySent: false,
    secondarySent: false,
  });
}

export function clearUpdateContext(): void {
  storage.disable();
}

export function canSendReply(kind: ReplyKind): boolean {
  const context = storage.getStore();
  if (!context) {
    return true;
  }
  if (kind === "primary") {
    return !context.primarySent;
  }
  return !context.secondarySent;
}

export function markSent(kind: ReplyKind): void {
  const context = storage.getStore();
  if (!context) {
    return;
  }
  if (kind === "primary") {
    context.primarySent = true;
  } else {
    context.secondarySent = true;
  }
}

export function getUpdateContext(): { updateId: number; telegramUserId: number } | null {
  const context = storage.getStore();
  if (!context) {
    return null;
  }
  return {
    updateId: context.updateId,
    telegramUserId: context.telegramUserId,
  };
}
