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
    const trimmedResumeText = resumeText.slice(0, 16_000);
    const prompt = `${CANDIDATE_RESUME_ANALYSIS_V2_PROMPT}\n\n${trimmedResumeText}`;
    let parsed: Record<string, unknown>;
    try {
      parsed = await this.generateWithRetry(prompt);
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
        extractedText: trimmedResumeText,
      });
      return nonTechnical;
    }

    const technical = parsed as unknown as CandidateResumeAnalysisV2;
    await this.profilesRepository.saveCandidateResumeAnalysis({
      telegramUserId,
      rawResumeAnalysisJson: technical,
      profileStatus: "analysis_ready",
      extractedText: trimmedResumeText,
    });
    return technical;
  }

  private async generateWithRetry(prompt: string): Promise<Record<string, unknown>> {
    const maxAttempts = 3;
    const timeouts = [70_000, 90_000, 110_000];
    let lastErrorCode = "unknown";

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        prompt,
        maxTokens: 2200,
        timeoutMs: timeouts[attempt - 1] ?? 110_000,
        promptName: "candidate_resume_analysis_v2",
        schemaHint: "Candidate resume analysis v2 JSON schema.",
      });
      if (safe.ok) {
        return parseResumeAnalysis(JSON.stringify(safe.data));
      }

      lastErrorCode = safe.error_code;
      if (!isRetryableResumeAnalysisError(safe.error_code) || attempt >= maxAttempts) {
        break;
      }
      await sleepWithJitter(350, 950);
    }

    throw new Error(`candidate_resume_analysis_v2_failed:${lastErrorCode}`);
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

function isRetryableResumeAnalysisError(
  errorCode:
    | "missing_system_prompt"
    | "timeout"
    | "transient_failure"
    | "llm_failure"
    | "json_parse_failed"
    | "schema_invalid",
): boolean {
  return errorCode === "timeout" || errorCode === "transient_failure" || errorCode === "llm_failure";
}

async function sleepWithJitter(minMs: number, maxMs: number): Promise<void> {
  const min = Math.max(0, Math.floor(minMs));
  const max = Math.max(min, Math.floor(maxMs));
  const delay = min + Math.floor(Math.random() * (max - min + 1));
  await new Promise<void>((resolve) => setTimeout(resolve, delay));
}
