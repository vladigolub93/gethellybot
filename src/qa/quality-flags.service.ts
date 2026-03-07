import { Logger } from "../config/logger";
import { QualityFlagRecordInput, QualityFlagsRepository } from "../db/repositories/quality-flags.repo";

export type QualityFlagName =
  | "resume_analysis_parse_failed"
  | "interview_plan_parse_failed"
  | "profile_update_parse_failed"
  | "excessive_follow_ups_loop_detected"
  | "follow_up_loop_prevented"
  | "too_many_low_answer_quality_in_row"
  | "candidate_ai_assisted_answer_likely"
  | "manager_ai_assisted_answer_likely"
  | "candidate_low_signal_answer"
  | "manager_low_signal_answer"
  | "matching_score_high_but_confidence_low"
  | "jd_analysis_high_ambiguity"
  | "guardrails_parse_failed"
  | "matching_decision_parse_failed";

export class QualityFlagsService {
  constructor(
    private readonly repository: QualityFlagsRepository,
    private readonly logger: Logger,
  ) {}

  async raise(input: {
    entityType: QualityFlagRecordInput["entityType"];
    entityId: string;
    flag: QualityFlagName;
    details?: Record<string, unknown>;
  }): Promise<void> {
    this.logger.warn("Quality flag raised", {
      entityType: input.entityType,
      entityId: input.entityId,
      flag: input.flag,
      details: input.details ?? {},
    });

    try {
      await this.repository.insertFlag({
        entityType: input.entityType,
        entityId: input.entityId,
        flag: input.flag,
        details: input.details,
      });
    } catch (error) {
      this.logger.warn("Failed to persist quality flag", {
        entityType: input.entityType,
        entityId: input.entityId,
        flag: input.flag,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }
}
