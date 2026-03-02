/**
 * Manager answer interpreter v3.
 * Output: extractedFacts (English), confidenceUpdates, followUpNeeded, followUpQuestion (max one), microConfirmation (user language).
 */

export type PrescreenV3Language = "en" | "ru" | "uk";

export interface ManagerAnswerInterpreterV3Input {
  language: PrescreenV3Language;
  questionId: string;
  questionText: string;
  answer: string;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const MANAGER_ANSWER_INTERPRETER_V3_SYSTEM = `You interpret one hiring manager prescreen answer.
- Extract facts in English. Update confidence for existing claims.
- At most ONE follow-up. microConfirmation: one short sentence in the USER's language (en|ru|uk).
- Detect AI-assisted style: ai_assisted_likelihood, ai_assisted_confidence.`;

export const MANAGER_ANSWER_INTERPRETER_V3_OUTPUT_SCHEMA = `
Output STRICT JSON:
{
  "extractedFacts": {
    "key": "value or number or boolean"
  },
  "confidenceUpdates": {
    "key": "high|medium|low"
  },
  "followUpNeeded": boolean,
  "followUpQuestion": "string" | null,
  "microConfirmation": "string",
  "ai_assisted_likelihood": "low|medium|high",
  "ai_assisted_confidence": 0-1
}`;

export function buildManagerAnswerInterpreterV3Prompt(input: ManagerAnswerInterpreterV3Input): string {
  return [
    MANAGER_ANSWER_INTERPRETER_V3_SYSTEM,
    "",
    MANAGER_ANSWER_INTERPRETER_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        language: input.language,
        question_id: input.questionId,
        question_text: input.questionText,
        answer: input.answer,
        known_facts: input.knownFacts.slice(0, 40),
      },
      null,
      2,
    ),
  ].join("\n");
}
