import { Logger } from "../config/logger";
import { HELLY_SYSTEM_PROMPT } from "./system/helly.system";
import { buildJsonRepairV1Prompt } from "./prompts/utils/json-repair.v1.prompt";

export interface JsonSafeCallArgs<T> {
  llmClient: {
    generateStructuredJson(prompt: string, maxTokens: number, options?: { promptName?: string }): Promise<string>;
    getModelName?(): string;
  };
  prompt: string;
  maxTokens: number;
  promptName: string;
  schemaHint: string;
  logger?: Logger;
  timeoutMs?: number;
  validate?: (value: unknown) => value is T;
}

export interface TextSafeCallArgs {
  llmClient: {
    generateAssistantReply(prompt: string, maxTokens?: number, options?: { promptName?: string }): Promise<string>;
    getModelName?(): string;
  };
  prompt: string;
  maxTokens?: number;
  promptName: string;
  logger?: Logger;
  timeoutMs?: number;
}

export type SafeJsonResult<T> =
  | {
      ok: true;
      data: T;
    }
  | {
      ok: false;
      error_code:
        | "missing_system_prompt"
        | "timeout"
        | "transient_failure"
        | "llm_failure"
        | "json_parse_failed"
        | "schema_invalid";
      raw?: string;
    };

export type SafeTextResult =
  | { ok: true; text: string }
  | { ok: false; error_code: "missing_system_prompt" | "timeout" | "transient_failure" | "llm_failure" };

const DEFAULT_TIMEOUT_MS = 25_000;

export async function callJsonPromptSafe<T>(args: JsonSafeCallArgs<T>): Promise<SafeJsonResult<T>> {
  if (!HELLY_SYSTEM_PROMPT.trim()) {
    return { ok: false, error_code: "missing_system_prompt" };
  }

  const timeoutMs = normalizeTimeout(args.timeoutMs);
  const initial = await attemptJsonCall(args, args.prompt, args.maxTokens, args.promptName, timeoutMs);
  if (!initial.ok) {
    return initial;
  }

  const parsed = tryParseJsonObject(initial.raw);
  if (parsed.ok) {
    if (args.validate && !args.validate(parsed.data)) {
      return { ok: false, error_code: "schema_invalid", raw: initial.raw };
    }
    return { ok: true, data: parsed.data as T };
  }

  const repairPrompt = buildJsonRepairV1Prompt({
    schemaHint: args.schemaHint,
    raw: initial.raw,
  });
  const repaired = await attemptJsonCall(
    args,
    repairPrompt,
    Math.max(240, Math.min(2400, args.maxTokens)),
    `${args.promptName}_json_repair`,
    timeoutMs,
  );
  if (!repaired.ok) {
    return repaired;
  }
  const repairedParsed = tryParseJsonObject(repaired.raw);
  if (!repairedParsed.ok) {
    return { ok: false, error_code: "json_parse_failed", raw: repaired.raw };
  }
  if (args.validate && !args.validate(repairedParsed.data)) {
    return { ok: false, error_code: "schema_invalid", raw: repaired.raw };
  }
  return { ok: true, data: repairedParsed.data as T };
}

export async function callTextPromptSafe(args: TextSafeCallArgs): Promise<SafeTextResult> {
  if (!HELLY_SYSTEM_PROMPT.trim()) {
    return { ok: false, error_code: "missing_system_prompt" };
  }

  const timeoutMs = normalizeTimeout(args.timeoutMs);
  const attempt = async (): Promise<string> =>
    withTimeout(
      args.llmClient.generateAssistantReply(args.prompt, args.maxTokens ?? 180, {
        promptName: args.promptName,
      }),
      timeoutMs,
    );

  try {
    const text = (await attempt()).trim();
    return { ok: true, text };
  } catch (error) {
    if (!isTransientError(error)) {
      return { ok: false, error_code: isTimeoutError(error) ? "timeout" : "llm_failure" };
    }
  }

  try {
    const retryText = (await attempt()).trim();
    return { ok: true, text: retryText };
  } catch (error) {
    return {
      ok: false,
      error_code: isTimeoutError(error)
        ? "timeout"
        : isTransientError(error)
          ? "transient_failure"
          : "llm_failure",
    };
  }
}

async function attemptJsonCall<T>(
  args: JsonSafeCallArgs<T>,
  prompt: string,
  maxTokens: number,
  promptName: string,
  timeoutMs: number,
): Promise<
  | { ok: true; raw: string }
  | {
      ok: false;
      error_code: "timeout" | "transient_failure" | "llm_failure";
      raw?: string;
    }
> {
  const attempt = async (): Promise<string> =>
    withTimeout(
      args.llmClient.generateStructuredJson(prompt, maxTokens, { promptName }),
      timeoutMs,
    );

  try {
    return { ok: true, raw: await attempt() };
  } catch (error) {
    if (!isTransientError(error)) {
      return {
        ok: false,
        error_code: isTimeoutError(error) ? "timeout" : "llm_failure",
      };
    }
  }

  args.logger?.warn("llm.safe.retry.once", {
    promptName,
    modelName: args.llmClient.getModelName?.(),
  });
  try {
    return { ok: true, raw: await attempt() };
  } catch (error) {
    return {
      ok: false,
      error_code: isTimeoutError(error)
        ? "timeout"
        : isTransientError(error)
          ? "transient_failure"
          : "llm_failure",
    };
  }
}

function tryParseJsonObject(raw: string): { ok: true; data: Record<string, unknown> } | { ok: false } {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    return { ok: false };
  }
  try {
    const parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
    return { ok: true, data: parsed };
  } catch {
    return { ok: false };
  }
}

function normalizeTimeout(value?: number): number {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return Math.round(value);
  }
  return DEFAULT_TIMEOUT_MS;
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error("timeout"));
    }, timeoutMs);
    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((error) => {
        clearTimeout(timer);
        reject(error);
      });
  });
}

function isTimeoutError(error: unknown): boolean {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  return message.includes("timeout");
}

function isTransientError(error: unknown): boolean {
  const message = error instanceof Error ? error.message.toLowerCase() : "";
  return (
    message.includes("timeout") ||
    message.includes("econnreset") ||
    message.includes("network") ||
    message.includes("429") ||
    message.includes("rate limit") ||
    message.includes("http 500") ||
    message.includes("http 502") ||
    message.includes("http 503") ||
    message.includes("http 504")
  );
}
