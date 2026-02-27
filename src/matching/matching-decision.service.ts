import { LlmClient } from "../ai/llm.client";
import { MATCHING_DECISION_V1_PROMPT } from "../ai/prompts/matching/matching-decision.v1.prompt";
import { Logger } from "../config/logger";
import { QualityFlagsService } from "../qa/quality-flags.service";
import { MatchBreakdownV2 } from "../shared/types/matching.types";
import { MatchingDecisionV1 } from "../shared/types/matching-decision.types";

export class MatchingDecisionService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async decide(input: {
    managerUserId: number;
    candidateUserId: number;
    matchScore: number;
    breakdown: MatchBreakdownV2;
    hardFilterFailed: boolean;
    candidateUnresolvedRiskFlags: string[];
    candidateInterviewConfidence: "low" | "medium" | "high";
    jobActiveStatus: boolean;
    candidateActivityRecencyHours: number | null;
    managerActivityRecencyHours: number | null;
    candidateCooldownStatus: boolean;
    managerCooldownStatus: boolean;
    candidatePreviouslyRejectedSameJob: boolean;
    managerPreviouslySkippedSameCandidate: boolean;
  }): Promise<MatchingDecisionV1> {
    const prompt = [
      MATCHING_DECISION_V1_PROMPT,
      "",
      JSON.stringify(
        {
          match_score: input.matchScore,
          breakdown: input.breakdown,
          hard_filter_failed: input.hardFilterFailed,
          candidate_unresolved_risk_flags: input.candidateUnresolvedRiskFlags,
          candidate_interview_confidence: input.candidateInterviewConfidence,
          job_active_status: input.jobActiveStatus,
          candidate_activity_recency_hours: input.candidateActivityRecencyHours,
          manager_activity_recency_hours: input.managerActivityRecencyHours,
          candidate_cooldown_status: input.candidateCooldownStatus,
          manager_cooldown_status: input.managerCooldownStatus,
          candidate_previously_rejected_same_job: input.candidatePreviouslyRejectedSameJob,
          manager_previously_skipped_same_candidate: input.managerPreviouslySkippedSameCandidate,
        },
        null,
        2,
      ),
    ].join("\n");

    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 320, {
        promptName: "matching_decision_v1",
      });
      const parsed = parseDecision(raw);
      this.logger.info("Matching decision generated", {
        managerUserId: input.managerUserId,
        candidateUserId: input.candidateUserId,
        notifyCandidate: parsed.notify_candidate,
        notifyManager: parsed.notify_manager,
        priority: parsed.priority,
      });
      return parsed;
    } catch (error) {
      await this.qualityFlagsService?.raise({
        entityType: "match",
        entityId: `${input.managerUserId}:${input.candidateUserId}`,
        flag: "matching_decision_parse_failed",
        details: {
          error: error instanceof Error ? error.message : "Unknown error",
        },
      });
      this.logger.warn("Matching decision parse failed, using fallback decision", {
        managerUserId: input.managerUserId,
        candidateUserId: input.candidateUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });

      return buildFallbackDecision(input);
    }
  }
}

function parseDecision(raw: string): MatchingDecisionV1 {
  const parsed = parseJsonObject(raw);

  if (typeof parsed.notify_candidate !== "boolean") {
    throw new Error("Matching decision output missing notify_candidate.");
  }
  if (typeof parsed.notify_manager !== "boolean") {
    throw new Error("Matching decision output missing notify_manager.");
  }

  const priority = toText(parsed.priority).toLowerCase();
  if (priority !== "low" && priority !== "normal" && priority !== "high") {
    throw new Error("Matching decision output invalid priority.");
  }

  const messageLength = toText(parsed.message_length).toLowerCase();
  if (messageLength !== "short" && messageLength !== "standard") {
    throw new Error("Matching decision output invalid message_length.");
  }

  const cooldownHoursCandidate = toNonNegativeNumber(parsed.cooldown_hours_candidate);
  const cooldownHoursManager = toNonNegativeNumber(parsed.cooldown_hours_manager);
  const reason = toText(parsed.reason);

  if (!reason) {
    throw new Error("Matching decision output missing reason.");
  }

  return {
    notify_candidate: parsed.notify_candidate,
    notify_manager: parsed.notify_manager,
    priority,
    message_length: messageLength,
    cooldown_hours_candidate: cooldownHoursCandidate,
    cooldown_hours_manager: cooldownHoursManager,
    reason,
  };
}

function buildFallbackDecision(input: {
  matchScore: number;
  hardFilterFailed: boolean;
  jobActiveStatus: boolean;
  candidatePreviouslyRejectedSameJob: boolean;
  managerPreviouslySkippedSameCandidate: boolean;
}): MatchingDecisionV1 {
  if (
    input.hardFilterFailed ||
    !input.jobActiveStatus ||
    input.candidatePreviouslyRejectedSameJob ||
    input.managerPreviouslySkippedSameCandidate
  ) {
    return {
      notify_candidate: false,
      notify_manager: false,
      priority: "low",
      message_length: "short",
      cooldown_hours_candidate: 24,
      cooldown_hours_manager: 24,
      reason: "Suppressed by deterministic fallback constraints.",
    };
  }

  return {
    notify_candidate: input.matchScore >= 70,
    notify_manager: false,
    priority: input.matchScore >= 85 ? "high" : "normal",
    message_length: input.matchScore >= 80 ? "standard" : "short",
    cooldown_hours_candidate: 12,
    cooldown_hours_manager: 6,
    reason: "Fallback decision applied from score thresholds.",
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Matching decision output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toNonNegativeNumber(value: unknown): number {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numberValue) || numberValue < 0) {
    throw new Error("Matching decision output contains invalid cooldown value.");
  }
  return Math.round(numberValue);
}
