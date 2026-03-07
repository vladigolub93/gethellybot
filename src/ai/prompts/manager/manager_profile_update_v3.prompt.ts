/**
 * Manager (job) profile update v3 — merge new facts into job profile with confidence.
 * Never overwrite higher-confidence facts with lower without reason.
 */

export interface ManagerProfileUpdateV3Input {
  currentJobProfile: Record<string, unknown>;
  questionId: string;
  questionText: string;
  answerText: string;
  interpretedFacts: Record<string, unknown>;
  confidenceUpdates: Record<string, string>;
}

const MANAGER_PROFILE_UPDATE_V3_SYSTEM = `You merge new prescreen facts into the job/role structured profile.
Rules:
- Add or update only fields the answer supports.
- Never overwrite higher-confidence facts with lower without good reason.
- Use English for keys and stored values.`;

export const MANAGER_PROFILE_UPDATE_V3_OUTPUT_SCHEMA = `
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
}`;

export function buildManagerProfileUpdateV3Prompt(input: ManagerProfileUpdateV3Input): string {
  return [
    MANAGER_PROFILE_UPDATE_V3_SYSTEM,
    "",
    MANAGER_PROFILE_UPDATE_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        current_job_profile: input.currentJobProfile,
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
