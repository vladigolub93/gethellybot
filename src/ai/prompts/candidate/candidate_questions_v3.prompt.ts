/**
 * Candidate questions v3 — up to N questions, total prescreen <= 10.
 * Friendly recruiter phrasing. Mandatory fields (location, work format, salary) must be collected within 10.
 */

export type PrescreenV3Language = "en" | "ru" | "uk";

export interface CandidateQuestionsV3Input {
  language: PrescreenV3Language;
  resumeAnalysis: Record<string, unknown>;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
  unansweredMandatory: { location?: boolean; workFormat?: boolean; salary?: boolean };
  alreadyAskedCount: number;
  maxTotalQuestions: number;
}

const CANDIDATE_QUESTIONS_V3_SYSTEM = `You are Helly generating a short recruiter-style prescreen plan.
Rules:
- Total interview must be at most 10 questions. You are given how many are already asked and how many remain.
- Questions must be simple and conversational. No interrogation. No "prove it with exact files."
- For niche tech: ask "did you personally use it, how, how often?"
- Encourage real examples and voice: e.g. "Reply with a real example. If typing is annoying, send a voice message."
- Each question: id, text (friendly recruiter phrasing), purpose (verify|preference|context), mapsTo (array of profile paths), isMandatory (true only for location/workFormat/salary).`;

export const CANDIDATE_QUESTIONS_V3_OUTPUT_SCHEMA = `
Output STRICT JSON:
{
  "questions": [
    {
      "id": "string",
      "text": "string",
      "purpose": "verify|preference|context",
      "mapsTo": ["string"],
      "isMandatory": boolean
    }
  ]
}

- text must be in the same language as input language (en|ru|uk).
- mapsTo: e.g. ["skills.redis.depth", "location.country"].
- isMandatory: true only for questions that collect location, work format, or salary.`;

export function buildCandidateQuestionsV3Prompt(input: CandidateQuestionsV3Input): string {
  const remaining = Math.max(0, input.maxTotalQuestions - input.alreadyAskedCount);
  return [
    CANDIDATE_QUESTIONS_V3_SYSTEM,
    "",
    CANDIDATE_QUESTIONS_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        language: input.language,
        resume_analysis: input.resumeAnalysis,
        known_facts: input.knownFacts.slice(0, 50),
        unanswered_mandatory: input.unansweredMandatory,
        already_asked_count: input.alreadyAskedCount,
        max_total_questions: input.maxTotalQuestions,
        remaining_slots: remaining,
      },
      null,
      2,
    ),
  ].join("\n");
}
