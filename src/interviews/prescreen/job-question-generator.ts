import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import { PrescreenV2Language } from "./candidate-prescreen.schemas";
import {
  JobClaimExtractionResult,
  JobPrescreenQuestion,
  JobQuestionGeneratorResult,
  isJobQuestionGeneratorResult,
  normalizeJobQuestionGeneratorResult,
} from "./job-prescreen.schemas";

interface JobQuestionGeneratorInput {
  language: PrescreenV2Language;
  claimExtraction: JobClaimExtractionResult;
  maxQuestions?: number;
  knownFacts?: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const JOB_QUESTION_GENERATOR_PROMPT = `You are Helly hiring manager prescreen question generator.

Goal:
Generate a friendly recruiter-like prescreen plan for matching quality.

Constraints:
- Max 10 questions total.
- Keep one objective per question.
- Keep questions concise and plain.
- Avoid long technical interrogation.
- One question per message.
- followup_policy must be at_most_one_soft_followup.

Mandatory topics if still unclear:
- work format
- allowed countries and timezone if remote
- budget range and period
- team size and who the hire works with
- top 3 real tasks in first 1-2 months

Return STRICT JSON only.

Output JSON:
{
  "questions": [
    {
      "id": "j1",
      "topic": "product_context",
      "question": "What does the product do and what will this hire build in the first 1 to 2 months",
      "intent": "clarify",
      "followup_policy": "at_most_one_soft_followup"
    }
  ]
}`;

export class JobQuestionGenerator {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async generate(input: JobQuestionGeneratorInput): Promise<JobQuestionGeneratorResult> {
    const maxQuestions = Math.max(5, Math.min(10, input.maxQuestions ?? 9));
    const prompt = [
      JOB_QUESTION_GENERATOR_PROMPT,
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
      "Language rule (strict):",
      "Every \"question\" field in the JSON MUST be in the same language as input.language.",
      "If input.language is \"ru\", write all questions in Russian. If \"uk\", write in Ukrainian. Otherwise English.",
      "Do not mix languages.",
    ].join("\n");

    const safe = await callJsonPromptSafe<JobQuestionGeneratorResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 1700,
      timeoutMs: 55_000,
      promptName: "job_prescreen_question_generator_v1",
      schemaHint:
        "Question generator JSON with questions array of id, topic, question, intent, followup_policy.",
      validate: isJobQuestionGeneratorResult,
    });

    if (!safe.ok) {
      this.logger.warn("job.prescreen.question_generator.fallback", {
        errorCode: safe.error_code,
      });
      return { questions: buildFallbackQuestions(input.claimExtraction, input.language, maxQuestions) };
    }

    const normalized = normalizeJobQuestionGeneratorResult(safe.data, maxQuestions);
    if (!normalized.questions.length) {
      return { questions: buildFallbackQuestions(input.claimExtraction, input.language, maxQuestions) };
    }
    return normalized;
  }
}

function buildFallbackQuestions(
  claims: JobClaimExtractionResult,
  language: PrescreenV2Language,
  maxQuestions: number,
): JobPrescreenQuestion[] {
  const topics: Array<{ topic: string; question: string }> = [
    {
      topic: "product_context",
      question: byLang(
        language,
        "What does the product do, and what should this hire deliver in the first 1 to 2 months.",
        "Что делает продукт, и что новый человек должен сделать в первые 1 или 2 месяца.",
        "Що робить продукт, і що новий спеціаліст має зробити у перші 1 або 2 місяці.",
      ),
    },
    {
      topic: "team",
      question: byLang(
        language,
        "Who will this person work with day to day, and what is the team size.",
        "С кем этот человек будет работать каждый день, и какой размер команды.",
        "З ким ця людина працюватиме щодня, і який розмір команди.",
      ),
    },
    {
      topic: "work_format",
      question: byLang(
        language,
        "Is this role remote, hybrid, or onsite.",
        "Эта роль remote, hybrid или onsite.",
        "Ця роль remote, hybrid чи onsite.",
      ),
    },
    {
      topic: "countries",
      question: byLang(
        language,
        "If remote, which countries or timezones are acceptable.",
        "Если роль remote, какие страны или таймзоны подходят.",
        "Якщо роль remote, які країни або таймзони підходять.",
      ),
    },
    {
      topic: "budget",
      question: byLang(
        language,
        "What budget range do you have, and is it per month or per year.",
        "Какой бюджетный диапазон, и это в месяц или в год.",
        "Який бюджетний діапазон, і це за місяць чи за рік.",
      ),
    },
  ];

  const skillTopic = claims.must_have[0]?.skill;
  if (skillTopic) {
    topics.push({
      topic: "must_have",
      question: byLang(
        language,
        `You listed ${skillTopic} as must-have. What level is really required in day to day work.`,
        `Вы указали ${skillTopic} как must-have. Какой уровень реально нужен в ежедневной работе.`,
        `Ви вказали ${skillTopic} як must-have. Який рівень реально потрібен у щоденній роботі.`,
      ),
    });
  }

  return topics.slice(0, maxQuestions).map((item, index) => ({
    id: `j${index + 1}`,
    topic: item.topic,
    question: item.question,
    intent: "clarify",
    followup_policy: "at_most_one_soft_followup",
  }));
}

function byLang(language: PrescreenV2Language, en: string, ru: string, uk: string): string {
  if (language === "ru") {
    return ru;
  }
  if (language === "uk") {
    return uk;
  }
  return en;
}
