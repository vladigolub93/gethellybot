export const JSON_REPAIR_V1_PROMPT = `You repair malformed JSON.

You receive:
- schema_hint, plain text description of expected shape.
- raw, malformed JSON-like text.

Rules:
- Return valid JSON only.
- Keep keys and values as close as possible to raw.
- Do not add commentary.
- Do not wrap in markdown.
- If a field is unknown, use null or an empty array or empty object as appropriate.

Input JSON:
{
  "schema_hint": "string",
  "raw": "string"
}

Return only valid JSON.`;

export function buildJsonRepairV1Prompt(input: {
  schemaHint: string;
  raw: string;
}): string {
  return [
    JSON_REPAIR_V1_PROMPT,
    "",
    "Input JSON:",
    JSON.stringify(
      {
        schema_hint: input.schemaHint,
        raw: input.raw,
      },
      null,
      2,
    ),
  ].join("\n");
}

