import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import { JobDescriptionAnalysisV1Result } from "../../shared/types/job-analysis.types";
import {
  JobClaimExtractionResult,
  isJobClaimExtractionResult,
  normalizeJobClaimExtractionResult,
} from "./job-prescreen.schemas";

interface JobClaimExtractorInput {
  jdText: string;
  existingJobProfile?: Record<string, unknown> | null;
  jobAnalysis?: JobDescriptionAnalysisV1Result | null;
}

const JOB_CLAIM_EXTRACTOR_PROMPT = `You are Helly job claim extractor.

Extract structured hiring requirements from messy job description text.
Return STRICT JSON only.
No markdown.
No commentary.

Rules:
- Keep must_have to max 8.
- If JD is vague, explicitly fill risks_or_uncertainties.
- Prefer concrete matching signals over generic buzzwords.

Output JSON:
{
  "role_title": "string",
  "seniority_target": "junior|mid|senior|unknown",
  "domain": [{ "name": "healthcare", "confidence": 0.0 }],
  "product_type": "startup|scaleup|enterprise|agency|unknown",
  "team": { "size": 0, "composition": "string", "timezone": "string or null" },
  "work_format": "remote|hybrid|onsite|unknown",
  "allowed_countries": ["string"],
  "budget": { "currency": "USD|EUR|ILS|GBP|other", "min": 0, "max": 0, "period": "month|year|hour" },
  "must_have": [{ "skill": "string", "confidence": 0.0 }],
  "nice_to_have": [{ "skill": "string", "confidence": 0.0 }],
  "key_tasks": ["string"],
  "risks_or_uncertainties": ["string"]
}`;

export class JobClaimExtractor {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async extract(input: JobClaimExtractorInput): Promise<JobClaimExtractionResult> {
    const prompt = [
      JOB_CLAIM_EXTRACTOR_PROMPT,
      "",
      "Input JSON:",
      JSON.stringify(
        {
          jd_text: input.jdText.slice(0, 20_000),
          existing_job_profile: input.existingJobProfile ?? {},
          job_analysis_v1: input.jobAnalysis ?? null,
        },
        null,
        2,
      ),
    ].join("\n");

    const safe = await callJsonPromptSafe<JobClaimExtractionResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 2200,
      timeoutMs: 60_000,
      promptName: "job_prescreen_claim_extractor_v1",
      schemaHint:
        "Job claim extraction JSON with role_title, seniority_target, domain, product_type, team, work_format, allowed_countries, budget, must_have, nice_to_have, key_tasks, risks_or_uncertainties.",
      validate: isJobClaimExtractionResult,
    });

    if (!safe.ok) {
      this.logger.warn("job.prescreen.claim_extractor.fallback", {
        errorCode: safe.error_code,
      });
      return buildFallbackClaims(input.jdText, input.jobAnalysis ?? null);
    }

    const normalized = normalizeJobClaimExtractionResult(safe.data);
    if (!normalized.must_have.length && !normalized.key_tasks.length) {
      return buildFallbackClaims(input.jdText, input.jobAnalysis ?? null);
    }
    return normalized;
  }
}

function buildFallbackClaims(
  jdText: string,
  analysis: JobDescriptionAnalysisV1Result | null,
): JobClaimExtractionResult {
  const technicalAnalysis =
    analysis && analysis.is_technical_role ? analysis : null;
  const text = jdText.toLowerCase();
  const roleTitle = technicalAnalysis?.role_title_guess ?? guessRoleTitle(jdText);
  const seniority = /\bjunior\b/.test(text) ? "junior" : /\bsenior\b/.test(text) ? "senior" : /\bmid\b/.test(text)
    ? "mid"
    : "unknown";
  const workFormat = /\bhybrid\b/.test(text)
    ? "hybrid"
    : /\bonsite\b/.test(text) || /\bon-site\b/.test(text)
    ? "onsite"
    : /\bremote\b/.test(text)
    ? "remote"
    : "unknown";

  const mustHave = extractSkillHints(jdText).slice(0, 8).map((skill) => ({
    skill,
    confidence: 0.65,
  }));
  const niceToHave = extractSkillHints(jdText).slice(8, 12).map((skill) => ({
    skill,
    confidence: 0.45,
  }));

  return normalizeJobClaimExtractionResult({
    role_title: roleTitle,
    seniority_target: seniority,
    domain: (technicalAnalysis?.domain_inference.primary_domain
      ? [{ name: technicalAnalysis.domain_inference.primary_domain, confidence: 0.7 }]
      : []),
    product_type: mapProductType(technicalAnalysis?.product_context.product_type ?? "unknown"),
    team: {
      size: null,
      composition: "",
      timezone: null,
    },
    work_format: workFormat,
    allowed_countries: [],
    budget: null,
    must_have: mustHave,
    nice_to_have: niceToHave,
    key_tasks: technicalAnalysis?.work_scope.current_tasks ?? [],
    risks_or_uncertainties: technicalAnalysis?.missing_critical_information?.slice(0, 8) ?? [
      "Missing budget",
      "Must-have and nice-to-have are mixed",
      "Product context is not fully clear",
    ],
  });
}

function guessRoleTitle(text: string): string {
  const cleaned = text.replace(/\s+/g, " ");
  const firstLine = cleaned.slice(0, 120).trim();
  if (!firstLine) {
    return "Technical role";
  }
  return firstLine;
}

function extractSkillHints(text: string): string[] {
  const knownSkills = [
    "React",
    "TypeScript",
    "JavaScript",
    "Node.js",
    "NestJS",
    "Express",
    "PostgreSQL",
    "MySQL",
    "Redis",
    "Kafka",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "CI/CD",
    "Playwright",
    "Cypress",
    "Jest",
    "GraphQL",
  ];
  const lower = text.toLowerCase();
  return knownSkills.filter((skill) => lower.includes(skill.toLowerCase()));
}

function mapProductType(
  value: "b2b" | "b2c" | "internal" | "platform" | "unknown",
): "startup" | "scaleup" | "enterprise" | "agency" | "unknown" {
  if (value === "internal") {
    return "enterprise";
  }
  return "unknown";
}
