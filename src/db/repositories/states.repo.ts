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
  last_bot_message: string | null;
  updated_at: string;
}

export class StatesRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async loadByTelegramUserId(telegramUserId: number): Promise<UserSessionState | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<UserStateRow>(
      USER_STATES_TABLE,
      { telegram_user_id: telegramUserId },
      "telegram_user_id,chat_id,telegram_username,role,state,state_payload,last_bot_message,updated_at",
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

    await this.supabaseClient.upsert(
      USER_STATES_TABLE,
      {
        telegram_user_id: session.userId,
        chat_id: session.chatId,
        telegram_username: session.username ?? null,
        role: session.role ?? null,
        state: session.state,
        state_payload: payload,
        last_bot_message: session.lastBotMessage ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id" },
    );

    this.logger.debug("User state persisted in Supabase", { telegramUserId: session.userId });
  }
}

function normalizeRole(role: string | null): UserSessionState["role"] {
  if (role === "candidate" || role === "manager") {
    return role;
  }
  return undefined;
}
