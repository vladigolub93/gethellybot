import { Logger } from "../../config/logger";
import { UserSessionState } from "../../shared/types/state.types";
import { SupabaseRestClient } from "../supabase.client";

const USER_STATES_TABLE = "user_states";

interface UserStateRow {
  telegram_user_id: number;
  chat_id: number;
  telegram_username: string | null;
  role: string | null;
  state: string;
  state_payload: Record<string, unknown> | null;
  canonical_interview_status: string | null;
  last_bot_message: string | null;
  updated_at: string;
}

export class StatesRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  isEnabled(): boolean {
    return Boolean(this.supabaseClient);
  }

  async loadByTelegramUserId(telegramUserId: number): Promise<UserSessionState | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<UserStateRow>(
      USER_STATES_TABLE,
      { telegram_user_id: telegramUserId },
      "telegram_user_id,chat_id,telegram_username,role,state,state_payload,canonical_interview_status,last_bot_message,updated_at",
    );
    if (!row) {
      return null;
    }

    const payload = row.state_payload ?? {};

    const session: UserSessionState = {
      userId: row.telegram_user_id,
      chatId: row.chat_id,
      username: row.telegram_username ?? undefined,
      role: normalizeRole(row.role),
      state: row.state as UserSessionState["state"],
      ...payload,
      canonicalInterviewStatus:
        normalizeCanonicalInterviewStatus(
          (payload.canonicalInterviewStatus as string | undefined) ?? undefined,
        ) ??
        normalizeCanonicalInterviewStatus(row.canonical_interview_status ?? undefined) ??
        undefined,
      lastBotMessage: row.last_bot_message ?? undefined,
    };

    return session;
  }

  async saveSession(session: UserSessionState): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const payload: Record<string, unknown> = { ...session };
    delete payload.userId;
    delete payload.chatId;
    delete payload.username;
    delete payload.role;
    delete payload.state;
    delete payload.lastBotMessage;

    const basePayload = {
      telegram_user_id: session.userId,
      chat_id: session.chatId,
      telegram_username: session.username ?? null,
      role: session.role ?? null,
      state: session.state,
      state_payload: payload,
      last_bot_message: session.lastBotMessage ?? null,
      updated_at: new Date().toISOString(),
    };

    const canonicalInterviewStatus = normalizeCanonicalInterviewStatus(
      session.canonicalInterviewStatus,
    );
    if (canonicalInterviewStatus) {
      try {
        await this.supabaseClient.upsert(
          USER_STATES_TABLE,
          {
            ...basePayload,
            canonical_interview_status: canonicalInterviewStatus,
          },
          { onConflict: "telegram_user_id" },
        );
        this.logger.debug("interview_lifecycle.canonical_persisted", {
          telegramUserId: session.userId,
          canonicalInterviewStatus,
          source: "user_states",
        });
      } catch (error) {
        this.logger.warn("interview_lifecycle.canonical_persist_failed", {
          telegramUserId: session.userId,
          canonicalInterviewStatus,
          source: "user_states",
          error: error instanceof Error ? error.message : "Unknown error",
        });
        await this.supabaseClient.upsert(
          USER_STATES_TABLE,
          basePayload,
          { onConflict: "telegram_user_id" },
        );
      }
    } else {
      await this.supabaseClient.upsert(
        USER_STATES_TABLE,
        basePayload,
        { onConflict: "telegram_user_id" },
      );
    }

    this.logger.debug("User state persisted in Supabase", { telegramUserId: session.userId });
  }

  async listAllSessions(): Promise<Array<{ session: UserSessionState; updatedAt: string }>> {
    if (!this.supabaseClient) {
      return [];
    }

    const rows = await this.supabaseClient.selectMany<UserStateRow>(
      USER_STATES_TABLE,
      {},
      "telegram_user_id,chat_id,telegram_username,role,state,state_payload,canonical_interview_status,last_bot_message,updated_at",
    );

    return rows.map((row) => {
      const payload = row.state_payload ?? {};
      const session: UserSessionState = {
        userId: row.telegram_user_id,
        chatId: row.chat_id,
        username: row.telegram_username ?? undefined,
        role: normalizeRole(row.role),
        state: row.state as UserSessionState["state"],
        ...payload,
        canonicalInterviewStatus:
          normalizeCanonicalInterviewStatus(
            (payload.canonicalInterviewStatus as string | undefined) ?? undefined,
          ) ??
          normalizeCanonicalInterviewStatus(row.canonical_interview_status ?? undefined) ??
          undefined,
        lastBotMessage: row.last_bot_message ?? undefined,
      };
      return {
        session,
        updatedAt: row.updated_at,
      };
    });
  }
}

function normalizeRole(role: string | null): UserSessionState["role"] {
  if (role === "candidate" || role === "manager") {
    return role;
  }
  return undefined;
}

function normalizeCanonicalInterviewStatus(
  status: string | null | undefined,
): string | null {
  if (typeof status !== "string") {
    return null;
  }
  const trimmed = status.trim();
  return trimmed ? trimmed : null;
}
