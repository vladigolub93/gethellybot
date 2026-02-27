import { createApp } from "./app";
import { loadEnv } from "./config/env";

async function bootstrap(): Promise<void> {
  const env = loadEnv();
  const { app, telegramClient, logger } = createApp(env);

  app.listen(env.port, async () => {
    logger.info("Server started", { port: env.port, path: env.telegramWebhookPath });
    logger.info(`LLM chat model: ${env.openaiChatModel}`);

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
