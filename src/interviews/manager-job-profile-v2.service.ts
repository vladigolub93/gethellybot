import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { JOB_PROFILE_UPDATE_V2_PROMPT } from "../ai/prompts/manager/job-profile-update.v2.prompt";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { QualityFlagsService } from "../qa/quality-flags.service";
import {
  JobDescriptionAnalysisV1Result,
} from "../shared/types/job-analysis.types";
import { JobProfileUpdateV2, JobProfileV2 } from "../shared/types/job-profile.types";

interface ManagerJobProfileUpdateInput {
  managerTelegramUserId: number;
  currentQuestionText: string;
  managerAnswerText: string;
}

export class ManagerJobProfileV2Service {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly jobsRepository: JobsRepository,
    private readonly qualityFlagsService?: QualityFlagsService,
  ) {}

  async updateFromAnswer(input: ManagerJobProfileUpdateInput): Promise<JobProfileUpdateV2> {
    const currentProfile = await this.getOrInitializeJobProfile(input.managerTelegramUserId);
    const prompt = [
      JOB_PROFILE_UPDATE_V2_PROMPT,
      "",
      JSON.stringify(
        {
          current_job_profile: currentProfile,
          current_interview_question_text: input.currentQuestionText,
          hiring_manager_answer_text: input.managerAnswerText,
        },
        null,
        2,
      ),
    ].join("\n");

    let parsed: JobProfileUpdateV2;
    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        prompt,
        maxTokens: 2600,
        promptName: "manager_job_profile_update_v2",
        schemaHint:
          "Job profile update v2 JSON with updated_job_profile, profile_updates, contradiction_flags, answer_quality, authenticity_score, authenticity_label, authenticity_signals, follow_up_required, follow_up_focus.",
      });
      if (!safe.ok) {
        throw new Error(`manager_job_profile_update_v2_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      parsed = parseJobProfileUpdateV2(raw, currentProfile);
    } catch (error) {
      await this.qualityFlagsService?.raise({
        entityType: "job",
        entityId: String(input.managerTelegramUserId),
        flag: "profile_update_parse_failed",
        details: {
          error: error instanceof Error ? error.message : "Unknown error",
        },
      });
      throw error;
    }

    await this.jobsRepository.saveJobProfileV2({
      managerTelegramUserId: input.managerTelegramUserId,
      jobProfileV2: parsed.updated_job_profile,
    });

    return parsed;
  }

  async getCurrentJobProfile(managerTelegramUserId: number): Promise<JobProfileV2 | null> {
    return this.jobsRepository.getJobProfileV2(managerTelegramUserId);
  }

  private async getOrInitializeJobProfile(managerTelegramUserId: number): Promise<JobProfileV2> {
    const existing = await this.jobsRepository.getJobProfileV2(managerTelegramUserId);
    if (existing) {
      return existing;
    }

    const analysis = await this.jobsRepository.getJobDescriptionAnalysis(managerTelegramUserId);
    const mapped = mapJobAnalysisToProfileV2Internal(analysis);
    await this.jobsRepository.saveJobProfileV2({
      managerTelegramUserId,
      jobProfileV2: mapped,
    });
    return mapped;
  }
}

function parseJobProfileUpdateV2(raw: string, fallbackProfile: JobProfileV2): JobProfileUpdateV2 {
  const parsed = parseJsonObject(raw);
  const updated = isRecord(parsed.updated_job_profile)
    ? normalizeJobProfileV2(parsed.updated_job_profile)
    : fallbackProfile;
  const profileUpdates = Array.isArray(parsed.profile_updates)
    ? parsed.profile_updates
        .filter((item): item is Record<string, unknown> => isRecord(item))
        .map((item) => ({
          field: toText(item.field),
          previous_value: toText(item.previous_value),
          new_value: toText(item.new_value),
          reason: toText(item.reason),
        }))
    : [];
  const contradictionFlags = toStringArray(parsed.contradiction_flags);
  const qualityRaw = toText(parsed.answer_quality).toLowerCase();
  const answerQuality: JobProfileUpdateV2["answer_quality"] =
    qualityRaw === "low" || qualityRaw === "medium" || qualityRaw === "high"
      ? qualityRaw
      : "medium";
  const authenticityScore = toNumberInRange(parsed.authenticity_score, 0, 1, 0.5);
  const authenticityLabelRaw = toText(parsed.authenticity_label).toLowerCase();
  const authenticityLabel: JobProfileUpdateV2["authenticity_label"] =
    authenticityLabelRaw === "likely_human" ||
    authenticityLabelRaw === "uncertain" ||
    authenticityLabelRaw === "likely_ai_assisted"
      ? authenticityLabelRaw
      : "uncertain";
  const authenticitySignals = toStringArray(parsed.authenticity_signals).slice(0, 6);
  const followUpRequired = typeof parsed.follow_up_required === "boolean" ? parsed.follow_up_required : false;
  const followUpFocus = parsed.follow_up_focus === null ? null : toText(parsed.follow_up_focus) || null;

  return {
    updated_job_profile: updated,
    profile_updates: profileUpdates,
    contradiction_flags: contradictionFlags,
    answer_quality: answerQuality,
    authenticity_score: authenticityScore,
    authenticity_label: authenticityLabel,
    authenticity_signals: authenticitySignals,
    follow_up_required: followUpRequired,
    follow_up_focus: followUpFocus,
  };
}

function mapJobAnalysisToProfileV2Internal(analysis: JobDescriptionAnalysisV1Result | null): JobProfileV2 {
  if (!analysis || !analysis.is_technical_role) {
    return createEmptyJobProfileV2();
  }

  return {
    role_title: analysis.role_title_guess,
    product_context: {
      product_type: analysis.product_context.product_type,
      company_stage: analysis.product_context.company_stage,
      what_the_product_does: analysis.product_context.what_the_product_does,
      users_or_customers: analysis.product_context.users_or_customers,
    },
    work_scope: {
      current_tasks: analysis.work_scope.current_tasks,
      current_challenges: analysis.work_scope.current_challenges,
      deliverables_or_outcomes: analysis.work_scope.deliverables_or_outcomes,
    },
    technology_map: {
      core: analysis.technology_signal_map.likely_core.map((tech) => ({
        technology: tech,
        required_depth: "working",
        mandatory: true as const,
      })),
      secondary: analysis.technology_signal_map.likely_secondary.map((tech) => ({
        technology: tech,
        required_depth: "basic",
        mandatory: false as const,
      })),
      discarded_or_noise: analysis.technology_signal_map.likely_noise_or_unclear,
    },
    architecture_and_scale: {
      architecture_style: analysis.architecture_and_scale.architecture_style,
      distributed_systems: analysis.architecture_and_scale.distributed_systems,
      high_load: analysis.architecture_and_scale.high_load,
      scale_clues: analysis.architecture_and_scale.scale_clues,
    },
    domain_requirements: {
      primary_domain: analysis.domain_inference.primary_domain,
      domain_depth_required: analysis.domain_inference.domain_depth_required_guess,
      regulatory_or_constraints: null,
    },
    ownership_expectation: {
      decision_authority_required: analysis.ownership_expectation_guess.decision_authority_required,
      production_responsibility: analysis.ownership_expectation_guess.production_responsibility,
    },
    non_negotiables: analysis.requirements.non_negotiables_guess,
    flexible_requirements: analysis.requirements.flexible_or_nice_to_have_guess,
    constraints: analysis.requirements.constraints,
  };
}

function normalizeJobProfileV2(raw: Record<string, unknown>): JobProfileV2 {
  return {
    role_title: toNullableText(raw.role_title),
    product_context: {
      product_type: normalizeEnum(readNested(raw, "product_context", "product_type"), [
        "b2b",
        "b2c",
        "internal",
        "platform",
        "unknown",
      ]) as JobProfileV2["product_context"]["product_type"],
      company_stage: normalizeEnum(readNested(raw, "product_context", "company_stage"), [
        "early_startup",
        "growth",
        "enterprise",
        "unknown",
      ]) as JobProfileV2["product_context"]["company_stage"],
      what_the_product_does: toNullableText(readNested(raw, "product_context", "what_the_product_does")),
      users_or_customers: toNullableText(readNested(raw, "product_context", "users_or_customers")),
    },
    work_scope: {
      current_tasks: toNestedStringArray(raw, "work_scope", "current_tasks"),
      current_challenges: toNestedStringArray(raw, "work_scope", "current_challenges"),
      deliverables_or_outcomes: toNestedStringArray(raw, "work_scope", "deliverables_or_outcomes"),
    },
    technology_map: {
      core: toTechArray(readNested(raw, "technology_map", "core"), true),
      secondary: toTechArray(readNested(raw, "technology_map", "secondary"), false),
      discarded_or_noise: toNestedStringArray(raw, "technology_map", "discarded_or_noise"),
    },
    architecture_and_scale: {
      architecture_style: normalizeEnum(readNested(raw, "architecture_and_scale", "architecture_style"), [
        "microservices",
        "monolith",
        "event_driven",
        "mixed",
        "unknown",
      ]) as JobProfileV2["architecture_and_scale"]["architecture_style"],
      distributed_systems: normalizeEnum(
        readNested(raw, "architecture_and_scale", "distributed_systems"),
        ["yes", "no", "unknown"],
      ) as JobProfileV2["architecture_and_scale"]["distributed_systems"],
      high_load: normalizeEnum(readNested(raw, "architecture_and_scale", "high_load"), [
        "yes",
        "no",
        "unknown",
      ]) as JobProfileV2["architecture_and_scale"]["high_load"],
      scale_clues: toNestedStringArray(raw, "architecture_and_scale", "scale_clues"),
    },
    domain_requirements: {
      primary_domain: toNullableText(readNested(raw, "domain_requirements", "primary_domain")),
      domain_depth_required: normalizeEnum(
        readNested(raw, "domain_requirements", "domain_depth_required"),
        ["none", "helpful", "important", "critical", "unknown"],
      ) as JobProfileV2["domain_requirements"]["domain_depth_required"],
      regulatory_or_constraints: toNullableText(
        readNested(raw, "domain_requirements", "regulatory_or_constraints"),
      ),
    },
    ownership_expectation: {
      decision_authority_required: normalizeEnum(
        readNested(raw, "ownership_expectation", "decision_authority_required"),
        ["executor", "contributor", "owner", "technical_lead", "unknown"],
      ) as JobProfileV2["ownership_expectation"]["decision_authority_required"],
      production_responsibility: normalizeEnum(
        readNested(raw, "ownership_expectation", "production_responsibility"),
        ["yes", "no", "unknown"],
      ) as JobProfileV2["ownership_expectation"]["production_responsibility"],
    },
    non_negotiables: toStringArray(raw.non_negotiables),
    flexible_requirements: toStringArray(raw.flexible_requirements),
    constraints: toStringArray(raw.constraints),
  };
}

function createEmptyJobProfileV2(): JobProfileV2 {
  return {
    role_title: null,
    product_context: {
      product_type: "unknown",
      company_stage: "unknown",
      what_the_product_does: null,
      users_or_customers: null,
    },
    work_scope: {
      current_tasks: [],
      current_challenges: [],
      deliverables_or_outcomes: [],
    },
    technology_map: {
      core: [],
      secondary: [],
      discarded_or_noise: [],
    },
    architecture_and_scale: {
      architecture_style: "unknown",
      distributed_systems: "unknown",
      high_load: "unknown",
      scale_clues: [],
    },
    domain_requirements: {
      primary_domain: null,
      domain_depth_required: "unknown",
      regulatory_or_constraints: null,
    },
    ownership_expectation: {
      decision_authority_required: "unknown",
      production_responsibility: "unknown",
    },
    non_negotiables: [],
    flexible_requirements: [],
    constraints: [],
  };
}

function toTechArray(
  value: unknown,
  mandatory: true,
): Array<{ technology: string; required_depth: "basic" | "working" | "strong" | "expert"; mandatory: true }>;
function toTechArray(
  value: unknown,
  mandatory: false,
): Array<{ technology: string; required_depth: "basic" | "working" | "strong" | "expert"; mandatory: false }>;
function toTechArray(
  value: unknown,
  mandatory: boolean,
): Array<{ technology: string; required_depth: "basic" | "working" | "strong" | "expert"; mandatory: boolean }> {
  if (!Array.isArray(value)) {
    return [];
  }
  const depthAllowed = ["basic", "working", "strong", "expert"];
  const result: Array<{ technology: string; required_depth: "basic" | "working" | "strong" | "expert"; mandatory: boolean }> =
    [];
  for (const item of value) {
    if (!isRecord(item)) {
      continue;
    }
    const technology = toText(item.technology);
    if (!technology) {
      continue;
    }
    const requiredDepthRaw = toText(item.required_depth).toLowerCase();
    const requiredDepth = depthAllowed.includes(requiredDepthRaw)
      ? (requiredDepthRaw as "basic" | "working" | "strong" | "expert")
      : "working";
    result.push({
      technology,
      required_depth: requiredDepth,
      mandatory,
    });
  }
  return result.slice(0, 30);
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Job profile update output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toNullableText(value: unknown): string | null {
  const text = toText(value);
  return text || null;
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter((item) => Boolean(item))
    .slice(0, 30);
}

function readNested(source: Record<string, unknown>, key: string, nestedKey: string): unknown {
  const nested = source[key];
  if (!isRecord(nested)) {
    return undefined;
  }
  return nested[nestedKey];
}

function toNestedStringArray(source: Record<string, unknown>, key: string, nestedKey: string): string[] {
  return toStringArray(readNested(source, key, nestedKey));
}

function normalizeEnum(value: unknown, allowed: string[]): string {
  const normalized = toText(value).toLowerCase();
  if (allowed.includes(normalized)) {
    return normalized;
  }
  return "unknown";
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

export function mapJobAnalysisToProfileV2(
  analysis: JobDescriptionAnalysisV1Result | null,
): JobProfileV2 {
  return mapJobAnalysisToProfileV2Internal(analysis);
}
