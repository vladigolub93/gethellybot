import { AUTHENTICITY_POLICY_BLOCK } from "./shared/authenticity-policy";

export function buildManagerInterviewPlanPrompt(jobDescriptionText: string): string {
  return [
    AUTHENTICITY_POLICY_BLOCK,
    "",
    "Task: design a hiring manager intake interview plan.",
    "Use the JD text to find unclear requirements.",
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
    "- Cover must-have skills, nice-to-have skills, responsibilities, budget, urgency.",
    "- Questions must be specific and practical.",
    "",
    `JD text:\n${jobDescriptionText}`,
  ].join("\n");
}
