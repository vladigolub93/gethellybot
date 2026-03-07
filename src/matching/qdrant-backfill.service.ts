import { EmbeddingsClient } from "../ai/embeddings.client";
import { Logger } from "../config/logger";
import { CandidateMatchSource, ProfilesRepository } from "../db/repositories/profiles.repo";
import { QdrantClient } from "./qdrant.client";

export class QdrantBackfillService {
  constructor(
    private readonly profilesRepository: ProfilesRepository,
    private readonly embeddingsClient: EmbeddingsClient,
    private readonly qdrantClient: QdrantClient | undefined,
    private readonly logger: Logger,
  ) {}

  isEnabled(): boolean {
    return Boolean(this.qdrantClient?.isEnabled());
  }

  async backfillExistingCandidates(limit = 500): Promise<{ requested: number; indexed: number }> {
    const qdrant = this.qdrantClient;
    if (!qdrant || !qdrant.isEnabled()) {
      return { requested: 0, indexed: 0 };
    }

    const candidateIds = await this.profilesRepository.listCandidateTelegramUserIds(limit);
    let indexed = 0;
    for (const candidateId of candidateIds) {
      const ok = await this.upsertCandidate(candidateId);
      if (ok) {
        indexed += 1;
      }
    }

    this.logger.info("qdrant.backfill.completed", {
      requested: candidateIds.length,
      indexed,
    });
    return { requested: candidateIds.length, indexed };
  }

  async upsertCandidate(candidateTelegramUserId: number): Promise<boolean> {
    const qdrant = this.qdrantClient;
    if (!qdrant || !qdrant.isEnabled()) {
      return false;
    }
    const source = await this.profilesRepository.getCandidateMatchSource(candidateTelegramUserId);
    if (!source) {
      return false;
    }
    return this.upsertCandidateFromSource(source);
  }

  async upsertCandidateFromSource(source: CandidateMatchSource): Promise<boolean> {
    const qdrant = this.qdrantClient;
    if (!qdrant || !qdrant.isEnabled()) {
      return false;
    }

    const embeddingText = buildCandidateEmbeddingText(source);
    if (!embeddingText.trim()) {
      return false;
    }

    try {
      const vector = await this.embeddingsClient.createEmbedding(embeddingText);
      await qdrant.upsertCandidateVector({
        candidateTelegramUserId: source.telegramUserId,
        vector,
        payload: {
          searchable_text: source.searchableText.slice(0, 500),
          seniority: source.resumeAnalysis.seniority_estimate,
          primary_direction: source.resumeAnalysis.primary_direction,
        },
      });
      return true;
    } catch (error) {
      this.logger.warn("qdrant.candidate.upsert.failed", {
        candidateTelegramUserId: source.telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return false;
    }
  }
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
