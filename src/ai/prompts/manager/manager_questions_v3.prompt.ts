/**
 * Manager questions v3 — up to N questions, total prescreen <= 10.
 * Must uncover: product, tasks, must-have skills, constraints, budget, format, countries, hiring urgency.
 */

export type PrescreenV3Language = "en" | "ru" | "uk";

export interface ManagerQuestionsV3Input {
  language: PrescreenV3Language;
  jdAnalysis: Record<string, unknown>;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
  unansweredMandatory: { workFormat?: boolean; allowedCountries?: boolean; budget?: boolean };
  alreadyAskedCount: number;
  maxTotalQuestions: number;
}

const MANAGER_QUESTIONS_V3_SYSTEM = `You are Helly generating a short recruiter-style prescreen plan for a hiring manager.
Rules:
- Total prescreen at most 10 questions. You are given already_asked_count and max_total_questions.
- Questions must be simple and conversational. No interrogation.
- Cover: product, tasks, must-have skills, constraints, budget, work format, allowed countries, hiring urgency.
- Each question: id, text (friendly), purpose (verify|preference|context), mapsTo, isMandatory (true for workFormat, allowedCountries, budget).`;

export const MANAGER_QUESTIONS_V3_OUTPUT_SCHEMA = `
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

- text in the same language as input language (en|ru|uk).`;

export function buildManagerQuestionsV3Prompt(input: ManagerQuestionsV3Input): string {
  const remaining = Math.max(0, input.maxTotalQuestions - input.alreadyAskedCount);
  return [
    MANAGER_QUESTIONS_V3_SYSTEM,
    "",
    MANAGER_QUESTIONS_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        language: input.language,
        jd_analysis: input.jdAnalysis,
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
