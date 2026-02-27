import { LlmClient } from "../ai/llm.client";
import { buildCandidateResultPrompt } from "../prompts/candidate-result.prompt";
import { buildHiringResultPrompt } from "../prompts/hiring-result.prompt";
import {
  CandidateInterviewArtifact,
  HiringInterviewArtifact,
  InterviewPlan,
  InterviewResultArtifact,
} from "../shared/types/domain.types";
import { InterviewAnswer, UserRole } from "../shared/types/state.types";

export interface InterviewResultInput {
  role: UserRole;
  extractedText: string;
  plan: InterviewPlan;
  answers: ReadonlyArray<InterviewAnswer>;
}

const MAX_ARRAY_ITEMS = 4;
const PROMPT_TEXT_LIMIT = 5000;

export class InterviewResultService {
  constructor(private readonly llmClient: LlmClient) {}

  async generateArtifact(input: InterviewResultInput): Promise<InterviewResultArtifact> {
    const payload = buildResultPayload(input);
    const prompt =
      input.role === "candidate"
        ? buildCandidateResultPrompt(JSON.stringify(payload))
        : buildHiringResultPrompt(JSON.stringify(payload));

    const raw = await this.llmClient.generateStructuredJson(prompt, 320);
    const parsed = parseJsonObject(raw);

    if (input.role === "candidate") {
      return normalizeCandidateArtifact(parsed);
    }

    return normalizeHiringArtifact(parsed);
  }
}

export function formatInterviewResultMessage(artifact: InterviewResultArtifact): string {
  if (artifact.title === "Interview Summary") {
    return [
      artifact.title,
      "",
      `1) Profile snapshot: ${artifact.profileSnapshot}`,
      `2) Strengths: ${joinItems(artifact.strengths)}`,
      `3) Gaps / unclear points: ${joinItems(artifact.gaps)}`,
      `4) Suggested next step: ${artifact.nextStep}`,
      "",
      "You can /start to run another interview.",
    ].join("\n");
  }

  return [
    artifact.title,
    "",
    `1) Role overview: ${artifact.roleOverview}`,
    `2) Must-haves: ${joinItems(artifact.mustHaves)}`,
    `3) Risks / ambiguities: ${joinItems(artifact.risks)}`,
    `4) Suggested next step: ${artifact.nextStep}`,
    "",
    "You can /start to run another interview.",
  ].join("\n");
}

function buildResultPayload(input: InterviewResultInput): Record<string, unknown> {
  return {
    role: input.role,
    extractedText: input.extractedText.slice(0, PROMPT_TEXT_LIMIT),
    planQuestions: input.plan.questions.map((question) => ({
      id: question.id,
      question: question.question,
    })),
    answers: input.answers.map((answer) => ({
      questionIndex: answer.questionIndex,
      questionId: answer.questionId,
      questionText: answer.questionText,
      answerText: answer.answerText,
      answeredAt: answer.answeredAt,
    })),
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Result artifact does not contain a JSON object.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeCandidateArtifact(raw: Record<string, unknown>): CandidateInterviewArtifact {
  const profileSnapshot = toCleanString(raw.profileSnapshot);
  const strengths = toStringArray(raw.strengths);
  const gaps = toStringArray(raw.gaps);
  const nextStep = toCleanString(raw.nextStep);

  if (!profileSnapshot || strengths.length === 0 || gaps.length === 0 || !nextStep) {
    throw new Error("Invalid candidate artifact shape.");
  }

  return {
    title: "Interview Summary",
    profileSnapshot,
    strengths,
    gaps,
    nextStep,
  };
}

function normalizeHiringArtifact(raw: Record<string, unknown>): HiringInterviewArtifact {
  const roleOverview = toCleanString(raw.roleOverview);
  const mustHaves = toStringArray(raw.mustHaves);
  const risks = toStringArray(raw.risks);
  const nextStep = toCleanString(raw.nextStep);

  if (!roleOverview || mustHaves.length === 0 || risks.length === 0 || !nextStep) {
    throw new Error("Invalid hiring artifact shape.");
  }

  return {
    title: "Role Intake Summary",
    roleOverview,
    mustHaves,
    risks,
    nextStep,
  };
}

function toCleanString(value: unknown): string {
  if (typeof value !== "string") {
    return "";
  }
  return value.replace(/\s+/g, " ").trim();
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => toCleanString(item))
    .filter((item) => Boolean(item))
    .slice(0, MAX_ARRAY_ITEMS);
}

function joinItems(items: ReadonlyArray<string>): string {
  return items.join("; ");
}
