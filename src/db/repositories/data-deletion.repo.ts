import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";

const DATA_DELETION_REQUESTS_TABLE = "data_deletion_requests";

export class DataDeletionRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async markRequested(input: {
    telegramUserId: number;
    telegramUsername?: string;
    reason?: string;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    await this.supabaseClient.upsert(
      DATA_DELETION_REQUESTS_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        telegram_username: input.telegramUsername ?? null,
        reason: input.reason ?? "user_requested",
        status: "requested",
        requested_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id" },
    );

    this.logger.info("Data deletion request persisted", {
      telegramUserId: input.telegramUserId,
    });
  }
}
