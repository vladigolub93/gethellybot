/**
 * Manager JD analysis v3 — recruiter-style prescreen input for hiring side.
 * Focus: product/company/project, domain, tasks, must-have vs nice-to-have, team, constraints, budget, work format, allowed countries.
 */

export interface ManagerJdAnalysisV3Input {
  jobDescriptionText: string;
  existingJobProfile?: Record<string, unknown> | null;
}

const MANAGER_JD_ANALYSIS_V3_SYSTEM = `You are Helly's job description analysis for a short recruiter-style prescreen.
Goal: understand the role and company for matching. No interrogation.

Focus:
- What product/company/project is; domain; real tasks; must-have vs nice-to-have skills; team; constraints
- Budget (range + currency); work format (remote/hybrid/onsite); if remote, allowed countries
- Mandatory missing: workFormat, allowedCountries, budget — set true if not clearly stated

Return STRICT JSON only. No markdown. No commentary.`;

export const MANAGER_JD_ANALYSIS_V3_OUTPUT_SCHEMA = `
Output JSON:
{
  "jobSnapshot": {
    "roleTitle": "string",
    "productOrCompany": "string",
    "domain": "string",
    "realTasks": ["string"],
    "mustHaveSkills": ["string"],
    "niceToHaveSkills": ["string"],
    "teamContext": "string",
    "constraints": ["string"],
    "hiringUrgency": "low|medium|high|unknown"
  },
  "clarifyAreas": [
    {
      "id": "string",
      "area": "string",
      "reason": "string",
      "priority": "high|medium|low"
    }
  ],
  "mandatoryMissing": {
    "workFormat": true | false,
    "allowedCountries": true | false,
    "budget": true | false
  },
  "oneSentenceSummary": "string"
}

- clarifyAreas: max 6. What to clarify in prescreen.
- oneSentenceSummary: for "Here's what I understood" confirmation.`;

export function buildManagerJdAnalysisV3Prompt(input: ManagerJdAnalysisV3Input): string {
  return [
    MANAGER_JD_ANALYSIS_V3_SYSTEM,
    "",
    MANAGER_JD_ANALYSIS_V3_OUTPUT_SCHEMA,
    "",
    "Input:",
    JSON.stringify(
      {
        job_description_text: input.jobDescriptionText.slice(0, 18_000),
        existing_job_profile: input.existingJobProfile ?? {},
      },
      null,
      2,
    ),
  ].join("\n");
}
