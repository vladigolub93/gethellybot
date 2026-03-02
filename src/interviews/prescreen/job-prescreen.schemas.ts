import { PrescreenV2Language } from "./candidate-prescreen.schemas";

export type JobSeniorityTarget = "junior" | "mid" | "senior" | "unknown";
export type JobProductType = "startup" | "scaleup" | "enterprise" | "agency" | "unknown";
export type JobWorkFormatHint = "remote" | "hybrid" | "onsite" | "unknown";
export type JobBudgetCurrencyHint = "USD" | "EUR" | "ILS" | "GBP" | "other";
export type JobBudgetPeriodHint = "month" | "year" | "hour";

export interface JobDomainClaim {
  name: string;
  confidence: number;
}

export interface JobMustHaveClaim {
  skill: string;
  confidence: number;
}

export interface JobTeamClaim {
  size: number | null;
  composition: string;
  timezone: string | null;
}

export interface JobBudgetClaim {
  currency: JobBudgetCurrencyHint;
  min: number | null;
  max: number | null;
  period: JobBudgetPeriodHint;
}

export interface JobClaimExtractionResult {
  role_title: string;
  seniority_target: JobSeniorityTarget;
  domain: JobDomainClaim[];
  product_type: JobProductType;
  team: JobTeamClaim;
  work_format: JobWorkFormatHint;
  allowed_countries: string[];
  budget: JobBudgetClaim | null;
  must_have: JobMustHaveClaim[];
  nice_to_have: JobMustHaveClaim[];
  key_tasks: string[];
  risks_or_uncertainties: string[];
}

export interface JobPrescreenQuestion {
  id: string;
  topic: string;
  question: string;
  intent: "clarify";
  followup_policy: "at_most_one_soft_followup";
}

export interface JobQuestionGeneratorResult {
  questions: JobPrescreenQuestion[];
}

export interface JobPrescreenFact {
  key: string;
  value: string | number | boolean | null;
  confidence: number;
}

export interface JobAnswerInterpreterResult {
  facts: JobPrescreenFact[];
  notes: string;
  should_follow_up: boolean;
  follow_up_question: string | null;
}

export function isJobClaimExtractionResult(value: unknown): value is JobClaimExtractionResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.role_title)) {
    return false;
  }
  if (!isEnum(value.seniority_target, ["junior", "mid", "senior", "unknown"])) {
    return false;
  }
  if (!Array.isArray(value.domain) || !value.domain.every(isJobDomainClaim)) {
    return false;
  }
  if (!isEnum(value.product_type, ["startup", "scaleup", "enterprise", "agency", "unknown"])) {
    return false;
  }
  if (!isJobTeamClaim(value.team)) {
    return false;
  }
  if (!isEnum(value.work_format, ["remote", "hybrid", "onsite", "unknown"])) {
    return false;
  }
  if (!isStringArray(value.allowed_countries)) {
    return false;
  }
  if (!(value.budget === null || isJobBudgetClaim(value.budget))) {
    return false;
  }
  if (!Array.isArray(value.must_have) || !value.must_have.every(isJobMustHaveClaim)) {
    return false;
  }
  if (!Array.isArray(value.nice_to_have) || !value.nice_to_have.every(isJobMustHaveClaim)) {
    return false;
  }
  if (!isStringArray(value.key_tasks)) {
    return false;
  }
  if (!isStringArray(value.risks_or_uncertainties)) {
    return false;
  }
  return true;
}

export function isJobQuestionGeneratorResult(value: unknown): value is JobQuestionGeneratorResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.questions)) {
    return false;
  }
  return value.questions.every(isJobPrescreenQuestion);
}

export function isJobAnswerInterpreterResult(value: unknown): value is JobAnswerInterpreterResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.facts) || !value.facts.every(isJobPrescreenFact)) {
    return false;
  }
  if (!isString(value.notes)) {
    return false;
  }
  if (typeof value.should_follow_up !== "boolean") {
    return false;
  }
  if (!isNullableString(value.follow_up_question)) {
    return false;
  }
  return true;
}

export function normalizeJobClaimExtractionResult(
  value: JobClaimExtractionResult,
): JobClaimExtractionResult {
  return {
    role_title: cleanText(value.role_title).slice(0, 120) || "Technical role",
    seniority_target: isEnum(value.seniority_target, ["junior", "mid", "senior", "unknown"])
      ? value.seniority_target
      : "unknown",
    domain: value.domain
      .map((item) => ({
        name: cleanText(item.name).slice(0, 90),
        confidence: clamp01(item.confidence),
      }))
      .filter((item) => item.name.length > 0)
      .slice(0, 8),
    product_type: isEnum(value.product_type, ["startup", "scaleup", "enterprise", "agency", "unknown"])
      ? value.product_type
      : "unknown",
    team: {
      size: value.team.size === null ? null : Math.max(1, Math.min(5000, Math.round(value.team.size))),
      composition: cleanText(value.team.composition).slice(0, 220),
      timezone: value.team.timezone ? cleanText(value.team.timezone).slice(0, 80) : null,
    },
    work_format: isEnum(value.work_format, ["remote", "hybrid", "onsite", "unknown"])
      ? value.work_format
      : "unknown",
    allowed_countries: value.allowed_countries.map((item) => cleanText(item)).filter(Boolean).slice(0, 20),
    budget: value.budget
      ? {
          currency: isEnum(value.budget.currency, ["USD", "EUR", "ILS", "GBP", "other"])
            ? value.budget.currency
            : "other",
          min: value.budget.min === null ? null : sanitizeBudgetNumber(value.budget.min),
          max: value.budget.max === null ? null : sanitizeBudgetNumber(value.budget.max),
          period: isEnum(value.budget.period, ["month", "year", "hour"]) ? value.budget.period : "month",
        }
      : null,
    must_have: value.must_have
      .map((item) => ({
        skill: cleanText(item.skill).slice(0, 80),
        confidence: clamp01(item.confidence),
      }))
      .filter((item) => item.skill.length > 0)
      .slice(0, 8),
    nice_to_have: value.nice_to_have
      .map((item) => ({
        skill: cleanText(item.skill).slice(0, 80),
        confidence: clamp01(item.confidence),
      }))
      .filter((item) => item.skill.length > 0)
      .slice(0, 10),
    key_tasks: value.key_tasks.map((item) => cleanText(item).slice(0, 180)).filter(Boolean).slice(0, 10),
    risks_or_uncertainties: value.risks_or_uncertainties
      .map((item) => cleanText(item).slice(0, 180))
      .filter(Boolean)
      .slice(0, 12),
  };
}

export function normalizeJobQuestionGeneratorResult(
  value: JobQuestionGeneratorResult,
  maxQuestions = 10,
): JobQuestionGeneratorResult {
  const seen = new Set<string>();
  const questions = value.questions
    .map((question, index) => {
      const id = cleanText(question.id) || `j${index + 1}`;
      const topic = cleanText(question.topic) || "clarification";
      const text = cleanText(question.question).slice(0, 260);
      const dedupe = `${topic}:${text.toLowerCase()}`;
      if (!text || seen.has(dedupe)) {
        return null;
      }
      seen.add(dedupe);
      return {
        id,
        topic,
        question: text,
        intent: "clarify" as const,
        followup_policy: "at_most_one_soft_followup" as const,
      };
    })
    .filter((item): item is JobPrescreenQuestion => Boolean(item))
    .slice(0, Math.max(1, Math.min(maxQuestions, 10)));

  return { questions };
}

export function normalizeJobAnswerInterpreterResult(
  value: JobAnswerInterpreterResult,
): JobAnswerInterpreterResult {
  return {
    facts: value.facts
      .map((fact) => ({
        key: cleanText(fact.key).slice(0, 120),
        value: normalizeFactValue(fact.value),
        confidence: clamp01(fact.confidence),
      }))
      .filter((fact) => fact.key.length > 0)
      .slice(0, 12),
    notes: cleanText(value.notes).slice(0, 220),
    should_follow_up: Boolean(value.should_follow_up),
    follow_up_question: value.follow_up_question ? cleanText(value.follow_up_question).slice(0, 260) : null,
  };
}

export function buildJobSummarySentence(
  claims: JobClaimExtractionResult,
  language: PrescreenV2Language,
): string {
  const role = claims.role_title || "technical role";
  const domain = claims.domain[0]?.name || "general domain";
  const seniority = claims.seniority_target === "unknown" ? "" : `${claims.seniority_target} `;
  if (language === "ru") {
    return `Понял. Похоже это ${seniority}${role} в домене ${domain}. Я задам несколько коротких вопросов, чтобы уточнить требования для качественного матчинга.`;
  }
  if (language === "uk") {
    return `Зрозуміло. Схоже це ${seniority}${role} у домені ${domain}. Я поставлю кілька коротких питань, щоб уточнити вимоги для якісного матчингу.`;
  }
  return `Got it. This looks like a ${seniority}${role} role in ${domain}. I will ask a few quick questions to clarify what matters for candidates and matching.`;
}

function sanitizeBudgetNumber(value: number): number {
  const rounded = Math.round(value);
  return Math.max(0, Math.min(1_000_000_000, rounded));
}

function normalizeFactValue(value: unknown): string | number | boolean | null {
  if (value === null) {
    return null;
  }
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    return cleanText(value).slice(0, 180);
  }
  return null;
}

function isJobDomainClaim(value: unknown): value is JobDomainClaim {
  return isRecord(value) && isString(value.name) && isNumberInRange(value.confidence, 0, 1);
}

function isJobMustHaveClaim(value: unknown): value is JobMustHaveClaim {
  return isRecord(value) && isString(value.skill) && isNumberInRange(value.confidence, 0, 1);
}

function isJobTeamClaim(value: unknown): value is JobTeamClaim {
  return (
    isRecord(value) &&
    (value.size === null || isNumber(value.size)) &&
    isString(value.composition) &&
    isNullableString(value.timezone)
  );
}

function isJobBudgetClaim(value: unknown): value is JobBudgetClaim {
  return (
    isRecord(value) &&
    isEnum(value.currency, ["USD", "EUR", "ILS", "GBP", "other"]) &&
    (value.min === null || isNumber(value.min)) &&
    (value.max === null || isNumber(value.max)) &&
    isEnum(value.period, ["month", "year", "hour"])
  );
}

function isJobPrescreenQuestion(value: unknown): value is JobPrescreenQuestion {
  return (
    isRecord(value) &&
    isString(value.id) &&
    isString(value.topic) &&
    isString(value.question) &&
    value.intent === "clarify" &&
    value.followup_policy === "at_most_one_soft_followup"
  );
}

function isJobPrescreenFact(value: unknown): value is JobPrescreenFact {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.key)) {
    return false;
  }
  if (!isNumberInRange(value.confidence, 0, 1)) {
    return false;
  }
  const factValue = value.value;
  return (
    factValue === null ||
    typeof factValue === "string" ||
    typeof factValue === "boolean" ||
    (typeof factValue === "number" && Number.isFinite(factValue))
  );
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNumberInRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isEnum<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return typeof value === "string" && allowed.includes(value as T);
}

function cleanText(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/\s+/g, " ").trim();
}

function clamp01(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return 0;
  }
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}
