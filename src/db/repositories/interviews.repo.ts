import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";
import { PersistedInterviewRecord } from "../../storage/interview-storage.service";

const INTERVIEWS_TABLE = "interview_runs";

export class InterviewsRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  isEnabled(): boolean {
    return Boolean(this.supabaseClient);
  }

  async saveCompletedInterview(record: PersistedInterviewRecord): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const legacyPayload = {
      role: record.role,
      telegram_user_id: record.telegramUserId,
      started_at: record.startedAt,
      completed_at: record.completedAt,
      document_type: record.documentType,
      extracted_text: record.extractedText,
      plan_questions: record.planQuestions,
      answers: record.answers,
      final_artifact: record.finalArtifact,
      created_at: new Date().toISOString(),
    };

    const canonicalInterviewStatus =
      typeof record.canonicalInterviewStatus === "string" && record.canonicalInterviewStatus.trim()
        ? record.canonicalInterviewStatus.trim()
        : null;

    if (canonicalInterviewStatus) {
      try {
        await this.supabaseClient.insert(INTERVIEWS_TABLE, {
          ...legacyPayload,
          canonical_interview_status: canonicalInterviewStatus,
        });
        this.logger.debug("interview_lifecycle.canonical_persisted", {
          telegramUserId: record.telegramUserId,
          role: record.role,
          canonicalInterviewStatus,
        });
      } catch (error) {
        this.logger.warn("interview_lifecycle.canonical_persist_failed", {
          telegramUserId: record.telegramUserId,
          role: record.role,
          canonicalInterviewStatus,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        await this.supabaseClient.insert(INTERVIEWS_TABLE, legacyPayload);
      }
    } else {
      await this.supabaseClient.insert(INTERVIEWS_TABLE, legacyPayload);
    }

    this.logger.info("Interview persisted to Supabase", {
      telegramUserId: record.telegramUserId,
      role: record.role,
    });
  }
}
