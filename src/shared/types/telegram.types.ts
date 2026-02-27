export interface TelegramUser {
  id: number;
  username?: string;
}

export interface TelegramChat {
  id: number;
}

export interface TelegramDocument {
  file_id: string;
  file_name?: string;
  mime_type?: string;
}

export interface TelegramVoice {
  file_id: string;
  duration: number;
}

export interface TelegramMessage {
  message_id: number;
  chat: TelegramChat;
  from?: TelegramUser;
  text?: string;
  document?: TelegramDocument;
  voice?: TelegramVoice;
}

export interface TelegramCallbackQuery {
  id: string;
  from: TelegramUser;
  data?: string;
  message?: TelegramMessage;
}

export interface TelegramUpdate {
  update_id: number;
  message?: TelegramMessage;
  callback_query?: TelegramCallbackQuery;
}

export interface TelegramInlineKeyboardButton {
  text: string;
  callback_data: string;
}

export interface TelegramReplyMarkup {
  inline_keyboard: TelegramInlineKeyboardButton[][];
}

interface TelegramApiSuccess<T> {
  ok: true;
  result: T;
}

interface TelegramApiFailure {
  ok: false;
  error_code: number;
  description: string;
}

export type TelegramApiResponse<T> = TelegramApiSuccess<T> | TelegramApiFailure;

export type NormalizedUpdate =
  | {
      kind: "text";
      updateId: number;
      messageId?: number;
      chatId: number;
      userId: number;
      username?: string;
      text: string;
    }
  | {
      kind: "document";
      updateId: number;
      messageId?: number;
      chatId: number;
      userId: number;
      username?: string;
      fileId: string;
      mimeType?: string;
      fileName?: string;
    }
  | {
      kind: "voice";
      updateId: number;
      messageId?: number;
      chatId: number;
      userId: number;
      username?: string;
      fileId: string;
      durationSec: number;
    }
  | {
      kind: "callback";
      updateId: number;
      callbackQueryId: string;
      chatId: number;
      userId: number;
      username?: string;
      data: string;
    }
  | {
      kind: "unsupported_message";
      updateId: number;
      messageId?: number;
      chatId: number;
      userId: number;
      username?: string;
    };
