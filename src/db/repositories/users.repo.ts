import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";
import { UserRole } from "../../shared/types/state.types";

const USERS_TABLE = "users";

export class UsersRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async upsertTelegramUser(input: {
    telegramUserId: number;
    telegramUsername?: string;
    role?: UserRole;
    onboardingCompleted?: boolean;
    firstMatchExplained?: boolean;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const payload: Record<string, unknown> = {
      telegram_user_id: input.telegramUserId,
      updated_at: new Date().toISOString(),
    };
    if (typeof input.telegramUsername === "string") {
      payload.telegram_username = input.telegramUsername;
    }
    if (input.role === "candidate" || input.role === "manager") {
      payload.role = input.role;
    }
    if (typeof input.onboardingCompleted === "boolean") {
      payload.onboarding_completed = input.onboardingCompleted;
    }
    if (typeof input.firstMatchExplained === "boolean") {
      payload.first_match_explained = input.firstMatchExplained;
    }

    await this.supabaseClient.upsert(USERS_TABLE, payload, { onConflict: "telegram_user_id" });

    this.logger.debug("User upserted in Supabase", {
      telegramUserId: input.telegramUserId,
    });
  }

  async getUserFlags(telegramUserId: number): Promise<{
    onboardingCompleted: boolean;
    firstMatchExplained: boolean;
  }> {
    if (!this.supabaseClient) {
      return {
        onboardingCompleted: false,
        firstMatchExplained: false,
      };
    }

    const row = await this.supabaseClient.selectOne<{
      onboarding_completed: boolean | null;
      first_match_explained: boolean | null;
    }>(
      USERS_TABLE,
      {
        telegram_user_id: telegramUserId,
      },
      "onboarding_completed,first_match_explained",
    );

    return {
      onboardingCompleted: Boolean(row?.onboarding_completed),
      firstMatchExplained: Boolean(row?.first_match_explained),
    };
  }

  async markFirstMatchExplained(telegramUserId: number, explained: boolean): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId,
      firstMatchExplained: explained,
    });
  }
}
