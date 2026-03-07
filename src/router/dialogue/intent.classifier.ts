import { Logger } from "../../config/logger";
import { LlmClient } from "../../ai/llm.client";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import type { UserRole } from "../../shared/types/state.types";
import type { DialogueLanguage } from "./language.service";

export type DialogueIntent =
  | "answer_to_current_question"
  | "ask_bot_question"
  | "request_matching"
  | "pause_stop"
  | "skip"
  | "profile_status"
  | "admin_debug"
  | "other";

export interface IntentClassificationResult {
  intent: DialogueIntent;
  confidence: number;
  language: DialogueLanguage;
  notes: string;
}

const DIALOGUE_INTENT_PROMPT = `You are an intent classifier for a hiring/recruitment Telegram bot.
Given the user message and context, return STRICT JSON only (no markdown, no commentary).

Allowed intent values:
- answer_to_current_question: user is answering the current prescreen/interview question
- ask_bot_question: user asks a clarifying question (what, why, how, when, language, format, privacy)
- request_matching: user wants to find jobs (candidate) or candidates (manager)
- pause_stop: user wants to pause, stop, or take a break
- skip: user wants to skip current question or step
- profile_status: user asks what we know about them / show my profile / status
- admin_debug: only if message clearly targets admin/debug (e.g. /admin, debug)
- other: none of the above

Allowed language values: en, ru, uk (detect from message).

Output JSON schema:
{
  "intent": "answer_to_current_question|ask_bot_question|request_matching|pause_stop|skip|profile_status|admin_debug|other",
  "confidence": 0.0 to 1.0,
  "language": "en|ru|uk",
  "notes": "optional short note"
}

Rules:
1) During prescreen/interview, short substantive answers => answer_to_current_question.
2) Questions about process, timing, language, privacy => ask_bot_question.
3) "Find jobs", "match me", "show vacancies" => request_matching (candidate); "find candidates" => request_matching (manager).
4) "Stop", "pause", "later", "not now" => pause_stop.
5) "Skip", "next", "pass" => skip.
6) "What do you know about me", "my profile", "my status" => profile_status.`;

function buildIntentPrompt(input: {
  userMessage: string;
  role: UserRole;
  currentState: string;
  currentQuestionHint?: string | null;
}): string {
  return [
    DIALOGUE_INTENT_PROMPT,
    "",
    "Runtime input:",
    JSON.stringify(
      {
        user_message: input.userMessage,
        role: input.role,
        current_state: input.currentState,
        current_question_hint: input.currentQuestionHint ?? null,
      },
      null,
      2,
    ),
  ].join("\n");
}

function parseIntentPayload(raw: Record<string, unknown>): IntentClassificationResult | null {
  const intent = normalizeIntent(raw.intent);
  const confidence = clamp01(toNumber(raw.confidence));
  const language = normalizeLanguage(raw.language);
  const notes = typeof raw.notes === "string" ? raw.notes.trim() : "";

  if (!intent || !language) {
    return null;
  }

  return {
    intent,
    confidence,
    language,
    notes,
  };
}

function normalizeIntent(value: unknown): DialogueIntent | null {
  const s = typeof value === "string" ? value.trim().toLowerCase() : "";
  const allowed: DialogueIntent[] = [
    "answer_to_current_question",
    "ask_bot_question",
    "request_matching",
    "pause_stop",
    "skip",
    "profile_status",
    "admin_debug",
    "other",
  ];
  if (allowed.includes(s as DialogueIntent)) {
    return s as DialogueIntent;
  }
  return null;
}

function normalizeLanguage(value: unknown): DialogueLanguage | null {
  const s = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (s === "en" || s === "ru" || s === "uk") {
    return s;
  }
  return null;
}

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const n = parseFloat(value);
    if (Number.isFinite(n)) return n;
  }
  return 0.5;
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

const FALLBACK_RESULT: IntentClassificationResult = {
  intent: "other",
  confidence: 0.3,
  language: "en",
  notes: "classification failed",
};

export class IntentClassifier {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: {
    userMessage: string;
    role: UserRole;
    currentState: string;
    currentQuestionHint?: string | null;
  }): Promise<IntentClassificationResult> {
    const trimmed = input.userMessage?.trim();
    if (!trimmed) {
      return { ...FALLBACK_RESULT, language: "en" };
    }

    const prompt = buildIntentPrompt({
      ...input,
      userMessage: trimmed,
    });

    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 120,
      timeoutMs: 15_000,
      promptName: "dialogue_intent_classifier",
      schemaHint: "Intent classification JSON with intent, confidence, language, notes.",
      validate: (v): v is Record<string, unknown> =>
        typeof v === "object" && v !== null && !Array.isArray(v),
    });

    if (!safe.ok) {
      this.logger.warn("dialogue.intent.classifier.failed", {
        errorCode: safe.error_code,
      });
      return FALLBACK_RESULT;
    }

    const result = parseIntentPayload(safe.data);
    if (!result) {
      this.logger.warn("dialogue.intent.classifier.invalid_schema");
      return FALLBACK_RESULT;
    }

    this.logger.debug("dialogue.intent.classified", {
      intent: result.intent,
      confidence: result.confidence,
      language: result.language,
    });
    return result;
  }
}
