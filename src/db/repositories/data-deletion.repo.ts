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

  async purgeUserData(telegramUserId: number): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const deletions: Array<{ table: string; filters: Record<string, string | number> }> = [
      { table: "user_states", filters: { telegram_user_id: telegramUserId } },
      { table: "profiles", filters: { telegram_user_id: telegramUserId } },
      { table: "interview_runs", filters: { telegram_user_id: telegramUserId } },
      { table: "jobs", filters: { manager_telegram_user_id: telegramUserId } },
      { table: "matches", filters: { candidate_telegram_user_id: telegramUserId } },
      { table: "matches", filters: { manager_telegram_user_id: telegramUserId } },
      { table: "notification_limits", filters: { telegram_user_id: telegramUserId } },
      { table: "telegram_updates", filters: { telegram_user_id: telegramUserId } },
      { table: "users", filters: { telegram_user_id: telegramUserId } },
    ];

    for (const item of deletions) {
      await this.supabaseClient.deleteMany(item.table, item.filters);
    }

    this.logger.info("User data purged from Supabase", {
      telegramUserId,
    });
  }
}
