import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { Logger } from "../../config/logger";
import { PrescreenV2Language } from "./candidate-prescreen.schemas";
import {
  JobAnswerInterpreterResult,
  isJobAnswerInterpreterResult,
  normalizeJobAnswerInterpreterResult,
} from "./job-prescreen.schemas";

interface JobAnswerInterpreterInput {
  language: PrescreenV2Language;
  question: string;
  answer: string;
  knownFacts: Array<{ key: string; value: string | number | boolean | null; confidence: number }>;
}

const JOB_ANSWER_INTERPRETER_PROMPT = `You are Helly hiring manager prescreen answer interpreter.

Analyze one manager answer and convert it into structured facts for matching.
Return STRICT JSON only.

Output JSON:
{
  "facts": [
    { "key": "work_format", "value": "remote", "confidence": 0.85 }
  ],
  "notes": "short note",
  "should_follow_up": false,
  "follow_up_question": null
}

Rules:
- Follow-up is only when matching-critical info is still unclear.
- Keep follow-up short and friendly.
- Use language from input for follow_up_question.
- Never ask aggressive multi-part follow-ups.
`;

export class JobAnswerInterpreter {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async interpret(input: JobAnswerInterpreterInput): Promise<JobAnswerInterpreterResult> {
    const prompt = [
      JOB_ANSWER_INTERPRETER_PROMPT,
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

    const safe = await callJsonPromptSafe<JobAnswerInterpreterResult>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 1200,
      timeoutMs: 45_000,
      promptName: "job_prescreen_answer_interpreter_v1",
      schemaHint:
        "Answer interpretation JSON with facts, notes, should_follow_up, follow_up_question.",
      validate: isJobAnswerInterpreterResult,
    });

    if (!safe.ok) {
      this.logger.warn("job.prescreen.answer_interpreter.fallback", {
        errorCode: safe.error_code,
      });
      return buildFallbackInterpretation(input.language, input.answer);
    }

    return normalizeJobAnswerInterpreterResult(safe.data);
  }
}

function buildFallbackInterpretation(
  language: PrescreenV2Language,
  answer: string,
): JobAnswerInterpreterResult {
  const words = answer.trim().split(/\s+/).filter(Boolean).length;
  const tooShort = words < 8;
  return {
    facts: [],
    notes: tooShort ? "Answer is short, some matching details may be missing." : "Answer captured for matching.",
    should_follow_up: tooShort,
    follow_up_question: tooShort ? buildSoftFollowUp(language) : null,
  };
}

function buildSoftFollowUp(language: PrescreenV2Language): string {
  if (language === "ru") {
    return "Можете добавить один конкретный пример, чтобы уточнить требования.";
  }
  if (language === "uk") {
    return "Можете додати один конкретний приклад, щоб уточнити вимоги.";
  }
  return "Can you add one concrete example to clarify this requirement.";
}
