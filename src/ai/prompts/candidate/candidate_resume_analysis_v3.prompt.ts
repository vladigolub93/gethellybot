/**
 * Candidate resume analysis v3 — recruiter-style prescreen input.
 * Output: candidateSnapshot, verifyClaims (prescreen_focus up to 6), domainModel, mandatoryMissing, oneSentenceSummary.
 */

export interface CandidateResumeAnalysisV3Input {
  resumeText: string;
  existingProfile?: Record<string, unknown> | null;
}

const CANDIDATE_RESUME_ANALYSIS_V3_SYSTEM = `You are Helly's resume analysis for a short recruiter-style prescreen.
Goal: understand the candidate for matching. No interrogation. Extract what we can verify in up to 10 questions.

Focus:
- Role(s), seniority estimate, years, core stack, niche tech mentioned, domain expertise, team/leadership
- Strongest claims vs weakest/uncertain claims
- prescreen_focus: up to 6 areas to verify (e.g. "Redis depth", "AWS real usage", "Kubernetes listed but maybe shallow")
- If present, extract: location (country+city), work format preference, salary expectation (monthly/yearly + currency)

Return STRICT JSON only. No markdown. No commentary.`;

export const CANDIDATE_RESUME_ANALYSIS_V3_OUTPUT_SCHEMA = `
Output JSON:
{
  "candidateSnapshot": {
    "primaryRoles": ["string"],
    "seniorityEstimate": "junior|middle|senior|lead|principal|unknown",
    "yearsExperience": number | null,
    "coreStack": ["string"],
    "nicheTechMentioned": ["string"],
    "domainExpertise": ["string"],
    "teamLeadership": "none|some|lead|unknown",
    "strongestClaims": ["string"],
    "weakestOrUncertainClaims": ["string"]
  },
  "verifyClaims": [
    {
      "id": "string",
      "area": "string",
      "reason": "string",
      "priority": "high|medium|low"
    }
  ],
  "domainModel": {
    "primaryDomains": ["string"],
    "secondaryDomains": ["string"],
    "confidence": 0-1
  },
  "mandatoryMissing": {
    "location": true | false,
    "workFormat": true | false,
    "salary": true | false
  },
  "oneSentenceSummary": "string"
}

Rules:
- verifyClaims: max 6 items. Areas we should verify in prescreen.
- mandatoryMissing: true if not clearly stated in resume.
- oneSentenceSummary: one sentence for "Here's what I understood" confirmation.`;

export function buildCandidateResumeAnalysisV3Prompt(input: CandidateResumeAnalysisV3Input): string {
  return [
    CANDIDATE_RESUME_ANALYSIS_V3_SYSTEM,
    "",
    CANDIDATE_RESUME_ANALYSIS_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        resume_text: input.resumeText.slice(0, 18_000),
        existing_profile: input.existingProfile ?? {},
      },
      null,
      2,
    ),
  ].join("\n");
}
