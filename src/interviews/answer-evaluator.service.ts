import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { buildAnswerEvaluatorV1Prompt } from "../ai/prompts/interview/answer-evaluator.v1.prompt";
import { Logger } from "../config/logger";
import { InterviewAnswerEvaluation } from "../shared/types/answer-evaluator.types";

export type EvaluatorLanguage = "en" | "ru" | "uk";

interface EvaluateAnswerInput {
  role: "candidate" | "manager";
  question: string;
  answer: string;
  preferredLanguage?: "en" | "ru" | "uk" | "unknown";
  detectedLanguage?: "en" | "ru" | "uk" | "other";
}

const FIXED_REANSWER_MESSAGES: Record<EvaluatorLanguage, string> = {
  en: "This feels a bit too perfect, like an AI answer. I would rather you not do that. I need your real experience. Please answer again with one real project, what you personally did, and one concrete production detail. Voice message is totally fine if that is easier.",
  ru: "Это звучит слишком идеально, как ответ от AI. Я бы не хотел, чтобы ты так делал. Мне нужен твой реальный опыт. Ответь заново, на примере одного реального проекта, что именно ты делал лично, и добавь одну конкретную продовую деталь. Если не хочется печатать, можешь записать голосовое.",
  uk: "Це звучить надто ідеально, як відповідь від AI. Я б не хотів, щоб ти так робив. Мені потрібен твій реальний досвід. Відповідай ще раз, на прикладі одного реального проєкту, що саме ти робив особисто, і додай одну конкретну продову деталь. Якщо не хочеш друкувати, можеш записати голосове.",
};

export class AnswerEvaluatorService {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async evaluateAnswer(input: EvaluateAnswerInput): Promise<InterviewAnswerEvaluation> {
    const language = resolveEvaluatorLanguage(input.preferredLanguage, input.detectedLanguage);
    const prompt = buildAnswerEvaluatorV1Prompt({
      role: input.role,
      question: input.question,
      answer: input.answer,
      language,
    });
    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 900,
      timeoutMs: 45_000,
      promptName: "interview_answer_evaluator_v1",
      schemaHint:
        "Answer evaluator JSON with should_accept, should_request_reanswer, ai_assisted_likelihood, ai_assisted_confidence, signals, missing_elements, message_to_user.",
    });

    if (!safe.ok) {
      this.logger.warn("answer.evaluator.fallback", {
        role: input.role,
        errorCode: safe.error_code,
      });
      return buildFallbackEvaluation(input.answer, language);
    }

    return normalizeEvaluation(safe.data, language);
  }
}

function normalizeEvaluation(
  raw: Record<string, unknown>,
  language: EvaluatorLanguage,
): InterviewAnswerEvaluation {
  const shouldRequest = Boolean(raw.should_request_reanswer);
  const shouldAccept = shouldRequest ? false : Boolean(raw.should_accept);
  let likelihood = normalizeLikelihood(raw.ai_assisted_likelihood);
  let confidence = clamp01(raw.ai_assisted_confidence);
  const signals = toStringArray(raw.signals, 8);
  const missingElements = toStringArray(raw.missing_elements, 8);

  if (shouldRequest && likelihood === "low") {
    likelihood = "medium";
  }
  if (shouldRequest && confidence < 0.55) {
    confidence = 0.55;
  }

  return {
    should_accept: shouldAccept,
    should_request_reanswer: shouldRequest,
    ai_assisted_likelihood: likelihood,
    ai_assisted_confidence: confidence,
    signals,
    missing_elements: missingElements,
    message_to_user: shouldRequest ? FIXED_REANSWER_MESSAGES[language] : "",
  };
}

function buildFallbackEvaluation(answer: string, language: EvaluatorLanguage): InterviewAnswerEvaluation {
  const normalized = answer.trim();
  const tokenCount = normalized.split(/\s+/).filter(Boolean).length;
  const hasProjectContext = /project|service|system|feature|прод|production|module|api|endpoint|таблиц|table|queue|kafka|redis|postgres|incident|metric|deployment|constraint|schema/i.test(
    normalized,
  );
  const hasPersonalOwnership = /\bI\b|\bmy\b|я\b|мене\b|моє\b|мой\b|лично\b|owned\b|implemented\b/i.test(
    normalized,
  );
  const hasConcreteProductionDetail = /(\/[a-z0-9/_:-]+)|\b(table|constraint|index|latency|p95|kafka|redis|postgres|endpoint|queue|consumer|producer|migration|rollback|incident|deploy)\b/i.test(
    normalized,
  );

  const shouldRequest = !(tokenCount >= 20 && hasProjectContext && hasPersonalOwnership && hasConcreteProductionDetail);
  return {
    should_accept: !shouldRequest,
    should_request_reanswer: shouldRequest,
    ai_assisted_likelihood: shouldRequest ? "medium" : "low",
    ai_assisted_confidence: shouldRequest ? 0.72 : 0.28,
    signals: shouldRequest
      ? [
          "Missing concrete project evidence",
          "Missing explicit personal ownership",
          "Missing production-level artifact",
        ]
      : ["Contains project context and production evidence"],
    missing_elements: shouldRequest
      ? ["specific project context", "personal implementation details", "one concrete production detail"]
      : [],
    message_to_user: shouldRequest ? FIXED_REANSWER_MESSAGES[language] : "",
  };
}

function resolveEvaluatorLanguage(
  preferredLanguage: "en" | "ru" | "uk" | "unknown" | undefined,
  detectedLanguage: "en" | "ru" | "uk" | "other" | undefined,
): EvaluatorLanguage {
  if (detectedLanguage === "en") {
    return "en";
  }
  if (detectedLanguage === "ru" || detectedLanguage === "uk") {
    return detectedLanguage;
  }
  if (preferredLanguage === "ru" || preferredLanguage === "uk") {
    return preferredLanguage;
  }
  return "en";
}

function normalizeLikelihood(value: unknown): "low" | "medium" | "high" {
  if (typeof value !== "string") {
    return "medium";
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "low" || normalized === "medium" || normalized === "high") {
    return normalized;
  }
  return "medium";
}

function clamp01(value: unknown): number {
  const numeric = typeof value === "number" ? value : Number.NaN;
  if (!Number.isFinite(numeric)) {
    return 0.5;
  }
  if (numeric < 0) {
    return 0;
  }
  if (numeric > 1) {
    return 1;
  }
  return numeric;
}

function toStringArray(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => Boolean(item))
    .slice(0, limit);
}
