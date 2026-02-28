import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { CANDIDATE_TECHNICAL_SUMMARY_V1_PROMPT } from "../ai/prompts/candidate/candidate-summary.v1.prompt";
import { CandidateResumeAnalysisV2 } from "../shared/types/candidate-analysis.types";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";

export interface CandidateInterviewConfidenceUpdate {
  field: string;
  previous_value: string;
  new_value: string;
  reason: string;
}

export class CandidateTechnicalSummaryService {
  constructor(private readonly llmClient: LlmClient) {}

  async generateCandidateTechnicalSummary(
    updatedResumeAnalysis: CandidateResumeAnalysisV2,
    confidenceUpdates: CandidateInterviewConfidenceUpdate[],
    contradictionFlags: string[],
  ): Promise<CandidateTechnicalSummaryV1> {
    const prompt = [
      CANDIDATE_TECHNICAL_SUMMARY_V1_PROMPT,
      "",
      JSON.stringify(
        {
          updated_resume_analysis: updatedResumeAnalysis,
          confidence_updates: confidenceUpdates,
          contradiction_flags: contradictionFlags,
        },
        null,
        2,
      ),
    ].join("\n");

    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      prompt,
      maxTokens: 1200,
      promptName: "candidate_technical_summary_v1",
      schemaHint:
        "Candidate technical summary JSON with headline, technical_depth_summary, architecture_and_scale, domain_expertise, ownership_and_authority, strength_highlights, risk_flags, interview_confidence_level, overall_assessment.",
    });
    if (!safe.ok) {
      throw new Error(`candidate_technical_summary_v1_failed:${safe.error_code}`);
    }
    const raw = JSON.stringify(safe.data);
    return parseCandidateTechnicalSummary(raw);
  }
}

function parseCandidateTechnicalSummary(raw: string): CandidateTechnicalSummaryV1 {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Candidate technical summary output is not valid JSON.");
  }

  const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
  const confidenceRaw = toText(parsed.interview_confidence_level).toLowerCase();
  const interviewConfidenceLevel: CandidateTechnicalSummaryV1["interview_confidence_level"] =
    confidenceRaw === "low" || confidenceRaw === "medium" || confidenceRaw === "high"
      ? confidenceRaw
      : "medium";

  const summary: CandidateTechnicalSummaryV1 = {
    headline: toText(parsed.headline),
    technical_depth_summary: toText(parsed.technical_depth_summary),
    architecture_and_scale: toText(parsed.architecture_and_scale),
    domain_expertise: toText(parsed.domain_expertise),
    ownership_and_authority: toText(parsed.ownership_and_authority),
    strength_highlights: toStringArray(parsed.strength_highlights, 6),
    risk_flags: toStringArray(parsed.risk_flags, 6),
    interview_confidence_level: interviewConfidenceLevel,
    overall_assessment: toText(parsed.overall_assessment),
  };

  if (
    !summary.headline ||
    !summary.technical_depth_summary ||
    !summary.architecture_and_scale ||
    !summary.domain_expertise ||
    !summary.ownership_and_authority ||
    !summary.overall_assessment
  ) {
    throw new Error("Candidate technical summary output is invalid: missing required fields.");
  }

  return summary;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toStringArray(value: unknown, max = 6): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter((item) => Boolean(item))
    .slice(0, max);
}
