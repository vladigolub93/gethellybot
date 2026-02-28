import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe } from "../ai/llm.safe";
import { NORMALIZE_TO_ENGLISH_V1_PROMPT } from "../ai/prompts/i18n/normalize-to-english.v1.prompt";

export type NormalizedDetectedLanguage = "en" | "ru" | "uk" | "other";

export interface NormalizedEnglishResult {
  detected_language: NormalizedDetectedLanguage;
  english_text: string;
}

interface NormalizationLlmClient {
  generateStructuredJson(prompt: string, maxTokens: number, options?: { promptName?: string }): Promise<string>;
  getModelName?(): string;
}

export class NormalizationService {
  constructor(private readonly llmClient: NormalizationLlmClient) {}

  async normalizeToEnglish(inputText: string): Promise<NormalizedEnglishResult> {
    const trimmed = inputText.trim();
    if (!trimmed) {
      return {
        detected_language: "other",
        english_text: "",
      };
    }

    try {
      const prompt = buildNormalizationPrompt(trimmed);
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        prompt,
        maxTokens: estimateNormalizationMaxTokens(trimmed),
        promptName: "normalize_to_english_v1",
        schemaHint: "Normalization JSON with detected_language, needs_translation, english_text.",
      });
      if (!safe.ok) {
        throw new Error(`normalize_to_english_v1_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      return parseNormalizationResult(raw, trimmed);
    } catch {
      return {
        detected_language: "other",
        english_text: inputText,
      };
    }
  }

  async normalizeUserTextToEnglish(inputText: string): Promise<NormalizedEnglishResult> {
    return this.normalizeToEnglish(inputText);
  }
}

export function buildNormalizationPrompt(inputText: string): string {
  return [
    NORMALIZE_TO_ENGLISH_V1_PROMPT,
    "",
    "Input text:",
    inputText,
  ].join("\n");
}

export function parseNormalizationResult(
  raw: string,
  _fallbackOriginalText: string,
): NormalizedEnglishResult {
  const parsed = parseJsonObject(raw);
  const detectedLanguage = normalizeDetectedLanguage(parsed.detected_language);
  const englishText = toText(parsed.english_text);
  if (!englishText) {
    throw new Error("Normalization output is invalid, english_text is required.");
  }

  return {
    detected_language: detectedLanguage,
    english_text: englishText,
  };
}

export function detectLanguageQuick(text: string): NormalizedDetectedLanguage {
  const normalized = text.trim();
  if (!normalized) {
    return "other";
  }

  if (/[А-Яа-яЁё]/.test(normalized)) {
    if (/[ІіЇїЄєҐґ]/.test(normalized)) {
      return "uk";
    }
    return "ru";
  }

  if (/[A-Za-z]/.test(normalized)) {
    return "en";
  }

  return "other";
}

export function toPreferredLanguage(
  detectedLanguage: NormalizedDetectedLanguage,
): "en" | "ru" | "uk" | "unknown" {
  if (detectedLanguage === "en" || detectedLanguage === "ru" || detectedLanguage === "uk") {
    return detectedLanguage;
  }
  return "unknown";
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const text = raw.trim();
  const firstBrace = text.indexOf("{");
  const lastBrace = text.lastIndexOf("}");
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) {
    throw new Error("Normalization output is not valid JSON.");
  }
  return JSON.parse(text.slice(firstBrace, lastBrace + 1)) as Record<string, unknown>;
}

function normalizeDetectedLanguage(value: unknown): NormalizedDetectedLanguage {
  const normalized = toText(value).toLowerCase();
  if (normalized === "en" || normalized === "ru" || normalized === "uk" || normalized === "other") {
    return normalized;
  }
  return "other";
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function estimateNormalizationMaxTokens(text: string): number {
  const estimated = Math.ceil(text.length / 3);
  return Math.max(260, Math.min(3200, estimated));
}

export function createNormalizationService(llmClient: LlmClient): NormalizationService {
  return new NormalizationService(llmClient);
}
