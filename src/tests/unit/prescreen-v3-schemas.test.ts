/**
 * Unit tests for v3 JSON parsing and max-10-question enforcement.
 * Run: ts-node src/tests/unit/prescreen-v3-schemas.test.ts
 */
import assert from "node:assert/strict";
import {
  isCandidateQuestionsV3Schema,
  isManagerQuestionsV3Schema,
  isCandidateResumeAnalysisV3Schema,
  isCandidateAnswerInterpreterV3Schema,
  isManagerJdAnalysisV3Schema,
  isOutboundComposeV3Schema,
} from "../../ai/schemas/llm-json-schemas";

function runTests(): void {
  // Candidate questions: max 10
  const valid10 = {
    questions: Array.from({ length: 10 }, (_, i) => ({
      id: `q${i + 1}`,
      text: "Did you use Redis in production?",
      purpose: "verify",
      mapsTo: ["skills.redis.depth"],
      isMandatory: false,
    })),
  };
  assert.equal(isCandidateQuestionsV3Schema(valid10), true, "candidate questions: 10 allowed");

  const invalid11 = {
    questions: Array.from({ length: 11 }, (_, i) => ({
      id: `q${i + 1}`,
      text: "Q?",
      purpose: "verify",
      mapsTo: [],
      isMandatory: false,
    })),
  };
  assert.equal(isCandidateQuestionsV3Schema(invalid11), false, "candidate questions: 11 rejected");

  assert.equal(isCandidateQuestionsV3Schema(null), false);
  assert.equal(isCandidateQuestionsV3Schema({}), false);

  // Manager questions: max 10
  const validManager10 = {
    questions: Array.from({ length: 10 }, (_, i) => ({
      id: `jq${i + 1}`,
      text: "What's the team size?",
      purpose: "context",
      mapsTo: ["team.size"],
      isMandatory: false,
    })),
  };
  assert.equal(isManagerQuestionsV3Schema(validManager10), true, "manager questions: 10 allowed");
  assert.equal(
    isManagerQuestionsV3Schema({
      questions: Array.from({ length: 11 }, (_, i) => ({
        id: `jq${i + 1}`,
        text: "Q?",
        purpose: "verify",
        mapsTo: [],
        isMandatory: false,
      })),
    }),
    false,
    "manager questions: 11 rejected",
  );

  // Candidate resume analysis v3
  const validResume = {
    candidateSnapshot: {
      primaryRoles: ["Backend"],
      seniorityEstimate: "senior",
      yearsExperience: 5,
      coreStack: ["Node.js"],
      nicheTechMentioned: ["Redis"],
      domainExpertise: ["fintech"],
      teamLeadership: "some",
      strongestClaims: ["Led API"],
      weakestOrUncertainClaims: ["K8s listed"],
    },
    verifyClaims: [{ id: "v1", area: "Redis", reason: "depth", priority: "high" }],
    domainModel: { primaryDomains: ["fintech"], secondaryDomains: [], confidence: 0.8 },
    mandatoryMissing: { location: true, workFormat: true, salary: true },
    oneSentenceSummary: "Senior backend, fintech.",
  };
  assert.equal(isCandidateResumeAnalysisV3Schema(validResume), true);
  assert.equal(isCandidateResumeAnalysisV3Schema(null), false);

  // Candidate answer interpreter v3
  const validInterpreter = {
    extractedFacts: { "skills.redis.depth": "high" },
    confidenceUpdates: { redis: "high" },
    followUpNeeded: false,
    followUpQuestion: null,
    microConfirmation: "Got it, I noted Redis.",
    ai_assisted_likelihood: "low",
    ai_assisted_confidence: 0.2,
  };
  assert.equal(isCandidateAnswerInterpreterV3Schema(validInterpreter), true);

  // Manager JD analysis v3
  const validJd = {
    jobSnapshot: { roleTitle: "Backend Lead" },
    clarifyAreas: [{ id: "c1", area: "Budget", reason: "missing", priority: "high" }],
    mandatoryMissing: { workFormat: true, allowedCountries: true, budget: true },
    oneSentenceSummary: "Backend lead, fintech.",
  };
  assert.equal(isManagerJdAnalysisV3Schema(validJd), true);

  // Outbound compose v3
  assert.equal(
    isOutboundComposeV3Schema({ message: "Thanks!", reaction: "👍", buttons: [] }),
    true,
  );

  process.stdout.write("OK, all prescreen v3 schema checks passed.\n");
}

runTests();
