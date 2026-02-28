import { Logger } from "../../config/logger";
import { TelegramUpdatesRepository } from "../../db/repositories/telegram-updates.repo";

const MEMORY_MAX_SIZE = 5_000;

const processedUpdates = new Set<number>();
const processedOrder: number[] = [];

let repository: TelegramUpdatesRepository | undefined;
let logger: Logger | undefined;

export function configureTelegramIdempotency(input: {
  repository?: TelegramUpdatesRepository;
  logger?: Logger;
}): void {
  repository = input.repository;
  logger = input.logger;
}

export async function shouldProcessUpdate(
  updateId: number,
  telegramUserId: number,
): Promise<boolean> {
  const isNewInMemory = markInMemory(updateId);
  if (!isNewInMemory) {
    return false;
  }

  if (!repository) {
    return true;
  }

  const isNewInDatabase = await repository.markIfNew(updateId, telegramUserId);
  if (!isNewInDatabase) {
    processedUpdates.delete(updateId);
    return false;
  }

  logger?.debug("telegram idempotency accepted update", {
    updateId,
    telegramUserId,
  });
  return true;
}

function markInMemory(updateId: number): boolean {
  if (processedUpdates.has(updateId)) {
    return false;
  }
  processedUpdates.add(updateId);
  processedOrder.push(updateId);
  if (processedOrder.length > MEMORY_MAX_SIZE) {
    const oldest = processedOrder.shift();
    if (typeof oldest === "number") {
      processedUpdates.delete(oldest);
    }
  }
  return true;
}
