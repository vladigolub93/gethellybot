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
  job_analysis_json?: unknown;
  manager_interview_plan_json?: unknown;
  job_profile_json?: unknown;
  technical_summary_json?: unknown;
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
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
