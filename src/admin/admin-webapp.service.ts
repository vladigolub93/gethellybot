import { Logger } from "../config/logger";
import { SupabaseRestClient } from "../db/supabase.client";
import { QdrantClient } from "../matching/qdrant.client";
import { DataDeletionService } from "../privacy/data-deletion.service";

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

interface AdminProfileRow {
  telegram_user_id: number;
  kind: "candidate" | "job";
  profile_status: string | null;
  technical_summary_json: unknown;
  raw_resume_analysis_json: unknown;
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

interface AdminMatchIdRow {
  id: string;
  job_id: string | number | null;
}

interface AdminQualityFlagRow {
  id: string;
  entity_type: string;
  entity_id: string;
  flag: string;
  details: unknown;
  created_at: string | null;
}

interface DataDeletionRequestRow {
  telegram_user_id: number;
  reason: string | null;
  status: string;
  requested_at: string | null;
  updated_at: string | null;
}

interface AdminInterviewRunRow {
  telegram_user_id: number;
  role: string;
  completed_at: string | null;
}

type InterviewProgressStatus = "not_started" | "in_progress" | "completed";

export interface AdminDashboardData {
  generatedAt: string;
  consistency: {
    supabaseConfigured: boolean;
    qdrantEnabled: boolean;
    candidateProfilesInSupabase: number;
    candidateVectorsInQdrant: number | null;
    vectorSyncGap: number | null;
  };
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
    interviewsTotal: number;
    candidateInterviewsCompleted: number;
    candidateInterviewsInProgress: number;
    managerInterviewsCompleted: number;
    managerInterviewsInProgress: number;
  };
  users: Array<{
    telegramUserId: number;
    username?: string;
    fullName?: string;
    role: string;
    preferredLanguage: string;
    contactShared: boolean;
    candidateProfileComplete: boolean;
    candidateInterviewStatus: InterviewProgressStatus;
    managerInterviewStatus: InterviewProgressStatus;
    updatedAt?: string;
  }>;
  candidates: Array<{
    telegramUserId: number;
    username?: string;
    fullName?: string;
    profileStatus: string;
    interviewConfidence?: string;
    interviewStatus: InterviewProgressStatus;
    candidateProfileComplete: boolean;
    contactShared: boolean;
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
    managerInterviewStatus: InterviewProgressStatus;
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
  deletionRequests: Array<{
    telegramUserId: number;
    reason: string;
    status: string;
    requestedAt?: string;
    updatedAt?: string;
  }>;
  interviewProgress: {
    candidates: Array<{
      telegramUserId: number;
      username?: string;
      fullName?: string;
      status: InterviewProgressStatus;
      currentState: string;
      updatedAt?: string;
    }>;
    managers: Array<{
      telegramUserId: number;
      username?: string;
      fullName?: string;
      status: InterviewProgressStatus;
      currentState: string;
      updatedAt?: string;
    }>;
  };
}

export interface AdminDeleteResult {
  ok: boolean;
  message: string;
  verification?: {
    remainingRefs: string[];
  };
}

export class AdminWebappService {
  constructor(
    private readonly logger: Logger,
    private readonly dataDeletionService: DataDeletionService,
    private readonly supabaseClient?: SupabaseRestClient,
    private readonly qdrantClient?: QdrantClient,
  ) {}

  async getDashboardData(): Promise<AdminDashboardData> {
    if (!this.supabaseClient) {
      return {
        generatedAt: new Date().toISOString(),
        consistency: {
          supabaseConfigured: false,
          qdrantEnabled: Boolean(this.qdrantClient?.isEnabled()),
          candidateProfilesInSupabase: 0,
          candidateVectorsInQdrant: null,
          vectorSyncGap: null,
        },
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
          interviewsTotal: 0,
          candidateInterviewsCompleted: 0,
          candidateInterviewsInProgress: 0,
          managerInterviewsCompleted: 0,
          managerInterviewsInProgress: 0,
        },
        users: [],
        candidates: [],
        jobs: [],
        matches: [],
        qualityFlags: [],
        deletionRequests: [],
        interviewProgress: {
          candidates: [],
          managers: [],
        },
      };
    }

    const [users, profiles, jobs, matches, qualityFlags, deletionRequests, interviews, userStates] = await Promise.all([
      this.supabaseClient.selectMany<AdminUserRow>(
        "users",
        {},
        "telegram_user_id,telegram_username,first_name,last_name,role,preferred_language,contact_shared,candidate_profile_complete,created_at,updated_at",
      ),
      this.supabaseClient.selectMany<AdminProfileRow>(
        "profiles",
        {},
        "telegram_user_id,kind,profile_status,technical_summary_json,raw_resume_analysis_json,updated_at",
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
      this.supabaseClient.selectMany<DataDeletionRequestRow>(
        "data_deletion_requests",
        {},
        "telegram_user_id,reason,status,requested_at,updated_at",
      ),
      this.supabaseClient.selectMany<AdminInterviewRunRow>(
        "interview_runs",
        {},
        "telegram_user_id,role,completed_at",
      ),
      this.supabaseClient.selectMany<{
        telegram_user_id: number;
        state: string;
        updated_at: string;
      }>(
        "user_states",
        {},
        "telegram_user_id,state,updated_at",
      ),
    ]);

    const usersSorted = users.sort((a, b) => safeTime(b.updated_at) - safeTime(a.updated_at));
    const jobsSorted = jobs.sort((a, b) => safeTime(b.updated_at) - safeTime(a.updated_at));
    const matchesSorted = matches.sort((a, b) => safeTime(b.created_at) - safeTime(a.created_at));
    const flagsSorted = qualityFlags.sort((a, b) => safeTime(b.created_at) - safeTime(a.created_at));
    const deletionSorted = deletionRequests.sort((a, b) => safeTime(b.requested_at) - safeTime(a.requested_at));

    const userById = new Map<number, AdminUserRow>();
    for (const user of users) {
      userById.set(user.telegram_user_id, user);
    }
    const userStateById = new Map<number, { state: string; updatedAt: string }>();
    for (const row of userStates) {
      userStateById.set(row.telegram_user_id, {
        state: row.state,
        updatedAt: row.updated_at,
      });
    }

    const candidateInterviewCompleted = new Set<number>();
    const managerInterviewCompleted = new Set<number>();
    for (const run of interviews) {
      if (run.role === "candidate") {
        candidateInterviewCompleted.add(run.telegram_user_id);
      } else if (run.role === "manager") {
        managerInterviewCompleted.add(run.telegram_user_id);
      }
    }

    const candidateProfiles = profiles
      .filter((profile) => profile.kind === "candidate")
      .sort((a, b) => safeTime(b.updated_at) - safeTime(a.updated_at));

    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;
    const qdrantEnabled = Boolean(this.qdrantClient?.isEnabled());
    const qdrantCount = qdrantEnabled
      ? await this.qdrantClient!.getCandidateVectorCount()
      : null;

    const consistencyGap =
      typeof qdrantCount === "number"
        ? candidateProfiles.length - qdrantCount
        : null;

    const usersWithInterviewStatus = usersSorted.map((item) => {
      const stateRow = userStateById.get(item.telegram_user_id);
      const candidateInterviewStatus = resolveInterviewStatus({
        role: "candidate",
        state: stateRow?.state,
        completed: candidateInterviewCompleted.has(item.telegram_user_id),
      });
      const managerInterviewStatus = resolveInterviewStatus({
        role: "manager",
        state: stateRow?.state,
        completed: managerInterviewCompleted.has(item.telegram_user_id),
      });
      return {
        telegramUserId: item.telegram_user_id,
        username: item.telegram_username ?? undefined,
        fullName: [item.first_name, item.last_name]
          .filter((part) => Boolean(part))
          .join(" ") || undefined,
        role: item.role ?? "unknown",
        preferredLanguage: item.preferred_language ?? "unknown",
        contactShared: Boolean(item.contact_shared),
        candidateProfileComplete: Boolean(item.candidate_profile_complete),
        candidateInterviewStatus,
        managerInterviewStatus,
        updatedAt: item.updated_at ?? undefined,
      };
    });

    const interviewProgressCandidates = usersWithInterviewStatus
      .filter((item) => item.role === "candidate")
      .map((item) => ({
        telegramUserId: item.telegramUserId,
        username: item.username,
        fullName: item.fullName,
        status: item.candidateInterviewStatus,
        currentState: userStateById.get(item.telegramUserId)?.state ?? "unknown",
        updatedAt: item.updatedAt,
      }))
      .sort((a, b) => safeTime(b.updatedAt ?? null) - safeTime(a.updatedAt ?? null))
      .slice(0, 150);

    const interviewProgressManagers = usersWithInterviewStatus
      .filter((item) => item.role === "manager")
      .map((item) => ({
        telegramUserId: item.telegramUserId,
        username: item.username,
        fullName: item.fullName,
        status: item.managerInterviewStatus,
        currentState: userStateById.get(item.telegramUserId)?.state ?? "unknown",
        updatedAt: item.updatedAt,
      }))
      .sort((a, b) => safeTime(b.updatedAt ?? null) - safeTime(a.updatedAt ?? null))
      .slice(0, 150);

    return {
      generatedAt: new Date().toISOString(),
      consistency: {
        supabaseConfigured: true,
        qdrantEnabled,
        candidateProfilesInSupabase: candidateProfiles.length,
        candidateVectorsInQdrant: qdrantCount,
        vectorSyncGap: consistencyGap,
      },
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
        interviewsTotal: interviews.length,
        candidateInterviewsCompleted: usersWithInterviewStatus.filter(
          (item) => item.role === "candidate" && item.candidateInterviewStatus === "completed",
        ).length,
        candidateInterviewsInProgress: usersWithInterviewStatus.filter(
          (item) => item.role === "candidate" && item.candidateInterviewStatus === "in_progress",
        ).length,
        managerInterviewsCompleted: usersWithInterviewStatus.filter(
          (item) => item.role === "manager" && item.managerInterviewStatus === "completed",
        ).length,
        managerInterviewsInProgress: usersWithInterviewStatus.filter(
          (item) => item.role === "manager" && item.managerInterviewStatus === "in_progress",
        ).length,
      },
      users: usersWithInterviewStatus.slice(0, 120),
      candidates: candidateProfiles.slice(0, 120).map((profile) => {
        const user = userById.get(profile.telegram_user_id);
        const stateRow = userStateById.get(profile.telegram_user_id);
        const summary = asRecord(profile.technical_summary_json);
        const confidence = toText(summary?.interview_confidence_level).toLowerCase();
        return {
          telegramUserId: profile.telegram_user_id,
          username: user?.telegram_username ?? undefined,
          fullName:
            [user?.first_name, user?.last_name]
              .filter((part) => Boolean(part))
              .join(" ") || undefined,
          profileStatus: profile.profile_status ?? "unknown",
          interviewConfidence:
            confidence === "low" || confidence === "medium" || confidence === "high"
              ? confidence
              : undefined,
          interviewStatus: resolveInterviewStatus({
            role: "candidate",
            state: stateRow?.state,
            completed: candidateInterviewCompleted.has(profile.telegram_user_id),
          }),
          candidateProfileComplete: Boolean(user?.candidate_profile_complete),
          contactShared: Boolean(user?.contact_shared),
          updatedAt: profile.updated_at ?? user?.updated_at ?? undefined,
        };
      }),
      jobs: jobsSorted.slice(0, 120).map((item) => {
        const jobProfile = asRecord(item.job_profile_json);
        const roleTitle = toText(jobProfile?.role_title) || toText(jobProfile?.title);
        const domainRequirements = asRecord(jobProfile?.domain_requirements);
        const domain =
          toText(jobProfile?.domain) || toText(domainRequirements?.primary_domain);

        return {
          id: String(item.id),
          managerTelegramUserId: item.manager_telegram_user_id,
          title: roleTitle || truncate(item.job_summary, 70) || "Untitled job",
          domain: domain || "unknown",
          status: item.status,
          workFormat: item.job_work_format ?? "unknown",
          profileComplete: Boolean(item.job_profile_complete),
          managerInterviewStatus: resolveInterviewStatus({
            role: "manager",
            state: userStateById.get(item.manager_telegram_user_id)?.state,
            completed: managerInterviewCompleted.has(item.manager_telegram_user_id),
          }),
          updatedAt: item.updated_at ?? undefined,
        };
      }),
      matches: matchesSorted.slice(0, 150).map((item) => ({
        id: item.id,
        jobId:
          item.job_id !== null && item.job_id !== undefined
            ? String(item.job_id)
            : undefined,
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
      deletionRequests: deletionSorted.slice(0, 120).map((item) => ({
        telegramUserId: item.telegram_user_id,
        reason: item.reason ?? "user_requested",
        status: item.status,
        requestedAt: item.requested_at ?? undefined,
        updatedAt: item.updated_at ?? undefined,
      })),
      interviewProgress: {
        candidates: interviewProgressCandidates,
        managers: interviewProgressManagers,
      },
    };
  }

  async deleteUser(telegramUserId: number): Promise<AdminDeleteResult> {
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

    const verification = await this.verifyUserDeletion(telegramUserId);

    return {
      ok: result.requested && verification.remainingRefs.length === 0,
      message:
        verification.remainingRefs.length === 0
          ? result.confirmationMessage
          : "Deletion requested, but some references are still present",
      verification,
    };
  }

  async deleteCandidate(telegramUserId: number): Promise<AdminDeleteResult> {
    return this.deleteUser(telegramUserId);
  }

  async deleteJob(jobIdRaw: string): Promise<AdminDeleteResult> {
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
      const jobRow = await this.supabaseClient.selectOne<{
        id: string | number;
        manager_telegram_user_id: number;
      }>(
        "jobs",
        { id: jobId },
        "id,manager_telegram_user_id",
      );

      if (isUuidLike(String(jobId))) {
        await this.supabaseClient.deleteMany("matches", { job_id: jobId });
      }
      if (jobRow?.manager_telegram_user_id) {
        const managerMatches = await this.supabaseClient.selectMany<AdminMatchIdRow>(
          "matches",
          { manager_telegram_user_id: jobRow.manager_telegram_user_id },
          "id,job_id",
        );
        const targetMatchIds = managerMatches
          .filter((item) => String(item.job_id ?? "") === String(jobId))
          .map((item) => item.id)
          .filter((id) => typeof id === "string" && id.length > 0);
        for (const matchId of targetMatchIds) {
          await this.supabaseClient.deleteMany("matches", { id: matchId });
        }
      }
      await this.supabaseClient.deleteMany("jobs", { id: jobId });

      if (jobRow?.manager_telegram_user_id) {
        const managerJobs = await this.supabaseClient.selectMany<{ id: string | number }>(
          "jobs",
          {
            manager_telegram_user_id: jobRow.manager_telegram_user_id,
          },
          "id",
        );
        if (managerJobs.length === 0) {
          await this.supabaseClient.deleteMany("profiles", {
            telegram_user_id: jobRow.manager_telegram_user_id,
            kind: "job",
          });
        }
      }

      const verification = await this.verifyJobDeletion(
        jobId,
        jobRow?.manager_telegram_user_id,
      );
      this.logger.info("admin.job.deleted", { jobId, verification });
      return {
        ok: verification.remainingRefs.length === 0,
        message:
          verification.remainingRefs.length === 0
            ? `Job ${jobId} deleted`
            : `Job ${jobId} deletion incomplete`,
        verification,
      };
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

  private async verifyUserDeletion(telegramUserId: number): Promise<{ remainingRefs: string[] }> {
    if (!this.supabaseClient) {
      return { remainingRefs: [] };
    }

    const checks: Array<Promise<{ name: string; hasRows: boolean }>> = [
      this.tableHasRows("users", { telegram_user_id: telegramUserId }),
      this.tableHasRows("user_states", { telegram_user_id: telegramUserId }),
      this.tableHasRows("profiles", { telegram_user_id: telegramUserId }),
      this.tableHasRows("jobs", { manager_telegram_user_id: telegramUserId }),
      this.tableHasRows("interview_runs", { telegram_user_id: telegramUserId }),
      this.tableHasRows("matches", { candidate_telegram_user_id: telegramUserId }),
      this.tableHasRows("matches", { manager_telegram_user_id: telegramUserId }),
      this.tableHasRows("notification_limits", { telegram_user_id: telegramUserId }),
      this.tableHasRows("telegram_updates", { telegram_user_id: telegramUserId }),
    ];

    const results = await Promise.all(checks);
    return {
      remainingRefs: results.filter((item) => item.hasRows).map((item) => item.name),
    };
  }

  private async verifyJobDeletion(
    jobId: string | number,
    managerTelegramUserId?: number,
  ): Promise<{ remainingRefs: string[] }> {
    if (!this.supabaseClient) {
      return { remainingRefs: [] };
    }
    const checks: Array<Promise<{ name: string; hasRows: boolean }>> = [this.tableHasRows("jobs", { id: jobId })];
    if (typeof managerTelegramUserId === "number" && Number.isInteger(managerTelegramUserId)) {
      checks.push(
        this.managerHasMatchesForJob(managerTelegramUserId, jobId),
      );
    }
    const results = await Promise.all(checks);
    return {
      remainingRefs: results.filter((item) => item.hasRows).map((item) => item.name),
    };
  }

  private async managerHasMatchesForJob(
    managerTelegramUserId: number,
    jobId: string | number,
  ): Promise<{ name: string; hasRows: boolean }> {
    if (!this.supabaseClient) {
      return {
        name: `matches:manager_${managerTelegramUserId}:job_${jobId}`,
        hasRows: false,
      };
    }
    try {
      const matches = await this.supabaseClient.selectMany<AdminMatchIdRow>(
        "matches",
        { manager_telegram_user_id: managerTelegramUserId },
        "id,job_id",
      );
      const hasRows = matches.some(
        (item) => String(item.job_id ?? "") === String(jobId),
      );
      return {
        name: `matches:manager_${managerTelegramUserId}:job_${jobId}`,
        hasRows,
      };
    } catch (error) {
      this.logger.warn("admin.manager_job_matches_check_failed", {
        managerTelegramUserId,
        jobId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        name: `matches:manager_${managerTelegramUserId}:job_${jobId}:check_failed`,
        hasRows: true,
      };
    }
  }

  private async tableHasRows(
    table: string,
    filters: Record<string, string | number>,
  ): Promise<{ name: string; hasRows: boolean }> {
    try {
      const rows = await this.supabaseClient!.selectMany<{ id?: string | number }>(
        table,
        filters,
        "*",
      );
      return {
        name: `${table}:${JSON.stringify(filters)}`,
        hasRows: rows.length > 0,
      };
    } catch (error) {
      this.logger.warn("admin.table_has_rows_failed", {
        table,
        filters,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        name: `${table}:${JSON.stringify(filters)}:check_failed`,
        hasRows: true,
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

const CANDIDATE_INCOMPLETE_STATES = new Set<string>([
  "waiting_resume",
  "extracting_resume",
  "interviewing_candidate",
  "candidate_mandatory_fields",
]);

const MANAGER_INCOMPLETE_STATES = new Set<string>([
  "waiting_job",
  "extracting_job",
  "interviewing_manager",
  "manager_mandatory_fields",
]);

function resolveInterviewStatus(input: {
  role: "candidate" | "manager";
  state?: string;
  completed: boolean;
}): InterviewProgressStatus {
  if (input.completed) {
    return "completed";
  }
  if (!input.state) {
    return "not_started";
  }
  if (input.role === "candidate" && CANDIDATE_INCOMPLETE_STATES.has(input.state)) {
    return "in_progress";
  }
  if (input.role === "manager" && MANAGER_INCOMPLETE_STATES.has(input.state)) {
    return "in_progress";
  }
  return "not_started";
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

function isUuidLike(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value.trim(),
  );
}
