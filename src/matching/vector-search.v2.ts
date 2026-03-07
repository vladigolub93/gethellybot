import { EmbeddingsClient } from "../ai/embeddings.client";
import { Logger } from "../config/logger";
import { CandidateMatchSource, ProfilesRepository } from "../db/repositories/profiles.repo";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { InterviewStorageService } from "../storage/interview-storage.service";
import { QdrantClient } from "./qdrant.client";
import { VectorItem, VectorSearchRepository } from "./vector-search.repo";

const DEFAULT_SHORTLIST_TOP_N = 50;
const FALLBACK_DB_LIMIT = 200;
const QDRANT_INDEX_SYNC_LIMIT = 300;

export class VectorSearchV2 {
  constructor(
    private readonly embeddingsClient: EmbeddingsClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly vectorSearchRepository: VectorSearchRepository,
    private readonly storage: InterviewStorageService,
    private readonly logger: Logger,
    private readonly qdrantClient?: QdrantClient,
  ) {}

  async shortlistCandidateIds(input: {
    jobProfile: JobProfileV2;
    jobTechnicalSummary: JobTechnicalSummaryV2 | null;
    topN?: number;
  }): Promise<number[]> {
    const topN = input.topN ?? DEFAULT_SHORTLIST_TOP_N;
    const jobEmbeddingText = buildJobEmbeddingText(input.jobProfile, input.jobTechnicalSummary);
    if (!jobEmbeddingText) {
      return [];
    }

    try {
      const queryEmbedding = await this.embeddingsClient.createEmbedding(jobEmbeddingText);
      if (this.qdrantClient?.isEnabled()) {
        const qdrantIds = await this.shortlistFromQdrant(queryEmbedding, topN);
        if (qdrantIds.length > 0) {
          return qdrantIds;
        }
      }

      if (this.profilesRepository.isEnabled()) {
        const rows = await this.profilesRepository.searchCandidateProfilesByEmbedding(
          queryEmbedding,
          topN,
        );
        const ids = rows
          .map((row) => row.telegramUserId)
          .filter((id) => Number.isInteger(id) && id > 0);
        if (ids.length > 0) {
          return dedupe(ids).slice(0, topN);
        }
      }

      return this.shortlistFromCandidateEmbeddings(queryEmbedding, topN);
    } catch (error) {
      this.logger.warn("Vector shortlist failed, using fallback candidate list", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return this.fallbackCandidateIds(topN);
    }
  }

  private async shortlistFromCandidateEmbeddings(queryEmbedding: number[], topN: number): Promise<number[]> {
    const candidateIds = await this.profilesRepository.listCandidateTelegramUserIds(FALLBACK_DB_LIMIT);
    const vectorItems: VectorItem[] = [];

    for (const candidateId of candidateIds) {
      const source = await this.profilesRepository.getCandidateMatchSource(candidateId);
      if (!source) {
        continue;
      }

      try {
        const embeddingText = buildCandidateEmbeddingText(source);
        const vector = await this.embeddingsClient.createEmbedding(embeddingText);
        vectorItems.push({
          userId: candidateId,
          vector,
          summaryText: embeddingText,
        });
      } catch (error) {
        this.logger.warn("Candidate embedding fallback failed, skipping candidate", {
          candidateId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    if (vectorItems.length === 0) {
      return this.fallbackCandidateIds(topN);
    }

    const top = this.vectorSearchRepository.searchTopK(queryEmbedding, vectorItems, topN);
    return dedupe(top.map((item) => item.userId)).slice(0, topN);
  }

  private async fallbackCandidateIds(topN: number): Promise<number[]> {
    const dbCandidates = await this.profilesRepository.listCandidateTelegramUserIds(FALLBACK_DB_LIMIT);
    if (dbCandidates.length > 0) {
      return dedupe(dbCandidates).slice(0, topN);
    }

    const localCandidates = await this.storage.listByRole("candidate");
    return dedupe(localCandidates.map((item) => item.telegramUserId)).slice(0, topN);
  }

  private async shortlistFromQdrant(queryEmbedding: number[], topN: number): Promise<number[]> {
    const qdrant = this.qdrantClient;
    if (!qdrant || !qdrant.isEnabled()) {
      return [];
    }

    try {
      const direct = await qdrant.searchCandidateIds({
        vector: queryEmbedding,
        limit: topN,
      });
      if (direct.length > 0) {
        this.logger.info("Vector shortlist from Qdrant", {
          topN,
          resultCount: direct.length,
        });
        return dedupe(direct).slice(0, topN);
      }

      await this.syncCandidatesToQdrant(QDRANT_INDEX_SYNC_LIMIT);
      const afterSync = await qdrant.searchCandidateIds({
        vector: queryEmbedding,
        limit: topN,
      });
      if (afterSync.length > 0) {
        this.logger.info("Vector shortlist from Qdrant after sync", {
          topN,
          resultCount: afterSync.length,
        });
      }
      return dedupe(afterSync).slice(0, topN);
    } catch (error) {
      this.logger.warn("Qdrant shortlist failed, fallback to Supabase and local search", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return [];
    }
  }

  private async syncCandidatesToQdrant(limit: number): Promise<void> {
    const qdrant = this.qdrantClient;
    if (!qdrant || !qdrant.isEnabled()) {
      return;
    }
    const candidateIds = await this.profilesRepository.listCandidateTelegramUserIds(limit);
    let synced = 0;
    for (const candidateId of candidateIds) {
      const source = await this.profilesRepository.getCandidateMatchSource(candidateId);
      if (!source) {
        continue;
      }
      const embeddingText = buildCandidateEmbeddingText(source);
      if (!embeddingText.trim()) {
        continue;
      }
      try {
        const vector = await this.embeddingsClient.createEmbedding(embeddingText);
        await qdrant.upsertCandidateVector({
          candidateTelegramUserId: candidateId,
          vector,
          payload: {
            searchable_text: source.searchableText.slice(0, 400),
            seniority: source.resumeAnalysis.seniority_estimate,
            primary_direction: source.resumeAnalysis.primary_direction,
          },
        });
        synced += 1;
      } catch (error) {
        this.logger.debug("Qdrant candidate upsert skipped", {
          candidateId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }
    this.logger.info("Qdrant candidate sync completed", {
      requested: candidateIds.length,
      synced,
    });
  }
}

function buildJobEmbeddingText(
  jobProfile: JobProfileV2,
  jobTechnicalSummary: JobTechnicalSummaryV2 | null,
): string {
  return [
    jobTechnicalSummary?.headline ?? "",
    jobTechnicalSummary?.product_context ?? "",
    jobTechnicalSummary?.core_tech.join(", ") ?? "",
    jobTechnicalSummary?.key_requirements.join(", ") ?? "",
    jobProfile.role_title ?? "",
    jobProfile.work_scope.current_tasks.join(", "),
    jobProfile.work_scope.current_challenges.join(", "),
    jobProfile.technology_map.core.map((item) => item.technology).join(", "),
    jobProfile.domain_requirements.primary_domain ?? "",
    jobProfile.ownership_expectation.decision_authority_required,
  ]
    .filter((item) => Boolean(item))
    .join(" | ")
    .slice(0, 4000);
}

function buildCandidateEmbeddingText(source: CandidateMatchSource): string {
  const analysis = source.resumeAnalysis;
  return [
    source.technicalSummary?.headline ?? "",
    source.technicalSummary?.technical_depth_summary ?? "",
    source.searchableText,
    analysis.primary_direction,
    analysis.seniority_estimate,
    analysis.skill_depth_classification.deep_experience.join(", "),
    analysis.skill_depth_classification.working_experience.join(", "),
    analysis.domain_expertise.map((item) => item.domain).join(", "),
    analysis.impact_indicators.join(", "),
  ]
    .filter((item) => Boolean(item))
    .join(" | ")
    .slice(0, 4000);
}

function dedupe(values: ReadonlyArray<number>): number[] {
  return Array.from(new Set(values.filter((value) => Number.isInteger(value) && value > 0)));
}
