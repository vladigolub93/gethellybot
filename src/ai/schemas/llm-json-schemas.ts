/**
 * LLM JSON schema examples and v3 validators for prescreen prompts.
 */

export const interviewPlanSchemaExample = {
  summary: "Strong backend candidate, unclear cloud depth and availability.",
  questions: [
    {
      id: "q1",
      question: "What was your hands-on ownership in your latest backend project?",
      goal: "Validate practical ownership scope",
      gapToClarify: "Depth vs supporting role",
    },
  ],
};

// --- V3 Candidate Resume Analysis ---

export interface CandidateResumeAnalysisV3Schema {
  candidateSnapshot: {
    primaryRoles: string[];
    seniorityEstimate: string;
    yearsExperience: number | null;
    coreStack: string[];
    nicheTechMentioned: string[];
    domainExpertise: string[];
    teamLeadership: string;
    strongestClaims: string[];
    weakestOrUncertainClaims: string[];
  };
  verifyClaims: Array<{ id: string; area: string; reason: string; priority: string }>;
  domainModel: { primaryDomains: string[]; secondaryDomains: string[]; confidence: number };
  mandatoryMissing: { location: boolean; workFormat: boolean; salary: boolean };
  oneSentenceSummary: string;
}

export function isCandidateResumeAnalysisV3Schema(value: unknown): value is CandidateResumeAnalysisV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!o.candidateSnapshot || typeof o.candidateSnapshot !== "object") return false;
  if (!Array.isArray(o.verifyClaims)) return false;
  if (!o.domainModel || typeof o.domainModel !== "object") return false;
  if (!o.mandatoryMissing || typeof o.mandatoryMissing !== "object") return false;
  if (typeof o.oneSentenceSummary !== "string") return false;
  return true;
}

// --- V3 Candidate Questions (max 10) ---

export interface CandidateQuestionV3Schema {
  id: string;
  text: string;
  purpose: "verify" | "preference" | "context";
  mapsTo: string[];
  isMandatory: boolean;
}

export interface CandidateQuestionsV3Schema {
  questions: CandidateQuestionV3Schema[];
}

export function isCandidateQuestionsV3Schema(value: unknown): value is CandidateQuestionsV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!Array.isArray(o.questions)) return false;
  if (o.questions.length > 10) return false;
  return o.questions.every(
    (q: unknown) =>
      q &&
      typeof q === "object" &&
      !Array.isArray(q) &&
      typeof (q as Record<string, unknown>).id === "string" &&
      typeof (q as Record<string, unknown>).text === "string" &&
      Array.isArray((q as Record<string, unknown>).mapsTo),
  );
}

// --- V3 Candidate Answer Interpreter ---

export interface CandidateAnswerInterpreterV3Schema {
  extractedFacts: Record<string, unknown>;
  confidenceUpdates: Record<string, string>;
  followUpNeeded: boolean;
  followUpQuestion: string | null;
  microConfirmation: string;
  ai_assisted_likelihood: "low" | "medium" | "high";
  ai_assisted_confidence: number;
}

export function isCandidateAnswerInterpreterV3Schema(
  value: unknown,
): value is CandidateAnswerInterpreterV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (typeof o.extractedFacts !== "object" || o.extractedFacts === null) return false;
  if (typeof o.confidenceUpdates !== "object" || o.confidenceUpdates === null) return false;
  if (typeof o.followUpNeeded !== "boolean") return false;
  if (o.followUpQuestion !== null && typeof o.followUpQuestion !== "string") return false;
  if (typeof o.microConfirmation !== "string") return false;
  if (!["low", "medium", "high"].includes(String(o.ai_assisted_likelihood))) return false;
  if (typeof o.ai_assisted_confidence !== "number") return false;
  return true;
}

// --- V3 Manager JD Analysis ---

export interface ManagerJdAnalysisV3Schema {
  jobSnapshot: Record<string, unknown>;
  clarifyAreas: Array<{ id: string; area: string; reason: string; priority: string }>;
  mandatoryMissing: { workFormat: boolean; allowedCountries: boolean; budget: boolean };
  oneSentenceSummary: string;
}

export function isManagerJdAnalysisV3Schema(value: unknown): value is ManagerJdAnalysisV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!o.jobSnapshot || typeof o.jobSnapshot !== "object") return false;
  if (!Array.isArray(o.clarifyAreas)) return false;
  if (!o.mandatoryMissing || typeof o.mandatoryMissing !== "object") return false;
  if (typeof o.oneSentenceSummary !== "string") return false;
  return true;
}

// --- V3 Manager Questions (max 10) ---

export interface ManagerQuestionV3Schema {
  id: string;
  text: string;
  purpose: "verify" | "preference" | "context";
  mapsTo: string[];
  isMandatory: boolean;
}

export interface ManagerQuestionsV3Schema {
  questions: ManagerQuestionV3Schema[];
}

export function isManagerQuestionsV3Schema(value: unknown): value is ManagerQuestionsV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!Array.isArray(o.questions)) return false;
  if (o.questions.length > 10) return false;
  return o.questions.every(
    (q: unknown) =>
      q &&
      typeof q === "object" &&
      !Array.isArray(q) &&
      typeof (q as Record<string, unknown>).id === "string" &&
      typeof (q as Record<string, unknown>).text === "string" &&
      Array.isArray((q as Record<string, unknown>).mapsTo),
  );
}

// --- V3 Outbound Compose ---

export interface OutboundComposeV3Schema {
  message: string;
  reaction: string | null;
  buttons: Array<{ text: string; data: string }>;
}

export function isOutboundComposeV3Schema(value: unknown): value is OutboundComposeV3Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (typeof o.message !== "string") return false;
  if (o.reaction !== null && typeof o.reaction !== "string") return false;
  if (!Array.isArray(o.buttons)) return false;
  return true;
}

// --- Intent Router V2 ---

export type IntentRouterV2Intent =
  | "answer"
  | "clarify_question"
  | "skip"
  | "pause"
  | "resume"
  | "restart"
  | "switch_role"
  | "request_matching"
  | "match_apply"
  | "match_reject"
  | "smalltalk"
  | "other";

export interface IntentRouterV2Schema {
  intent: IntentRouterV2Intent;
  language: "en" | "ru" | "uk";
  confidence: number;
  userQuestion: string | null;
}

export function isIntentRouterV2Schema(value: unknown): value is IntentRouterV2Schema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  const intents: IntentRouterV2Intent[] = [
    "answer", "clarify_question", "skip", "pause", "resume", "restart",
    "switch_role", "request_matching", "match_apply", "match_reject", "smalltalk", "other",
  ];
  if (!intents.includes(o.intent as IntentRouterV2Intent)) return false;
  if (!["en", "ru", "uk"].includes(String(o.language))) return false;
  if (typeof o.confidence !== "number") return false;
  if (o.userQuestion !== null && typeof o.userQuestion !== "string") return false;
  return true;
}

// --- Match Card Compose V3 (Stage 10) ---

export interface MatchCardComposeV3OutputSchema {
  title: string;
  body: string;
  keyFacts: Record<string, string>;
}

export function isMatchCardComposeV3OutputSchema(value: unknown): value is MatchCardComposeV3OutputSchema {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (typeof o.title !== "string") return false;
  if (typeof o.body !== "string") return false;
  if (!o.keyFacts || typeof o.keyFacts !== "object" || Array.isArray(o.keyFacts)) return false;
  return true;
}
