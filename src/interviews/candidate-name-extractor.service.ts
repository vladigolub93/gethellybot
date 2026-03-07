import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildExtractCandidateNameV1Prompt } from "../ai/prompts/candidate/extract-candidate-name.v1.prompt";
import { Logger } from "../config/logger";

export interface CandidateNameExtractionResult {
  firstName: string | null;
  lastName: string | null;
  confidence: number;
}

export class CandidateNameExtractorService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async extractFromResume(resumeText: string): Promise<CandidateNameExtractionResult | null> {
    const prompt = buildExtractCandidateNameV1Prompt({ resumeText });
    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 220,
      promptName: "extract_candidate_name_v1",
      schemaHint:
        "Candidate name JSON with first_name, last_name, full_name, confidence between 0 and 1.",
    });
    if (!safe.ok) {
      return null;
    }

    const firstName = normalizeNamePart(safe.data.first_name);
    const lastName = normalizeNamePart(safe.data.last_name);
    const confidence = normalizeConfidence(safe.data.confidence);
    if (!firstName && !lastName) {
      return null;
    }

    return {
      firstName,
      lastName,
      confidence,
    };
  }
}

function normalizeNamePart(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const collapsed = trimmed.replace(/\s+/g, " ");
  if (collapsed.length > 60) {
    return collapsed.slice(0, 60);
  }
  return collapsed;
}

function normalizeConfidence(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 0;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}
