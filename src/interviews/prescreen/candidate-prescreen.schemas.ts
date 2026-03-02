export type PrescreenV2Language = "en" | "ru" | "uk";

export type ClaimImportance = "high" | "medium" | "low";
export type ClaimStrength = "strong" | "weak";

export interface CandidateTechClaim {
  tech: string;
  type: string;
  importance: ClaimImportance;
  claim_strength: ClaimStrength;
  evidence_snippet: string;
  confidence: number;
}

export interface CandidateDomainClaim {
  name: string;
  confidence: number;
}

export interface CandidateClaimExtractionResult {
  candidate_name: string | null;
  primary_roles: string[];
  years_experience_estimate: number | null;
  domains: CandidateDomainClaim[];
  tech_claims: CandidateTechClaim[];
  work_preferences_hints: Record<string, unknown>;
}

export interface CandidatePrescreenQuestion {
  id: string;
  tech_or_topic: string;
  question: string;
  intent: "verify_claim";
  expected_answer_shape: "short_story";
  followup_policy: "at_most_one_soft_followup";
}

export interface CandidateQuestionGeneratorResult {
  questions: CandidatePrescreenQuestion[];
}

export interface CandidatePrescreenFact {
  key: string;
  value: string | number | boolean | null;
  confidence: number;
}

export interface CandidateAnswerInterpreterResult {
  facts: CandidatePrescreenFact[];
  notes: string;
  should_follow_up: boolean;
  follow_up_question: string | null;
  ai_assisted_likelihood: "low" | "medium" | "high";
  ai_assisted_confidence: number;
}

export interface CandidatePrescreenAnswerRecord {
  question_id: string;
  question_text: string;
  answer_text: string;
  interpreted_facts: CandidatePrescreenFact[];
  notes: string;
  ai_assisted_likelihood: "low" | "medium" | "high";
  ai_assisted_confidence: number;
  quality_warning?: boolean;
  created_at: string;
}

export function isCandidateClaimExtractionResult(
  value: unknown,
): value is CandidateClaimExtractionResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!isNullableString(value.candidate_name)) {
    return false;
  }
  if (!isStringArray(value.primary_roles)) {
    return false;
  }
  if (!isNullableNumber(value.years_experience_estimate)) {
    return false;
  }
  if (!Array.isArray(value.domains) || !value.domains.every(isCandidateDomainClaim)) {
    return false;
  }
  if (!Array.isArray(value.tech_claims) || !value.tech_claims.every(isCandidateTechClaim)) {
    return false;
  }
  if (!isRecord(value.work_preferences_hints)) {
    return false;
  }
  return true;
}

export function isCandidateQuestionGeneratorResult(
  value: unknown,
): value is CandidateQuestionGeneratorResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.questions)) {
    return false;
  }
  return value.questions.every(isCandidatePrescreenQuestion);
}

export function isCandidateAnswerInterpreterResult(
  value: unknown,
): value is CandidateAnswerInterpreterResult {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.facts) || !value.facts.every(isCandidatePrescreenFact)) {
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
  if (!isLikelihood(value.ai_assisted_likelihood)) {
    return false;
  }
  if (!isNumberInRange(value.ai_assisted_confidence, 0, 1)) {
    return false;
  }
  return true;
}

export function normalizeClaimExtractionResult(
  value: CandidateClaimExtractionResult,
): CandidateClaimExtractionResult {
  const techClaims = value.tech_claims
    .map((claim) => ({
      tech: cleanText(claim.tech),
      type: cleanText(claim.type) || "technology",
      importance: normalizeImportance(claim.importance),
      claim_strength: normalizeClaimStrength(claim.claim_strength),
      evidence_snippet: cleanText(claim.evidence_snippet).slice(0, 280),
      confidence: clamp01(claim.confidence),
    }))
    .filter((claim) => claim.tech.length > 0)
    .slice(0, 15);

  const domains = value.domains
    .map((domain) => ({
      name: cleanText(domain.name),
      confidence: clamp01(domain.confidence),
    }))
    .filter((domain) => domain.name.length > 0)
    .slice(0, 8);

  return {
    candidate_name: value.candidate_name ? cleanText(value.candidate_name) : null,
    primary_roles: value.primary_roles.map(cleanText).filter(Boolean).slice(0, 6),
    years_experience_estimate: value.years_experience_estimate === null
      ? null
      : Math.max(0, Math.min(40, Math.round(value.years_experience_estimate))),
    domains,
    tech_claims: techClaims,
    work_preferences_hints: isRecord(value.work_preferences_hints) ? value.work_preferences_hints : {},
  };
}

export function normalizeQuestionGeneratorResult(
  value: CandidateQuestionGeneratorResult,
  maxQuestions = 10,
): CandidateQuestionGeneratorResult {
  const seen = new Set<string>();
  const questions = value.questions
    .map((question, index) => {
      const id = cleanText(question.id) || `q${index + 1}`;
      const dedupeKey = `${id}:${cleanText(question.question).toLowerCase()}`;
      if (seen.has(dedupeKey)) {
        return null;
      }
      seen.add(dedupeKey);
      return {
        id,
        tech_or_topic: cleanText(question.tech_or_topic) || "experience",
        question: cleanText(question.question),
        intent: "verify_claim" as const,
        expected_answer_shape: "short_story" as const,
        followup_policy: "at_most_one_soft_followup" as const,
      };
    })
    .filter((question): question is CandidatePrescreenQuestion => Boolean(question?.question))
    .slice(0, Math.max(1, Math.min(maxQuestions, 10)));

  return { questions };
}

export function normalizeAnswerInterpreterResult(
  value: CandidateAnswerInterpreterResult,
): CandidateAnswerInterpreterResult {
  return {
    facts: value.facts
      .map((fact) => ({
        key: cleanText(fact.key).slice(0, 120),
        value: normalizeFactValue(fact.value),
        confidence: clamp01(fact.confidence),
      }))
      .filter((fact) => fact.key.length > 0)
      .slice(0, 10),
    notes: cleanText(value.notes).slice(0, 220),
    should_follow_up: Boolean(value.should_follow_up),
    follow_up_question: value.follow_up_question ? cleanText(value.follow_up_question).slice(0, 300) : null,
    ai_assisted_likelihood: isLikelihood(value.ai_assisted_likelihood)
      ? value.ai_assisted_likelihood
      : "low",
    ai_assisted_confidence: clamp01(value.ai_assisted_confidence),
  };
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

function normalizeImportance(value: unknown): ClaimImportance {
  if (value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "medium";
}

function normalizeClaimStrength(value: unknown): ClaimStrength {
  if (value === "strong" || value === "weak") {
    return value;
  }
  return "weak";
}

function isCandidateTechClaim(value: unknown): value is CandidateTechClaim {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.tech)) {
    return false;
  }
  if (!isString(value.type)) {
    return false;
  }
  if (!isImportance(value.importance)) {
    return false;
  }
  if (!isClaimStrength(value.claim_strength)) {
    return false;
  }
  if (!isString(value.evidence_snippet)) {
    return false;
  }
  if (!isNumberInRange(value.confidence, 0, 1)) {
    return false;
  }
  return true;
}

function isCandidateDomainClaim(value: unknown): value is CandidateDomainClaim {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.name)) {
    return false;
  }
  if (!isNumberInRange(value.confidence, 0, 1)) {
    return false;
  }
  return true;
}

function isCandidatePrescreenQuestion(value: unknown): value is CandidatePrescreenQuestion {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.id)) {
    return false;
  }
  if (!isString(value.tech_or_topic)) {
    return false;
  }
  if (!isString(value.question)) {
    return false;
  }
  if (value.intent !== "verify_claim") {
    return false;
  }
  if (value.expected_answer_shape !== "short_story") {
    return false;
  }
  if (value.followup_policy !== "at_most_one_soft_followup") {
    return false;
  }
  return true;
}

function isCandidatePrescreenFact(value: unknown): value is CandidatePrescreenFact {
  if (!isRecord(value)) {
    return false;
  }
  if (!isString(value.key)) {
    return false;
  }
  if (!isNumberInRange(value.confidence, 0, 1)) {
    return false;
  }
  const factValue = (value as Record<string, unknown>).value;
  if (
    factValue !== null &&
    typeof factValue !== "string" &&
    typeof factValue !== "number" &&
    typeof factValue !== "boolean"
  ) {
    return false;
  }
  return true;
}

function isImportance(value: unknown): value is ClaimImportance {
  return value === "high" || value === "medium" || value === "low";
}

function isClaimStrength(value: unknown): value is ClaimStrength {
  return value === "strong" || value === "weak";
}

function isLikelihood(value: unknown): value is "low" | "medium" | "high" {
  return value === "low" || value === "medium" || value === "high";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isNumberInRange(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) {
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

function cleanText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}
