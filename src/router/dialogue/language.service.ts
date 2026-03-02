import { Logger } from "../../config/logger";
import { UsersRepository } from "../../db/repositories/users.repo";
import { detectLanguageQuick, toPreferredLanguage } from "../../i18n/normalization.service";
import type { NormalizedDetectedLanguage } from "../../i18n/normalization.service";
import { PreferredLanguage } from "../../shared/types/state.types";

export type DialogueLanguage = "en" | "ru" | "uk";

const FALLBACK_LANGUAGE: DialogueLanguage = "en";

/** Resolves user's preferred language for replies. Stores and returns RU/UK/EN. */
export class LanguageService {
  constructor(
    private readonly usersRepository: UsersRepository,
    private readonly logger: Logger,
  ) {}

  /**
   * Detect language from message text (fast heuristic).
   * Use this when LLM classifier is not available or as fallback.
   */
  detectFromText(text: string): DialogueLanguage {
    const detected = detectLanguageQuick(text.trim());
    return toDialogueLanguage(toPreferredLanguage(detected));
  }

  /**
   * Get stored user language preference from DB.
   */
  async getUserLanguage(telegramUserId: number): Promise<DialogueLanguage> {
    const flags = await this.usersRepository.getUserFlags(telegramUserId);
    const pref = flags.preferredLanguage;
    if (pref === "en" || pref === "ru" || pref === "uk") {
      return pref;
    }
    return FALLBACK_LANGUAGE;
  }

  /**
   * Update and persist user language preference (e.g. from classifier or detection).
   */
  async setUserLanguage(
    telegramUserId: number,
    language: DialogueLanguage,
  ): Promise<void> {
    const pref: PreferredLanguage =
      language === "en" || language === "ru" || language === "uk"
        ? language
        : "unknown";
    await this.usersRepository.upsertTelegramUser({
      telegramUserId,
      preferredLanguage: pref === "unknown" ? undefined : pref,
    });
    this.logger.debug("dialogue.language.updated", {
      telegramUserId,
      language,
    });
  }

  /**
   * Resolve language for this turn: prefer classifier output, then stored preference, then detect from message.
   */
  resolveLanguage(
    classifierLanguage: DialogueLanguage | null,
    storedPreference: DialogueLanguage,
    messageText: string,
  ): DialogueLanguage {
    if (classifierLanguage && isDialogueLanguage(classifierLanguage)) {
      return classifierLanguage;
    }
    if (storedPreference && storedPreference !== FALLBACK_LANGUAGE) {
      return storedPreference;
    }
    return this.detectFromText(messageText);
  }
}

function toDialogueLanguage(
  pref: "en" | "ru" | "uk" | "unknown",
): DialogueLanguage {
  if (pref === "en" || pref === "ru" || pref === "uk") {
    return pref;
  }
  return FALLBACK_LANGUAGE;
}

export function isDialogueLanguage(
  value: string,
): value is DialogueLanguage {
  return value === "en" || value === "ru" || value === "uk";
}

export function toNormalizedDetectedLanguage(
  lang: DialogueLanguage,
): NormalizedDetectedLanguage {
  return lang;
}
