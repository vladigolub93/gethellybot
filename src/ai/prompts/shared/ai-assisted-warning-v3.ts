/**
 * AI-assisted answer warning copy v3 (soft). Exact localized text per spec.
 * Only one retry per question, then continue with lower confidence.
 */

export type PrescreenV3Language = "en" | "ru" | "uk";

export const AI_ASSISTED_WARNING_V3: Record<PrescreenV3Language, string> = {
  en: "This looks like an AI-generated answer. Please don't do that. Re-answer from your real experience. If you don't want to type, send a voice message.",
  ru: "Похоже, это ответ, сгенерированный AI. Пожалуйста, не делай так. Ответь снова из своего реального опыта. Если не хочешь печатать, отправь голосовое сообщение.",
  uk: "Схоже, це відповідь, згенерована AI. Будь ласка, не роби так. Дай відповідь ще раз зі свого реального досвіду. Якщо не хочеш друкувати, надішли голосове повідомлення.",
};
