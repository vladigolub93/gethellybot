import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildProfileUpdatePrompt } from "../ai/prompts/profile-update.prompt";
import { InterviewQuestion, JobProfile } from "../shared/types/domain.types";
import { createEmptyJobProfile, normalizeJobProfile } from "./profile.schemas";

interface JobProfileUpdateInput {
  jobId: string;
  previousProfile?: JobProfile;
  question: InterviewQuestion;
  answerText: string;
  extractedText: string;
}

export class JobProfileBuilder {
  constructor(private readonly llmClient: LlmClient) {}

  async update(input: JobProfileUpdateInput): Promise<JobProfile> {
    const previous = input.previousProfile ?? createEmptyJobProfile(input.jobId);
    const prompt = buildProfileUpdatePrompt({
      role: "manager",
      previousProfileJson: JSON.stringify(previous),
      question: input.question,
      answerText: input.answerText,
      extractedText: input.extractedText,
    });

    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        prompt,
        maxTokens: 520,
        promptName: "job_profile_builder_v1",
        schemaHint: "Job profile JSON schema.",
      });
      if (!safe.ok) {
        throw new Error(`job_profile_builder_v1_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      const parsed = parseJson(raw);
      return normalizeJobProfile(input.jobId, parsed);
    } catch {
      return fallbackFromPrevious(previous, input.answerText);
    }
  }
}

function parseJson(raw: string): unknown {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Invalid profile JSON output.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1));
}

function fallbackFromPrevious(previous: JobProfile, answerText: string): JobProfile {
  const fallbackSearchable = `${previous.searchableText} | ${answerText}`.trim().slice(0, 800);
  return normalizeJobProfile(previous.jobId, {
    ...previous,
    searchableText: fallbackSearchable,
  });
}
