import { Logger } from "../../config/logger";
import { CandidateProfile, JobProfile } from "../../shared/types/domain.types";
import { normalizeCandidateProfile, normalizeJobProfile } from "../../profiles/profile.schemas";
import {
  CandidateResumeAnalysisV2,
  CandidateResumeAnalysisV2Result,
} from "../../shared/types/candidate-analysis.types";
import { CandidateInterviewPlanV2 } from "../../shared/types/interview-plan.types";
import { CandidateTechnicalSummaryV1 } from "../../shared/types/candidate-summary.types";
import { SupabaseRestClient } from "../supabase.client";

const PROFILES_TABLE = "profiles";
const SEARCH_CANDIDATES_RPC = "search_candidate_profiles";

interface ProfileRow {
  telegram_user_id: number;
  kind: "candidate" | "job";
  profile_json: unknown;
  searchable_text: string;
  raw_resume_analysis_json?: unknown;
  technical_summary_json?: unknown;
  profile_status?: string | null;
  source_type?: unknown;
  source_text_original?: unknown;
  source_text_english?: unknown;
  telegram_file_id?: unknown;
  last_confirmation_one_liner?: unknown;
}

interface CandidateVectorSearchRow {
  telegram_user_id: number;
  similarity: number;
  profile_json: unknown;
  searchable_text: string;
}

export interface CandidateVectorSearchResult {
  telegramUserId: number;
  similarity: number;
  profile: CandidateProfile;
  searchableText: string;
  technicalSummary?: CandidateTechnicalSummaryV1 | null;
}

export interface CandidateMatchSource {
  telegramUserId: number;
  searchableText: string;
  resumeAnalysis: CandidateResumeAnalysisV2;
  technicalSummary: CandidateTechnicalSummaryV1 | null;
}

export class ProfilesRepository {
  constructor(
    private readonly logger: Logger,
    private readonly supabaseClient?: SupabaseRestClient,
  ) {}

  isEnabled(): boolean {
    return Boolean(this.supabaseClient);
  }

  async upsertCandidateProfile(input: {
    telegramUserId: number;
    profile: CandidateProfile;
    embedding?: number[];
  }): Promise<void> {
    await this.upsertProfile({
      telegramUserId: input.telegramUserId,
      kind: "candidate",
      profile: input.profile,
      searchableText: input.profile.searchableText,
      embedding: input.embedding,
      profileStatus: "active",
    });
  }

  async upsertJobProfile(input: {
    telegramUserId: number;
    profile: JobProfile;
    embedding?: number[];
  }): Promise<void> {
    await this.upsertProfile({
      telegramUserId: input.telegramUserId,
      kind: "job",
      profile: input.profile,
      searchableText: input.profile.searchableText,
      embedding: input.embedding,
    });
  }

  async saveCandidateResumeAnalysis(input: {
    telegramUserId: number;
    rawResumeAnalysisJson: CandidateResumeAnalysisV2Result;
    profileStatus: "analysis_ready" | "rejected_non_technical";
    extractedText: string;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,profile_json,searchable_text,raw_resume_analysis_json,profile_status",
    );

    const profileJson = existing?.profile_json ?? {};
    const searchableText =
      existing?.searchable_text?.trim() || input.extractedText.slice(0, 10000);

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
        profile_json: profileJson,
        searchable_text: searchableText,
        raw_resume_analysis_json: input.rawResumeAnalysisJson,
        profile_status: input.profileStatus,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );

    this.logger.info("Candidate resume analysis persisted to Supabase", {
      telegramUserId: input.telegramUserId,
      profileStatus: input.profileStatus,
    });
  }

  async saveCandidateInterviewPlanV2(input: {
    telegramUserId: number;
    plan: CandidateInterviewPlanV2;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,profile_json,searchable_text,raw_resume_analysis_json,profile_status",
    );

    const existingProfile = isRecord(existing?.profile_json)
      ? (existing.profile_json as Record<string, unknown>)
      : {};
    const profileJson = {
      ...existingProfile,
      candidateInterviewPlanV2: {
        interview_strategy: input.plan.interview_strategy,
        answer_instruction: input.plan.answer_instruction,
        questions: input.plan.questions,
        current_question_index: 0,
        created_at: new Date().toISOString(),
      },
    };

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
        profile_json: profileJson,
        searchable_text: existing?.searchable_text ?? "",
        raw_resume_analysis_json: existing?.raw_resume_analysis_json ?? null,
        profile_status: existing?.profile_status ?? "analysis_ready",
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );

    this.logger.info("Candidate interview plan v2 persisted to Supabase", {
      telegramUserId: input.telegramUserId,
      questions: input.plan.questions.length,
    });
  }

  async getCandidateResumeAnalysis(
    telegramUserId: number,
  ): Promise<CandidateResumeAnalysisV2Result | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,raw_resume_analysis_json",
    );

    if (!row || !row.raw_resume_analysis_json) {
      return null;
    }

    if (typeof row.raw_resume_analysis_json !== "object" || row.raw_resume_analysis_json === null) {
      return null;
    }

    const analysis = row.raw_resume_analysis_json as Record<string, unknown>;
    if (typeof analysis.is_technical !== "boolean") {
      return null;
    }

    return analysis as unknown as CandidateResumeAnalysisV2Result;
  }

  async saveCandidateTechnicalSummary(input: {
    telegramUserId: number;
    technicalSummary: CandidateTechnicalSummaryV1;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,profile_json,searchable_text,raw_resume_analysis_json,technical_summary_json,profile_status",
    );

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
        profile_json: existing?.profile_json ?? {},
        searchable_text: existing?.searchable_text ?? "",
        raw_resume_analysis_json: existing?.raw_resume_analysis_json ?? null,
        technical_summary_json: input.technicalSummary,
        profile_status: existing?.profile_status ?? "analysis_ready",
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );

    this.logger.info("Candidate technical summary persisted to Supabase", {
      telegramUserId: input.telegramUserId,
    });
  }

  async getCandidateTechnicalSummary(
    telegramUserId: number,
  ): Promise<CandidateTechnicalSummaryV1 | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,technical_summary_json",
    );
    if (!row || !row.technical_summary_json || !isRecord(row.technical_summary_json)) {
      return null;
    }

    const raw = row.technical_summary_json;
    const confidenceRaw =
      typeof raw.interview_confidence_level === "string"
        ? raw.interview_confidence_level.trim().toLowerCase()
        : "";
    const confidence: CandidateTechnicalSummaryV1["interview_confidence_level"] =
      confidenceRaw === "low" || confidenceRaw === "medium" || confidenceRaw === "high"
        ? confidenceRaw
        : "medium";

    return {
      headline: toText(raw.headline),
      technical_depth_summary: toText(raw.technical_depth_summary),
      architecture_and_scale: toText(raw.architecture_and_scale),
      domain_expertise: toText(raw.domain_expertise),
      ownership_and_authority: toText(raw.ownership_and_authority),
      strength_highlights: toStringArray(raw.strength_highlights),
      risk_flags: toStringArray(raw.risk_flags),
      interview_confidence_level: confidence,
      overall_assessment: toText(raw.overall_assessment),
    };
  }

  async listCandidateTelegramUserIds(limit = 200): Promise<number[]> {
    if (!this.supabaseClient) {
      return [];
    }

    const rows = await this.supabaseClient.selectMany<ProfileRow>(
      PROFILES_TABLE,
      {
        kind: "candidate",
      },
      "telegram_user_id,kind",
    );

    return rows
      .map((row) => Number(row.telegram_user_id))
      .filter((id) => Number.isInteger(id) && id > 0)
      .slice(0, Math.max(1, limit));
  }

  async getCandidateMatchSource(telegramUserId: number): Promise<CandidateMatchSource | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,searchable_text,raw_resume_analysis_json,technical_summary_json",
    );

    if (!row) {
      return null;
    }

    if (!isRecord(row.raw_resume_analysis_json)) {
      return null;
    }
    const rawAnalysis = row.raw_resume_analysis_json;
    if (rawAnalysis.is_technical !== true) {
      return null;
    }

    const technicalSummary = isRecord(row.technical_summary_json)
      ? ({
          headline: toText(row.technical_summary_json.headline),
          technical_depth_summary: toText(row.technical_summary_json.technical_depth_summary),
          architecture_and_scale: toText(row.technical_summary_json.architecture_and_scale),
          domain_expertise: toText(row.technical_summary_json.domain_expertise),
          ownership_and_authority: toText(row.technical_summary_json.ownership_and_authority),
          strength_highlights: toStringArray(row.technical_summary_json.strength_highlights),
          risk_flags: toStringArray(row.technical_summary_json.risk_flags),
          interview_confidence_level: normalizeConfidence(
            row.technical_summary_json.interview_confidence_level,
          ),
          overall_assessment: toText(row.technical_summary_json.overall_assessment),
        } as CandidateTechnicalSummaryV1)
      : null;

    return {
      telegramUserId,
      searchableText: row.searchable_text || "",
      resumeAnalysis: rawAnalysis as unknown as CandidateResumeAnalysisV2,
      technicalSummary,
    };
  }

  async getJobProfileByTelegramUserId(telegramUserId: number): Promise<JobProfile | null> {
    if (!this.supabaseClient) {
      return null;
    }

    const row = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: telegramUserId,
        kind: "job",
      },
      "telegram_user_id,kind,profile_json,searchable_text",
    );

    if (!row) {
      return null;
    }

    return normalizeJobProfile(String(telegramUserId), row.profile_json);
  }

  async searchCandidateProfilesByEmbedding(
    queryEmbedding: number[],
    topK: number,
  ): Promise<CandidateVectorSearchResult[]> {
    if (!this.supabaseClient) {
      return [];
    }

    const rows = await this.supabaseClient.rpc<CandidateVectorSearchRow>(
      SEARCH_CANDIDATES_RPC,
      {
        query_embedding: vectorLiteral(queryEmbedding),
        match_count: topK,
      },
    );

    return rows
      .map((row) => ({
        telegramUserId: Number(row.telegram_user_id),
        similarity: Number(row.similarity),
        searchableText: typeof row.searchable_text === "string" ? row.searchable_text : "",
        profile: normalizeCandidateProfile(String(row.telegram_user_id), row.profile_json),
      }))
      .filter(
        (row) =>
          Number.isInteger(row.telegramUserId) &&
          Number.isFinite(row.similarity) &&
          row.telegramUserId > 0,
      );
  }

  async saveCandidateResumeIntakeSource(input: {
    telegramUserId: number;
    sourceType: "file" | "text";
    sourceTextOriginal?: string | null;
    sourceTextEnglish?: string | null;
    telegramFileId?: string | null;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,profile_json,searchable_text,raw_resume_analysis_json,technical_summary_json,profile_status",
    );

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
        profile_json: existing?.profile_json ?? {},
        searchable_text: existing?.searchable_text ?? "",
        raw_resume_analysis_json: existing?.raw_resume_analysis_json ?? null,
        technical_summary_json: existing?.technical_summary_json ?? null,
        profile_status: existing?.profile_status ?? "analysis_ready",
        source_type: input.sourceType,
        source_text_original: normalizeNullableText(input.sourceTextOriginal),
        source_text_english: normalizeNullableText(input.sourceTextEnglish),
        telegram_file_id: normalizeNullableText(input.telegramFileId),
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );

    this.logger.info("Candidate resume intake source persisted to Supabase", {
      telegramUserId: input.telegramUserId,
      sourceType: input.sourceType,
      hasTelegramFileId: Boolean(input.telegramFileId),
      hasTextOriginal: Boolean(input.sourceTextOriginal?.trim()),
      hasTextEnglish: Boolean(input.sourceTextEnglish?.trim()),
    });
  }

  async saveLastConfirmationOneLiner(input: {
    telegramUserId: number;
    oneLiner: string;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    const existing = await this.supabaseClient.selectOne<ProfileRow>(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
      },
      "telegram_user_id,kind,profile_json,searchable_text,raw_resume_analysis_json,technical_summary_json,profile_status,source_type,source_text_original,source_text_english,telegram_file_id",
    );
    if (!existing) {
      return;
    }

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: "candidate",
        profile_json: existing.profile_json ?? {},
        searchable_text: existing.searchable_text ?? "",
        raw_resume_analysis_json: existing.raw_resume_analysis_json ?? null,
        technical_summary_json: existing.technical_summary_json ?? null,
        profile_status: existing.profile_status ?? "analysis_ready",
        source_type: existing.source_type ?? null,
        source_text_original: existing.source_text_original ?? null,
        source_text_english: existing.source_text_english ?? null,
        telegram_file_id: existing.telegram_file_id ?? null,
        last_confirmation_one_liner: input.oneLiner,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );
  }

  private async upsertProfile(input: {
    telegramUserId: number;
    kind: "candidate" | "job";
    profile: CandidateProfile | JobProfile;
    searchableText: string;
    embedding?: number[];
    profileStatus?: string;
  }): Promise<void> {
    if (!this.supabaseClient) {
      return;
    }

    await this.supabaseClient.upsert(
      PROFILES_TABLE,
      {
        telegram_user_id: input.telegramUserId,
        kind: input.kind,
        profile_json: input.profile,
        searchable_text: input.searchableText,
        embedding: vectorLiteral(input.embedding),
        profile_status: input.profileStatus ?? null,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "telegram_user_id,kind" },
    );

    this.logger.info("Profile persisted to Supabase", {
      telegramUserId: input.telegramUserId,
      kind: input.kind,
    });
  }
}

function vectorLiteral(embedding?: number[]): string | null {
  if (!embedding || embedding.length === 0) {
    return null;
  }
  const normalized = embedding
    .filter((value) => Number.isFinite(value))
    .map((value) => Number(value.toFixed(8)));
  if (normalized.length === 0) {
    return null;
  }
  return `[${normalized.join(",")}]`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => Boolean(item))
    .slice(0, 8);
}

function normalizeConfidence(value: unknown): CandidateTechnicalSummaryV1["interview_confidence_level"] {
  const normalized = toText(value).toLowerCase();
  if (normalized === "low" || normalized === "medium" || normalized === "high") {
    return normalized;
  }
  return "medium";
}

function normalizeNullableText(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}
