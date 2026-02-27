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

    await this.supabaseClient.insert(INTERVIEWS_TABLE, {
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
    });

    this.logger.info("Interview persisted to Supabase", {
      telegramUserId: record.telegramUserId,
      role: record.role,
    });
  }
}
