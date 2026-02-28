import { Logger } from "../config/logger";
import { TELEGRAM_PARSE_MODE } from "../shared/constants";
import { TelegramApiResponse, TelegramReplyMarkup } from "../shared/types/telegram.types";
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
  ) {
    this.apiBase = `https://api.telegram.org/bot${this.token}`;
    if (!this.buttonsEnabled) {
      this.logger.info("Telegram buttons are disabled, text and voice only mode is active");
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
    });
  }

  // Internal low-level sender. Prefer sendUserMessage in business logic.
  async sendMessage(
    chatId: number,
    text: string,
    options?: { replyMarkup?: TelegramReplyMarkup },
  ): Promise<void> {
    const payload: SendMessagePayload = {
      chat_id: chatId,
      text,
      parse_mode: TELEGRAM_PARSE_MODE,
    };

    if (options?.replyMarkup && shouldSendReplyMarkup(options.replyMarkup, this.buttonsEnabled)) {
      payload.reply_markup = options.replyMarkup;
    }

    await this.request("sendMessage", payload);
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

function shouldSendReplyMarkup(
  replyMarkup: TelegramReplyMarkup,
  buttonsEnabled: boolean,
): boolean {
  if (buttonsEnabled) {
    return true;
  }
  return "remove_keyboard" in replyMarkup;
}
