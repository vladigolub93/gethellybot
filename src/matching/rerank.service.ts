import { LlmClient } from "../ai/llm.client";
import { buildRerankPrompt } from "../ai/prompts/rerank.prompt";

export interface InitialRankedCandidate {
  candidateUserId: number;
  similarityScore: number;
  summaryText: string;
}

export interface RerankedCandidate {
  candidateUserId: number;
  score: number;
  explanation: string;
}

interface RerankResponseShape {
  ranked?: Array<{
    candidateUserId?: number;
    score?: number;
    explanation?: string;
  }>;
}

export class RerankService {
  constructor(private readonly llmClient: LlmClient) {}

  async rerank(jobSummary: string, initial: ReadonlyArray<InitialRankedCandidate>): Promise<RerankedCandidate[]> {
    if (initial.length === 0) {
      return [];
    }

    const prompt = buildRerankPrompt(
      jobSummary,
      initial.map((candidate) => ({
        candidateUserId: candidate.candidateUserId,
        similarityScore: Number(candidate.similarityScore.toFixed(4)),
        summaryText: candidate.summaryText.slice(0, 350),
      })),
    );

    const raw = await this.llmClient.generateStructuredJson(prompt, 360);
    const parsed = parseRerankResponse(raw);
    if (parsed.length === 0) {
      throw new Error("Rerank response did not contain candidates.");
    }

    const allowedIds = new Set(initial.map((candidate) => candidate.candidateUserId));
    const sanitized = parsed
      .filter((item) => allowedIds.has(item.candidateUserId))
      .map((item) => ({
        candidateUserId: item.candidateUserId,
        score: clamp(item.score, 0, 1),
        explanation: item.explanation.slice(0, 180),
      }))
      .sort((a, b) => b.score - a.score);

    return sanitized;
  }
}

function parseRerankResponse(raw: string): RerankedCandidate[] {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Rerank output is not a JSON object.");
  }

  const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as RerankResponseShape;
  const ranked = Array.isArray(parsed.ranked) ? parsed.ranked : [];

  return ranked
    .map((item) => ({
      candidateUserId: Number(item.candidateUserId),
      score: Number(item.score),
      explanation: typeof item.explanation === "string" ? item.explanation.trim() : "",
    }))
    .filter(
      (item) =>
        Number.isInteger(item.candidateUserId) &&
        Number.isFinite(item.score) &&
        Boolean(item.explanation),
    );
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) {
    return min;
  }
  if (value > max) {
    return max;
  }
  return value;
}
