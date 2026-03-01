import dotenv from "dotenv";

dotenv.config();

export interface EnvConfig {
  nodeEnv: string;
  debugMode: boolean;
  telegramLogsEnabled: boolean;
  telegramLogsChatId?: string;
  telegramLogsLevel: "debug" | "info" | "warn" | "error";
  telegramLogsRatePerMin: number;
  telegramLogsBatchMs: number;
  adminSecret?: string;
  adminWebappPin: string;
  adminUserIds: number[];
  adminWebappSessionTtlSec: number;
  adminWebappRequireTelegram: boolean;
  port: number;
  telegramBotToken: string;
  telegramWebhookPath: string;
  telegramWebhookUrl?: string;
  telegramSecretToken?: string;
  openaiApiKey: string;
  openaiChatModel: string;
  openaiEmbeddingModel: string;
  openaiTranscriptionModel: string;
  voiceMaxDurationSec: number;
  telegramReactionsEnabled: boolean;
  telegramReactionsProbability: number;
  telegramButtonsEnabled: boolean;
  interviewReminderEnabled: boolean;
  interviewReminderCheckIntervalMinutes: number;
  supabaseUrl?: string;
  supabasePublishableKey?: string;
  supabaseServiceRoleKey?: string;
  supabaseApiKey?: string;
  qdrantUrl?: string;
  qdrantApiKey?: string;
  qdrantCandidateCollection: string;
  qdrantBackfillOnStart: boolean;
}

function getRequiredString(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return trimmed;
}

function getOptionalTrimmed(name: string): string | undefined {
  const value = process.env[name];
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function loadEnv(): EnvConfig {
  const telegramWebhookPath = process.env.TELEGRAM_WEBHOOK_PATH ?? "/telegram/webhook";
  const portRaw = process.env.PORT ?? "3000";
  const port = Number(portRaw);
  const voiceLimitRaw = process.env.VOICE_MAX_DURATION_SEC ?? "180";
  const voiceMaxDurationSec = Number(voiceLimitRaw);
  const reactionsEnabledRaw = process.env.TELEGRAM_REACTIONS_ENABLED ?? "true";
  const reactionsProbabilityRaw = process.env.TELEGRAM_REACTIONS_PROBABILITY ?? "0.12";
  const buttonsEnabledRaw = process.env.TELEGRAM_BUTTONS_ENABLED ?? "true";
  const interviewReminderEnabledRaw = process.env.INTERVIEW_REMINDER_ENABLED ?? "true";
  const interviewReminderCheckIntervalRaw = process.env.INTERVIEW_REMINDER_CHECK_INTERVAL_MINUTES ?? "60";
  const qdrantBackfillOnStartRaw = process.env.QDRANT_BACKFILL_ON_START ?? "true";
  const adminWebappSessionTtlRaw = process.env.ADMIN_WEBAPP_SESSION_TTL_SEC ?? "3600";
  const adminWebappRequireTelegramRaw = process.env.ADMIN_WEBAPP_REQUIRE_TELEGRAM ?? "false";
  const debugModeRaw = process.env.DEBUG_MODE ?? "false";
  const telegramLogsEnabledRaw =
    process.env.TELEGRAM_LOGS_ENABLED ?? ((process.env.NODE_ENV ?? "development") === "production" ? "true" : "false");
  const telegramLogsLevelRaw = (process.env.TELEGRAM_LOG_LEVEL ?? "warn").trim().toLowerCase();
  const telegramLogsRatePerMinRaw = process.env.TELEGRAM_LOG_RATE_PER_MIN ?? "20";
  const telegramLogsBatchMsRaw = process.env.TELEGRAM_LOG_BATCH_MS ?? "2500";
  const telegramReactionsEnabled = parseBoolean(reactionsEnabledRaw);
  const telegramReactionsProbability = Number(reactionsProbabilityRaw);
  const telegramButtonsEnabled = parseBoolean(buttonsEnabledRaw);
  const interviewReminderEnabled = parseBoolean(interviewReminderEnabledRaw);
  const interviewReminderCheckIntervalMinutes = Number(interviewReminderCheckIntervalRaw);
  const qdrantBackfillOnStart = parseBoolean(qdrantBackfillOnStartRaw);
  const adminWebappSessionTtlSec = Number(adminWebappSessionTtlRaw);
  const adminWebappRequireTelegram = parseBoolean(adminWebappRequireTelegramRaw);
  const debugMode = parseBoolean(debugModeRaw);
  const telegramLogsEnabled = parseBoolean(telegramLogsEnabledRaw);
  const telegramLogsRatePerMin = Number(telegramLogsRatePerMinRaw);
  const telegramLogsBatchMs = Number(telegramLogsBatchMsRaw);
  const telegramLogsLevel = parseLogLevel(telegramLogsLevelRaw);

  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`Invalid PORT value: ${portRaw}`);
  }
  if (!Number.isInteger(voiceMaxDurationSec) || voiceMaxDurationSec <= 0) {
    throw new Error(`Invalid VOICE_MAX_DURATION_SEC value: ${voiceLimitRaw}`);
  }
  if (!Number.isFinite(telegramReactionsProbability) || telegramReactionsProbability < 0 || telegramReactionsProbability > 1) {
    throw new Error(
      `Invalid TELEGRAM_REACTIONS_PROBABILITY value: ${reactionsProbabilityRaw}. Expected number between 0 and 1.`,
    );
  }
  if (!Number.isFinite(interviewReminderCheckIntervalMinutes) || interviewReminderCheckIntervalMinutes < 10) {
    throw new Error(
      `Invalid INTERVIEW_REMINDER_CHECK_INTERVAL_MINUTES value: ${interviewReminderCheckIntervalRaw}`,
    );
  }
  if (!Number.isFinite(telegramLogsRatePerMin) || telegramLogsRatePerMin < 1) {
    throw new Error(`Invalid TELEGRAM_LOG_RATE_PER_MIN value: ${telegramLogsRatePerMinRaw}`);
  }
  if (!Number.isFinite(telegramLogsBatchMs) || telegramLogsBatchMs < 250) {
    throw new Error(`Invalid TELEGRAM_LOG_BATCH_MS value: ${telegramLogsBatchMsRaw}`);
  }
  if (!Number.isInteger(adminWebappSessionTtlSec) || adminWebappSessionTtlSec < 300) {
    throw new Error(`Invalid ADMIN_WEBAPP_SESSION_TTL_SEC value: ${adminWebappSessionTtlRaw}`);
  }

  return {
    nodeEnv: process.env.NODE_ENV ?? "development",
    debugMode,
    telegramLogsEnabled,
    telegramLogsChatId: process.env.TELEGRAM_LOG_CHAT_ID ?? "-1003451429547",
    telegramLogsLevel,
    telegramLogsRatePerMin: telegramLogsRatePerMin,
    telegramLogsBatchMs: telegramLogsBatchMs,
    adminSecret: getOptionalTrimmed("ADMIN_SECRET"),
    adminWebappPin: process.env.ADMIN_WEBAPP_PIN?.trim() || "21041993",
    adminUserIds: parseAdminUserIds(process.env.ADMIN_USER_IDS),
    adminWebappSessionTtlSec,
    adminWebappRequireTelegram,
    port,
    telegramBotToken: getRequiredString("TELEGRAM_BOT_TOKEN"),
    telegramWebhookPath,
    telegramWebhookUrl: getOptionalTrimmed("TELEGRAM_WEBHOOK_URL"),
    telegramSecretToken: getOptionalTrimmed("TELEGRAM_SECRET_TOKEN"),
    openaiApiKey: getRequiredString("OPENAI_API_KEY"),
    openaiChatModel: process.env.OPENAI_CHAT_MODEL ?? "gpt-5.2",
    openaiEmbeddingModel: process.env.OPENAI_EMBEDDINGS_MODEL ?? process.env.OPENAI_EMBEDDING_MODEL ?? "text-embedding-3-large",
    openaiTranscriptionModel: process.env.OPENAI_TRANSCRIPTION_MODEL ?? "whisper-1",
    voiceMaxDurationSec,
    telegramReactionsEnabled,
    telegramReactionsProbability,
    telegramButtonsEnabled,
    interviewReminderEnabled,
    interviewReminderCheckIntervalMinutes,
    supabaseUrl: getOptionalTrimmed("SUPABASE_URL"),
    supabasePublishableKey: getOptionalTrimmed("SUPABASE_PUBLISHABLE_KEY"),
    supabaseServiceRoleKey: getOptionalTrimmed("SUPABASE_SERVICE_ROLE_KEY"),
    supabaseApiKey: getOptionalTrimmed("SUPABASE_SERVICE_ROLE_KEY") ?? getOptionalTrimmed("SUPABASE_PUBLISHABLE_KEY"),
    qdrantUrl: getOptionalTrimmed("QDRANT_URL"),
    qdrantApiKey: getOptionalTrimmed("QDRANT_API_KEY"),
    qdrantCandidateCollection: getOptionalTrimmed("QDRANT_CANDIDATE_COLLECTION") ?? "helly_candidates_v1",
    qdrantBackfillOnStart,
  };
}

function parseAdminUserIds(rawValue: string | undefined): number[] {
  const values = (rawValue || "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0);
  values.push(768517770);
  return Array.from(new Set(values));
}

function parseBoolean(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (normalized === "true" || normalized === "1" || normalized === "yes") {
    return true;
  }
  if (normalized === "false" || normalized === "0" || normalized === "no") {
    return false;
  }
  throw new Error(`Invalid boolean value: ${value}`);
}

function parseLogLevel(value: string): "debug" | "info" | "warn" | "error" {
  if (value === "debug" || value === "info" || value === "warn" || value === "error") {
    return value;
  }
  throw new Error(`Invalid TELEGRAM_LOG_LEVEL value: ${value}`);
}
