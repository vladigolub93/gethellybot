/**
 * Stage 10: LLM prompt to compose a single match card (job for candidate, candidate for manager).
 * Output: short title, body (<=800 chars, user language, recruiter tone), keyFacts (internal EN).
 * Buttons (Apply/Reject or Accept/Reject) are added in code with matchId.
 */

export interface MatchCardComposeV3InputCandidate {
  role: "candidate";
  language: "en" | "ru" | "uk";
  jobSummary: string;
  headline?: string | null;
  coreTech?: string[];
  mustHaves?: string[];
  domain?: string | null;
  workFormat?: string | null;
  allowedCountries?: string[];
  budget?: string | null;
  whyMatched: string;
}

export interface MatchCardComposeV3InputManager {
  role: "manager";
  language: "en" | "ru" | "uk";
  candidateSummary: string;
  roleSeniority?: string | null;
  yearsExperience?: string | null;
  coreStack?: string[];
  domains?: string[];
  location?: string | null;
  workPreference?: string | null;
  salaryExpectation?: string | null;
  whyMatched: string;
}

export type MatchCardComposeV3Input = MatchCardComposeV3InputCandidate | MatchCardComposeV3InputManager;

export interface MatchCardComposeV3Output {
  title: string;
  body: string;
  keyFacts: Record<string, string>;
}

const RULES_CANDIDATE = `
For CANDIDATE (job card):
- title: short job title or role (e.g. "Senior Backend Engineer").
- body: 1–2 sentence context, then must-haves (max 5), domain, work format + allowed countries, budget, then "Why matched: <one sentence>".
- keyFacts: internal English object with keys like role, mustHaves, domain, workFormat, budget, whyMatched.
- Tone: recruiter-style, warm, concise. Use the requested language for title and body.
`;

const RULES_MANAGER = `
For MANAGER (candidate card):
- title: role/seniority (e.g. "Senior Backend Developer").
- body: role/seniority, years, core stack, domains, location + work preference, salary expectation, then "Why matched: <one sentence>".
- keyFacts: internal English object with keys like role, years, coreStack, domains, location, salaryExpectation, whyMatched.
- Tone: recruiter-style, warm, concise. Use the requested language for title and body.
`;

export function buildMatchCardComposeV3Prompt(input: MatchCardComposeV3Input): string {
  const lang = input.language;
  const rules = input.role === "candidate" ? RULES_CANDIDATE : RULES_MANAGER;

  const payload =
    input.role === "candidate"
      ? {
          role: "candidate",
          language: lang,
          jobSummary: input.jobSummary,
          headline: input.headline ?? null,
          coreTech: input.coreTech ?? [],
          mustHaves: (input.mustHaves ?? []).slice(0, 5),
          domain: input.domain ?? null,
          workFormat: input.workFormat ?? null,
          allowedCountries: input.allowedCountries ?? [],
          budget: input.budget ?? null,
          whyMatched: input.whyMatched,
        }
      : {
          role: "manager",
          language: lang,
          candidateSummary: input.candidateSummary,
          roleSeniority: input.roleSeniority ?? null,
          yearsExperience: input.yearsExperience ?? null,
          coreStack: input.coreStack ?? [],
          domains: input.domains ?? [],
          location: input.location ?? null,
          workPreference: input.workPreference ?? null,
          salaryExpectation: input.salaryExpectation ?? null,
          whyMatched: input.whyMatched,
        };

  return `You are Helly match card composer. Compose a single match card for the recipient.

${rules}

Constraints:
- body length: max 800 characters. Be concise.
- Output STRICT JSON only, no markdown. Keys: "title", "body", "keyFacts".
- keyFacts: plain object, values in English, for internal use.

Input (JSON):
${JSON.stringify(payload, null, 2)}

Return only valid JSON:
{"title":"...","body":"...","keyFacts":{...}}`;
}
