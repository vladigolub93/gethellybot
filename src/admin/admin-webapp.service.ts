import { Logger } from "../config/logger";
import { EvaluationStatus } from "../core/matching/evaluation-statuses";
import { INTERVIEW_STATUSES, InterviewStatus } from "../core/matching/interview-statuses";
import {
  DecisionGateSnapshot,
  resolveDecisionGateSnapshot,
} from "../core/matching/decision-gate-snapshot";
import {
  normalizeLegacyEvaluationStatus,
  normalizeLegacyInterviewStatus,
  normalizeLegacyMatchStatus,
} from "../core/matching/lifecycle-normalizers";
import { resolveLifecycleSnapshot } from "../core/matching/lifecycle-snapshot.resolver";
import { MATCH_STATUSES, MatchStatus } from "../core/matching/match-statuses";
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
  canonical_match_status?: string | null;
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
  canonical_interview_status?: string | null;
  completed_at: string | null;
}

interface AdminUserStateRow {
  telegram_user_id: number;
  state: string;
  canonical_interview_status?: string | null;
  updated_at: string;
}

type InterviewProgressStatus = "not_started" | "in_progress" | "completed";

interface AdminNormalizedLifecycle {
  matchStatus: MatchStatus | null;
  interviewStatus: InterviewStatus | null;
  evaluationStatus: EvaluationStatus | null;
  fallbackUsed: boolean;
  fallbackReasons: string[];
}

interface AdminDecisionGateSummary {
  total: number;
  aligned: number;
  diverged: number;
  unresolved: number;
  overloadedLegacy: number;
  canonicalMismatch: number;
}

interface AdminDecisionGateObservability {
  total: number;
  canonicalGateEligible: number;
  canonicalGateUsed: number;
  legacyFallbackUsed: number;
  divergenceDetected: number;
  canonicalMissing: number;
  unresolved: number;
}

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
  decisionGateSummary: AdminDecisionGateSummary;
  decisionGateObservability: AdminDecisionGateObservability;
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
    lifecycleSnapshot?: {
      matchStatus: MatchStatus | null;
      interviewStatus: InterviewStatus | null;
      evaluationStatus: EvaluationStatus | null;
      notes: string[];
      risks: string[];
      raw: {
        matchId: string | null;
        status: string | null;
        candidateDecision: string | null;
        managerDecision: string | null;
        interviewSessionState: string | null;
        interviewRunStatus: string | null;
        profileStatus: string | null;
        interviewConfidenceLevel: string | null;
        recommendation: string | null;
        managerVisibleHint: boolean | null;
        exposureSource: string | null;
      };
    };
    normalizedLifecycle?: AdminNormalizedLifecycle;
    decisionGateSnapshot?: DecisionGateSnapshot;
  }>;
  qualityFlags: Array<{
    id: string;
    entityType: string;
    entityId: string;
    flag: string;
    details?: string;
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
        decisionGateSummary: {
          total: 0,
          aligned: 0,
          diverged: 0,
          unresolved: 0,
          overloadedLegacy: 0,
          canonicalMismatch: 0,
        },
        decisionGateObservability: {
          total: 0,
          canonicalGateEligible: 0,
          canonicalGateUsed: 0,
          legacyFallbackUsed: 0,
          divergenceDetected: 0,
          canonicalMissing: 0,
          unresolved: 0,
        },
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
      this.selectManyWithCanonicalFallback<AdminMatchRow>(
        "matches",
        "id,job_id,candidate_id,manager_telegram_user_id,candidate_telegram_user_id,total_score,status,candidate_decision,manager_decision,canonical_match_status,created_at,updated_at",
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
      this.selectManyWithCanonicalFallback<AdminInterviewRunRow>(
        "interview_runs",
        "telegram_user_id,role,canonical_interview_status,completed_at",
        "telegram_user_id,role,completed_at",
      ),
      this.selectManyWithCanonicalFallback<AdminUserStateRow>(
        "user_states",
        "telegram_user_id,state,canonical_interview_status,updated_at",
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
    const userStateById = new Map<number, { state: string; canonicalInterviewStatus: InterviewStatus | null; updatedAt: string }>();
    for (const row of userStates) {
      userStateById.set(row.telegram_user_id, {
        state: row.state,
        canonicalInterviewStatus: parseCanonicalInterviewStatus(row.canonical_interview_status),
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
    const candidateProfileByUserId = new Map<number, AdminProfileRow>();
    for (const profile of candidateProfiles) {
      candidateProfileByUserId.set(profile.telegram_user_id, profile);
    }
    const candidateInterviewCompletedAtByUserId = new Map<number, string>();
    const candidateCanonicalInterviewStatusFromCompletedRunByUserId = new Map<number, InterviewStatus>();
    const candidateCanonicalInterviewStatusFromActiveRunByUserId = new Map<number, InterviewStatus>();
    for (const run of interviews) {
      if (run.role !== "candidate") {
        continue;
      }

      if (run.completed_at) {
        const current = candidateInterviewCompletedAtByUserId.get(run.telegram_user_id);
        if (!current || safeTime(run.completed_at) > safeTime(current)) {
          candidateInterviewCompletedAtByUserId.set(run.telegram_user_id, run.completed_at);
        }

        const status = parseCanonicalInterviewStatus(run.canonical_interview_status);
        if (status) {
          const previousCompletedAt = candidateInterviewCompletedAtByUserId.get(run.telegram_user_id);
          if (!previousCompletedAt || safeTime(run.completed_at) >= safeTime(previousCompletedAt)) {
            candidateCanonicalInterviewStatusFromCompletedRunByUserId.set(
              run.telegram_user_id,
              status,
            );
          }
        }
      } else {
        const status = parseCanonicalInterviewStatus(run.canonical_interview_status);
        if (status) {
          candidateCanonicalInterviewStatusFromActiveRunByUserId.set(
            run.telegram_user_id,
            status,
          );
        }
      }
    }

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

    const matchesWithDiagnostics = matchesSorted.slice(0, 150).map((item) => {
      const candidateStateRow = userStateById.get(item.candidate_telegram_user_id);
      const candidateState = candidateStateRow?.state;
      const canonicalInterviewStatusFromCompletedRun =
        candidateCanonicalInterviewStatusFromCompletedRunByUserId.get(
          item.candidate_telegram_user_id,
        ) ?? null;
      const canonicalInterviewStatusFromActiveSession =
        candidateStateRow?.canonicalInterviewStatus ??
        candidateCanonicalInterviewStatusFromActiveRunByUserId.get(
          item.candidate_telegram_user_id,
        ) ??
        null;
      const canonicalInterviewStatus =
        canonicalInterviewStatusFromCompletedRun ??
        canonicalInterviewStatusFromActiveSession ??
        null;
      const canonicalMatchStatus = parseCanonicalMatchStatus(item.canonical_match_status);
      const candidateProfile = candidateProfileByUserId.get(item.candidate_telegram_user_id);
      const candidateTechnicalSummary = asRecord(candidateProfile?.technical_summary_json);
      const interviewConfidenceLevel = extractInterviewConfidenceLevel(candidateTechnicalSummary);
      const managerVisibleByLegacyStatus = new Set([
        "candidate_applied",
        "manager_accepted",
        "manager_rejected",
        "contact_shared",
      ]).has(toText(item.status).toLowerCase());
      const lifecycleSnapshot = resolveLifecycleSnapshot({
        canonicalMatchStatus,
        canonicalInterviewStatus,
        match: {
          id: item.id,
          status: item.status,
          candidateDecision: item.candidate_decision,
          managerDecision: item.manager_decision,
          contactShared: item.status === "contact_shared",
        },
        interview: {
          sessionState: candidateState,
          interviewRunStatus: candidateInterviewCompleted.has(item.candidate_telegram_user_id)
            ? "completed"
            : null,
          hasInterviewRunRow: candidateInterviewCompleted.has(item.candidate_telegram_user_id),
          interviewRunCompletedAt:
            candidateInterviewCompletedAtByUserId.get(item.candidate_telegram_user_id) ?? null,
        },
        evaluation: {
          profileStatus: candidateProfile?.profile_status ?? null,
          interviewConfidenceLevel,
          matchScore:
            typeof item.total_score === "number" && Number.isFinite(item.total_score)
              ? item.total_score
              : null,
        },
        exposure: {
          managerVisible: managerVisibleByLegacyStatus,
          source: "admin_webapp.matches",
        },
      });

      this.logger.debug("lifecycle_snapshot.resolved", {
        matchId: item.id,
        managerTelegramUserId: item.manager_telegram_user_id,
        candidateTelegramUserId: item.candidate_telegram_user_id,
        canonicalMatchStatusProvided: Boolean(canonicalMatchStatus),
        canonicalInterviewStatusProvided: Boolean(canonicalInterviewStatus),
        canonicalInterviewStatusSource: canonicalInterviewStatusFromCompletedRun
          ? "completed_interview_run"
          : canonicalInterviewStatusFromActiveSession
          ? "active_session_or_run"
          : "none",
        matchStatus: lifecycleSnapshot.matchStatus,
        interviewStatus: lifecycleSnapshot.interviewStatus,
        evaluationStatus: lifecycleSnapshot.evaluationStatus,
      });
      if (lifecycleSnapshot.notes.length > 0) {
        this.logger.debug("lifecycle_snapshot.notes", {
          matchId: item.id,
          notes: lifecycleSnapshot.notes,
        });
      }
      if (lifecycleSnapshot.risks.length > 0) {
        this.logger.debug("lifecycle_snapshot.risks", {
          matchId: item.id,
          risks: lifecycleSnapshot.risks,
        });
      }
      const normalizedLifecycle = resolveNormalizedLifecycleForAdmin({
        lifecycleSnapshot,
        legacy: {
          status: item.status,
          candidateDecision: item.candidate_decision,
          managerDecision: item.manager_decision,
          candidateSessionState: candidateState,
          candidateInterviewCompleted: candidateInterviewCompleted.has(item.candidate_telegram_user_id),
          profileStatus: candidateProfile?.profile_status ?? null,
          interviewConfidenceLevel,
          matchScore:
            typeof item.total_score === "number" && Number.isFinite(item.total_score)
              ? item.total_score
              : null,
        },
      });
      const decisionGateSnapshot = resolveDecisionGateSnapshot({
        status: item.status,
        candidateDecision: item.candidate_decision,
        managerDecision: item.manager_decision,
        contactShared: item.status === "contact_shared",
        canonicalMatchStatus,
        hints: {
          managerVisible: managerVisibleByLegacyStatus,
          interviewCompleted: candidateInterviewCompleted.has(item.candidate_telegram_user_id),
        },
      });
      this.logger.debug("decision_gate_snapshot.resolved", {
        matchId: item.id,
        managerTelegramUserId: item.manager_telegram_user_id,
        candidateTelegramUserId: item.candidate_telegram_user_id,
        canonicalMatchStatus: decisionGateSnapshot.canonicalMatchStatus,
        legacyGateState: decisionGateSnapshot.legacyGateState,
        candidateMayAccept: decisionGateSnapshot.candidateMayAccept,
        candidateMayReject: decisionGateSnapshot.candidateMayReject,
        managerMayApprove: decisionGateSnapshot.managerMayApprove,
        managerMayReject: decisionGateSnapshot.managerMayReject,
      });
      if (decisionGateSnapshot.divergenceNotes.length > 0) {
        this.logger.debug("decision_gate_snapshot.divergence", {
          matchId: item.id,
          divergenceNotes: decisionGateSnapshot.divergenceNotes,
          risks: decisionGateSnapshot.risks,
        });
      }
      if (normalizedLifecycle.fallbackUsed) {
        this.logger.debug("lifecycle_snapshot.fallback", {
          matchId: item.id,
          fallbackReasons: normalizedLifecycle.fallbackReasons,
          matchStatus: normalizedLifecycle.matchStatus,
          interviewStatus: normalizedLifecycle.interviewStatus,
          evaluationStatus: normalizedLifecycle.evaluationStatus,
        });
      }

      return {
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
        lifecycleSnapshot,
        normalizedLifecycle,
        decisionGateSnapshot,
      };
    });
    const decisionGateSummary = summarizeDecisionGateSnapshots(matchesWithDiagnostics);
    const decisionGateObservability = summarizeDecisionGateObservability(matchesWithDiagnostics);
    this.logger.debug("decision_gate_snapshot.summary_resolved", {
      total: decisionGateSummary.total,
      aligned: decisionGateSummary.aligned,
      diverged: decisionGateSummary.diverged,
      unresolved: decisionGateSummary.unresolved,
      overloadedLegacy: decisionGateSummary.overloadedLegacy,
      canonicalMismatch: decisionGateSummary.canonicalMismatch,
    });
    this.logger.debug("decision_gate_snapshot.observability_resolved", {
      ...decisionGateObservability,
    });

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
      decisionGateSummary,
      decisionGateObservability,
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
      matches: matchesWithDiagnostics,
      qualityFlags: flagsSorted.slice(0, 200).map((item) => ({
        id: item.id,
        entityType: item.entity_type,
        entityId: item.entity_id,
        flag: item.flag,
        details: stringifyUnknown(item.details),
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

  private async selectManyWithCanonicalFallback<T>(
    table: string,
    columnsWithCanonical: string,
    fallbackColumns: string,
  ): Promise<T[]> {
    try {
      return await this.supabaseClient!.selectMany<T>(table, {}, columnsWithCanonical);
    } catch (error) {
      this.logger.warn("admin.read.canonical_columns_unavailable", {
        table,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return this.supabaseClient!.selectMany<T>(table, {}, fallbackColumns);
    }
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

function extractInterviewConfidenceLevel(
  technicalSummary: Record<string, unknown> | null,
): string | null {
  const value = toText(technicalSummary?.interview_confidence_level);
  if (!value) {
    return null;
  }
  return value;
}

function parseCanonicalMatchStatus(value: string | null | undefined): MatchStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toUpperCase();
  const allowed = new Set<string>(Object.values(MATCH_STATUSES));
  return allowed.has(normalized) ? (normalized as MatchStatus) : null;
}

function parseCanonicalInterviewStatus(value: string | null | undefined): InterviewStatus | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toUpperCase();
  const allowed = new Set<string>(Object.values(INTERVIEW_STATUSES));
  return allowed.has(normalized) ? (normalized as InterviewStatus) : null;
}

function resolveNormalizedLifecycleForAdmin(input: {
  lifecycleSnapshot: {
    matchStatus: MatchStatus | null;
    interviewStatus: InterviewStatus | null;
    evaluationStatus: EvaluationStatus | null;
  };
  legacy: {
    status: string | null;
    candidateDecision: string | null;
    managerDecision: string | null;
    candidateSessionState: string | undefined;
    candidateInterviewCompleted: boolean;
    profileStatus: string | null;
    interviewConfidenceLevel: string | null;
    matchScore: number | null;
  };
}): AdminNormalizedLifecycle {
  const fallbackReasons: string[] = [];
  let fallbackUsed = false;

  const legacyNormalized = {
    matchStatus: normalizeLegacyMatchStatus({
      status: input.legacy.status,
      candidateDecision: input.legacy.candidateDecision,
      managerDecision: input.legacy.managerDecision,
      contactShared: toText(input.legacy.status).toLowerCase() === "contact_shared",
    }),
    interviewStatus: normalizeLegacyInterviewStatus({
      sessionState: input.legacy.candidateSessionState ?? null,
      interviewRunStatus: input.legacy.candidateInterviewCompleted ? "completed" : null,
      hasInterviewRunRow: input.legacy.candidateInterviewCompleted,
      interviewRunCompletedAt: input.legacy.candidateInterviewCompleted
        ? "completed"
        : null,
    }),
    evaluationStatus: normalizeLegacyEvaluationStatus({
      profileStatus: input.legacy.profileStatus,
      interviewConfidenceLevel: input.legacy.interviewConfidenceLevel,
      matchScore: input.legacy.matchScore,
    }),
  };

  let matchStatus = input.lifecycleSnapshot.matchStatus;
  let interviewStatus = input.lifecycleSnapshot.interviewStatus;
  let evaluationStatus = input.lifecycleSnapshot.evaluationStatus;

  if (matchStatus === null) {
    fallbackUsed = true;
    fallbackReasons.push("MATCH_STATUS_SNAPSHOT_NULL");
    matchStatus =
      legacyNormalized.matchStatus ??
      deriveMatchStatusFromLegacyForAdmin(input.legacy);
  }

  if (interviewStatus === null) {
    fallbackUsed = true;
    fallbackReasons.push("INTERVIEW_STATUS_SNAPSHOT_NULL");
    interviewStatus =
      legacyNormalized.interviewStatus ??
      deriveInterviewStatusFromLegacyForAdmin(input.legacy);
  }

  if (evaluationStatus === null) {
    fallbackUsed = true;
    fallbackReasons.push("EVALUATION_STATUS_SNAPSHOT_NULL");
    evaluationStatus =
      legacyNormalized.evaluationStatus ??
      deriveEvaluationStatusFromLegacyForAdmin(input.legacy);
  }

  return {
    matchStatus,
    interviewStatus,
    evaluationStatus,
    fallbackUsed,
    fallbackReasons,
  };
}

function deriveMatchStatusFromLegacyForAdmin(legacy: {
  status: string | null;
  candidateDecision: string | null;
  managerDecision: string | null;
}): MatchStatus | null {
  const normalizedStatus = toText(legacy.status).toLowerCase();
  if (normalizedStatus === "contact_shared" || normalizedStatus === "manager_accepted") {
    return "APPROVED";
  }
  if (normalizedStatus === "manager_rejected") {
    return "REJECTED";
  }
  if (normalizedStatus === "candidate_rejected") {
    return "DECLINED";
  }
  if (normalizedStatus === "candidate_applied") {
    return "SENT_TO_MANAGER";
  }

  const normalizedCandidateDecision = toText(legacy.candidateDecision).toLowerCase();
  if (
    normalizedCandidateDecision === "applied" ||
    normalizedCandidateDecision === "apply"
  ) {
    return "SENT_TO_MANAGER";
  }
  if (
    normalizedCandidateDecision === "rejected" ||
    normalizedCandidateDecision === "reject" ||
    normalizedCandidateDecision === "declined"
  ) {
    return "DECLINED";
  }

  const normalizedManagerDecision = toText(legacy.managerDecision).toLowerCase();
  if (
    normalizedManagerDecision === "accepted" ||
    normalizedManagerDecision === "accept" ||
    normalizedManagerDecision === "approved"
  ) {
    return "APPROVED";
  }
  if (
    normalizedManagerDecision === "rejected" ||
    normalizedManagerDecision === "reject" ||
    normalizedManagerDecision === "declined"
  ) {
    return "REJECTED";
  }

  return null;
}

function deriveInterviewStatusFromLegacyForAdmin(legacy: {
  candidateSessionState: string | undefined;
  candidateInterviewCompleted: boolean;
}): InterviewStatus | null {
  if (legacy.candidateInterviewCompleted) {
    return "COMPLETED";
  }

  const normalizedState = toText(legacy.candidateSessionState).toLowerCase();
  if (normalizedState === "interviewing_candidate" || normalizedState === "interviewing_manager") {
    return "STARTED";
  }

  return null;
}

function deriveEvaluationStatusFromLegacyForAdmin(legacy: {
  profileStatus: string | null;
  interviewConfidenceLevel: string | null;
  matchScore: number | null;
}): EvaluationStatus | null {
  const normalizedProfileStatus = toText(legacy.profileStatus).toLowerCase();
  if (normalizedProfileStatus === "rejected_non_technical") {
    return "WEAK";
  }

  const normalizedConfidence = toText(legacy.interviewConfidenceLevel).toLowerCase();
  if (normalizedConfidence === "high") {
    return "STRONG";
  }
  if (normalizedConfidence === "medium") {
    return "POSSIBLE";
  }
  if (normalizedConfidence === "low") {
    return "WEAK";
  }

  if (typeof legacy.matchScore === "number" && Number.isFinite(legacy.matchScore)) {
    if (legacy.matchScore >= 0.75) {
      return "STRONG";
    }
    if (legacy.matchScore >= 0.5) {
      return "POSSIBLE";
    }
    return "WEAK";
  }

  return null;
}

function summarizeDecisionGateSnapshots(matches: Array<{
  decisionGateSnapshot?: DecisionGateSnapshot;
}>): AdminDecisionGateSummary {
  let total = 0;
  let aligned = 0;
  let diverged = 0;
  let unresolved = 0;
  let overloadedLegacy = 0;
  let canonicalMismatch = 0;

  for (const item of matches) {
    const snapshot = item.decisionGateSnapshot;
    if (!snapshot) {
      continue;
    }
    total += 1;

    const hasDivergence = snapshot.divergenceNotes.length > 0;
    if (hasDivergence) {
      diverged += 1;
    } else {
      aligned += 1;
    }

    if (snapshot.risks.includes("CANONICAL_STATUS_UNRESOLVED")) {
      unresolved += 1;
    }
    if (snapshot.risks.includes("LEGACY_STATUS_OVERLOADED_CANDIDATE_APPLIED")) {
      overloadedLegacy += 1;
    }
    if (
      snapshot.divergenceNotes.includes(
        "CANONICAL_PERSISTED_DIFFERS_FROM_LEGACY_NORMALIZED",
      )
    ) {
      canonicalMismatch += 1;
    }
  }

  return {
    total,
    aligned,
    diverged,
    unresolved,
    overloadedLegacy,
    canonicalMismatch,
  };
}

function summarizeDecisionGateObservability(matches: Array<{
  decisionGateSnapshot?: DecisionGateSnapshot;
}>): AdminDecisionGateObservability {
  let total = 0;
  let canonicalGateEligible = 0;
  let canonicalGateUsed = 0;
  let legacyFallbackUsed = 0;
  let divergenceDetected = 0;
  let canonicalMissing = 0;
  let unresolved = 0;

  for (const item of matches) {
    const snapshot = item.decisionGateSnapshot;
    if (!snapshot) {
      continue;
    }
    total += 1;

    const hasCanonical = snapshot.canonicalMatchStatus !== null;
    const hasDivergence = snapshot.divergenceNotes.length > 0;
    const isUnresolved =
      snapshot.risks.includes("CANONICAL_STATUS_UNRESOLVED") ||
      snapshot.risks.includes("LEGACY_GATE_STATE_UNRESOLVED");

    if (hasCanonical) {
      canonicalGateEligible += 1;
      if (!hasDivergence) {
        canonicalGateUsed += 1;
      } else {
        legacyFallbackUsed += 1;
      }
    } else {
      canonicalMissing += 1;
      legacyFallbackUsed += 1;
    }

    if (hasDivergence) {
      divergenceDetected += 1;
    }
    if (isUnresolved) {
      unresolved += 1;
    }
  }

  return {
    total,
    canonicalGateEligible,
    canonicalGateUsed,
    legacyFallbackUsed,
    divergenceDetected,
    canonicalMissing,
    unresolved,
  };
}

function stringifyUnknown(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (_error) {
    return String(value);
  }
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
