export const JOB_ONE_LINER_V1_PROMPT = `You generate a one sentence confirmation for a hiring manager.

Input JSON:
{
  "job_analysis_json": {},
  "current_job_profile_json": {}
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

export function buildJobOneLinerV1Prompt(input: {
  jobAnalysisJson: unknown;
  currentJobProfileJson: unknown;
}): string {
  return [
    JOB_ONE_LINER_V1_PROMPT,
    "",
    JSON.stringify(
      {
        job_analysis_json: input.jobAnalysisJson,
        current_job_profile_json: input.currentJobProfileJson,
      },
      null,
      2,
    ),
  ].join("\n");
}
