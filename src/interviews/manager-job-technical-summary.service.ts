import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
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

    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      prompt,
      maxTokens: 1000,
      promptName: "job_technical_summary_v2",
      schemaHint:
        "Job technical summary v2 JSON with headline, product_context, current_tasks, current_challenges, core_tech, key_requirements, domain_need, ownership_expectation, notes_for_matching.",
    });
    if (!safe.ok) {
      throw new Error(`job_technical_summary_v2_failed:${safe.error_code}`);
    }
    const raw = JSON.stringify(safe.data);
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
