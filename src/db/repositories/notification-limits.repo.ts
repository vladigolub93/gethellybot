import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";

const NOTIFICATION_LIMITS_TABLE = "notification_limits";

interface NotificationLimitRow {
  telegram_user_id: number;
  role: "candidate" | "manager";
  last_candidate_notify_at?: string | null;
  last_manager_notify_at?: string | null;
  daily_count?: number | null;
  daily_reset_at?: string | null;
}

export interface NotificationLimitRecord {
  telegramUserId: number;
  role: "candidate" | "manager";
  lastCandidateNotifyAt: string | null;
  lastManagerNotifyAt: string | null;
  dailyCount: number;
  dailyResetAt: string | null;
}

export class NotificationLimitsRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async getByUserAndRole(
    telegramUserId: number,
    role: "candidate" | "manager",
  ): Promise<NotificationLimitRecord | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<NotificationLimitRow>(
      NOTIFICATION_LIMITS_TABLE,
      {
        telegram_user_id: telegramUserId,
        role,
      },
      "telegram_user_id,role,last_candidate_notify_at,last_manager_notify_at,daily_count,daily_reset_at",
    );

    if (!row) {
      return null;
    }

    return {
      telegramUserId: row.telegram_user_id,
      role: row.role,
      lastCandidateNotifyAt: row.last_candidate_notify_at ?? null,
      lastManagerNotifyAt: row.last_manager_notify_at ?? null,
      dailyCount: typeof row.daily_count === "number" ? row.daily_count : 0,
      dailyResetAt: row.daily_reset_at ?? null,
    };
  }

  async upsertRecord(record: NotificationLimitRecord): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    await this.supabaseClient.upsert(
      NOTIFICATION_LIMITS_TABLE,
      {
        telegram_user_id: record.telegramUserId,
        role: record.role,
        last_candidate_notify_at: record.lastCandidateNotifyAt,
        last_manager_notify_at: record.lastManagerNotifyAt,
        daily_count: record.dailyCount,
        daily_reset_at: record.dailyResetAt,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,role" },
    );

    this.logger.debug("Notification limit record upserted", {
      telegramUserId: record.telegramUserId,
      role: record.role,
      dailyCount: record.dailyCount,
    });
  }
}
