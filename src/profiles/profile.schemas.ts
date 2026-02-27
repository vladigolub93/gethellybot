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
