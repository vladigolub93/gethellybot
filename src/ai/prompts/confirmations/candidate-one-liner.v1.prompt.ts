export const CANDIDATE_ONE_LINER_V1_PROMPT = `You generate a one sentence confirmation for a candidate.

Input JSON:
{
  "resume_analysis_json": {},
  "current_profile_json": {}
}

Output JSON:
{
  "one_liner": "string"
}

Rules:
- Exactly one sentence.
- Specific and concrete.
- No hedging language.
- No bullet points.
- No markdown.
- No extra fields.

Return only valid JSON.`;

export function buildCandidateOneLinerV1Prompt(input: {
  resumeAnalysisJson: unknown;
  currentProfileJson: unknown;
}): string {
  return [
    CANDIDATE_ONE_LINER_V1_PROMPT,
    "",
    JSON.stringify(
      {
        resume_analysis_json: input.resumeAnalysisJson,
        current_profile_json: input.currentProfileJson,
      },
      null,
      2,
    ),
  ].join("\n");
}
