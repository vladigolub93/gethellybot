import { Logger } from "../../config/logger";
import { SupabaseRestClient } from "../supabase.client";

const QUALITY_FLAGS_TABLE = "quality_flags";

export interface QualityFlagRecordInput {
  entityType: "candidate" | "job" | "match";
  entityId: string;
  flag: string;
  details?: Record<string, unknown>;
}

export class QualityFlagsRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  async insertFlag(input: QualityFlagRecordInput): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    await this.supabaseClient.insert(QUALITY_FLAGS_TABLE, {
      entity_type: input.entityType,
      entity_id: input.entityId,
      flag: input.flag,
      details: input.details ?? {},
      created_at: new Date().toISOString(),
    });

    this.logger.info("Quality flag persisted", {
      entityType: input.entityType,
      entityId: input.entityId,
      flag: input.flag,
    });
  }
}
