/**
 * Candidate answer interpreter v3.
 * Output: extractedFacts (English), confidenceUpdates, followUpNeeded, followUpQuestion (max one), microConfirmation (user language).
 */

export type PrescreenV3Language = "en" | "ru" | "uk";

export interface CandidateAnswerInterpreterV3Input {
  language: PrescreenV3Language;
  questionId: string;
  questionText: string;
  answer: string;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const CANDIDATE_ANSWER_INTERPRETER_V3_SYSTEM = `You interpret one candidate prescreen answer.
- Extract facts in English (for embeddings/profile). Update confidence for existing claims.
- At most ONE follow-up: set followUpNeeded true and provide followUpQuestion only if answer is too vague for matching. If still unclear after one follow-up, we accept and lower confidence—so use follow-up sparingly.
- microConfirmation: one short sentence in the USER's language (en|ru|uk) to confirm understanding, e.g. "Got it, I noted X/Y."
- Detect AI-assisted style: set ai_assisted_likelihood and ai_assisted_confidence. Never accuse; we use this only to show the standard warning once per question.`;

export const CANDIDATE_ANSWER_INTERPRETER_V3_OUTPUT_SCHEMA = `
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
}

- extractedFacts: flat keys in English, e.g. "skills.redis.depth", "location.country".
- confidenceUpdates: only for claims that were updated by this answer.
- followUpQuestion: only if followUpNeeded is true. One question max. In user language.
- microConfirmation: one sentence in user language.`;

export function buildCandidateAnswerInterpreterV3Prompt(input: CandidateAnswerInterpreterV3Input): string {
  return [
    CANDIDATE_ANSWER_INTERPRETER_V3_SYSTEM,
    "",
    CANDIDATE_ANSWER_INTERPRETER_V3_OUTPUT_SCHEMA,
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
