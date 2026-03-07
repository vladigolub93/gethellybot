import { AUTHENTICITY_POLICY_BLOCK } from "./shared/authenticity-policy";

export function buildCandidateInterviewPlanPrompt(resumeText: string): string {
  return [
    AUTHENTICITY_POLICY_BLOCK,
    "",
    "Task: design a candidate screening interview plan.",
    "Use the resume text to find missing critical info.",
    "Return STRICT JSON only.",
    "",
    "Schema:",
    "{",
    '  "summary": "string",',
    '  "questions": [',
    "    {",
    '      "id": "q1",',
    '      "question": "string",',
    '      "goal": "string",',
    '      "gapToClarify": "string"',
    "    }",
    "  ]",
    "}",
    "",
    "Rules:",
    "- Max 5 questions.",
    "- Questions must be short and concrete.",
    "- Focus on skills depth, years, domain, availability, salary expectations.",
    "",
    `Resume text:\n${resumeText}`,
  ].join("\n");
}
