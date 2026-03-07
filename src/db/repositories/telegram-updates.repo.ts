import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";

const TELEGRAM_UPDATES_TABLE = "telegram_updates";

export class TelegramUpdatesRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async markIfNew(updateId: number, telegramUserId: number): Promise<boolean> {
    if (!this.supabaseClient) {
      return true;
    }

    try {
      await this.supabaseClient.insert(TELEGRAM_UPDATES_TABLE, {
        update_id: updateId,
        telegram_user_id: telegramUserId,
        received_at: new Date().toISOString(),
      });
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      if (isDuplicateConstraintError(message)) {
        this.logger.debug("telegram update already processed", {
          updateId,
          telegramUserId,
        });
        return false;
      }
      this.logger.warn("failed to persist telegram update idempotency marker", {
        updateId,
        telegramUserId,
        error: message,
      });
      return true;
    }
  }
}

function isDuplicateConstraintError(message: string): boolean {
  const normalized = message.toLowerCase();
  return (
    normalized.includes("duplicate key") ||
    normalized.includes("already exists") ||
    normalized.includes("23505")
  );
}
