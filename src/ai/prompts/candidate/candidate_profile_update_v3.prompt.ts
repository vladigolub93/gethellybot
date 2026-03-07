/**
 * Candidate profile update v3 — merge new facts into structured profile with confidence.
 * Never overwrite higher-confidence facts with lower without reason.
 */

export interface CandidateProfileUpdateV3Input {
  currentProfile: Record<string, unknown>;
  questionId: string;
  questionText: string;
  answerText: string;
  interpretedFacts: Record<string, unknown>;
  confidenceUpdates: Record<string, string>;
}

const CANDIDATE_PROFILE_UPDATE_V3_SYSTEM = `You merge new prescreen facts into the candidate's structured profile.
Rules:
- Add or update only fields that the answer supports.
- Never overwrite higher-confidence facts with lower-confidence without a good reason (e.g. user correction).
- Keep profile flat or nested consistently. Use English for all keys and stored values (for embeddings).
- Do not invent information.`;

export const CANDIDATE_PROFILE_UPDATE_V3_OUTPUT_SCHEMA = `
Output STRICT JSON:
{
  "updatedProfile": { ... },
  "changes": [
    {
      "path": "string",
      "oldValue": "any",
      "newValue": "any",
      "confidence": "high|medium|low"
    }
  ]
}

- updatedProfile: full merged profile (skills, location, workFormat, salary, domains, etc.).
- changes: list of what changed for logging.`;

export function buildCandidateProfileUpdateV3Prompt(input: CandidateProfileUpdateV3Input): string {
  return [
    CANDIDATE_PROFILE_UPDATE_V3_SYSTEM,
    "",
    CANDIDATE_PROFILE_UPDATE_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        current_profile: input.currentProfile,
        question_id: input.questionId,
        question_text: input.questionText,
        answer_text: input.answerText,
        interpreted_facts: input.interpretedFacts,
        confidence_updates: input.confidenceUpdates,
      },
      null,
      2,
    ),
  ].join("\n");
}
