import { Logger } from "../config/logger";
import { TELEGRAM_PARSE_MODE } from "../shared/constants";
import { TelegramApiResponse, TelegramReplyMarkup } from "../shared/types/telegram.types";
import { isHardSystemSource } from "../shared/utils/message-source";
import fetch from "node-fetch";

interface SetWebhookPayload {
  url: string;
  secret_token?: string;
}

interface SendMessagePayload {
  chat_id: number;
  text: string;
  parse_mode?: string;
  reply_markup?: TelegramReplyMarkup;
}

interface MessageComposeInput {
  source: string;
  chatId: number;
  text: string;
}

interface AnswerCallbackQueryPayload {
  callback_query_id: string;
  text?: string;
}

interface SetMessageReactionPayload {
  chat_id: number;
  message_id: number;
  reaction: Array<{ type: "emoji"; emoji: string }>;
  is_big?: boolean;
}

interface TelegramFileInfo {
  file_id: string;
  file_unique_id: string;
  file_path?: string;
}

export class TelegramClient {
  private readonly apiBase: string;

  constructor(
    private readonly token: string,
    private readonly logger: Logger,
    private readonly buttonsEnabled = true,
    private readonly composeMessage?: (input: MessageComposeInput) => Promise<string>,
  ) {
    this.apiBase = `https://api.telegram.org/bot${this.token}`;
    if (!this.buttonsEnabled) {
      this.logger.info("TELEGRAM_BUTTONS_ENABLED is false, but reply_markup is still sent for onboarding safety.");
    }
  }

  async setWebhook(url: string, secretToken?: string): Promise<void> {
    const payload: SetWebhookPayload = { url };
    if (secretToken) {
      payload.secret_token = secretToken;
    }

    await this.request<boolean>("setWebhook", payload);
  }

  async sendUserMessage(input: {
    source: string;
    chatId: number;
    text: string;
    replyMarkup?: TelegramReplyMarkup;
  }): Promise<void> {
    this.logger.debug("telegram.user_message", {
      source: input.source,
      chatId: input.chatId,
      textPreview: input.text.slice(0, 140),
    });
    await this.sendMessage(input.chatId, input.text, {
      replyMarkup: input.replyMarkup,
      source: input.source,
    });
  }

  // Internal low-level sender. Prefer sendUserMessage in business logic.
  async sendMessage(
    chatId: number,
    text: string,
    options?: { replyMarkup?: TelegramReplyMarkup; source?: string; skipCompose?: boolean },
  ): Promise<void> {
    const source = options?.source ?? "telegram_send_message";
    const hasReplyMarkup = Boolean(options?.replyMarkup);
    const finalText = await this.composeOutgoingText({
      source,
      chatId,
      text,
      skipCompose:
        options?.skipCompose ||
        hasReplyMarkup ||
        isHardSystemSource(source),
    });

    const payload: SendMessagePayload = {
      chat_id: chatId,
      text: clampTelegramText(finalText),
    };
    if (TELEGRAM_PARSE_MODE && isHardSystemSource(source)) {
      payload.parse_mode = TELEGRAM_PARSE_MODE;
    }

    if (options?.replyMarkup && shouldSendReplyMarkup(options.replyMarkup, this.buttonsEnabled)) {
      payload.reply_markup = options.replyMarkup;
    }

    try {
      await this.request("sendMessage", payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      if (message.includes("sendMessage") && message.includes("HTTP 400") && payload.parse_mode) {
        this.logger.warn("sendMessage failed with parse_mode, retrying without parse_mode", {
          chatId,
          source,
        });
        const retryPayload: SendMessagePayload = { ...payload };
        delete retryPayload.parse_mode;
        await this.request("sendMessage", retryPayload);
        return;
      }
      throw error;
    }
  }

  async answerCallbackQuery(callbackQueryId: string, text?: string): Promise<void> {
    const payload: AnswerCallbackQueryPayload = { callback_query_id: callbackQueryId };
    if (text) {
      payload.text = text;
    }
    await this.request("answerCallbackQuery", payload);
  }

  async setMessageReaction(
    chatId: number,
    messageId: number,
    reaction: string,
  ): Promise<void> {
    const payload: SetMessageReactionPayload = {
      chat_id: chatId,
      message_id: messageId,
      reaction: [{ type: "emoji", emoji: reaction }],
      is_big: false,
    };

    try {
      await this.request("setMessageReaction", payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      this.logger.debug("setMessageReaction unavailable or failed, skipping reaction", {
        chatId,
        messageId,
        error: message,
      });
    }
  }

  async downloadFileById(fileId: string): Promise<Buffer> {
    const fileInfo = await this.request<TelegramFileInfo>("getFile", { file_id: fileId });
    if (!fileInfo.file_path) {
      throw new Error("Telegram file path is missing");
    }

    const response = await fetch(
      `https://api.telegram.org/file/bot${this.token}/${fileInfo.file_path}`,
      {
        method: "GET",
      },
    );

    if (!response.ok) {
      throw new Error(`Telegram file download failed: HTTP ${response.status}`);
    }

    return response.buffer();
  }

  private async composeOutgoingText(input: {
    source: string;
    chatId: number;
    text: string;
    skipCompose?: boolean;
  }): Promise<string> {
    if (!this.composeMessage || input.skipCompose) {
      return input.text;
    }
    try {
      return await this.composeMessage({
        source: input.source,
        chatId: input.chatId,
        text: input.text,
      });
    } catch (error) {
      this.logger.warn("outbound.message.compose.exception", {
        source: input.source,
        chatId: input.chatId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return input.text;
    }
  }

  private async request<TResponse>(method: string, payload: unknown): Promise<TResponse> {
    const response = await fetch(`${this.apiBase}/${method}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Telegram request failed (${method}): HTTP ${response.status}`);
    }

    const body = (await response.json()) as TelegramApiResponse<TResponse>;

    if (!body.ok) {
      this.logger.error("Telegram API returned failure", {
        method,
        code: body.error_code,
        description: body.description,
      });
      throw new Error(`Telegram API error (${method}): ${body.description}`);
    }

    return body.result;
  }
}

function clampTelegramText(text: string): string {
  const MAX_TEXT_LENGTH = 3900;
  if (text.length <= MAX_TEXT_LENGTH) {
    return text;
  }
  return `${text.slice(0, MAX_TEXT_LENGTH - 3)}...`;
}

function shouldSendReplyMarkup(
  replyMarkup: TelegramReplyMarkup,
  buttonsEnabled: boolean,
): boolean {
  void replyMarkup;
  void buttonsEnabled;
  return true;
}
