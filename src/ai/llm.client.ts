import fetch from "node-fetch";
import { Logger } from "../config/logger";
import { InterviewPlan } from "../shared/types/domain.types";
import { HELLY_SYSTEM_PROMPT } from "./system/helly.system";

export const CHAT_MODEL = process.env.OPENAI_CHAT_MODEL || "gpt-5.2";
export const EMBEDDINGS_MODEL = process.env.OPENAI_EMBEDDINGS_MODEL || "text-embedding-3-large";
export const TRANSCRIPTION_MODEL = process.env.OPENAI_TRANSCRIPTION_MODEL || "whisper-1";

const HELLY_EXECUTION_SYSTEM_PROMPT = [
  "Universal execution rules.",
  "Keep responses human-like, concise, and natural.",
  "Avoid robotic phrasing and repetitive templates.",
  "If output requires strict JSON, return JSON only and follow schema exactly.",
  "If generating interview questions, keep each question short and focused.",
  "Use one objective per question.",
  "Do not generate long multi-part questions.",
  "Prefer progressive follow-ups in later turns.",
].join(" ");

export interface ChatCompletionsRequestBody {
  model: string;
  temperature: number;
  messages: Array<{
    role: "system" | "user";
    content: string;
  }>;
  max_tokens?: number;
  max_completion_tokens?: number;
}

interface ChatCompletionsResponse {
  choices: Array<{
    message: {
      content?: string | null;
    };
  }>;
}

interface LlmCallOptions {
  promptName?: string;
}

export class LlmClient {
  private readonly chatModel: string;

  constructor(
    private readonly apiKey: string,
    private readonly logger: Logger,
    modelOverride?: string,
  ) {
    this.chatModel = modelOverride || CHAT_MODEL;
    const isProd = (process.env.NODE_ENV ?? "development") === "production";
    if (!HELLY_SYSTEM_PROMPT.trim() && !isProd) {
      throw new Error("HELLY_SYSTEM_PROMPT is empty. Refusing to start in non-production mode.");
    }
  }

  getModelName(): string {
    return this.chatModel;
  }

  async generateInterviewPlan(prompt: string): Promise<InterviewPlan> {
    const content = await this.generateJsonContent(prompt, 600, {
      promptName: "legacy_interview_plan",
    });
    const parsed = this.parseInterviewPlan(content);
    this.logger.info("Interview plan generated", {
      questions: parsed.questions.length,
      parseSuccess: true,
      promptName: "legacy_interview_plan",
    });
    return parsed;
  }

  async generateStructuredJson(
    prompt: string,
    maxTokens: number,
    options?: LlmCallOptions,
  ): Promise<string> {
    return this.generateJsonContent(prompt, maxTokens, options);
  }

  async generateAssistantReply(
    prompt: string,
    maxTokens = 180,
    options?: LlmCallOptions,
  ): Promise<string> {
    const startedAt = Date.now();
    const requestBody = this.buildRequestBody(prompt, maxTokens, 0.4);
    try {
      const response = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          authorization: `Bearer ${this.apiKey}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`OpenAI API error: HTTP ${response.status} - ${body}`);
      }

      const body = (await response.json()) as ChatCompletionsResponse;
      const content = body.choices[0]?.message?.content;
      if (!content) {
        throw new Error("OpenAI response does not contain message content");
      }

      const trimmed = content.trim();
      this.logger.info("llm.call.completed", {
        promptName: options?.promptName ?? "assistant_reply",
        latencyMs: Date.now() - startedAt,
        maxTokens,
        tokenEstimate: estimateTokenCount(prompt, trimmed),
        parseSuccess: true,
      });
      return trimmed;
    } catch (error) {
      this.logger.warn("llm.call.failed", {
        promptName: options?.promptName ?? "assistant_reply",
        latencyMs: Date.now() - startedAt,
        maxTokens,
        parseSuccess: false,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  buildJsonRequestBody(prompt: string, maxTokens: number): ChatCompletionsRequestBody {
    return this.buildRequestBody(prompt, maxTokens, 0.2);
  }

  private buildRequestBody(
    prompt: string,
    maxTokens: number,
    temperature: number,
  ): ChatCompletionsRequestBody {
    const body: ChatCompletionsRequestBody = {
      model: this.chatModel,
      temperature,
      messages: [
        {
          role: "system",
          content: HELLY_SYSTEM_PROMPT,
        },
        {
          role: "system",
          content: HELLY_EXECUTION_SYSTEM_PROMPT,
        },
        {
          role: "user",
          content: prompt,
        },
      ],
    };
    if (usesMaxCompletionTokens(this.chatModel)) {
      body.max_completion_tokens = maxTokens;
    } else {
      body.max_tokens = maxTokens;
    }
    return body;
  }

  private async generateJsonContent(
    prompt: string,
    maxTokens: number,
    options?: LlmCallOptions,
  ): Promise<string> {
    const startedAt = Date.now();
    const requestBody = this.buildJsonRequestBody(prompt, maxTokens);
    try {
      const response = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          authorization: `Bearer ${this.apiKey}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`OpenAI API error: HTTP ${response.status} - ${body}`);
      }

      const body = (await response.json()) as ChatCompletionsResponse;
      const content = body.choices[0]?.message?.content;
      if (!content) {
        throw new Error("OpenAI response does not contain message content");
      }

      this.logger.info("llm.call.completed", {
        promptName: options?.promptName ?? "structured_json",
        latencyMs: Date.now() - startedAt,
        maxTokens,
        tokenEstimate: estimateTokenCount(prompt, content),
        parseSuccess: true,
      });
      return content;
    } catch (error) {
      this.logger.warn("llm.call.failed", {
        promptName: options?.promptName ?? "structured_json",
        latencyMs: Date.now() - startedAt,
        maxTokens,
        parseSuccess: false,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      throw error;
    }
  }

  private parseInterviewPlan(raw: string): InterviewPlan {
    const text = raw.trim();
    const firstBrace = text.indexOf("{");
    const lastBrace = text.lastIndexOf("}");
    if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
      throw new Error("LLM output does not include JSON object");
    }

    const jsonSlice = text.slice(firstBrace, lastBrace + 1);
    const parsed = JSON.parse(jsonSlice) as Partial<InterviewPlan>;
    const sourceQuestions = Array.isArray(parsed.questions) ? parsed.questions : [];
    const questions = sourceQuestions.map((q, index) => ({
      id: typeof q.id === "string" ? q.id.trim() : `q${index + 1}`,
      question: typeof q.question === "string" ? q.question.trim() : "",
      goal: typeof q.goal === "string" ? q.goal.trim() : "",
      gapToClarify: typeof q.gapToClarify === "string" ? q.gapToClarify.trim() : "",
    }));

    return {
      summary: typeof parsed.summary === "string" ? parsed.summary.trim() : "",
      questions,
    };
  }
}

function estimateTokenCount(prompt: string, output: string): number {
  const totalChars = prompt.length + output.length;
  return Math.max(1, Math.round(totalChars / 4));
}

function usesMaxCompletionTokens(model: string): boolean {
  const normalized = model.trim().toLowerCase();
  return normalized.startsWith("gpt-5");
}
