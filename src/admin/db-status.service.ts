import { Logger } from "../config/logger";
import { SupabaseRestClient } from "../db/supabase.client";

interface SchemaSnapshotRow {
  table_name: string;
  columns: string[] | null;
}

interface AppliedMigrationsRow {
  applied_migrations_count: number | null;
}

export interface DbStatusReport {
  ok: boolean;
  missing_tables: string[];
  missing_columns: Array<{
    table: string;
    column: string;
  }>;
  applied_migrations_count: number;
}

const REQUIRED_SCHEMA: Record<string, string[]> = {
  users: [
    "telegram_user_id",
    "telegram_username",
    "role",
    "preferred_language",
    "onboarding_completed",
    "first_match_explained",
    "phone_number",
    "first_name",
    "last_name",
    "contact_shared",
    "contact_shared_at",
    "matching_paused",
    "matching_paused_at",
    "auto_matching_enabled",
    "auto_notify_enabled",
    "candidate_country",
    "candidate_city",
    "candidate_work_mode",
    "candidate_salary_amount",
    "candidate_salary_currency",
    "candidate_salary_period",
    "candidate_profile_complete",
    "updated_at",
  ],
  user_states: [
    "telegram_user_id",
    "chat_id",
    "role",
    "state",
    "state_payload",
    "last_bot_message",
    "updated_at",
  ],
  interview_runs: [
    "role",
    "telegram_user_id",
    "started_at",
    "completed_at",
    "document_type",
    "extracted_text",
    "plan_questions",
    "answers",
    "final_artifact",
  ],
  profiles: [
    "telegram_user_id",
    "kind",
    "profile_json",
    "searchable_text",
    "embedding",
    "raw_resume_analysis_json",
    "technical_summary_json",
    "profile_status",
    "source_type",
    "source_text_original",
    "source_text_english",
    "telegram_file_id",
    "last_confirmation_one_liner",
    "updated_at",
  ],
  jobs: [
    "manager_telegram_user_id",
    "status",
    "job_summary",
    "job_profile",
    "source_type",
    "source_text_original",
    "source_text_english",
    "telegram_file_id",
    "job_analysis_json",
    "manager_interview_plan_json",
    "job_profile_json",
    "technical_summary_json",
    "job_work_format",
    "job_remote_countries",
    "job_remote_worldwide",
    "job_budget_min",
    "job_budget_max",
    "job_budget_currency",
    "job_budget_period",
    "job_profile_complete",
    "last_confirmation_one_liner",
    "updated_at",
  ],
  matches: [
    "id",
    "job_id",
    "candidate_id",
    "manager_telegram_user_id",
    "candidate_telegram_user_id",
    "job_summary",
    "candidate_summary",
    "job_technical_summary_json",
    "candidate_technical_summary_json",
    "score",
    "total_score",
    "breakdown_json",
    "reasons_json",
    "explanation_json",
    "matching_decision_json",
    "candidate_decision",
    "manager_decision",
    "status",
    "created_at",
    "updated_at",
  ],
  telegram_updates: ["update_id", "telegram_user_id", "received_at"],
  notification_limits: [
    "telegram_user_id",
    "role",
    "last_candidate_notify_at",
    "last_manager_notify_at",
    "daily_count",
    "daily_reset_at",
  ],
  quality_flags: ["entity_type", "entity_id", "flag", "details", "created_at"],
  data_deletion_requests: [
    "telegram_user_id",
    "telegram_username",
    "reason",
    "status",
    "requested_at",
    "updated_at",
  ],
};

export class DbStatusService {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async getStatus(): Promise<DbStatusReport> {
    if (!this.supabaseClient) {
      return {
        ok: false,
        missing_tables: Object.keys(REQUIRED_SCHEMA),
        missing_columns: [],
        applied_migrations_count: 0,
      };
    }

    try {
      const [snapshotRows, migrationRows] = await Promise.all([
        this.supabaseClient.rpc<SchemaSnapshotRow>("get_db_schema_snapshot", {}),
        this.supabaseClient.rpc<AppliedMigrationsRow>("get_applied_migrations_count", {}),
      ]);

      const schemaMap = new Map<string, Set<string>>();
      for (const row of snapshotRows) {
        const columns = Array.isArray(row.columns) ? row.columns : [];
        schemaMap.set(row.table_name, new Set(columns.map((item) => item.trim())));
      }

      const missingTables: string[] = [];
      const missingColumns: Array<{ table: string; column: string }> = [];
      for (const [table, columns] of Object.entries(REQUIRED_SCHEMA)) {
        const existing = schemaMap.get(table);
        if (!existing) {
          missingTables.push(table);
          continue;
        }
        for (const column of columns) {
          if (!existing.has(column)) {
            missingColumns.push({ table, column });
          }
        }
      }

      const appliedCount = Number(
        migrationRows[0]?.applied_migrations_count ?? 0,
      );
      const report: DbStatusReport = {
        ok: missingTables.length === 0 && missingColumns.length === 0,
        missing_tables: missingTables,
        missing_columns: missingColumns,
        applied_migrations_count:
          Number.isFinite(appliedCount) && appliedCount >= 0 ? appliedCount : 0,
      };
      return report;
    } catch (error) {
      this.logger.error("DB status check failed", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        ok: false,
        missing_tables: Object.keys(REQUIRED_SCHEMA),
        missing_columns: [],
        applied_migrations_count: 0,
      };
    }
  }
}
