import { InterviewQuestion } from "../../shared/types/domain.types";
import { AUTHENTICITY_POLICY_BLOCK } from "./shared/authenticity-policy";

interface ProfileUpdatePromptInput {
  role: "candidate" | "manager";
  previousProfileJson: string;
  question: InterviewQuestion;
  answerText: string;
  extractedText: string;
}

export function buildProfileUpdatePrompt(input: ProfileUpdatePromptInput): string {
  const roleSchema =
    input.role === "candidate"
      ? [
          "{",
          '  "headline": "string",',
          '  "seniorityEstimate": "junior|mid|senior|lead|unknown",',
          '  "coreSkills": ["string"],',
          '  "secondarySkills": ["string"],',
          '  "yearsExperienceTotal": "string",',
          '  "relevantExperienceSummary": "string",',
          '  "domains": ["string"],',
          '  "notableProjects": [{"role":"string","impact":"string","stack":["string"]}],',
          '  "constraints": {"timezone":"string","location":"string","workFormat":"string","salaryExpectation":"string","availabilityDate":"string"},',
          '  "communication": {"englishLevelEstimate":"string","notes":"string"},',
          '  "redFlags": ["string"],',
          '  "dealbreakers": ["string"],',
          '  "searchableText": "string"',
          "}",
        ].join("\n")
      : [
          "{",
          '  "title": "string",',
          '  "mustHaveSkills": ["string"],',
          '  "niceToHaveSkills": ["string"],',
          '  "responsibilitiesSummary": "string",',
          '  "domain": "string",',
          '  "seniorityTarget": "string",',
          '  "constraints": {"timezoneOverlap":"string","location":"string","format":"string","budgetRange":"string","contractType":"string"},',
          '  "interviewProcessSummary": "string",',
          '  "urgency": "string",',
          '  "dealbreakers": ["string"],',
          '  "searchableText": "string"',
          "}",
        ].join("\n");

  return [
    AUTHENTICITY_POLICY_BLOCK,
    "",
    "Task: update a structured profile after one interview answer.",
    "Return STRICT JSON only.",
    "Do not remove previously known facts unless contradicted.",
    "Keep concise and factual.",
    "",
    `Role: ${input.role}`,
    "",
    "Expected output JSON shape:",
    roleSchema,
    "",
    "Context:",
    `Question: ${input.question.question}`,
    `Goal: ${input.question.goal}`,
    `Answer: ${input.answerText}`,
    "",
    "Previous profile JSON:",
    input.previousProfileJson,
    "",
    "Extracted document text snippet:",
    input.extractedText.slice(0, 2200),
  ].join("\n");
}
