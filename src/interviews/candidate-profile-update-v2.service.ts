import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { CANDIDATE_PROFILE_UPDATE_V2_PROMPT } from "../ai/prompts/candidate/profile-update.v2.prompt";
import { Logger } from "../config/logger";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { QualityFlagsService } from "../qa/quality-flags.service";
import { CandidateResumeAnalysisV2 } from "../shared/types/candidate-analysis.types";
import { CandidateProfileUpdateV2 } from "../shared/types/interview-plan.types";

interface CandidateProfileUpdateInput {
  telegramUserId: number;
  currentQuestion: {
    id: string;
    text: string;
    questionType?: string;
    targetValidation?: string;
    basedOnField?: string;
  };
  answerText: string;
}

export class CandidateProfileUpdateV2Service {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly logger: Logger,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async updateFromAnswer(input: CandidateProfileUpdateInput): Promise<CandidateProfileUpdateV2 | null> {
    const currentAnalysis = await this.loadTechnicalAnalysis(input.telegramUserId);
    if (!currentAnalysis) {
      this.logger.warn("Candidate resume analysis v2 is missing during answer processing", {
        telegramUserId: input.telegramUserId,
      });
      return null;
    }

    const prompt = [
      CANDIDATE_PROFILE_UPDATE_V2_PROMPT,
      "",
      JSON.stringify(
        {
          original_resume_analysis: currentAnalysis,
          current_interview_question: {
            question_id: input.currentQuestion.id,
            question_text: input.currentQuestion.text,
            question_type: input.currentQuestion.questionType ?? "depth_test",
            target_validation: input.currentQuestion.targetValidation ?? "",
            based_on_field: input.currentQuestion.basedOnField ?? "",
          },
          candidate_answer_text: input.answerText,
        },
        null,
        2,
      ),
    ].join("\n");

    let parsed: CandidateProfileUpdateV2;
    try {
      parsed = await this.generateWithRetry(prompt);
    } catch (error) {
      await this.qualityFlagsService?.raise({
        entityType: "candidate",
        entityId: String(input.telegramUserId),
        flag: "profile_update_parse_failed",
        details: {
          error: error instanceof Error ? error.message : "Unknown error",
        },
      });
      throw error;
    }

    await this.profilesRepository.saveCandidateResumeAnalysis({
      telegramUserId: input.telegramUserId,
      rawResumeAnalysisJson: parsed.updated_resume_analysis,
      profileStatus: "analysis_ready",
      extractedText: "",
    });

    return parsed;
  }

  private async generateWithRetry(prompt: string): Promise<CandidateProfileUpdateV2> {
    const maxAttempts = 3;
    const timeouts = [40_000, 55_000, 70_000];
    let lastErrorCode = "unknown";

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 2600,
        timeoutMs: timeouts[attempt - 1] ?? 70_000,
        promptName: "candidate_profile_update_v2",
        schemaHint:
          "Candidate profile update v2 JSON with updated_resume_analysis, confidence_updates, contradiction_flags, answer_quality, authenticity_score, authenticity_label, authenticity_signals, depth_change_detected, follow_up_required, follow_up_focus.",
      });
      if (safe.ok) {
        return parseCandidateProfileUpdate(JSON.stringify(safe.data));
      }

      lastErrorCode = safe.error_code;
      this.logger.warn("candidate.profile.update.retry", {
        promptName: "candidate_profile_update_v2",
        attempt,
        errorCode: safe.error_code,
      });
      if (!isRetryableProfileUpdateError(safe.error_code) || attempt >= maxAttempts) {
        break;
      }
      await sleepWithJitter(300, 900);
    }

    throw new Error(`candidate_profile_update_v2_failed:${lastErrorCode}`);
  }

  private async loadTechnicalAnalysis(telegramUserId: number): Promise<CandidateResumeAnalysisV2 | null> {
    const analysis = await this.profilesRepository.getCandidateResumeAnalysis(telegramUserId);
    if (!analysis || !analysis.is_technical) {
      return null;
    }
    return analysis;
  }
}

function parseCandidateProfileUpdate(raw: string): CandidateProfileUpdateV2 {
  const parsed = parseJsonObject(raw);

  if (!isRecord(parsed.updated_resume_analysis)) {
    throw new Error("Candidate profile update v2 output is invalid: missing updated_resume_analysis.");
  }
  if (parsed.updated_resume_analysis.is_technical !== true) {
    throw new Error(
      "Candidate profile update v2 output is invalid: updated_resume_analysis.is_technical must be true.",
    );
  }

  const confidenceUpdates = Array.isArray(parsed.confidence_updates)
    ? parsed.confidence_updates
        .filter((item): item is Record<string, unknown> => isRecord(item))
        .map((item) => ({
          field: toText(item.field),
          previous_value: toText(item.previous_value),
          new_value: toText(item.new_value),
          reason: toText(item.reason),
        }))
    : [];

  const contradictionFlags = Array.isArray(parsed.contradiction_flags)
    ? parsed.contradiction_flags.map((item) => toText(item)).filter(Boolean)
    : [];

  const answerQualityRaw = toText(parsed.answer_quality).toLowerCase();
  const answerQuality: CandidateProfileUpdateV2["answer_quality"] =
    answerQualityRaw === "low" || answerQualityRaw === "medium" || answerQualityRaw === "high"
      ? answerQualityRaw
      : "medium";

  const authenticityScore = toNumberInRange(parsed.authenticity_score, 0, 1, 0.5);
  const authenticityLabelRaw = toText(parsed.authenticity_label).toLowerCase();
  const authenticityLabel: CandidateProfileUpdateV2["authenticity_label"] =
    authenticityLabelRaw === "likely_human" ||
    authenticityLabelRaw === "uncertain" ||
    authenticityLabelRaw === "likely_ai_assisted"
      ? authenticityLabelRaw
      : "uncertain";
  const authenticitySignals = Array.isArray(parsed.authenticity_signals)
    ? parsed.authenticity_signals.map((item) => toText(item)).filter(Boolean).slice(0, 6)
    : [];

  if (typeof parsed.depth_change_detected !== "boolean") {
    throw new Error("Candidate profile update v2 output is invalid: depth_change_detected must be boolean.");
  }
  if (typeof parsed.follow_up_required !== "boolean") {
    throw new Error("Candidate profile update v2 output is invalid: follow_up_required must be boolean.");
  }

  return {
    updated_resume_analysis: parsed.updated_resume_analysis as unknown as CandidateResumeAnalysisV2,
    confidence_updates: confidenceUpdates,
    contradiction_flags: contradictionFlags,
    answer_quality: answerQuality,
    authenticity_score: authenticityScore,
    authenticity_label: authenticityLabel,
    authenticity_signals: authenticitySignals,
    depth_change_detected: parsed.depth_change_detected,
    follow_up_required: parsed.follow_up_required,
    follow_up_focus: parsed.follow_up_focus === null ? null : toText(parsed.follow_up_focus) || null,
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Candidate profile update v2 output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toNumberInRange(value: unknown, min: number, max: number, fallback: number): number {
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : Number.NaN;
  if (!Number.isFinite(numeric)) {
    return fallback;
  }
  if (numeric < min) {
    return min;
  }
  if (numeric > max) {
    return max;
  }
  return numeric;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isRetryableProfileUpdateError(
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
