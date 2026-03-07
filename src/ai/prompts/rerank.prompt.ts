export interface RerankCandidateInput {
  candidateUserId: number;
  similarityScore: number;
  summaryText: string;
}

export function buildRerankPrompt(jobSummary: string, candidates: RerankCandidateInput[]): string {
  return [
    "Task: rank candidate matches for a job intake.",
    "Return STRICT JSON only.",
    "",
    "Output schema:",
    "{",
    '  "ranked": [',
    "    {",
    '      "candidateUserId": 123,',
    '      "score": 0.0,',
    '      "explanation": "string"',
    "    }",
    "  ]",
    "}",
    "",
    "Rules:",
    "- Keep score in [0,1].",
    "- Rank best to worst.",
    "- Explanation max 140 chars.",
    "- Include only provided candidates.",
    "",
    `Job summary:\n${jobSummary}`,
    "",
    `Candidates:\n${JSON.stringify(candidates)}`,
  ].join("\n");
}
