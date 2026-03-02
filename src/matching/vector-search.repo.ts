import { Logger } from "../config/logger";
import { ProfilesRepository } from "../db/repositories/profiles.repo";

export interface VectorItem {
  userId: number;
  vector: number[];
  summaryText: string;
}

export interface VectorSearchResult {
  userId: number;
  similarity: number;
  summaryText: string;
}

interface VectorMetadata {
  entity_id: number;
  entity_type: "candidate" | "job";
  seniority?: string;
  location?: string;
  budget_range?: string;
  must_have?: string[];
}

export class VectorSearchRepository {
  private readonly candidateVectors = new Map<number, { vector: number[]; text: string; metadata: VectorMetadata }>();
  private readonly jobVectors = new Map<number, { vector: number[]; text: string; metadata: VectorMetadata }>();

  constructor(
    private readonly profilesRepository?: ProfilesRepository,
    private readonly logger?: Logger,
  ) {}

  searchTopK(queryVector: number[], items: ReadonlyArray<VectorItem>, topK: number): VectorSearchResult[] {
    const scored = items
      .map((item) => ({
        userId: item.userId,
        similarity: cosineSimilarity(queryVector, item.vector),
        summaryText: item.summaryText,
      }))
      .filter((item) => Number.isFinite(item.similarity))
      .sort((a, b) => b.similarity - a.similarity);

    return scored.slice(0, topK);
  }

  async upsertCandidateProfileVector(input: {
    telegramUserId: number;
    vector: number[];
    profileText: string;
    metadata: {
      seniority?: string;
      location?: string;
    };
  }): Promise<void> {
    const metadata: VectorMetadata = {
      entity_id: input.telegramUserId,
      entity_type: "candidate",
      seniority: input.metadata.seniority,
      location: input.metadata.location,
    };
    this.candidateVectors.set(input.telegramUserId, {
      vector: input.vector,
      text: input.profileText,
      metadata,
    });
    this.logger?.debug("vector.candidate.upserted", {
      telegramUserId: input.telegramUserId,
      vectorLength: input.vector.length,
    });
  }

  async upsertJobProfileVector(input: {
    telegramUserId: number;
    vector: number[];
    profileText: string;
    metadata: {
      seniority?: string;
      location?: string;
      budgetRange?: string;
      mustHave?: string[];
    };
  }): Promise<void> {
    const metadata: VectorMetadata = {
      entity_id: input.telegramUserId,
      entity_type: "job",
      seniority: input.metadata.seniority,
      location: input.metadata.location,
      budget_range: input.metadata.budgetRange,
      must_have: input.metadata.mustHave?.slice(0, 12) ?? [],
    };
    this.jobVectors.set(input.telegramUserId, {
      vector: input.vector,
      text: input.profileText,
      metadata,
    });
    this.logger?.debug("vector.job.upserted", {
      telegramUserId: input.telegramUserId,
      vectorLength: input.vector.length,
    });
  }
}

function cosineSimilarity(a: number[], b: number[]): number {
  const size = Math.min(a.length, b.length);
  if (size === 0) {
    return 0;
  }

  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let index = 0; index < size; index += 1) {
    dot += a[index] * b[index];
    normA += a[index] * a[index];
    normB += b[index] * b[index];
  }

  if (normA === 0 || normB === 0) {
    return 0;
  }

  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}
