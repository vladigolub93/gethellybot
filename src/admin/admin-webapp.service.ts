import { Logger } from "../config/logger";
import { DataDeletionService } from "../privacy/data-deletion.service";
import { SupabaseRestClient } from "../db/supabase.client";

interface AdminUserRow {
  telegram_user_id: number;
  telegram_username: string | null;
  first_name: string | null;
  last_name: string | null;
  role: string | null;
  preferred_language: string | null;
  contact_shared: boolean | null;
  candidate_profile_complete: boolean | null;
  created_at: string | null;
  updated_at: string | null;
}

interface AdminJobRow {
  id: number | string;
  manager_telegram_user_id: number;
  status: string;
  job_summary: string | null;
  job_profile_json: unknown;
  job_work_format: string | null;
  job_profile_complete: boolean | null;
  created_at: string | null;
  updated_at: string | null;
}

interface AdminMatchRow {
  id: string;
  job_id: string | number | null;
  candidate_id: string | number | null;
  manager_telegram_user_id: number;
  candidate_telegram_user_id: number;
  total_score: number | null;
  status: string;
  candidate_decision: string | null;
  manager_decision: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface AdminQualityFlagRow {
  id: string;
  entity_type: string;
  entity_id: string;
  flag: string;
  details: unknown;
  created_at: string | null;
}

export interface AdminDashboardData {
  stats: {
    usersTotal: number;
    candidatesTotal: number;
    managersTotal: number;
    jobsTotal: number;
    jobsActive: number;
    matchesTotal: number;
    matchesContactShared: number;
    candidatesApplied: number;
    contactSharedUsers: number;
    qualityFlags24h: number;
  };
  users: Array<{
    telegramUserId: number;
    username?: string;
    fullName?: string;
    role: string;
    preferredLanguage: string;
    contactShared: boolean;
    candidateProfileComplete: boolean;
    updatedAt?: string;
  }>;
  jobs: Array<{
    id: string;
    managerTelegramUserId: number;
    title: string;
    domain: string;
    status: string;
    workFormat: string;
    profileComplete: boolean;
    updatedAt?: string;
  }>;
  matches: Array<{
    id: string;
    jobId?: string;
    candidateId?: string;
    managerTelegramUserId: number;
    candidateTelegramUserId: number;
    totalScore?: number;
    status: string;
    candidateDecision?: string;
    managerDecision?: string;
    createdAt?: string;
  }>;
  qualityFlags: Array<{
    id: string;
    entityType: string;
    entityId: string;
    flag: string;
    createdAt?: string;
  }>;
}

export class AdminWebappService {
  constructor(
    private readonly logger: Logger,
    private readonly dataDeletionService: DataDeletionService,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async getDashboardData(): Promise<AdminDashboardData> {
    if (!this.supabaseClient) {
      return {
        stats: {
          usersTotal: 0,
          candidatesTotal: 0,
          managersTotal: 0,
          jobsTotal: 0,
          jobsActive: 0,
          matchesTotal: 0,
          matchesContactShared: 0,
          candidatesApplied: 0,
          contactSharedUsers: 0,
          qualityFlags24h: 0,
        },
        users: [],
        jobs: [],
        matches: [],
        qualityFlags: [],
      };
    }

    const [users, jobs, matches, qualityFlags] = await Promise.all([
      this.supabaseClient.selectMany<AdminUserRow>(
        "users",
        {},
        "telegram_user_id,telegram_username,first_name,last_name,role,preferred_language,contact_shared,candidate_profile_complete,created_at,updated_at",
      ),
      this.supabaseClient.selectMany<AdminJobRow>(
        "jobs",
        {},
        "id,manager_telegram_user_id,status,job_summary,job_profile_json,job_work_format,job_profile_complete,created_at,updated_at",
      ),
      this.supabaseClient.selectMany<AdminMatchRow>(
        "matches",
        {},
        "id,job_id,candidate_id,manager_telegram_user_id,candidate_telegram_user_id,total_score,status,candidate_decision,manager_decision,created_at,updated_at",
      ),
      this.supabaseClient.selectMany<AdminQualityFlagRow>(
        "quality_flags",
        {},
        "id,entity_type,entity_id,flag,details,created_at",
      ),
    ]);

    const usersSorted = users.sort((a, b) => safeTime(b.updated_at) - safeTime(a.updated_at));
    const jobsSorted = jobs.sort((a, b) => safeTime(b.updated_at) - safeTime(a.updated_at));
    const matchesSorted = matches.sort((a, b) => safeTime(b.created_at) - safeTime(a.created_at));
    const flagsSorted = qualityFlags.sort((a, b) => safeTime(b.created_at) - safeTime(a.created_at));

    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;

    return {
      stats: {
        usersTotal: users.length,
        candidatesTotal: users.filter((item) => item.role === "candidate").length,
        managersTotal: users.filter((item) => item.role === "manager").length,
        jobsTotal: jobs.length,
        jobsActive: jobs.filter((item) => item.status === "active").length,
        matchesTotal: matches.length,
        matchesContactShared: matches.filter((item) => item.status === "contact_shared").length,
        candidatesApplied: matches.filter((item) => item.candidate_decision === "apply").length,
        contactSharedUsers: users.filter((item) => Boolean(item.contact_shared)).length,
        qualityFlags24h: qualityFlags.filter((item) => now - safeTime(item.created_at) <= oneDayMs).length,
      },
      users: usersSorted.slice(0, 100).map((item) => ({
        telegramUserId: item.telegram_user_id,
        username: item.telegram_username ?? undefined,
        fullName: [item.first_name, item.last_name].filter((part) => Boolean(part)).join(" ") || undefined,
        role: item.role ?? "unknown",
        preferredLanguage: item.preferred_language ?? "unknown",
        contactShared: Boolean(item.contact_shared),
        candidateProfileComplete: Boolean(item.candidate_profile_complete),
        updatedAt: item.updated_at ?? undefined,
      })),
      jobs: jobsSorted.slice(0, 100).map((item) => {
        const jobProfile = asRecord(item.job_profile_json);
        const roleTitle = toText(jobProfile?.role_title) || toText(jobProfile?.title);
        const domainRequirements = asRecord(jobProfile?.domain_requirements);
        const domain = toText(jobProfile?.domain) || toText(domainRequirements?.primary_domain);
        return {
          id: String(item.id),
          managerTelegramUserId: item.manager_telegram_user_id,
          title: roleTitle || truncate(item.job_summary, 70) || "Untitled job",
          domain: domain || "unknown",
          status: item.status,
          workFormat: item.job_work_format ?? "unknown",
          profileComplete: Boolean(item.job_profile_complete),
          updatedAt: item.updated_at ?? undefined,
        };
      }),
      matches: matchesSorted.slice(0, 100).map((item) => ({
        id: item.id,
        jobId: item.job_id !== null && item.job_id !== undefined ? String(item.job_id) : undefined,
        candidateId:
          item.candidate_id !== null && item.candidate_id !== undefined
            ? String(item.candidate_id)
            : undefined,
        managerTelegramUserId: item.manager_telegram_user_id,
        candidateTelegramUserId: item.candidate_telegram_user_id,
        totalScore:
          typeof item.total_score === "number" && Number.isFinite(item.total_score)
            ? item.total_score
            : undefined,
        status: item.status,
        candidateDecision: item.candidate_decision ?? undefined,
        managerDecision: item.manager_decision ?? undefined,
        createdAt: item.created_at ?? undefined,
      })),
      qualityFlags: flagsSorted.slice(0, 200).map((item) => ({
        id: item.id,
        entityType: item.entity_type,
        entityId: item.entity_id,
        flag: item.flag,
        createdAt: item.created_at ?? undefined,
      })),
    };
  }

  async deleteUser(telegramUserId: number): Promise<{ ok: boolean; message: string }> {
    if (!Number.isInteger(telegramUserId) || telegramUserId <= 0) {
      return {
        ok: false,
        message: "Invalid telegram user id",
      };
    }

    const result = await this.dataDeletionService.requestDeletion({
      telegramUserId,
      reason: "admin_panel_delete_user",
    });

    return {
      ok: result.requested,
      message: result.confirmationMessage,
    };
  }

  async deleteJob(jobIdRaw: string): Promise<{ ok: boolean; message: string }> {
    if (!this.supabaseClient) {
      return {
        ok: false,
        message: "Supabase is not configured",
      };
    }

    const jobId = normalizeJobId(jobIdRaw);
    if (jobId === null) {
      return {
        ok: false,
        message: "Invalid job id",
      };
    }

    try {
      await this.supabaseClient.deleteMany("matches", { job_id: jobId });
      await this.supabaseClient.deleteMany("jobs", { id: jobId });
      this.logger.info("admin.job.deleted", { jobId });
      return { ok: true, message: `Job ${jobId} deleted` };
    } catch (error) {
      this.logger.error("admin.job.delete_failed", {
        jobId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        ok: false,
        message: "Failed to delete job",
      };
    }
  }
}

function safeTime(value: string | null): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as Record<string, unknown>;
}

function toText(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.trim();
}

function truncate(value: string | null | undefined, maxLength: number): string {
  if (!value) {
    return "";
  }
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3)}...`;
}

function normalizeJobId(jobIdRaw: string): string | number | null {
  const trimmed = jobIdRaw.trim();
  if (!trimmed) {
    return null;
  }
  const asNumber = Number(trimmed);
  if (Number.isInteger(asNumber) && asNumber > 0) {
    return asNumber;
  }
  return trimmed;
}
