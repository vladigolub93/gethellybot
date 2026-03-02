import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import {
  CandidateClaimExtractionResult,
  CandidateQuestionGeneratorResult,
  CandidatePrescreenQuestion,
  PrescreenV2Language,
  isCandidateQuestionGeneratorResult,
  normalizeQuestionGeneratorResult,
} from "./candidate-prescreen.schemas";

interface CandidateQuestionGeneratorInput {
  language: PrescreenV2Language;
  claimExtraction: CandidateClaimExtractionResult;
  maxQuestions?: number;
  knownFacts?: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const QUESTION_GENERATOR_PROMPT = `You are Helly candidate prescreen question generator.

Goal:
Generate a friendly recruiter-like prescreen plan that verifies resume claims.

Constraints:
- Max 10 questions total.
- Every question verifies one claim.
- Keep tone calm and friendly.
- No interrogation style.
- No requests for exact file paths.
- No demand for production metrics.
- Keep questions short and conversational.
- Prefer one idea per question.
- Use followup_policy: at_most_one_soft_followup.

Return STRICT JSON only.

Output JSON:
{
  "questions": [
    {
      "id": "q1",
      "tech_or_topic": "Redis",
      "question": "You mentioned Redis. Did you use it directly, and what did you personally do with it",
      "intent": "verify_claim",
      "expected_answer_shape": "short_story",
      "followup_policy": "at_most_one_soft_followup"
    }
  ]
}`;

export class CandidateQuestionGenerator {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async generate(input: CandidateQuestionGeneratorInput): Promise<CandidateQuestionGeneratorResult> {
    const maxQuestions = Math.max(4, Math.min(10, input.maxQuestions ?? 9));
    const prompt = [
      QUESTION_GENERATOR_PROMPT,
      "",
      "Input JSON:",
      JSON.stringify(
        {
          language: input.language,
          max_questions: maxQuestions,
          claim_extraction: input.claimExtraction,
          known_facts: input.knownFacts ?? [],
        },
        null,
        2,
      ),
      "",
      "Language rule:",
      "Write questions in the same language as input language.",
    ].join("\n");

    const safe = await callJsonPromptSafe<CandidateQuestionGeneratorResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 1700,
      timeoutMs: 55_000,
      promptName: "candidate_prescreen_question_generator_v1",
      schemaHint:
        "Question generator JSON with questions array of id, tech_or_topic, question, intent, expected_answer_shape, followup_policy.",
      validate: isCandidateQuestionGeneratorResult,
    });

    if (!safe.ok) {
      this.logger.warn("candidate.prescreen.question_generator.fallback", {
        errorCode: safe.error_code,
      });
      return { questions: buildFallbackQuestions(input.claimExtraction, input.language, maxQuestions) };
    }

    const normalized = normalizeQuestionGeneratorResult(safe.data, maxQuestions);
    if (!normalized.questions.length) {
      return { questions: buildFallbackQuestions(input.claimExtraction, input.language, maxQuestions) };
    }

    return normalized;
  }
}

function buildFallbackQuestions(
  claims: CandidateClaimExtractionResult,
  language: PrescreenV2Language,
  maxQuestions: number,
): CandidatePrescreenQuestion[] {
  const techTopics = claims.tech_claims
    .slice(0, maxQuestions)
    .map((claim) => claim.tech)
    .filter(Boolean);

  const questions: CandidatePrescreenQuestion[] = [];
  const topicList = techTopics.length ? techTopics : ["recent project", "backend work", "ownership", "debugging"];
  topicList.forEach((topic, index) => {
    questions.push({
      id: `q${index + 1}`,
      tech_or_topic: topic,
      question: buildQuestionByLanguage(language, topic),
      intent: "verify_claim",
      expected_answer_shape: "short_story",
      followup_policy: "at_most_one_soft_followup",
    });
  });

  return questions.slice(0, maxQuestions);
}

function buildQuestionByLanguage(language: PrescreenV2Language, topic: string): string {
  if (language === "ru") {
    return `Ты упоминал ${topic}. Расскажи коротко про один реальный пример, что ты делал лично.`;
  }
  if (language === "uk") {
    return `Ти згадував ${topic}. Розкажи коротко один реальний приклад, що саме ти робив особисто.`;
  }
  return `You mentioned ${topic}. Share one real example and what you personally did.`;
}
