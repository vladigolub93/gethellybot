import { Logger } from "../../config/logger";
import { JobProfile } from "../../shared/types/domain.types";
import {
  JobDescriptionAnalysisV1Result,
  ManagerInterviewPlanV1,
} from "../../shared/types/job-analysis.types";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../../shared/types/job-profile.types";
import { SupabaseRestClient } from "../supabase.client";

const JOBS_TABLE = "jobs";

export type JobStatus = "draft" | "active" | "paused" | "closed";

interface JobRow {
  manager_telegram_user_id: number;
  status: JobStatus;
  job_summary: string;
  job_profile: unknown;
  source_type?: unknown;
  source_text_original?: unknown;
  source_text_english?: unknown;
  telegram_file_id?: unknown;
  job_analysis_json?: unknown;
  manager_interview_plan_json?: unknown;
  job_profile_json?: unknown;
  technical_summary_json?: unknown;
  job_work_format?: unknown;
  job_remote_countries?: unknown;
  job_remote_worldwide?: unknown;
  job_budget_min?: unknown;
  job_budget_max?: unknown;
  job_budget_currency?: unknown;
  job_budget_period?: unknown;
  job_profile_complete?: unknown;
  last_confirmation_one_liner?: unknown;
}

export class JobsRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async upsertManagerJob(input: {
    managerTelegramUserId: number;
    status: JobStatus;
    jobSummary: string;
    jobProfile: JobProfile;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: input.status,
        job_summary: input.jobSummary.slice(0, 1200),
        job_profile: input.jobProfile,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Job persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
      status: input.status,
    });
  }

  async saveJobDescriptionAnalysis(input: {
    managerTelegramUserId: number;
    jobSummary: string;
    analysis: JobDescriptionAnalysisV1Result;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "manager_telegram_user_id,status,job_summary,job_profile,manager_interview_plan_json,job_profile_json,technical_summary_json",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing?.status ?? "draft",
        job_summary: (input.jobSummary || existing?.job_summary || "").slice(0, 1200),
        job_profile: existing?.job_profile ?? {},
        job_analysis_json: input.analysis,
        manager_interview_plan_json: existing?.manager_interview_plan_json ?? null,
        job_profile_json: existing?.job_profile_json ?? null,
        technical_summary_json: existing?.technical_summary_json ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Job description analysis persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
      isTechnicalRole: input.analysis.is_technical_role,
    });
  }

  async getJobDescriptionAnalysis(
    managerTelegramUserId: number,
  ): Promise<JobDescriptionAnalysisV1Result | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: managerTelegramUserId,
      },
      "manager_telegram_user_id,job_analysis_json",
    );
    if (!row || !isRecord(row.job_analysis_json)) {
      return null;
    }
    const analysis = row.job_analysis_json;
    if (typeof analysis.is_technical_role !== "boolean") {
      return null;
    }
    if (analysis.is_technical_role === false) {
      return {
        is_technical_role: false,
        reason: "Non technical role",
      };
    }
    return analysis as unknown as JobDescriptionAnalysisV1Result;
  }

  async saveManagerInterviewPlan(input: {
    managerTelegramUserId: number;
    plan: ManagerInterviewPlanV1;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "manager_telegram_user_id,status,job_summary,job_profile,job_analysis_json,job_profile_json,technical_summary_json",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing?.status ?? "draft",
        job_summary: existing?.job_summary ?? "",
        job_profile: existing?.job_profile ?? {},
        job_analysis_json: existing?.job_analysis_json ?? null,
        manager_interview_plan_json: input.plan,
        job_profile_json: existing?.job_profile_json ?? null,
        technical_summary_json: existing?.technical_summary_json ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Manager interview plan persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
      questions: input.plan.questions.length,
    });
  }

  async saveJobProfileV2(input: {
    managerTelegramUserId: number;
    jobProfileV2: JobProfileV2;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "manager_telegram_user_id,status,job_summary,job_profile,job_analysis_json,manager_interview_plan_json,technical_summary_json",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing?.status ?? "draft",
        job_summary: existing?.job_summary ?? "",
        job_profile: existing?.job_profile ?? {},
        job_analysis_json: existing?.job_analysis_json ?? null,
        manager_interview_plan_json: existing?.manager_interview_plan_json ?? null,
        job_profile_json: input.jobProfileV2,
        technical_summary_json: existing?.technical_summary_json ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Manager job profile v2 persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
    });
  }

  async getJobProfileV2(managerTelegramUserId: number): Promise<JobProfileV2 | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: managerTelegramUserId,
      },
      "manager_telegram_user_id,job_profile_json",
    );

    if (!row || !row.job_profile_json || !isRecord(row.job_profile_json)) {
      return null;
    }

    return row.job_profile_json as unknown as JobProfileV2;
  }

  async saveJobTechnicalSummary(input: {
    managerTelegramUserId: number;
    technicalSummary: JobTechnicalSummaryV2;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "manager_telegram_user_id,status,job_summary,job_profile,job_analysis_json,manager_interview_plan_json,job_profile_json",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing?.status ?? "draft",
        job_summary: existing?.job_summary ?? "",
        job_profile: existing?.job_profile ?? {},
        job_analysis_json: existing?.job_analysis_json ?? null,
        manager_interview_plan_json: existing?.manager_interview_plan_json ?? null,
        job_profile_json: existing?.job_profile_json ?? null,
        technical_summary_json: input.technicalSummary,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Manager job technical summary persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
    });
  }

  async getJobTechnicalSummary(managerTelegramUserId: number): Promise<JobTechnicalSummaryV2 | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: managerTelegramUserId,
      },
      "manager_telegram_user_id,technical_summary_json",
    );

    if (!row || !row.technical_summary_json || !isRecord(row.technical_summary_json)) {
      return null;
    }

    return row.technical_summary_json as unknown as JobTechnicalSummaryV2;
  }

  async getManagerJobStatus(managerTelegramUserId: number): Promise<JobStatus | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: managerTelegramUserId,
      },
      "manager_telegram_user_id,status",
    );

    return row?.status ?? null;
  }

  async listActiveManagerTelegramUserIds(limit = 200): Promise<number[]> {
    if (!this.supabaseClient) {
      return [];
    }

    const rows = await this.supabaseClient.selectMany<{
      manager_telegram_user_id: number;
    }>(
      JOBS_TABLE,
      {
        status: "active",
      },
      "manager_telegram_user_id",
    );

    const ids = rows
      .map((row) => row.manager_telegram_user_id)
      .filter((id) => Number.isInteger(id) && id > 0);
    return Array.from(new Set(ids)).slice(0, Math.max(1, limit));
  }

  async saveJobIntakeSource(input: {
    managerTelegramUserId: number;
    sourceType: "file" | "text";
    sourceTextOriginal?: string | null;
    sourceTextEnglish?: string | null;
    telegramFileId?: string | null;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "manager_telegram_user_id,status,job_summary,job_profile,job_analysis_json,manager_interview_plan_json,job_profile_json,technical_summary_json",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing?.status ?? "draft",
        job_summary: existing?.job_summary ?? "",
        job_profile: existing?.job_profile ?? {},
        source_type: input.sourceType,
        source_text_original: normalizeNullableText(input.sourceTextOriginal),
        source_text_english: normalizeNullableText(input.sourceTextEnglish),
        telegram_file_id: normalizeNullableText(input.telegramFileId),
        job_analysis_json: existing?.job_analysis_json ?? null,
        manager_interview_plan_json: existing?.manager_interview_plan_json ?? null,
        job_profile_json: existing?.job_profile_json ?? null,
        technical_summary_json: existing?.technical_summary_json ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );

    this.logger.info("Job intake source persisted to Supabase", {
      managerTelegramUserId: input.managerTelegramUserId,
      sourceType: input.sourceType,
      hasTelegramFileId: Boolean(input.telegramFileId),
      hasTextOriginal: Boolean(input.sourceTextOriginal?.trim()),
      hasTextEnglish: Boolean(input.sourceTextEnglish?.trim()),
    });
  }

  async getJobMandatoryFields(managerTelegramUserId: number): Promise<{
    workFormat: "remote" | "hybrid" | "onsite" | null;
    remoteCountries: string[];
    remoteWorldwide: boolean;
    budgetMin: number | null;
    budgetMax: number | null;
    budgetCurrency: "USD" | "EUR" | "ILS" | "GBP" | "other" | null;
    budgetPeriod: "month" | "year" | null;
    profileComplete: boolean;
  }> {
    if (!this.supabaseClient) {
      return {
        workFormat: null,
        remoteCountries: [],
        remoteWorldwide: false,
        budgetMin: null,
        budgetMax: null,
        budgetCurrency: null,
        budgetPeriod: null,
        profileComplete: false,
      };
    }

    const row = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: managerTelegramUserId,
      },
      "job_work_format,job_remote_countries,job_remote_worldwide,job_budget_min,job_budget_max,job_budget_currency,job_budget_period,job_profile_complete",
    );

    const workFormat = normalizeJobWorkFormat(row?.job_work_format);
    const remoteCountries = normalizeStringArray(row?.job_remote_countries);
    const remoteWorldwide = row?.job_remote_worldwide === true;
    const budgetMin = normalizeNullableNumber(row?.job_budget_min);
    const budgetMax = normalizeNullableNumber(row?.job_budget_max);
    const budgetCurrency = normalizeBudgetCurrency(row?.job_budget_currency);
    const budgetPeriod = normalizeBudgetPeriod(row?.job_budget_period);
    const profileComplete = Boolean(
      row?.job_profile_complete === true ||
      (
        workFormat &&
        (workFormat !== "remote" || remoteWorldwide || remoteCountries.length > 0) &&
        typeof budgetMin === "number" &&
        typeof budgetMax === "number" &&
        budgetMin > 0 &&
        budgetMax >= budgetMin &&
        budgetCurrency &&
        budgetPeriod
      ),
    );

    return {
      workFormat,
      remoteCountries,
      remoteWorldwide,
      budgetMin,
      budgetMax,
      budgetCurrency,
      budgetPeriod,
      profileComplete,
    };
  }

  async upsertJobMandatoryFields(input: {
    managerTelegramUserId: number;
    workFormat?: "remote" | "hybrid" | "onsite";
    remoteCountries?: string[];
    remoteWorldwide?: boolean;
    budgetMin?: number;
    budgetMax?: number;
    budgetCurrency?: "USD" | "EUR" | "ILS" | "GBP" | "other";
    budgetPeriod?: "month" | "year";
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.getJobMandatoryFields(input.managerTelegramUserId);
    const workFormat = input.workFormat ?? existing.workFormat;
    const remoteCountries = (input.remoteCountries ?? existing.remoteCountries).map((item) => item.trim()).filter(Boolean);
    const remoteWorldwide = typeof input.remoteWorldwide === "boolean" ? input.remoteWorldwide : existing.remoteWorldwide;
    const budgetMin = typeof input.budgetMin === "number" ? input.budgetMin : existing.budgetMin;
    const budgetMax = typeof input.budgetMax === "number" ? input.budgetMax : existing.budgetMax;
    const budgetCurrency = input.budgetCurrency ?? existing.budgetCurrency;
    const budgetPeriod = input.budgetPeriod ?? existing.budgetPeriod;
    const profileComplete = Boolean(
      workFormat &&
      (workFormat !== "remote" || remoteWorldwide || remoteCountries.length > 0) &&
      typeof budgetMin === "number" &&
      typeof budgetMax === "number" &&
      budgetMin > 0 &&
      budgetMax >= budgetMin &&
      budgetCurrency &&
      budgetPeriod
    );

    const base = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "status,job_summary,job_profile,job_analysis_json,manager_interview_plan_json,job_profile_json,technical_summary_json,source_type,source_text_original,source_text_english,telegram_file_id",
    );

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: base?.status ?? "draft",
        job_summary: base?.job_summary ?? "",
        job_profile: base?.job_profile ?? {},
        source_type: base?.source_type ?? null,
        source_text_original: base?.source_text_original ?? null,
        source_text_english: base?.source_text_english ?? null,
        telegram_file_id: base?.telegram_file_id ?? null,
        job_analysis_json: base?.job_analysis_json ?? null,
        manager_interview_plan_json: base?.manager_interview_plan_json ?? null,
        job_profile_json: base?.job_profile_json ?? null,
        technical_summary_json: base?.technical_summary_json ?? null,
        job_work_format: workFormat ?? "",
        job_remote_countries: workFormat === "remote" ? remoteCountries : [],
        job_remote_worldwide: workFormat === "remote" ? remoteWorldwide : false,
        job_budget_min: budgetMin,
        job_budget_max: budgetMax,
        job_budget_currency: budgetCurrency,
        job_budget_period: budgetPeriod,
        job_profile_complete: profileComplete,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );
  }

  async evaluateJobCompleteness(managerTelegramUserId: number): Promise<boolean> {
    const fields = await this.getJobMandatoryFields(managerTelegramUserId);
    return fields.profileComplete;
  }

  async saveLastConfirmationOneLiner(input: {
    managerTelegramUserId: number;
    oneLiner: string;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<JobRow>(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
      },
      "status,job_summary,job_profile,source_type,source_text_original,source_text_english,telegram_file_id,job_analysis_json,manager_interview_plan_json,job_profile_json,technical_summary_json,job_work_format,job_remote_countries,job_remote_worldwide,job_budget_min,job_budget_max,job_budget_currency,job_budget_period,job_profile_complete",
    );
    if (!existing) {
      return;
    }

    await this.supabaseClient.upsert(
      JOBS_TABLE,
      {
        manager_telegram_user_id: input.managerTelegramUserId,
        status: existing.status ?? "draft",
        job_summary: existing.job_summary ?? "",
        job_profile: existing.job_profile ?? {},
        source_type: existing.source_type ?? null,
        source_text_original: existing.source_text_original ?? null,
        source_text_english: existing.source_text_english ?? null,
        telegram_file_id: existing.telegram_file_id ?? null,
        job_analysis_json: existing.job_analysis_json ?? null,
        manager_interview_plan_json: existing.manager_interview_plan_json ?? null,
        job_profile_json: existing.job_profile_json ?? null,
        technical_summary_json: existing.technical_summary_json ?? null,
        job_work_format: existing.job_work_format ?? "",
        job_remote_countries: existing.job_remote_countries ?? [],
        job_remote_worldwide: existing.job_remote_worldwide ?? false,
        job_budget_min: existing.job_budget_min ?? null,
        job_budget_max: existing.job_budget_max ?? null,
        job_budget_currency: existing.job_budget_currency ?? null,
        job_budget_period: existing.job_budget_period ?? null,
        job_profile_complete: existing.job_profile_complete ?? false,
        last_confirmation_one_liner: input.oneLiner,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "manager_telegram_user_id" },
    );
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalizeNullableText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function normalizeNullableNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function normalizeJobWorkFormat(value: unknown): "remote" | "hybrid" | "onsite" | null {
  if (value === "remote" || value === "hybrid" || value === "onsite") {
    return value;
  }
  return null;
}

function normalizeBudgetCurrency(value: unknown): "USD" | "EUR" | "ILS" | "GBP" | "other" | null {
  if (value === "USD" || value === "EUR" || value === "ILS" || value === "GBP" || value === "other") {
    return value;
  }
  return null;
}

function normalizeBudgetPeriod(value: unknown): "month" | "year" | null {
  if (value === "month" || value === "year") {
    return value;
  }
  return null;
}
