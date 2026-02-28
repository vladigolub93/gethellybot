export const INTERVIEW_PROGRESS_ONE_LINER_V1_PROMPT = `You generate a one sentence progress confirmation during an interview.

Input JSON:
{
  "role": "candidate | manager",
  "last_answers_english": ["string"],
  "current_profile_json": {}
}

Output JSON:
{
  "one_liner": "string"
}

Rules:
- Exactly one sentence.
- Confirm understanding of what was clarified.
- Specific and concrete.
- No hedging language.
- No bullet points.
- No markdown.
- No extra fields.

Return only valid JSON.`;

export function buildInterviewProgressOneLinerV1Prompt(input: {
  role: "candidate" | "manager";
  lastAnswersEnglish: string[];
  currentProfileJson: unknown;
}): string {
  return [
    INTERVIEW_PROGRESS_ONE_LINER_V1_PROMPT,
    "",
    JSON.stringify(
      {
        role: input.role,
        last_answers_english: input.lastAnswersEnglish,
        current_profile_json: input.currentProfileJson,
      },
      null,
      2,
    ),
  ].join("\n");
}
