import { LlmClient } from "../ai/llm.client";
import { MATCHING_EXPLANATION_V1_PROMPT } from "../ai/prompts/matching/matching-explanation.v1.prompt";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { MatchBreakdownV2, MatchReasonsV2, MatchingExplanationV1 } from "../shared/types/matching.types";

export class MatchingExplanationService {
  constructor(private readonly llmClient: LlmClient) {}

  async generate(input: {
    jobTechnicalSummary: JobTechnicalSummaryV2 | null;
    candidateTechnicalSummary: CandidateTechnicalSummaryV1 | null;
    deterministicScore: number;
    breakdown: MatchBreakdownV2;
    reasons: MatchReasonsV2;
  }): Promise<MatchingExplanationV1> {
    const prompt = [
      MATCHING_EXPLANATION_V1_PROMPT,
      "",
      JSON.stringify(
        {
          job_technical_summary: input.jobTechnicalSummary,
          candidate_technical_summary: input.candidateTechnicalSummary,
          deterministic_score: input.deterministicScore,
          breakdown: input.breakdown,
          reasons: input.reasons,
        },
        null,
        2,
      ),
    ].join("\n");

    const raw = await this.llmClient.generateStructuredJson(prompt, 700);
    return parseExplanation(raw);
  }
}

function parseExplanation(raw: string): MatchingExplanationV1 {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Matching explanation output is not valid JSON.");
  }

  const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
  const messageForCandidate = toText(parsed.message_for_candidate);
  const messageForManager = toText(parsed.message_for_manager);
  const question = toText(parsed.one_suggested_live_question);

  if (!messageForCandidate || !messageForManager || !question) {
    throw new Error("Matching explanation output is invalid: missing required fields.");
  }

  return {
    message_for_candidate: messageForCandidate,
    message_for_manager: messageForManager,
    one_suggested_live_question: question,
  };
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
