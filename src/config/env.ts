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
  return value;
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
  const qdrantBackfillOnStartRaw = process.env.QDRANT_BACKFILL_ON_START ?? "true";
  const debugModeRaw = process.env.DEBUG_MODE ?? "false";
  const telegramLogsEnabledRaw =
    process.env.TELEGRAM_LOGS_ENABLED ?? ((process.env.NODE_ENV ?? "development") === "production" ? "true" : "false");
  const telegramLogsLevelRaw = (process.env.TELEGRAM_LOG_LEVEL ?? "warn").trim().toLowerCase();
  const telegramLogsRatePerMinRaw = process.env.TELEGRAM_LOG_RATE_PER_MIN ?? "20";
  const telegramLogsBatchMsRaw = process.env.TELEGRAM_LOG_BATCH_MS ?? "2500";
  const telegramReactionsEnabled = parseBoolean(reactionsEnabledRaw);
  const telegramReactionsProbability = Number(reactionsProbabilityRaw);
  const telegramButtonsEnabled = parseBoolean(buttonsEnabledRaw);
  const qdrantBackfillOnStart = parseBoolean(qdrantBackfillOnStartRaw);
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
  if (!Number.isFinite(telegramLogsRatePerMin) || telegramLogsRatePerMin < 1) {
    throw new Error(`Invalid TELEGRAM_LOG_RATE_PER_MIN value: ${telegramLogsRatePerMinRaw}`);
  }
  if (!Number.isFinite(telegramLogsBatchMs) || telegramLogsBatchMs < 250) {
    throw new Error(`Invalid TELEGRAM_LOG_BATCH_MS value: ${telegramLogsBatchMsRaw}`);
  }

  return {
    nodeEnv: process.env.NODE_ENV ?? "development",
    debugMode,
    telegramLogsEnabled,
    telegramLogsChatId: process.env.TELEGRAM_LOG_CHAT_ID ?? "-1003451429547",
    telegramLogsLevel,
    telegramLogsRatePerMin: telegramLogsRatePerMin,
    telegramLogsBatchMs: telegramLogsBatchMs,
    adminSecret: process.env.ADMIN_SECRET,
    port,
    telegramBotToken: getRequiredString("TELEGRAM_BOT_TOKEN"),
    telegramWebhookPath,
    telegramWebhookUrl: process.env.TELEGRAM_WEBHOOK_URL,
    telegramSecretToken: process.env.TELEGRAM_SECRET_TOKEN,
    openaiApiKey: getRequiredString("OPENAI_API_KEY"),
    openaiChatModel: process.env.OPENAI_CHAT_MODEL ?? "gpt-5.2",
    openaiEmbeddingModel: process.env.OPENAI_EMBEDDINGS_MODEL ?? process.env.OPENAI_EMBEDDING_MODEL ?? "text-embedding-3-large",
    openaiTranscriptionModel: process.env.OPENAI_TRANSCRIPTION_MODEL ?? "whisper-1",
    voiceMaxDurationSec,
    telegramReactionsEnabled,
    telegramReactionsProbability,
    telegramButtonsEnabled,
    supabaseUrl: process.env.SUPABASE_URL,
    supabasePublishableKey: process.env.SUPABASE_PUBLISHABLE_KEY,
    supabaseServiceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
    supabaseApiKey: process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.SUPABASE_PUBLISHABLE_KEY,
    qdrantUrl: process.env.QDRANT_URL,
    qdrantApiKey: process.env.QDRANT_API_KEY,
    qdrantCandidateCollection: process.env.QDRANT_CANDIDATE_COLLECTION ?? "helly_candidates_v1",
    qdrantBackfillOnStart,
  };
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
