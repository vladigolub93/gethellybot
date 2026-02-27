import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";
import { PreferredLanguage, UserRole } from "../../shared/types/state.types";

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
    preferredLanguage?: PreferredLanguage;
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
    if (
      input.preferredLanguage === "en" ||
      input.preferredLanguage === "ru" ||
      input.preferredLanguage === "uk" ||
      input.preferredLanguage === "unknown"
    ) {
      payload.preferred_language = input.preferredLanguage;
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
    preferredLanguage?: PreferredLanguage;
  }> {
    if (!this.supabaseClient) {
      return {
        onboardingCompleted: false,
        firstMatchExplained: false,
        preferredLanguage: "unknown",
      };
    }

    const row = await this.supabaseClient.selectOne<{
      onboarding_completed: boolean | null;
      first_match_explained: boolean | null;
      preferred_language: string | null;
    }>(
      USERS_TABLE,
      {
        telegram_user_id: telegramUserId,
      },
      "onboarding_completed,first_match_explained,preferred_language",
    );

    return {
      onboardingCompleted: Boolean(row?.onboarding_completed),
      firstMatchExplained: Boolean(row?.first_match_explained),
      preferredLanguage:
        row?.preferred_language === "en" ||
        row?.preferred_language === "ru" ||
        row?.preferred_language === "uk" ||
        row?.preferred_language === "unknown"
          ? row.preferred_language
          : "unknown",
    };
  }

  async markFirstMatchExplained(telegramUserId: number, explained: boolean): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId,
      firstMatchExplained: explained,
    });
  }
}
