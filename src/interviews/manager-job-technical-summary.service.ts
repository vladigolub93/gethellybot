import { LlmClient } from "../ai/llm.client";
import { JOB_TECHNICAL_SUMMARY_V2_PROMPT } from "../ai/prompts/manager/job-technical-summary.v2.prompt";
import { JobProfileV2, JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";

export class ManagerJobTechnicalSummaryService {
  constructor(private readonly llmClient: LlmClient) {}

  async generate(jobProfile: JobProfileV2): Promise<JobTechnicalSummaryV2> {
    const prompt = [
      JOB_TECHNICAL_SUMMARY_V2_PROMPT,
      "",
      JSON.stringify(
        {
          updated_job_profile: jobProfile,
        },
        null,
        2,
      ),
    ].join("\n");

    const raw = await this.llmClient.generateStructuredJson(prompt, 1000);
    return parseJobTechnicalSummary(raw);
  }
}

function parseJobTechnicalSummary(raw: string): JobTechnicalSummaryV2 {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Job technical summary output is not valid JSON.");
  }

  const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
  const domainNeedRaw = toText(parsed.domain_need).toLowerCase();
  const ownershipRaw = toText(parsed.ownership_expectation).toLowerCase();

  const summary: JobTechnicalSummaryV2 = {
    headline: toText(parsed.headline),
    product_context: toText(parsed.product_context),
    current_tasks: toStringArray(parsed.current_tasks, 10),
    current_challenges: toStringArray(parsed.current_challenges, 10),
    core_tech: toStringArray(parsed.core_tech, 15),
    key_requirements: toStringArray(parsed.key_requirements, 15),
    domain_need:
      domainNeedRaw === "none" ||
      domainNeedRaw === "helpful" ||
      domainNeedRaw === "important" ||
      domainNeedRaw === "critical" ||
      domainNeedRaw === "unknown"
        ? (domainNeedRaw as JobTechnicalSummaryV2["domain_need"])
        : "unknown",
    ownership_expectation:
      ownershipRaw === "executor" ||
      ownershipRaw === "contributor" ||
      ownershipRaw === "owner" ||
      ownershipRaw === "technical_lead" ||
      ownershipRaw === "unknown"
        ? (ownershipRaw as JobTechnicalSummaryV2["ownership_expectation"])
        : "unknown",
    notes_for_matching: toText(parsed.notes_for_matching),
  };

  if (!summary.headline || !summary.product_context || !summary.notes_for_matching) {
    throw new Error("Job technical summary output is invalid: missing required fields.");
  }

  return summary;
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function toStringArray(value: unknown, max: number): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter((item) => Boolean(item))
    .slice(0, max);
}
