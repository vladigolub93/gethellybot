import { createApp } from "./app";
import { HELLY_SYSTEM_PROMPT } from "./ai/system/helly.system";
import { CHAT_MODEL } from "./ai/llm.client";
import { loadEnv } from "./config/env";

async function bootstrap(): Promise<void> {
  const env = loadEnv();
  const { app, telegramClient, logger } = createApp(env);

  app.listen(env.port, async () => {
    logger.info("Server started", { port: env.port, path: env.telegramWebhookPath });
    logger.info(`LLM chat model: ${CHAT_MODEL}`);
    logger.info("LLM system prompt loaded", { length: HELLY_SYSTEM_PROMPT.length });
    logger.info("DEBUG_MODE", { enabled: env.debugMode });
    logger.info("TELEGRAM_LOGS", {
      enabled: env.telegramLogsEnabled,
      chatConfigured: Boolean(env.telegramLogsChatId),
      level: env.telegramLogsLevel,
    });

    if (!env.telegramWebhookUrl) {
      logger.warn("TELEGRAM_WEBHOOK_URL is not set, skipping webhook registration");
      return;
    }

    const webhookUrl = `${env.telegramWebhookUrl}${env.telegramWebhookPath}`;
    try {
      await telegramClient.setWebhook(webhookUrl, env.telegramSecretToken);
      logger.info("Telegram webhook registered", { webhookUrl });
    } catch (error) {
      logger.error("Failed to register Telegram webhook", {
        webhookUrl,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  });
}

void bootstrap();
