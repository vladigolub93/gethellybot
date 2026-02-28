import { NormalizedUpdate, TelegramUpdate } from "../shared/types/telegram.types";

export function normalizeUpdate(update: TelegramUpdate): NormalizedUpdate | null {
  if (update.message?.text && update.message.from) {
    return {
      kind: "text",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
      text: update.message.text,
    };
  }

  if (update.message?.document && update.message.from) {
    return {
      kind: "document",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
      fileId: update.message.document.file_id,
      mimeType: update.message.document.mime_type,
      fileName: update.message.document.file_name,
    };
  }

  if (update.message?.voice && update.message.from) {
    return {
      kind: "voice",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
      fileId: update.message.voice.file_id,
      durationSec: update.message.voice.duration,
    };
  }

  if (update.message?.contact && update.message.from) {
    return {
      kind: "contact",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
      phoneNumber: update.message.contact.phone_number,
      firstName: update.message.contact.first_name,
      lastName: update.message.contact.last_name,
      contactUserId: update.message.contact.user_id,
    };
  }

  if (update.message?.location && update.message.from) {
    return {
      kind: "location",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
      latitude: update.message.location.latitude,
      longitude: update.message.location.longitude,
    };
  }

  if (update.callback_query?.data && update.callback_query.message) {
    return {
      kind: "callback",
      updateId: update.update_id,
      callbackQueryId: update.callback_query.id,
      chatId: update.callback_query.message.chat.id,
      userId: update.callback_query.from.id,
      username: update.callback_query.from.username,
      data: update.callback_query.data,
    };
  }

  if (update.message?.from) {
    return {
      kind: "unsupported_message",
      updateId: update.update_id,
      messageId: update.message.message_id,
      chatId: update.message.chat.id,
      userId: update.message.from.id,
      username: update.message.from.username,
    };
  }

  return null;
}
