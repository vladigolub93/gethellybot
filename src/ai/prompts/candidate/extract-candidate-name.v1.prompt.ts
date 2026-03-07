export const EXTRACT_CANDIDATE_NAME_V1_PROMPT = `You extract candidate name from resume text.

Return STRICT JSON only.
No markdown.
No commentary.

Input:
- raw resume text

Output JSON:
{
  "first_name": "string or null",
  "last_name": "string or null",
  "full_name": "string or null",
  "confidence": number
}

Rules:
- Use only explicit evidence from the resume text.
- Do not invent name if unclear.
- confidence is between 0 and 1.
- If name is unclear, return null fields with low confidence.
`;

export function buildExtractCandidateNameV1Prompt(input: {
  resumeText: string;
}): string {
  return [
    EXTRACT_CANDIDATE_NAME_V1_PROMPT,
    "",
    "Resume text:",
    input.resumeText.slice(0, 12000),
  ].join("\n");
}
