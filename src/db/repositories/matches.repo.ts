import { Logger } from "../../config/logger";
import { MatchRecord } from "../../decisions/match.types";
import { SupabaseRestClient } from "../supabase.client";

const MATCHES_TABLE = "matches";

export class MatchesRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async upsertMatch(record: MatchRecord): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const legacyPayload = this.buildLegacyPayload(record);
    const canonicalMatchStatus =
      typeof record.canonicalMatchStatus === "string" && record.canonicalMatchStatus.trim()
        ? record.canonicalMatchStatus.trim()
        : null;

    if (canonicalMatchStatus) {
      try {
        await this.supabaseClient.upsert(
          MATCHES_TABLE,
          {
            ...legacyPayload,
            canonical_match_status: canonicalMatchStatus,
          },
          { onConflict: "id" },
        );
        this.logger.debug("match_lifecycle.canonical_persisted", {
          matchId: record.id,
          canonicalMatchStatus,
        });
      } catch (error) {
        this.logger.warn("match_lifecycle.canonical_persist_failed", {
          matchId: record.id,
          canonicalMatchStatus,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        await this.supabaseClient.upsert(
          MATCHES_TABLE,
          legacyPayload,
          { onConflict: "id" },
        );
      }
    } else {
      await this.supabaseClient.upsert(
        MATCHES_TABLE,
        legacyPayload,
        { onConflict: "id" },
      );
    }

    this.logger.debug("Match persisted to Supabase", {
      matchId: record.id,
      managerTelegramUserId: record.managerUserId,
      candidateTelegramUserId: record.candidateUserId,
      status: record.status,
    });
  }

  private buildLegacyPayload(record: MatchRecord): Record<string, unknown> {
    return {
      id: record.id,
      job_id: record.jobId ?? null,
      candidate_id: record.candidateId ?? null,
      manager_telegram_user_id: record.managerUserId,
      candidate_telegram_user_id: record.candidateUserId,
      job_summary: record.jobSummary,
      job_technical_summary_json: record.jobTechnicalSummary ?? null,
      candidate_summary: record.candidateSummary,
      candidate_technical_summary_json: record.candidateTechnicalSummary ?? null,
      total_score: Math.round(record.score),
      breakdown_json: record.breakdown ?? null,
      reasons_json: record.reasons ?? null,
      explanation_json: record.explanationJson ?? null,
      matching_decision_json: record.matchingDecision ?? null,
      score: record.score,
      explanation: record.explanation,
      candidate_decision: record.candidateDecision,
      manager_decision: record.managerDecision,
      status: record.status,
      created_at: record.createdAt,
      updated_at: record.updatedAt,
    };
  }
}
