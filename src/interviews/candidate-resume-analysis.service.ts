import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { CANDIDATE_RESUME_ANALYSIS_V2_PROMPT } from "../ai/prompts/candidate/resume-analysis.v2.prompt";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { QualityFlagsService } from "../qa/quality-flags.service";
import {
  CandidateResumeAnalysisV2,
  CandidateResumeAnalysisV2Result,
} from "../shared/types/candidate-analysis.types";

export class CandidateResumeAnalysisService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async analyzeAndPersist(
    telegramUserId: number,
    resumeText: string,
  ): Promise<CandidateResumeAnalysisV2Result> {
    const prompt = `${CANDIDATE_RESUME_ANALYSIS_V2_PROMPT}\n\n${resumeText}`;
    let parsed: Record<string, unknown>;
    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        prompt,
        maxTokens: 2200,
        promptName: "candidate_resume_analysis_v2",
        schemaHint: "Candidate resume analysis v2 JSON schema.",
      });
      if (!safe.ok) {
        throw new Error(`candidate_resume_analysis_v2_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      parsed = parseResumeAnalysis(raw);
    } catch (error) {
      await this.qualityFlagsService?.raise({
        entityType: "candidate",
        entityId: String(telegramUserId),
        flag: "resume_analysis_parse_failed",
        details: {
          error: error instanceof Error ? error.message : "Unknown error",
        },
      });
      throw error;
    }

    if (!Object.prototype.hasOwnProperty.call(parsed, "is_technical")) {
      throw new Error("Resume analysis response is invalid: missing is_technical.");
    }

    if (typeof parsed.is_technical !== "boolean") {
      throw new Error("Resume analysis response is invalid: is_technical must be boolean.");
    }

    const isTechnical = parsed.is_technical;
    if (!isTechnical) {
      const nonTechnical: CandidateResumeAnalysisV2Result = {
        is_technical: false,
        reason: "Non-technical profile",
      };
      await this.profilesRepository.saveCandidateResumeAnalysis({
        telegramUserId,
        rawResumeAnalysisJson: nonTechnical,
        profileStatus: "rejected_non_technical",
        extractedText: resumeText,
      });
      return nonTechnical;
    }

    const technical = parsed as unknown as CandidateResumeAnalysisV2;
    await this.profilesRepository.saveCandidateResumeAnalysis({
      telegramUserId,
      rawResumeAnalysisJson: technical,
      profileStatus: "analysis_ready",
      extractedText: resumeText,
    });
    return technical;
  }
}

function parseResumeAnalysis(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Resume analysis output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}
