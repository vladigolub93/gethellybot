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

    await this.supabaseClient.upsert(
      MATCHES_TABLE,
      {
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
      },
      { onConflict: "id" },
    );

    this.logger.debug("Match persisted to Supabase", {
      matchId: record.id,
      managerTelegramUserId: record.managerUserId,
      candidateTelegramUserId: record.candidateUserId,
      status: record.status,
    });
  }
}
