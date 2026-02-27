import { LlmClient } from "../ai/llm.client";
import { buildProfileUpdatePrompt } from "../ai/prompts/profile-update.prompt";
import { CandidateProfile, InterviewQuestion } from "../shared/types/domain.types";
import { createEmptyCandidateProfile, normalizeCandidateProfile } from "./profile.schemas";

interface CandidateProfileUpdateInput {
  candidateId: string;
  previousProfile?: CandidateProfile;
  question: InterviewQuestion;
  answerText: string;
  extractedText: string;
}

export class CandidateProfileBuilder {
  constructor(private readonly llmClient: LlmClient) {}

  async update(input: CandidateProfileUpdateInput): Promise<CandidateProfile> {
    const previous = input.previousProfile ?? createEmptyCandidateProfile(input.candidateId);
    const prompt = buildProfileUpdatePrompt({
      role: "candidate",
      previousProfileJson: JSON.stringify(previous),
      question: input.question,
      answerText: input.answerText,
      extractedText: input.extractedText,
    });

    try {
      const raw = await this.llmClient.generateStructuredJson(prompt, 520);
      const parsed = parseJson(raw);
      return normalizeCandidateProfile(input.candidateId, parsed);
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

function fallbackFromPrevious(previous: CandidateProfile, answerText: string): CandidateProfile {
  const fallbackSearchable = `${previous.searchableText} | ${answerText}`.trim().slice(0, 800);
  return normalizeCandidateProfile(previous.candidateId, {
    ...previous,
    searchableText: fallbackSearchable,
  });
}
