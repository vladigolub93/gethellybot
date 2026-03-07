import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import {
  CandidateClaimExtractionResult,
  CandidateTechClaim,
  isCandidateClaimExtractionResult,
  normalizeClaimExtractionResult,
} from "./candidate-prescreen.schemas";

interface CandidateClaimExtractorInput {
  resumeText: string;
  existingCandidateProfile?: Record<string, unknown> | null;
}

const CLAIM_EXTRACTOR_PROMPT = `You are Helly candidate claim extractor.

Extract structured candidate claims from resume text.
Return STRICT JSON only.
Do not add markdown.
Do not add commentary.

Requirements:
- Keep only top 10-15 most relevant claims.
- Prioritize high impact and niche technical claims first.
- Add short evidence snippets from the resume where possible.
- If uncertain, reduce confidence.

Output JSON:
{
  "candidate_name": "string or null",
  "primary_roles": ["string"],
  "years_experience_estimate": 0,
  "domains": [
    { "name": "string", "confidence": 0.0 }
  ],
  "tech_claims": [
    {
      "tech": "string",
      "type": "technology",
      "importance": "high|medium|low",
      "claim_strength": "strong|weak",
      "evidence_snippet": "string",
      "confidence": 0.0
    }
  ],
  "work_preferences_hints": {}
}`;

export class CandidateClaimExtractor {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async extract(input: CandidateClaimExtractorInput): Promise<CandidateClaimExtractionResult> {
    const prompt = [
      CLAIM_EXTRACTOR_PROMPT,
      "",
      "Input JSON:",
      JSON.stringify(
        {
          resume_text: input.resumeText.slice(0, 18_000),
          existing_candidate_profile: input.existingCandidateProfile ?? {},
        },
        null,
        2,
      ),
    ].join("\n");

    const safe = await callJsonPromptSafe<CandidateClaimExtractionResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 1800,
      timeoutMs: 60_000,
      promptName: "candidate_prescreen_claim_extractor_v1",
      schemaHint:
        "Claim extraction JSON with candidate_name, primary_roles, years_experience_estimate, domains, tech_claims, work_preferences_hints.",
      validate: isCandidateClaimExtractionResult,
    });

    if (!safe.ok) {
      this.logger.warn("candidate.prescreen.claim_extractor.fallback", {
        errorCode: safe.error_code,
      });
      return buildFallbackClaims(input.resumeText);
    }

    const normalized = normalizeClaimExtractionResult(safe.data);
    if (!normalized.tech_claims.length) {
      return buildFallbackClaims(input.resumeText);
    }
    return normalized;
  }
}

function buildFallbackClaims(resumeText: string): CandidateClaimExtractionResult {
  const text = resumeText.slice(0, 14_000);
  const candidateName = extractCandidateName(text);
  const roles = extractPrimaryRoles(text);
  const years = extractYears(text);
  const techClaims = extractTechClaims(text).slice(0, 12);
  const domains = extractDomainHints(text).slice(0, 6);

  return {
    candidate_name: candidateName,
    primary_roles: roles,
    years_experience_estimate: years,
    domains,
    tech_claims: techClaims,
    work_preferences_hints: {},
  };
}

function extractCandidateName(text: string): string | null {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 5);
  for (const line of lines) {
    if (/^[A-Z][a-z]+\s+[A-Z][a-z]+$/.test(line)) {
      return line;
    }
  }
  return null;
}

function extractPrimaryRoles(text: string): string[] {
  const lower = text.toLowerCase();
  const roles: string[] = [];
  if (/backend|back-end/.test(lower)) {
    roles.push("Backend Developer");
  }
  if (/frontend|front-end/.test(lower)) {
    roles.push("Frontend Developer");
  }
  if (/full[-\s]?stack/.test(lower)) {
    roles.push("Full-Stack Developer");
  }
  if (/qa|test automation|sdet/.test(lower)) {
    roles.push("QA Automation Engineer");
  }
  if (!roles.length) {
    roles.push("Software Engineer");
  }
  return roles.slice(0, 4);
}

function extractYears(text: string): number | null {
  const explicit = text.match(/(\d{1,2})\+?\s*(?:years|yrs|рок|роки|лет|рік)/i);
  if (explicit) {
    const value = Number(explicit[1]);
    if (Number.isFinite(value) && value >= 0 && value <= 40) {
      return value;
    }
  }
  return null;
}

function extractDomainHints(text: string): Array<{ name: string; confidence: number }> {
  const lower = text.toLowerCase();
  const hints: Array<{ name: string; confidence: number }> = [];
  pushDomainHint(hints, lower, "fintech", /(fintech|payment|bank|trading|wallet)/);
  pushDomainHint(hints, lower, "e-commerce", /(e-commerce|ecommerce|shop|checkout|cart)/);
  pushDomainHint(hints, lower, "healthcare", /(health|medical|clinic|ehr|hipaa)/);
  pushDomainHint(hints, lower, "saas", /(saas|b2b|subscription|tenant)/);
  pushDomainHint(hints, lower, "marketplace", /(marketplace|seller|buyer|listing)/);
  return hints;
}

function pushDomainHint(
  hints: Array<{ name: string; confidence: number }>,
  textLower: string,
  name: string,
  pattern: RegExp,
): void {
  if (pattern.test(textLower)) {
    hints.push({ name, confidence: 0.68 });
  }
}

function extractTechClaims(text: string): CandidateTechClaim[] {
  const lower = text.toLowerCase();
  const highImpactTech = [
    "kubernetes",
    "kafka",
    "redis",
    "postgresql",
    "websocket",
    "webrtc",
    "dpdk",
    "rabbitmq",
    "elasticsearch",
    "prometheus",
    "grafana",
  ];
  const commonTech = [
    "node.js",
    "typescript",
    "javascript",
    "react",
    "next.js",
    "express",
    "docker",
    "aws",
    "gcp",
    "azure",
    "mysql",
  ];

  const claims: CandidateTechClaim[] = [];
  for (const tech of highImpactTech) {
    if (lower.includes(tech.replace(".", "")) || lower.includes(tech)) {
      claims.push({
        tech: canonicalizeTech(tech),
        type: "technology",
        importance: "high",
        claim_strength: "strong",
        evidence_snippet: buildEvidenceSnippet(text, tech),
        confidence: 0.8,
      });
    }
  }

  for (const tech of commonTech) {
    if (lower.includes(tech.replace(".", "")) || lower.includes(tech)) {
      claims.push({
        tech: canonicalizeTech(tech),
        type: "technology",
        importance: claims.length < 6 ? "high" : "medium",
        claim_strength: "weak",
        evidence_snippet: buildEvidenceSnippet(text, tech),
        confidence: 0.62,
      });
    }
  }

  const deduped = new Map<string, CandidateTechClaim>();
  for (const claim of claims) {
    if (!deduped.has(claim.tech.toLowerCase())) {
      deduped.set(claim.tech.toLowerCase(), claim);
    }
  }

  return Array.from(deduped.values()).slice(0, 15);
}

function canonicalizeTech(value: string): string {
  const compact = value.trim().toLowerCase();
  if (compact === "node.js") {
    return "Node.js";
  }
  if (compact === "next.js") {
    return "Next.js";
  }
  if (compact === "javascript") {
    return "JavaScript";
  }
  if (compact === "typescript") {
    return "TypeScript";
  }
  if (compact === "postgresql") {
    return "PostgreSQL";
  }
  if (compact === "react") {
    return "React";
  }
  if (compact === "aws") {
    return "AWS";
  }
  if (compact === "gcp") {
    return "GCP";
  }
  if (compact === "azure") {
    return "Azure";
  }
  if (compact === "webrtc") {
    return "WebRTC";
  }
  return value
    .split(" ")
    .map((part) => (part.length ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

function buildEvidenceSnippet(text: string, token: string): string {
  const index = text.toLowerCase().indexOf(token.toLowerCase());
  if (index < 0) {
    return "";
  }
  const start = Math.max(0, index - 45);
  const end = Math.min(text.length, index + token.length + 70);
  return text
    .slice(start, end)
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
}
