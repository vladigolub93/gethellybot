export const PROFILE_SUMMARY_V2_PROMPT = `You generate concise profile text for matching.

Input JSON:
{
  "entity_type": "candidate|job",
  "profile_json": {}
}

Output JSON:
{
  "profile_text": "string"
}

Rules:
- Write in English only.
- Keep it concise and matching-focused.
- Mention role, seniority, core technologies, domain, work format, location or allowed countries, and budget or salary if available.
- Use factual language, no hype.
- If some fields are unknown, state unknown briefly.
- No markdown.
- No extra fields.

Return only valid JSON.`;

export function buildProfileSummaryV2Prompt(input: {
  entityType: "candidate" | "job";
  profileJson: unknown;
}): string {
  return [
    PROFILE_SUMMARY_V2_PROMPT,
    "",
    JSON.stringify(
      {
        entity_type: input.entityType,
        profile_json: input.profileJson,
      },
      null,
      2,
    ),
  ].join("\n");
}

