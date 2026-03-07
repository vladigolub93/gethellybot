import { CandidateProfile, JobProfile } from "../shared/types/domain.types";

const MAX_LIST_ITEMS = 12;
const MAX_TEXT = 800;

export function createEmptyCandidateProfile(candidateId: string): CandidateProfile {
  return {
    candidateId,
    headline: "",
    seniorityEstimate: "unknown",
    coreSkills: [],
    secondarySkills: [],
    yearsExperienceTotal: "",
    relevantExperienceSummary: "",
    domains: [],
    notableProjects: [],
    constraints: {
      timezone: "",
      location: "",
      workFormat: "",
      salaryExpectation: "",
      availabilityDate: "",
    },
    communication: {
      englishLevelEstimate: "",
      notes: "",
    },
    redFlags: [],
    dealbreakers: [],
    searchableText: "",
  };
}

export function createEmptyJobProfile(jobId: string): JobProfile {
  return {
    jobId,
    title: "",
    mustHaveSkills: [],
    niceToHaveSkills: [],
    responsibilitiesSummary: "",
    domain: "",
    seniorityTarget: "",
    constraints: {
      timezoneOverlap: "",
      location: "",
      format: "",
      budgetRange: "",
      contractType: "",
    },
    interviewProcessSummary: "",
    urgency: "",
    dealbreakers: [],
    searchableText: "",
  };
}

export function normalizeCandidateProfile(
  candidateId: string,
  raw: unknown,
): CandidateProfile {
  const source = isRecord(raw) ? raw : {};

  const normalized: CandidateProfile = {
    candidateId,
    headline: toText(source.headline),
    seniorityEstimate: toSeniority(source.seniorityEstimate),
    coreSkills: toStringArray(source.coreSkills),
    secondarySkills: toStringArray(source.secondarySkills),
    yearsExperienceTotal: toText(source.yearsExperienceTotal),
    relevantExperienceSummary: toText(source.relevantExperienceSummary),
    domains: toStringArray(source.domains),
    notableProjects: toCandidateProjects(source.notableProjects),
    constraints: {
      timezone: toText(readNested(source, "constraints", "timezone")),
      location: toText(readNested(source, "constraints", "location")),
      workFormat: toText(readNested(source, "constraints", "workFormat")),
      salaryExpectation: toText(readNested(source, "constraints", "salaryExpectation")),
      availabilityDate: toText(readNested(source, "constraints", "availabilityDate")),
    },
    communication: {
      englishLevelEstimate: toText(readNested(source, "communication", "englishLevelEstimate")),
      notes: toText(readNested(source, "communication", "notes")),
    },
    redFlags: toStringArray(source.redFlags),
    dealbreakers: toStringArray(source.dealbreakers),
    searchableText: toText(source.searchableText),
  };

  return buildCandidateSearchableText(normalized);
}

export function normalizeJobProfile(jobId: string, raw: unknown): JobProfile {
  const source = isRecord(raw) ? raw : {};

  const normalized: JobProfile = {
    jobId,
    title: toText(source.title),
    mustHaveSkills: toStringArray(source.mustHaveSkills),
    niceToHaveSkills: toStringArray(source.niceToHaveSkills),
    responsibilitiesSummary: toText(source.responsibilitiesSummary),
    domain: toText(source.domain),
    seniorityTarget: toText(source.seniorityTarget),
    constraints: {
      timezoneOverlap: toText(readNested(source, "constraints", "timezoneOverlap")),
      location: toText(readNested(source, "constraints", "location")),
      format: toText(readNested(source, "constraints", "format")),
      budgetRange: toText(readNested(source, "constraints", "budgetRange")),
      contractType: toText(readNested(source, "constraints", "contractType")),
    },
    interviewProcessSummary: toText(source.interviewProcessSummary),
    urgency: toText(source.urgency),
    dealbreakers: toStringArray(source.dealbreakers),
    searchableText: toText(source.searchableText),
  };

  return buildJobSearchableText(normalized);
}

function buildCandidateSearchableText(profile: CandidateProfile): CandidateProfile {
  const searchableText =
    profile.searchableText ||
    [
      profile.headline,
      profile.seniorityEstimate,
      profile.coreSkills.join(", "),
      profile.domains.join(", "),
      profile.constraints.timezone,
      profile.constraints.location,
      profile.constraints.workFormat,
      profile.constraints.salaryExpectation,
      profile.dealbreakers.join(", "),
    ]
      .filter(Boolean)
      .join(" | ")
      .slice(0, MAX_TEXT);

  return {
    ...profile,
    searchableText,
  };
}

function buildJobSearchableText(profile: JobProfile): JobProfile {
  const searchableText =
    profile.searchableText ||
    [
      profile.title,
      profile.seniorityTarget,
      profile.mustHaveSkills.join(", "),
      profile.niceToHaveSkills.join(", "),
      profile.domain,
      profile.constraints.timezoneOverlap,
      profile.constraints.location,
      profile.constraints.format,
      profile.constraints.budgetRange,
      profile.dealbreakers.join(", "),
    ]
      .filter(Boolean)
      .join(" | ")
      .slice(0, MAX_TEXT);

  return {
    ...profile,
    searchableText,
  };
}

function toCandidateProjects(value: unknown): CandidateProfile["notableProjects"] {
  if (!Array.isArray(value)) {
    return [];
  }

  const projects: Array<{ role: string; impact: string; stack: string[] }> = [];

  for (const item of value) {
    if (!isRecord(item)) {
      continue;
    }
    const role = toText(item.role);
    const impact = toText(item.impact);
    const stack = toStringArray(item.stack);
    if (!role && !impact && stack.length === 0) {
      continue;
    }
    projects.push({ role, impact, stack });
    if (projects.length >= 8) {
      break;
    }
  }

  return projects;
}

function toText(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter((item) => Boolean(item))
    .slice(0, MAX_LIST_ITEMS);
}

function toSeniority(value: unknown): CandidateProfile["seniorityEstimate"] {
  const normalized = toText(value).toLowerCase();
  if (normalized === "junior" || normalized === "mid" || normalized === "senior" || normalized === "lead") {
    return normalized;
  }
  return "unknown";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readNested(source: Record<string, unknown>, key: string, nestedKey: string): unknown {
  const nested = source[key];
  if (!isRecord(nested)) {
    return undefined;
  }
  return nested[nestedKey];
}

export interface CandidateProfileV2 {
  identity: {
    name: string | null;
    telegram_user_id: number;
    contact_phone: string | null;
    language_preference: "en" | "ru" | "uk" | "unknown";
  };
  location: {
    country: string;
    city: string;
    timezone: string | null;
  };
  work_preferences: {
    mode: "remote" | "hybrid" | "onsite" | "flexible" | "unknown";
    allowed_countries: string[] | null;
    relocation: boolean | null;
  };
  comp: {
    salary_expectations: {
      currency: "USD" | "EUR" | "ILS" | "GBP" | "other";
      min: number | null;
      max: number | null;
      period: "month" | "year" | "hour" | "unknown";
    } | null;
  };
  seniority: {
    estimate: "junior" | "mid" | "senior" | "lead" | "unknown";
    confidence: number;
  };
  roles: {
    primary: string[];
  };
  domains: Array<{
    name: string;
    confidence: number;
  }>;
  tech: Record<
    string,
    {
      used_directly: boolean | null;
      depth: "low" | "medium" | "high" | null;
      ownership: "observer" | "assisted" | "implemented" | "led" | null;
      last_used: string | null;
    }
  >;
  experience_notes: string[];
  evidence: string[];
  _fact_confidence?: Record<
    string,
    {
      confidence: number;
      updated_at: string;
    }
  >;
}

export interface JobProfileV2 {
  identity: {
    job_title: string;
    company_name: string | null;
    product_link: string | null;
  };
  work_format: {
    mode: "remote" | "hybrid" | "onsite" | "unknown";
    allowed_countries: string[];
    allowed_timezones: string[];
  };
  budget: {
    currency: "USD" | "EUR" | "ILS" | "GBP" | "other";
    min: number | null;
    max: number | null;
    period: "month" | "year" | "hour" | "unknown";
  } | null;
  domain: Array<{
    name: string;
    confidence: number;
  }>;
  product_context: {
    product_type: "startup" | "scaleup" | "enterprise" | "agency" | "unknown";
    stage: string;
    description: string;
  };
  team: {
    size: number | null;
    composition: string;
    manager_role: string;
  };
  must_have: string[];
  nice_to_have: string[];
  key_tasks: string[];
  dealbreakers: string[];
  constraints: string[];
  _fact_confidence?: Record<
    string,
    {
      confidence: number;
      updated_at: string;
    }
  >;
}

export interface ProfileFactV2 {
  key: string;
  value: string | number | boolean | null;
  confidence: number;
}

export function createEmptyCandidateProfileV2(telegramUserId: number): CandidateProfileV2 {
  return {
    identity: {
      name: null,
      telegram_user_id: telegramUserId,
      contact_phone: null,
      language_preference: "unknown",
    },
    location: {
      country: "",
      city: "",
      timezone: null,
    },
    work_preferences: {
      mode: "unknown",
      allowed_countries: null,
      relocation: null,
    },
    comp: {
      salary_expectations: null,
    },
    seniority: {
      estimate: "unknown",
      confidence: 0,
    },
    roles: {
      primary: [],
    },
    domains: [],
    tech: {},
    experience_notes: [],
    evidence: [],
    _fact_confidence: {},
  };
}

export function createEmptyJobProfileV2(): JobProfileV2 {
  return {
    identity: {
      job_title: "",
      company_name: null,
      product_link: null,
    },
    work_format: {
      mode: "unknown",
      allowed_countries: [],
      allowed_timezones: [],
    },
    budget: null,
    domain: [],
    product_context: {
      product_type: "unknown",
      stage: "",
      description: "",
    },
    team: {
      size: null,
      composition: "",
      manager_role: "",
    },
    must_have: [],
    nice_to_have: [],
    key_tasks: [],
    dealbreakers: [],
    constraints: [],
    _fact_confidence: {},
  };
}

export function normalizeCandidateProfileV2(raw: unknown, telegramUserId: number): CandidateProfileV2 {
  const profile = isRecord(raw)
    ? (raw as unknown as CandidateProfileV2)
    : createEmptyCandidateProfileV2(telegramUserId);
  const base = createEmptyCandidateProfileV2(telegramUserId);
  return {
    ...base,
    ...profile,
    identity: {
      ...base.identity,
      ...(isRecord(profile.identity) ? profile.identity : {}),
      telegram_user_id: telegramUserId,
      name: normalizeNullableShortText((profile as CandidateProfileV2).identity?.name, 120),
      contact_phone: normalizeNullableShortText((profile as CandidateProfileV2).identity?.contact_phone, 32),
      language_preference: normalizeLanguagePreference((profile as CandidateProfileV2).identity?.language_preference),
    },
    location: {
      ...base.location,
      ...(isRecord(profile.location) ? profile.location : {}),
      country: normalizeShortText((profile as CandidateProfileV2).location?.country, 80),
      city: normalizeShortText((profile as CandidateProfileV2).location?.city, 80),
      timezone: normalizeNullableShortText((profile as CandidateProfileV2).location?.timezone, 80),
    },
    work_preferences: {
      ...base.work_preferences,
      ...(isRecord(profile.work_preferences) ? profile.work_preferences : {}),
      mode: normalizeWorkMode((profile as CandidateProfileV2).work_preferences?.mode),
      allowed_countries: normalizeNullableStringArray(
        (profile as CandidateProfileV2).work_preferences?.allowed_countries,
        24,
        80,
      ),
      relocation:
        typeof (profile as CandidateProfileV2).work_preferences?.relocation === "boolean"
          ? (profile as CandidateProfileV2).work_preferences?.relocation
          : null,
    },
    comp: {
      salary_expectations: normalizeSalaryExpectations((profile as CandidateProfileV2).comp?.salary_expectations),
    },
    seniority: {
      estimate: normalizeCandidateSeniority((profile as CandidateProfileV2).seniority?.estimate),
      confidence: clamp01((profile as CandidateProfileV2).seniority?.confidence ?? 0),
    },
    roles: {
      primary: normalizeStringArray((profile as CandidateProfileV2).roles?.primary, 8, 80),
    },
    domains: normalizeDomains((profile as CandidateProfileV2).domains),
    tech: normalizeTechMap((profile as CandidateProfileV2).tech),
    experience_notes: normalizeStringArray((profile as CandidateProfileV2).experience_notes, 16, 180),
    evidence: normalizeStringArray((profile as CandidateProfileV2).evidence, 20, 220),
    _fact_confidence: normalizeFactConfidenceMap((profile as CandidateProfileV2)._fact_confidence),
  };
}

export function normalizeJobProfileV2(raw: unknown): JobProfileV2 {
  const profile = isRecord(raw) ? (raw as unknown as JobProfileV2) : createEmptyJobProfileV2();
  const base = createEmptyJobProfileV2();
  return {
    ...base,
    ...profile,
    identity: {
      ...base.identity,
      ...(isRecord(profile.identity) ? profile.identity : {}),
      job_title: normalizeShortText((profile as JobProfileV2).identity?.job_title, 140),
      company_name: normalizeNullableShortText((profile as JobProfileV2).identity?.company_name, 140),
      product_link: normalizeNullableShortText((profile as JobProfileV2).identity?.product_link, 200),
    },
    work_format: {
      ...base.work_format,
      ...(isRecord(profile.work_format) ? profile.work_format : {}),
      mode: normalizeJobMode((profile as JobProfileV2).work_format?.mode),
      allowed_countries: normalizeStringArray((profile as JobProfileV2).work_format?.allowed_countries, 32, 80),
      allowed_timezones: normalizeStringArray((profile as JobProfileV2).work_format?.allowed_timezones, 16, 80),
    },
    budget: normalizeJobBudget((profile as JobProfileV2).budget),
    domain: normalizeDomains((profile as JobProfileV2).domain),
    product_context: {
      ...base.product_context,
      ...(isRecord(profile.product_context) ? profile.product_context : {}),
      product_type: normalizeProductType((profile as JobProfileV2).product_context?.product_type),
      stage: normalizeShortText((profile as JobProfileV2).product_context?.stage, 80),
      description: normalizeShortText((profile as JobProfileV2).product_context?.description, 260),
    },
    team: {
      ...base.team,
      ...(isRecord(profile.team) ? profile.team : {}),
      size: normalizeNullableNumber((profile as JobProfileV2).team?.size),
      composition: normalizeShortText((profile as JobProfileV2).team?.composition, 180),
      manager_role: normalizeShortText((profile as JobProfileV2).team?.manager_role, 120),
    },
    must_have: normalizeStringArray((profile as JobProfileV2).must_have, 8, 90),
    nice_to_have: normalizeStringArray((profile as JobProfileV2).nice_to_have, 8, 90),
    key_tasks: normalizeStringArray((profile as JobProfileV2).key_tasks, 12, 180),
    dealbreakers: normalizeStringArray((profile as JobProfileV2).dealbreakers, 12, 180),
    constraints: normalizeStringArray((profile as JobProfileV2).constraints, 12, 180),
    _fact_confidence: normalizeFactConfidenceMap((profile as JobProfileV2)._fact_confidence),
  };
}

function normalizeLanguagePreference(value: unknown): CandidateProfileV2["identity"]["language_preference"] {
  const normalized = normalizeShortText(value, 8).toLowerCase();
  if (normalized === "en" || normalized === "ru" || normalized === "uk") {
    return normalized;
  }
  return "unknown";
}

function normalizeWorkMode(value: unknown): CandidateProfileV2["work_preferences"]["mode"] {
  const normalized = normalizeShortText(value, 16).toLowerCase();
  if (normalized === "remote" || normalized === "hybrid" || normalized === "onsite" || normalized === "flexible") {
    return normalized;
  }
  return "unknown";
}

function normalizeJobMode(value: unknown): JobProfileV2["work_format"]["mode"] {
  const normalized = normalizeShortText(value, 16).toLowerCase();
  if (normalized === "remote" || normalized === "hybrid" || normalized === "onsite") {
    return normalized;
  }
  return "unknown";
}

function normalizeCandidateSeniority(value: unknown): CandidateProfileV2["seniority"]["estimate"] {
  const normalized = normalizeShortText(value, 16).toLowerCase();
  if (normalized === "junior" || normalized === "mid" || normalized === "senior" || normalized === "lead") {
    return normalized;
  }
  if (normalized === "middle") {
    return "mid";
  }
  return "unknown";
}

function normalizeProductType(value: unknown): JobProfileV2["product_context"]["product_type"] {
  const normalized = normalizeShortText(value, 24).toLowerCase();
  if (normalized === "startup" || normalized === "scaleup" || normalized === "enterprise" || normalized === "agency") {
    return normalized;
  }
  return "unknown";
}

function normalizeSalaryExpectations(
  value: unknown,
): CandidateProfileV2["comp"]["salary_expectations"] {
  if (!isRecord(value)) {
    return null;
  }
  type CandidateSalary = NonNullable<CandidateProfileV2["comp"]["salary_expectations"]>;
  const currencyRaw = normalizeShortText(value.currency, 8).toUpperCase();
  const currency: CandidateSalary["currency"] =
    currencyRaw === "USD" || currencyRaw === "EUR" || currencyRaw === "ILS" || currencyRaw === "GBP"
      ? currencyRaw
      : "other";
  const periodRaw = normalizeShortText(value.period, 12).toLowerCase();
  const period: CandidateSalary["period"] =
    periodRaw === "month" || periodRaw === "year" || periodRaw === "hour" ? periodRaw : "unknown";
  const min = normalizeNullableNumber(value.min);
  const max = normalizeNullableNumber(value.max);
  return {
    currency,
    min,
    max,
    period,
  };
}

function normalizeJobBudget(value: unknown): JobProfileV2["budget"] {
  if (!isRecord(value)) {
    return null;
  }
  type JobBudget = NonNullable<JobProfileV2["budget"]>;
  const currencyRaw = normalizeShortText(value.currency, 8).toUpperCase();
  const currency: JobBudget["currency"] =
    currencyRaw === "USD" || currencyRaw === "EUR" || currencyRaw === "ILS" || currencyRaw === "GBP"
      ? currencyRaw
      : "other";
  const periodRaw = normalizeShortText(value.period, 12).toLowerCase();
  const period: JobBudget["period"] =
    periodRaw === "month" || periodRaw === "year" || periodRaw === "hour" ? periodRaw : "unknown";
  return {
    currency,
    min: normalizeNullableNumber(value.min),
    max: normalizeNullableNumber(value.max),
    period,
  };
}

function normalizeDomains(value: unknown): Array<{ name: string; confidence: number }> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => {
      if (!isRecord(item)) {
        return null;
      }
      const name = normalizeShortText(item.name, 80);
      if (!name) {
        return null;
      }
      return {
        name,
        confidence: clamp01(item.confidence),
      };
    })
    .filter((item): item is { name: string; confidence: number } => Boolean(item))
    .slice(0, 12);
}

function normalizeTechMap(
  value: unknown,
): CandidateProfileV2["tech"] {
  if (!isRecord(value)) {
    return {};
  }
  const result: CandidateProfileV2["tech"] = {};
  for (const [rawName, rawPayload] of Object.entries(value)) {
    const name = normalizeShortText(rawName, 80);
    if (!name || !isRecord(rawPayload)) {
      continue;
    }
    const depth = normalizeShortText(rawPayload.depth, 16).toLowerCase();
    const ownership = normalizeShortText(rawPayload.ownership, 16).toLowerCase();
    result[name] = {
      used_directly:
        typeof rawPayload.used_directly === "boolean" ? rawPayload.used_directly : null,
      depth: depth === "low" || depth === "medium" || depth === "high" ? depth : null,
      ownership:
        ownership === "observer" ||
        ownership === "assisted" ||
        ownership === "implemented" ||
        ownership === "led"
          ? ownership
          : null,
      last_used: normalizeNullableShortText(rawPayload.last_used, 80),
    };
  }
  return result;
}

function normalizeFactConfidenceMap(value: unknown): CandidateProfileV2["_fact_confidence"] {
  if (!isRecord(value)) {
    return {};
  }
  const result: NonNullable<CandidateProfileV2["_fact_confidence"]> = {};
  for (const [key, payload] of Object.entries(value)) {
    if (!key || !isRecord(payload)) {
      continue;
    }
    result[key] = {
      confidence: clamp01(payload.confidence),
      updated_at: normalizeShortText(payload.updated_at, 64),
    };
  }
  return result;
}

function normalizeNullableStringArray(
  value: unknown,
  maxItems: number,
  maxItemLength: number,
): string[] | null {
  if (value === null) {
    return null;
  }
  if (!Array.isArray(value)) {
    return null;
  }
  const normalized = normalizeStringArray(value, maxItems, maxItemLength);
  return normalized.length > 0 ? normalized : [];
}

function normalizeStringArray(value: unknown, maxItems: number, maxItemLength: number): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => normalizeShortText(item, maxItemLength))
    .filter(Boolean)
    .slice(0, maxItems);
}

function normalizeShortText(value: unknown, maxLength: number): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function normalizeNullableShortText(value: unknown, maxLength: number): string | null {
  const normalized = normalizeShortText(value, maxLength);
  return normalized || null;
}

function normalizeNullableNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function clamp01(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
}
