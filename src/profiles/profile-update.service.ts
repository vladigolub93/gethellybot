import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildProfileSummaryV2Prompt } from "../ai/prompts/profile-summary-v2.prompt";
import { EmbeddingsClient } from "../ai/embeddings.client";
import { LlmClient } from "../ai/llm.client";
import { Logger } from "../config/logger";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { CandidateResumeAnalysisV2Result } from "../shared/types/candidate-analysis.types";
import { JobDescriptionAnalysisV1Result } from "../shared/types/job-analysis.types";
import { VectorSearchRepository } from "../matching/vector-search.repo";
import {
  CandidateProfileV2,
  JobProfileV2,
  ProfileFactV2,
  createEmptyCandidateProfileV2,
  createEmptyJobProfileV2,
  normalizeCandidateProfileV2,
  normalizeJobProfileV2,
} from "./profile.schemas";
import { CandidateClaimExtractionResult } from "../interviews/prescreen/candidate-prescreen.schemas";
import { JobClaimExtractionResult } from "../interviews/prescreen/job-prescreen.schemas";

interface ProfileSummaryPromptResult {
  profile_text: string;
}

export class ProfileUpdateService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly embeddingsClient: EmbeddingsClient,
    private readonly profilesRepository: ProfilesRepository,
    private readonly vectorSearchRepository: VectorSearchRepository,
    private readonly logger: Logger,
  ) {}

  async updateCandidateProfileFromResumeExtract(input: {
    telegramUserId: number;
    resumeAnalysis: CandidateResumeAnalysisV2Result | null;
    claimExtraction: CandidateClaimExtractionResult | null;
    languagePreference?: CandidateProfileV2["identity"]["language_preference"];
    contactPhone?: string | null;
    name?: string | null;
  }): Promise<{ profileJson: CandidateProfileV2; profileText: string }> {
    const existing = await this.profilesRepository.getCanonicalCandidateProfileV2(input.telegramUserId);
    let profile = normalizeCandidateProfileV2(
      existing.profileJson ?? createEmptyCandidateProfileV2(input.telegramUserId),
      input.telegramUserId,
    );

    profile.identity.language_preference = input.languagePreference ?? profile.identity.language_preference;
    profile.identity.contact_phone = input.contactPhone ?? profile.identity.contact_phone;
    profile.identity.name = input.name ?? profile.identity.name;

    if (input.claimExtraction) {
      if (input.claimExtraction.candidate_name) {
        profile.identity.name = input.claimExtraction.candidate_name;
      }
      if (input.claimExtraction.primary_roles.length > 0) {
        profile.roles.primary = dedupeStrings([
          ...profile.roles.primary,
          ...input.claimExtraction.primary_roles,
        ]).slice(0, 8);
      }
      for (const domain of input.claimExtraction.domains) {
        profile = upsertDomain(profile, domain.name, domain.confidence);
      }
      for (const claim of input.claimExtraction.tech_claims) {
        const techName = normalizeTechName(claim.tech);
        if (!techName) {
          continue;
        }
        const current = profile.tech[techName] ?? {
          used_directly: null,
          depth: null,
          ownership: null,
          last_used: null,
        };
        profile.tech[techName] = {
          ...current,
          depth: current.depth ?? mapClaimStrengthToDepth(claim.claim_strength),
          used_directly: current.used_directly ?? true,
        };
        profile.evidence = dedupeStrings([
          ...profile.evidence,
          claim.evidence_snippet,
        ]).slice(0, 20);
      }
    }

    if (input.resumeAnalysis && input.resumeAnalysis.is_technical) {
      profile.seniority.estimate = mapCandidateSeniority(input.resumeAnalysis.seniority_estimate);
      profile.seniority.confidence = Math.max(profile.seniority.confidence, 0.65);
      if (typeof input.resumeAnalysis.total_experience_years_estimate === "number") {
        profile.experience_notes = upsertShortNote(
          profile.experience_notes,
          `Total experience estimate: ${input.resumeAnalysis.total_experience_years_estimate} years.`,
        );
      }
      const deep = input.resumeAnalysis.skill_depth_classification.deep_experience ?? [];
      const working = input.resumeAnalysis.skill_depth_classification.working_experience ?? [];
      for (const tech of [...deep, ...working]) {
        const techName = normalizeTechName(tech);
        if (!techName) {
          continue;
        }
        const current = profile.tech[techName] ?? {
          used_directly: null,
          depth: null,
          ownership: null,
          last_used: null,
        };
        profile.tech[techName] = {
          ...current,
          used_directly: current.used_directly ?? true,
          depth: current.depth ?? (deep.includes(tech) ? "high" : "medium"),
        };
      }
      for (const domain of input.resumeAnalysis.domain_expertise ?? []) {
        profile = upsertDomain(profile, domain.domain, domain.confidence);
      }
    }

    const profileText = await this.generateProfileText({
      entityType: "candidate",
      profileJson: profile,
      fallback: buildCandidateProfileTextFallback(profile),
    });
    const embedding = await this.safeEmbedding(profileText);

    await this.profilesRepository.upsertCanonicalCandidateProfileV2({
      telegramUserId: input.telegramUserId,
      profileJson: profile,
      profileText,
      embedding,
      embeddingMetadata: {
        entity_id: input.telegramUserId,
        entity_type: "candidate",
        seniority: profile.seniority.estimate,
        location: [profile.location.city, profile.location.country].filter(Boolean).join(", "),
      },
    });
    if (embedding) {
      await this.vectorSearchRepository.upsertCandidateProfileVector({
        telegramUserId: input.telegramUserId,
        vector: embedding,
        profileText,
        metadata: {
          seniority: profile.seniority.estimate,
          location: [profile.location.city, profile.location.country].filter(Boolean).join(", "),
        },
      });
    }
    return { profileJson: profile, profileText };
  }

  async updateCandidateProfileFromAnswerFacts(input: {
    telegramUserId: number;
    facts: ProfileFactV2[];
    notes?: string | null;
  }): Promise<{ profileJson: CandidateProfileV2; profileText: string }> {
    const existing = await this.profilesRepository.getCanonicalCandidateProfileV2(input.telegramUserId);
    let profile = normalizeCandidateProfileV2(
      existing.profileJson ?? createEmptyCandidateProfileV2(input.telegramUserId),
      input.telegramUserId,
    );
    profile = applyCandidateFacts(profile, input.facts);
    if (input.notes?.trim()) {
      profile.experience_notes = upsertShortNote(profile.experience_notes, input.notes);
    }

    const profileText = await this.generateProfileText({
      entityType: "candidate",
      profileJson: profile,
      fallback: buildCandidateProfileTextFallback(profile),
    });
    const embedding = await this.safeEmbedding(profileText);
    await this.profilesRepository.upsertCanonicalCandidateProfileV2({
      telegramUserId: input.telegramUserId,
      profileJson: profile,
      profileText,
      embedding,
      embeddingMetadata: {
        entity_id: input.telegramUserId,
        entity_type: "candidate",
        seniority: profile.seniority.estimate,
        location: [profile.location.city, profile.location.country].filter(Boolean).join(", "),
      },
    });
    if (embedding) {
      await this.vectorSearchRepository.upsertCandidateProfileVector({
        telegramUserId: input.telegramUserId,
        vector: embedding,
        profileText,
        metadata: {
          seniority: profile.seniority.estimate,
          location: [profile.location.city, profile.location.country].filter(Boolean).join(", "),
        },
      });
    }
    return { profileJson: profile, profileText };
  }

  async updateJobProfileFromJdExtract(input: {
    telegramUserId: number;
    jdAnalysis: JobDescriptionAnalysisV1Result | null;
    claimExtraction: JobClaimExtractionResult | null;
  }): Promise<{ profileJson: JobProfileV2; profileText: string }> {
    const existing = await this.profilesRepository.getCanonicalJobProfileV2(input.telegramUserId);
    let profile = normalizeJobProfileV2(existing.profileJson ?? createEmptyJobProfileV2());

    if (input.claimExtraction) {
      profile.identity.job_title = input.claimExtraction.role_title || profile.identity.job_title;
      profile.work_format.mode = input.claimExtraction.work_format;
      profile.work_format.allowed_countries = dedupeStrings([
        ...profile.work_format.allowed_countries,
        ...input.claimExtraction.allowed_countries,
      ]).slice(0, 24);
      profile.must_have = dedupeStrings([
        ...profile.must_have,
        ...input.claimExtraction.must_have.map((item) => item.skill),
      ]).slice(0, 8);
      profile.nice_to_have = dedupeStrings([
        ...profile.nice_to_have,
        ...input.claimExtraction.nice_to_have.map((item) => item.skill),
      ]).slice(0, 8);
      profile.key_tasks = dedupeStrings([
        ...profile.key_tasks,
        ...input.claimExtraction.key_tasks,
      ]).slice(0, 8);
      profile.constraints = dedupeStrings([
        ...profile.constraints,
        ...input.claimExtraction.risks_or_uncertainties,
      ]).slice(0, 16);
      profile.product_context.product_type = input.claimExtraction.product_type;
      if (input.claimExtraction.budget) {
        profile.budget = {
          currency: input.claimExtraction.budget.currency,
          min: input.claimExtraction.budget.min,
          max: input.claimExtraction.budget.max,
          period: input.claimExtraction.budget.period,
        };
      }
      for (const domain of input.claimExtraction.domain) {
        profile = upsertJobDomain(profile, domain.name, domain.confidence);
      }
      profile.team.size = input.claimExtraction.team.size;
      profile.team.composition = input.claimExtraction.team.composition;
      if (input.claimExtraction.team.timezone) {
        profile.work_format.allowed_timezones = dedupeStrings([
          ...profile.work_format.allowed_timezones,
          input.claimExtraction.team.timezone,
        ]).slice(0, 12);
      }
    }

    if (input.jdAnalysis && input.jdAnalysis.is_technical_role) {
      profile.identity.job_title = profile.identity.job_title || input.jdAnalysis.role_title_guess || "";
      profile.key_tasks = dedupeStrings([
        ...profile.key_tasks,
        ...input.jdAnalysis.work_scope.current_tasks,
      ]).slice(0, 8);
      profile.constraints = dedupeStrings([
        ...profile.constraints,
        ...input.jdAnalysis.missing_critical_information,
      ]).slice(0, 16);
      if (input.jdAnalysis.domain_inference.primary_domain) {
        profile = upsertJobDomain(profile, input.jdAnalysis.domain_inference.primary_domain, 0.65);
      }
    }

    const profileText = await this.generateProfileText({
      entityType: "job",
      profileJson: profile,
      fallback: buildJobProfileTextFallback(profile),
    });
    const embedding = await this.safeEmbedding(profileText);

    await this.profilesRepository.upsertCanonicalJobProfileV2({
      telegramUserId: input.telegramUserId,
      profileJson: profile,
      profileText,
      embedding,
      embeddingMetadata: {
        entity_id: input.telegramUserId,
        entity_type: "job",
        seniority: profile.identity.job_title,
        location: profile.work_format.allowed_countries.join(", "),
        budget_range: profile.budget ? `${profile.budget.min ?? "?"}-${profile.budget.max ?? "?"} ${profile.budget.currency}/${profile.budget.period}` : undefined,
        must_have: profile.must_have,
      },
    });
    if (embedding) {
      await this.vectorSearchRepository.upsertJobProfileVector({
        telegramUserId: input.telegramUserId,
        vector: embedding,
        profileText,
        metadata: {
          seniority: profile.identity.job_title,
          location: profile.work_format.allowed_countries.join(", "),
          budgetRange: profile.budget
            ? `${profile.budget.min ?? "?"}-${profile.budget.max ?? "?"} ${profile.budget.currency}/${profile.budget.period}`
            : "unknown",
          mustHave: profile.must_have,
        },
      });
    }
    return { profileJson: profile, profileText };
  }

  async updateJobProfileFromAnswerFacts(input: {
    telegramUserId: number;
    facts: ProfileFactV2[];
    notes?: string | null;
  }): Promise<{ profileJson: JobProfileV2; profileText: string }> {
    const existing = await this.profilesRepository.getCanonicalJobProfileV2(input.telegramUserId);
    let profile = normalizeJobProfileV2(existing.profileJson ?? createEmptyJobProfileV2());
    profile = applyJobFacts(profile, input.facts);
    if (input.notes?.trim()) {
      profile.constraints = upsertShortNote(profile.constraints, input.notes);
    }

    const profileText = await this.generateProfileText({
      entityType: "job",
      profileJson: profile,
      fallback: buildJobProfileTextFallback(profile),
    });
    const embedding = await this.safeEmbedding(profileText);
    await this.profilesRepository.upsertCanonicalJobProfileV2({
      telegramUserId: input.telegramUserId,
      profileJson: profile,
      profileText,
      embedding,
      embeddingMetadata: {
        entity_id: input.telegramUserId,
        entity_type: "job",
        seniority: profile.identity.job_title,
        location: profile.work_format.allowed_countries.join(", "),
        budget_range: profile.budget ? `${profile.budget.min ?? "?"}-${profile.budget.max ?? "?"} ${profile.budget.currency}/${profile.budget.period}` : undefined,
        must_have: profile.must_have,
      },
    });
    if (embedding) {
      await this.vectorSearchRepository.upsertJobProfileVector({
        telegramUserId: input.telegramUserId,
        vector: embedding,
        profileText,
        metadata: {
          seniority: profile.identity.job_title,
          location: profile.work_format.allowed_countries.join(", "),
          budgetRange: profile.budget
            ? `${profile.budget.min ?? "?"}-${profile.budget.max ?? "?"} ${profile.budget.currency}/${profile.budget.period}`
            : "unknown",
          mustHave: profile.must_have,
        },
      });
    }
    return { profileJson: profile, profileText };
  }

  private async generateProfileText(input: {
    entityType: "candidate" | "job";
    profileJson: unknown;
    fallback: string;
  }): Promise<string> {
    const prompt = buildProfileSummaryV2Prompt({
      entityType: input.entityType,
      profileJson: input.profileJson,
    });
    const safe = await callJsonPromptSafe<ProfileSummaryPromptResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 420,
      timeoutMs: 35_000,
      promptName: "profile_summary_v2",
      schemaHint: "JSON object with profile_text string",
      validate: (value: unknown): value is ProfileSummaryPromptResult =>
        Boolean(value) &&
        typeof value === "object" &&
        typeof (value as Record<string, unknown>).profile_text === "string",
    });
    if (!safe.ok) {
      this.logger.warn("profile.summary_v2.fallback", {
        entityType: input.entityType,
        errorCode: safe.error_code,
      });
      return input.fallback;
    }
    const text = (safe.data.profile_text ?? "").replace(/\s+/g, " ").trim();
    return text || input.fallback;
  }

  private async safeEmbedding(profileText: string): Promise<number[] | undefined> {
    try {
      if (!profileText.trim()) {
        return undefined;
      }
      return await this.embeddingsClient.createEmbedding(profileText);
    } catch (error) {
      this.logger.warn("profile.embedding.failed", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return undefined;
    }
  }
}

function mapCandidateSeniority(
  value: string,
): CandidateProfileV2["seniority"]["estimate"] {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "junior") {
    return "junior";
  }
  if (normalized === "middle" || normalized === "mid") {
    return "mid";
  }
  if (normalized === "senior" || normalized === "principal") {
    return "senior";
  }
  if (normalized === "lead") {
    return "lead";
  }
  return "unknown";
}

function mapClaimStrengthToDepth(value: string): "low" | "medium" | "high" {
  const normalized = value.toLowerCase();
  if (normalized === "strong") {
    return "high";
  }
  return "medium";
}

function upsertDomain(
  profile: CandidateProfileV2,
  domainName: string,
  confidence: number,
): CandidateProfileV2 {
  const normalized = domainName.trim().toLowerCase();
  if (!normalized) {
    return profile;
  }
  const existingIndex = profile.domains.findIndex(
    (item) => item.name.toLowerCase() === normalized,
  );
  if (existingIndex === -1) {
    return {
      ...profile,
      domains: [...profile.domains, { name: domainName.trim(), confidence: clamp01(confidence) }].slice(0, 12),
    };
  }
  const existing = profile.domains[existingIndex];
  const next = [...profile.domains];
  if (confidence >= existing.confidence) {
    next[existingIndex] = { name: existing.name, confidence: clamp01(confidence) };
  }
  return { ...profile, domains: next };
}

function upsertJobDomain(
  profile: JobProfileV2,
  domainName: string,
  confidence: number,
): JobProfileV2 {
  const normalized = domainName.trim().toLowerCase();
  if (!normalized) {
    return profile;
  }
  const existingIndex = profile.domain.findIndex(
    (item) => item.name.toLowerCase() === normalized,
  );
  if (existingIndex === -1) {
    return {
      ...profile,
      domain: [...profile.domain, { name: domainName.trim(), confidence: clamp01(confidence) }].slice(0, 12),
    };
  }
  const next = [...profile.domain];
  if (confidence >= next[existingIndex].confidence) {
    next[existingIndex] = {
      name: next[existingIndex].name,
      confidence: clamp01(confidence),
    };
  }
  return { ...profile, domain: next };
}

function dedupeStrings(values: string[]): string[] {
  const set = new Set<string>();
  for (const value of values) {
    const normalized = value.replace(/\s+/g, " ").trim();
    if (!normalized) {
      continue;
    }
    set.add(normalized);
  }
  return Array.from(set);
}

function upsertShortNote(list: string[], note: string): string[] {
  return dedupeStrings([...list, note]).slice(0, 16);
}

function normalizeTechName(value: string): string {
  return value.replace(/\s+/g, " ").trim().slice(0, 80);
}

function applyCandidateFacts(profile: CandidateProfileV2, facts: ProfileFactV2[]): CandidateProfileV2 {
  const next = normalizeCandidateProfileV2(profile, profile.identity.telegram_user_id);
  const now = new Date().toISOString();
  const confidenceMap = { ...(next._fact_confidence ?? {}) };

  for (const fact of facts) {
    const path = fact.key.trim();
    if (!path) {
      continue;
    }
    if (path.startsWith("tech.")) {
      const [, techRaw, field] = path.split(".");
      const techName = normalizeTechName(techRaw ?? "");
      if (!techName || !field) {
        continue;
      }
      const current = next.tech[techName] ?? {
        used_directly: null,
        depth: null,
        ownership: null,
        last_used: null,
      };
      if (!shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
        continue;
      }
      if (field === "used_directly" && typeof fact.value === "boolean") {
        current.used_directly = fact.value;
      } else if (
        field === "depth" &&
        typeof fact.value === "string" &&
        (fact.value === "low" || fact.value === "medium" || fact.value === "high")
      ) {
        current.depth = fact.value;
      } else if (
        field === "ownership" &&
        typeof fact.value === "string" &&
        (fact.value === "observer" ||
          fact.value === "assisted" ||
          fact.value === "implemented" ||
          fact.value === "led")
      ) {
        current.ownership = fact.value;
      } else if (field === "last_used" && typeof fact.value === "string") {
        current.last_used = fact.value;
      } else {
        continue;
      }
      next.tech[techName] = current;
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }

    if (path === "seniority.estimate" && typeof fact.value === "string") {
      if (shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
        next.seniority.estimate = mapCandidateSeniority(fact.value);
        next.seniority.confidence = Math.max(next.seniority.confidence, clamp01(fact.confidence));
        confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      }
      continue;
    }
    if (path === "location.country" && typeof fact.value === "string") {
      if (shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
        next.location.country = fact.value.trim();
        confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      }
      continue;
    }
    if (path === "location.city" && typeof fact.value === "string") {
      if (shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
        next.location.city = fact.value.trim();
        confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      }
      continue;
    }
    if (path === "work_preferences.mode" && typeof fact.value === "string") {
      if (shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
        const mode = fact.value.toLowerCase();
        if (mode === "remote" || mode === "hybrid" || mode === "onsite" || mode === "flexible") {
          next.work_preferences.mode = mode;
          confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
        }
      }
      continue;
    }
    if (path === "roles.primary" && typeof fact.value === "string") {
      next.roles.primary = dedupeStrings([...next.roles.primary, fact.value]).slice(0, 8);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path === "experience_notes" && typeof fact.value === "string") {
      next.experience_notes = upsertShortNote(next.experience_notes, fact.value);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path === "evidence" && typeof fact.value === "string") {
      next.evidence = dedupeStrings([...next.evidence, fact.value]).slice(0, 20);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
  }

  next._fact_confidence = confidenceMap;
  return normalizeCandidateProfileV2(next, next.identity.telegram_user_id);
}

function applyJobFacts(profile: JobProfileV2, facts: ProfileFactV2[]): JobProfileV2 {
  const next = normalizeJobProfileV2(profile);
  const now = new Date().toISOString();
  const confidenceMap = { ...(next._fact_confidence ?? {}) };

  for (const fact of facts) {
    const path = fact.key.trim();
    if (!path || !shouldReplaceConfidence(confidenceMap[path], fact.confidence, now)) {
      continue;
    }
    if (path === "work_format" && typeof fact.value === "string") {
      const mode = fact.value.toLowerCase();
      if (mode === "remote" || mode === "hybrid" || mode === "onsite") {
        next.work_format.mode = mode;
        confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      }
      continue;
    }
    if (path === "budget.min" && typeof fact.value === "number") {
      next.budget = next.budget ?? { currency: "other", min: null, max: null, period: "unknown" };
      next.budget.min = fact.value;
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path === "budget.max" && typeof fact.value === "number") {
      next.budget = next.budget ?? { currency: "other", min: null, max: null, period: "unknown" };
      next.budget.max = fact.value;
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path === "budget.currency" && typeof fact.value === "string") {
      next.budget = next.budget ?? { currency: "other", min: null, max: null, period: "unknown" };
      const currency = fact.value.toUpperCase();
      next.budget.currency =
        currency === "USD" || currency === "EUR" || currency === "ILS" || currency === "GBP"
          ? currency
          : "other";
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path === "budget.period" && typeof fact.value === "string") {
      next.budget = next.budget ?? { currency: "other", min: null, max: null, period: "unknown" };
      const period = fact.value.toLowerCase();
      if (period === "month" || period === "year" || period === "hour") {
        next.budget.period = period;
      }
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path.startsWith("must_have") && typeof fact.value === "string") {
      next.must_have = dedupeStrings([...next.must_have, fact.value]).slice(0, 8);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path.startsWith("nice_to_have") && typeof fact.value === "string") {
      next.nice_to_have = dedupeStrings([...next.nice_to_have, fact.value]).slice(0, 8);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
    if (path.startsWith("task") && typeof fact.value === "string") {
      next.key_tasks = dedupeStrings([...next.key_tasks, fact.value]).slice(0, 8);
      confidenceMap[path] = { confidence: clamp01(fact.confidence), updated_at: now };
      continue;
    }
  }

  next._fact_confidence = confidenceMap;
  return normalizeJobProfileV2(next);
}

function shouldReplaceConfidence(
  previous: { confidence: number; updated_at: string } | undefined,
  nextConfidence: number,
  nextTimestamp: string,
): boolean {
  if (!previous) {
    return true;
  }
  const normalizedNext = clamp01(nextConfidence);
  if (normalizedNext > previous.confidence) {
    return true;
  }
  if (normalizedNext < previous.confidence) {
    return false;
  }
  return nextTimestamp >= previous.updated_at;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}

function buildCandidateProfileTextFallback(profile: CandidateProfileV2): string {
  const topTech = Object.entries(profile.tech)
    .sort((a, b) => rankDepth(b[1].depth) - rankDepth(a[1].depth))
    .slice(0, 8)
    .map(([name, details]) => `${name}${details.depth ? ` (${details.depth})` : ""}`);
  const domain = profile.domains.slice(0, 3).map((item) => item.name).join(", ") || "unknown";
  const location = [profile.location.city, profile.location.country].filter(Boolean).join(", ") || "unknown";
  const salary = profile.comp.salary_expectations
    ? `${profile.comp.salary_expectations.min ?? "?"}-${profile.comp.salary_expectations.max ?? "?"} ${profile.comp.salary_expectations.currency}/${profile.comp.salary_expectations.period}`
    : "unknown";
  return [
    `${profile.seniority.estimate} ${profile.roles.primary[0] ?? "engineer"}.`,
    `Core tech: ${topTech.join(", ") || "unknown"}.`,
    `Domain: ${domain}.`,
    `Work mode: ${profile.work_preferences.mode}, location: ${location}.`,
    `Salary expectation: ${salary}.`,
  ]
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildJobProfileTextFallback(profile: JobProfileV2): string {
  const budget = profile.budget
    ? `${profile.budget.min ?? "?"}-${profile.budget.max ?? "?"} ${profile.budget.currency}/${profile.budget.period}`
    : "unknown";
  const domain = profile.domain.slice(0, 3).map((item) => item.name).join(", ") || "unknown";
  const countries = profile.work_format.allowed_countries.slice(0, 6).join(", ") || "unknown";
  return [
    `${profile.identity.job_title || "Technical role"} for ${profile.product_context.product_type}.`,
    `Work format: ${profile.work_format.mode}, countries: ${countries}.`,
    `Budget: ${budget}.`,
    `Must-have: ${profile.must_have.slice(0, 8).join(", ") || "unknown"}.`,
    `Tasks: ${profile.key_tasks.slice(0, 6).join(", ") || "unknown"}.`,
    `Domain: ${domain}.`,
  ]
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function rankDepth(value: CandidateProfileV2["tech"][string]["depth"]): number {
  if (value === "high") {
    return 3;
  }
  if (value === "medium") {
    return 2;
  }
  if (value === "low") {
    return 1;
  }
  return 0;
}
