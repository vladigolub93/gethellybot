import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import {
  CandidateAnswerInterpreterResult,
  PrescreenV2Language,
  isCandidateAnswerInterpreterResult,
  normalizeAnswerInterpreterResult,
} from "./candidate-prescreen.schemas";

interface CandidateAnswerInterpreterInput {
  language: PrescreenV2Language;
  question: string;
  answer: string;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const ANSWER_INTERPRETER_PROMPT = `You are Helly candidate prescreen answer interpreter.

Analyze one candidate answer and convert it into structured facts.
We need practical matching quality, not perfect essays.

Return STRICT JSON only.

Output JSON:
{
  "facts": [
    { "key": "tech.Redis.used_directly", "value": true, "confidence": 0.75 }
  ],
  "notes": "short note",
  "should_follow_up": false,
  "follow_up_question": null,
  "ai_assisted_likelihood": "low|medium|high",
  "ai_assisted_confidence": 0.0
}

Rules:
- Follow-up is allowed only when answer is too vague for matching.
- Keep follow-up soft and short.
- If answer is clear enough, should_follow_up must be false.
- ai_assisted_likelihood is heuristic, never certainty.
- Never accuse the candidate.
- Use language from input for follow_up_question.
`;

export class CandidateAnswerInterpreter {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async interpret(input: CandidateAnswerInterpreterInput): Promise<CandidateAnswerInterpreterResult> {
    const prompt = [
      ANSWER_INTERPRETER_PROMPT,
      "",
      "Input JSON:",
      JSON.stringify(
        {
          language: input.language,
          question: input.question,
          answer: input.answer,
          known_facts: input.knownFacts.slice(0, 30),
        },
        null,
        2,
      ),
    ].join("\n");

    const safe = await callJsonPromptSafe<CandidateAnswerInterpreterResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 1300,
      timeoutMs: 45_000,
      promptName: "candidate_prescreen_answer_interpreter_v1",
      schemaHint:
        "Answer interpretation JSON with facts, notes, should_follow_up, follow_up_question, ai_assisted_likelihood, ai_assisted_confidence.",
      validate: isCandidateAnswerInterpreterResult,
    });

    if (!safe.ok) {
      this.logger.warn("candidate.prescreen.answer_interpreter.fallback", {
        errorCode: safe.error_code,
      });
      return buildFallbackInterpretation(input.language, input.answer);
    }

    return normalizeAnswerInterpreterResult(safe.data);
  }
}

function buildFallbackInterpretation(
  language: PrescreenV2Language,
  answer: string,
): CandidateAnswerInterpreterResult {
  const trimmed = answer.trim();
  const words = trimmed.split(/\s+/).filter(Boolean).length;
  const tooShort = words < 12;

  return {
    facts: [],
    notes: tooShort ? "Answer is short, matching confidence is limited." : "Answer captured for matching.",
    should_follow_up: tooShort,
    follow_up_question: tooShort ? buildSoftFollowUp(language) : null,
    ai_assisted_likelihood: "low",
    ai_assisted_confidence: 0.2,
  };
}

function buildSoftFollowUp(language: PrescreenV2Language): string {
  if (language === "ru") {
    return "Можешь добавить один реальный пример, что именно ты делал лично.";
  }
  if (language === "uk") {
    return "Можеш додати один реальний приклад, що саме ти робив особисто.";
  }
  return "Can you add one real example of what you personally did.";
}
