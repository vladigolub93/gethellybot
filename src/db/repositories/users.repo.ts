import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";
import {
  CandidateSalaryCurrency,
  CandidateSalaryPeriod,
  CandidateWorkMode,
  PreferredLanguage,
  UserRole,
} from "../../shared/types/state.types";

const USERS_TABLE = "users";

export class UsersRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async upsertTelegramUser(input: {
    telegramUserId: number;
    telegramUsername?: string | null;
    role?: UserRole;
    preferredLanguage?: PreferredLanguage;
    onboardingCompleted?: boolean;
    firstMatchExplained?: boolean;
    phoneNumber?: string | null;
    firstName?: string | null;
    lastName?: string | null;
    contactShared?: boolean;
    contactSharedAt?: string | null;
    autoMatchingEnabled?: boolean;
    autoNotifyEnabled?: boolean;
    matchingPaused?: boolean;
    matchingPausedAt?: string | null;
    candidateCountry?: string | null;
    candidateCity?: string | null;
    candidateWorkMode?: CandidateWorkMode | null;
    candidateSalaryAmount?: number | null;
    candidateSalaryCurrency?: CandidateSalaryCurrency | null;
    candidateSalaryPeriod?: CandidateSalaryPeriod | null;
    candidateProfileComplete?: boolean;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const payload: Record<string, unknown> = {
      telegram_user_id: input.telegramUserId,
      updated_at: new Date().toISOString(),
    };
    if (typeof input.telegramUsername === "string") {
      payload.telegram_username = input.telegramUsername;
    } else if (input.telegramUsername === null) {
      payload.telegram_username = null;
    }
    if (input.role === "candidate" || input.role === "manager") {
      payload.role = input.role;
    }
    if (
      input.preferredLanguage === "en" ||
      input.preferredLanguage === "ru" ||
      input.preferredLanguage === "uk" ||
      input.preferredLanguage === "unknown"
    ) {
      payload.preferred_language = input.preferredLanguage;
    }
    if (typeof input.onboardingCompleted === "boolean") {
      payload.onboarding_completed = input.onboardingCompleted;
    }
    if (typeof input.firstMatchExplained === "boolean") {
      payload.first_match_explained = input.firstMatchExplained;
    }
    if (typeof input.phoneNumber === "string") {
      payload.phone_number = input.phoneNumber;
    } else if (input.phoneNumber === null) {
      payload.phone_number = null;
    }
    if (typeof input.firstName === "string") {
      payload.first_name = input.firstName;
    } else if (input.firstName === null) {
      payload.first_name = null;
    }
    if (typeof input.lastName === "string") {
      payload.last_name = input.lastName;
    } else if (input.lastName === null) {
      payload.last_name = null;
    }
    if (typeof input.contactShared === "boolean") {
      payload.contact_shared = input.contactShared;
    }
    if (typeof input.contactSharedAt === "string") {
      payload.contact_shared_at = input.contactSharedAt;
    } else if (input.contactSharedAt === null) {
      payload.contact_shared_at = null;
    }
    if (typeof input.autoMatchingEnabled === "boolean") {
      payload.auto_matching_enabled = input.autoMatchingEnabled;
    }
    if (typeof input.autoNotifyEnabled === "boolean") {
      payload.auto_notify_enabled = input.autoNotifyEnabled;
    }
    if (typeof input.matchingPaused === "boolean") {
      payload.matching_paused = input.matchingPaused;
    }
    if (typeof input.matchingPausedAt === "string") {
      payload.matching_paused_at = input.matchingPausedAt;
    } else if (input.matchingPausedAt === null) {
      payload.matching_paused_at = null;
    }
    if (typeof input.candidateCountry === "string") {
      payload.candidate_country = input.candidateCountry;
    } else if (input.candidateCountry === null) {
      payload.candidate_country = "";
    }
    if (typeof input.candidateCity === "string") {
      payload.candidate_city = input.candidateCity;
    } else if (input.candidateCity === null) {
      payload.candidate_city = "";
    }
    if (
      input.candidateWorkMode === "remote" ||
      input.candidateWorkMode === "hybrid" ||
      input.candidateWorkMode === "onsite" ||
      input.candidateWorkMode === "flexible"
    ) {
      payload.candidate_work_mode = input.candidateWorkMode;
    } else if (input.candidateWorkMode === null) {
      payload.candidate_work_mode = "";
    }
    if (typeof input.candidateSalaryAmount === "number" && Number.isFinite(input.candidateSalaryAmount)) {
      payload.candidate_salary_amount = input.candidateSalaryAmount;
    } else if (input.candidateSalaryAmount === null) {
      payload.candidate_salary_amount = null;
    }
    if (
      input.candidateSalaryCurrency === "USD" ||
      input.candidateSalaryCurrency === "EUR" ||
      input.candidateSalaryCurrency === "ILS" ||
      input.candidateSalaryCurrency === "GBP" ||
      input.candidateSalaryCurrency === "other"
    ) {
      payload.candidate_salary_currency = input.candidateSalaryCurrency;
    } else if (input.candidateSalaryCurrency === null) {
      payload.candidate_salary_currency = null;
    }
    if (
      input.candidateSalaryPeriod === "month" ||
      input.candidateSalaryPeriod === "year"
    ) {
      payload.candidate_salary_period = input.candidateSalaryPeriod;
    } else if (input.candidateSalaryPeriod === null) {
      payload.candidate_salary_period = null;
    }
    if (typeof input.candidateProfileComplete === "boolean") {
      payload.candidate_profile_complete = input.candidateProfileComplete;
    }

    await this.supabaseClient.upsert(USERS_TABLE, payload, { onConflict: "telegram_user_id" });

    this.logger.debug("User upserted in Supabase", {
      telegramUserId: input.telegramUserId,
    });
  }

  async getUserFlags(telegramUserId: number): Promise<{
    onboardingCompleted: boolean;
    firstMatchExplained: boolean;
    preferredLanguage?: PreferredLanguage;
    autoMatchingEnabled: boolean;
    autoNotifyEnabled: boolean;
    matchingPaused: boolean;
    matchingPausedAt?: string;
    contactShared: boolean;
  }> {
    if (!this.supabaseClient) {
      return {
        onboardingCompleted: false,
        firstMatchExplained: false,
        preferredLanguage: "unknown",
        autoMatchingEnabled: true,
        autoNotifyEnabled: true,
        matchingPaused: false,
        contactShared: false,
      };
    }

    const row = await this.supabaseClient.selectOne<{
      onboarding_completed: boolean | null;
      first_match_explained: boolean | null;
      preferred_language: string | null;
      auto_matching_enabled: boolean | null;
      auto_notify_enabled: boolean | null;
      matching_paused: boolean | null;
      matching_paused_at: string | null;
      contact_shared: boolean | null;
    }>(
      USERS_TABLE,
      {
        telegram_user_id: telegramUserId,
      },
      "onboarding_completed,first_match_explained,preferred_language,auto_matching_enabled,auto_notify_enabled,matching_paused,matching_paused_at,contact_shared",
    );

    return {
      onboardingCompleted: Boolean(row?.onboarding_completed),
      firstMatchExplained: Boolean(row?.first_match_explained),
      preferredLanguage:
        row?.preferred_language === "en" ||
        row?.preferred_language === "ru" ||
        row?.preferred_language === "uk" ||
        row?.preferred_language === "unknown"
          ? row.preferred_language
          : "unknown",
      autoMatchingEnabled: row?.auto_matching_enabled ?? true,
      autoNotifyEnabled: row?.auto_notify_enabled ?? true,
      matchingPaused: row?.matching_paused ?? false,
      matchingPausedAt: row?.matching_paused_at ?? undefined,
      contactShared: row?.contact_shared ?? false,
    };
  }

  async setMatchingPreferences(input: {
    telegramUserId: number;
    autoMatchingEnabled?: boolean;
    autoNotifyEnabled?: boolean;
    matchingPaused?: boolean;
  }): Promise<void> {
    const matchingPausedAt =
      input.matchingPaused === true
        ? new Date().toISOString()
        : input.matchingPaused === false
          ? null
          : undefined;
    await this.upsertTelegramUser({
      telegramUserId: input.telegramUserId,
      autoMatchingEnabled: input.autoMatchingEnabled,
      autoNotifyEnabled: input.autoNotifyEnabled,
      matchingPaused: input.matchingPaused,
      matchingPausedAt,
    });
  }

  async saveContact(input: {
    telegramUserId: number;
    telegramUsername?: string;
    phoneNumber: string;
    firstName: string;
    lastName?: string;
    contactSharedAt?: string;
  }): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId: input.telegramUserId,
      telegramUsername: input.telegramUsername,
      phoneNumber: input.phoneNumber,
      firstName: input.firstName,
      lastName: input.lastName,
      contactShared: true,
      contactSharedAt: input.contactSharedAt ?? new Date().toISOString(),
    });
  }

  async getContact(telegramUserId: number): Promise<{
    telegramUserId: number;
    telegramUsername?: string;
    phoneNumber?: string;
    firstName?: string;
    lastName?: string;
    contactShared: boolean;
    contactSharedAt?: string;
  } | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<{
      telegram_user_id: number;
      telegram_username: string | null;
      phone_number: string | null;
      first_name: string | null;
      last_name: string | null;
      contact_shared: boolean | null;
      contact_shared_at: string | null;
    }>(
      USERS_TABLE,
      {
        telegram_user_id: telegramUserId,
      },
      "telegram_user_id,telegram_username,phone_number,first_name,last_name,contact_shared,contact_shared_at",
    );

    if (!row) {
      return null;
    }

    return {
      telegramUserId: row.telegram_user_id,
      telegramUsername: row.telegram_username ?? undefined,
      phoneNumber: row.phone_number ?? undefined,
      firstName: row.first_name ?? undefined,
      lastName: row.last_name ?? undefined,
      contactShared: Boolean(row.contact_shared),
      contactSharedAt: row.contact_shared_at ?? undefined,
    };
  }

  async setContactShared(telegramUserId: number, contactShared: boolean): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId,
      contactShared,
      contactSharedAt: contactShared ? new Date().toISOString() : null,
    });
  }

  async clearSensitivePersonalData(telegramUserId: number): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId,
      telegramUsername: null,
      phoneNumber: null,
      firstName: null,
      lastName: null,
      contactShared: false,
      contactSharedAt: null,
    });
  }

  async markFirstMatchExplained(telegramUserId: number, explained: boolean): Promise<void> {
    await this.upsertTelegramUser({
      telegramUserId,
      firstMatchExplained: explained,
    });
  }

  async getCandidateMandatoryFields(telegramUserId: number): Promise<{
    country: string;
    city: string;
    workMode: CandidateWorkMode | null;
    salaryAmount: number | null;
    salaryCurrency: CandidateSalaryCurrency | null;
    salaryPeriod: CandidateSalaryPeriod | null;
    profileComplete: boolean;
  }> {
    if (!this.supabaseClient) {
      return {
        country: "",
        city: "",
        workMode: null,
        salaryAmount: null,
        salaryCurrency: null,
        salaryPeriod: null,
        profileComplete: false,
      };
    }

    const row = await this.supabaseClient.selectOne<{
      candidate_country: string | null;
      candidate_city: string | null;
      candidate_work_mode: string | null;
      candidate_salary_amount: number | null;
      candidate_salary_currency: string | null;
      candidate_salary_period: string | null;
      candidate_profile_complete: boolean | null;
    }>(
      USERS_TABLE,
      { telegram_user_id: telegramUserId },
      "candidate_country,candidate_city,candidate_work_mode,candidate_salary_amount,candidate_salary_currency,candidate_salary_period,candidate_profile_complete",
    );

    const country = (row?.candidate_country ?? "").trim();
    const city = (row?.candidate_city ?? "").trim();
    const workMode = normalizeWorkMode(row?.candidate_work_mode ?? null);
    const salaryAmount = typeof row?.candidate_salary_amount === "number" ? row.candidate_salary_amount : null;
    const salaryCurrency = normalizeSalaryCurrency(row?.candidate_salary_currency ?? null);
    const salaryPeriod = normalizeSalaryPeriod(row?.candidate_salary_period ?? null);
    const profileComplete = Boolean(
      row?.candidate_profile_complete ??
      (
        country &&
        city &&
        workMode &&
        typeof salaryAmount === "number" &&
        salaryAmount > 0 &&
        salaryCurrency &&
        salaryPeriod
      ),
    );

    return {
      country,
      city,
      workMode,
      salaryAmount,
      salaryCurrency,
      salaryPeriod,
      profileComplete,
    };
  }

  async upsertCandidateMandatoryFields(input: {
    telegramUserId: number;
    country?: string;
    city?: string;
    workMode?: CandidateWorkMode;
    salaryAmount?: number;
    salaryCurrency?: CandidateSalaryCurrency;
    salaryPeriod?: CandidateSalaryPeriod;
  }): Promise<void> {
    const existing = await this.getCandidateMandatoryFields(input.telegramUserId);
    const country = (input.country ?? existing.country).trim();
    const city = (input.city ?? existing.city).trim();
    const workMode = input.workMode ?? existing.workMode;
    const salaryAmount =
      typeof input.salaryAmount === "number"
        ? input.salaryAmount
        : existing.salaryAmount;
    const salaryCurrency = input.salaryCurrency ?? existing.salaryCurrency;
    const salaryPeriod = input.salaryPeriod ?? existing.salaryPeriod;

    const profileComplete = Boolean(
      country &&
      city &&
      workMode &&
      typeof salaryAmount === "number" &&
      salaryAmount > 0 &&
      salaryCurrency &&
      salaryPeriod,
    );

    await this.upsertTelegramUser({
      telegramUserId: input.telegramUserId,
      candidateCountry: country,
      candidateCity: city,
      candidateWorkMode: workMode ?? null,
      candidateSalaryAmount: salaryAmount ?? null,
      candidateSalaryCurrency: salaryCurrency ?? null,
      candidateSalaryPeriod: salaryPeriod ?? null,
      candidateProfileComplete: profileComplete,
    });
  }

  async evaluateCandidateCompleteness(telegramUserId: number): Promise<boolean> {
    const fields = await this.getCandidateMandatoryFields(telegramUserId);
    return fields.profileComplete;
  }
}

function normalizeWorkMode(value: string | null): CandidateWorkMode | null {
  if (value === "remote" || value === "hybrid" || value === "onsite" || value === "flexible") {
    return value;
  }
  return null;
}

function normalizeSalaryCurrency(value: string | null): CandidateSalaryCurrency | null {
  if (value === "USD" || value === "EUR" || value === "ILS" || value === "GBP" || value === "other") {
    return value;
  }
  return null;
}

function normalizeSalaryPeriod(value: string | null): CandidateSalaryPeriod | null {
  if (value === "month" || value === "year") {
    return value;
  }
  return null;
}
