import { Logger } from "../config/logger";
import { callJsonPromptSafe } from "./llm.safe";
import { LlmClient } from "./llm.client";

export type RouterV2Language = "ru" | "uk" | "en";
export type RouterV2Intent =
  | "resume_upload"
  | "job_upload"
  | "prescreen_answer"
  | "match_request"
  | "match_request_jobs"
  | "match_request_candidates"
  | "status_request"
  | "clarification"
  | "smalltalk"
  | "command"
  | "other";

export type RouterV2MatchingDirection =
  | "candidate_to_jobs"
  | "job_to_candidates"
  | null;

export type RouterV2NextAction =
  | "none"
  | "extract_resume"
  | "extract_job"
  | "ask_next_question"
  | "run_matching";

export interface RouterV2Input {
  userMessage: string;
  currentState: string;
  partialProfile: Record<string, unknown> | null;
  lastMessages: string[];
  role: "candidate" | "manager";
}

export interface RouterV2Decision {
  language: RouterV2Language;
  intent: RouterV2Intent;
  assistant_message: string;
  next_action: RouterV2NextAction;
  matching_direction: RouterV2MatchingDirection;
  state_patch: Record<string, unknown>;
  facts: string[];
}

export interface RouterV2Result {
  decision: RouterV2Decision;
  parseSuccess: boolean;
}

const ROUTER_V2_SAFE_FALLBACK = "Something went wrong. Please repeat your last message.";

const ROUTER_V2_PROMPT = `You are Helly Router v2.

Classify one incoming user message for a hiring assistant.
Return STRICT JSON only, no markdown, no commentary.

Input fields:
- user_message
- current_state
- partial_profile
- last_5_messages
- role

Allowed language values:
- ru
- uk
- en

Allowed intent values:
- resume_upload
- job_upload
- prescreen_answer
- match_request
- match_request_jobs
- match_request_candidates
- status_request
- clarification
- smalltalk
- command
- other

Allowed next_action values:
- none
- extract_resume
- extract_job
- ask_next_question
- run_matching

Rules:
1) If message asks to upload, send, attach, paste resume, intent resume_upload.
2) If message asks to upload, send, attach, paste job description, intent job_upload.
3) If current_state is interviewing_candidate or interviewing_manager and message is not command or clarification, intent prescreen_answer.
4) If message asks to find jobs or roles, or command /find_jobs, intent match_request_jobs.
5) If message asks to find candidates, or command /find_candidates, intent match_request_candidates.
6) If message asks what you know about me, show my profile, status, intent status_request.
7) If message asks to find roles or candidates without clear side, intent match_request.
8) If message asks what is next, why, repeat, clarify, timing, language, format, privacy, intent clarification.
9) If message is social short talk, intent smalltalk.
10) If message is command like start, stop, pause, resume, restart, skip, intent command.
11) Otherwise intent other.

Action mapping:
- resume_upload can use extract_resume.
- job_upload can use extract_job.
- prescreen_answer can use ask_next_question.
- match_request, match_request_jobs, match_request_candidates can use run_matching.
- otherwise none.

matching_direction mapping:
- match_request_jobs => candidate_to_jobs.
- match_request_candidates => job_to_candidates.
- match_request => infer from role, candidate => candidate_to_jobs, manager => job_to_candidates.
- all other intents => null.

state_patch must be an object.
facts must be an array of short strings.

Output JSON schema:
{
  "language": "ru|uk|en",
  "intent": "resume_upload|job_upload|prescreen_answer|match_request|match_request_jobs|match_request_candidates|status_request|clarification|smalltalk|command|other",
  "assistant_message": "string",
  "next_action": "none|extract_resume|extract_job|ask_next_question|run_matching",
  "matching_direction": "candidate_to_jobs|job_to_candidates|null",
  "state_patch": {},
  "facts": []
}`;

export class RouterV2Service {
  constructor(
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async classify(input: RouterV2Input): Promise<RouterV2Result> {
    const prompt = [
      ROUTER_V2_PROMPT,
      "",
      "Runtime JSON:",
      JSON.stringify(
        {
          user_message: input.userMessage,
          current_state: input.currentState,
          partial_profile: input.partialProfile ?? {},
          last_5_messages: input.lastMessages.slice(0, 5),
          role: input.role,
        },
        null,
        2,
      ),
    ].join("\n");

    const safe = await callJsonPromptSafe<Record<string, unknown>>({
      llmClient: this.llmClient,
      logger: this.logger,
      prompt,
      maxTokens: 360,
      timeoutMs: 30_000,
      promptName: "router_v2",
      schemaHint:
        "Router v2 JSON with language, intent, assistant_message, next_action, matching_direction, state_patch, facts.",
      validate: isRouterV2Payload,
    });

    if (!safe.ok) {
      this.logger.warn("router.v2.parse.failed", {
        parseSuccess: false,
        errorCode: safe.error_code,
      });
      return {
        parseSuccess: false,
        decision: buildSafeFallback(),
      };
    }

    const decision = normalizeRouterV2Decision(safe.data);
    if (!decision) {
      this.logger.warn("router.v2.parse.failed", {
        parseSuccess: false,
        errorCode: "schema_invalid",
      });
      return {
        parseSuccess: false,
        decision: buildSafeFallback(),
      };
    }

    this.logger.info("router.v2.parse.completed", {
      parseSuccess: true,
      intent: decision.intent,
      nextAction: decision.next_action,
    });
    return {
      parseSuccess: true,
      decision,
    };
  }
}

function normalizeRouterV2Decision(raw: Record<string, unknown>): RouterV2Decision | null {
  const language = normalizeLanguage(raw.language);
  const intent = normalizeIntent(raw.intent);
  const assistantMessage = toText(raw.assistant_message);
  const nextAction = normalizeNextAction(raw.next_action);
  const matchingDirection = normalizeMatchingDirection(raw.matching_direction, intent, nextAction);
  const statePatch = isPlainObject(raw.state_patch) ? raw.state_patch : {};
  const facts = normalizeFacts(raw.facts);

  if (!language || !intent || !nextAction || !assistantMessage || matchingDirection === undefined) {
    return null;
  }

  return {
    language,
    intent,
    assistant_message: assistantMessage,
    next_action: nextAction,
    matching_direction: matchingDirection,
    state_patch: statePatch,
    facts,
  };
}

function buildSafeFallback(): RouterV2Decision {
  return {
    language: "en",
    intent: "other",
    assistant_message: ROUTER_V2_SAFE_FALLBACK,
    next_action: "none",
    matching_direction: null,
    state_patch: {},
    facts: [],
  };
}

function isRouterV2Payload(value: unknown): value is Record<string, unknown> {
  if (!isPlainObject(value)) {
    return false;
  }
  if (!normalizeLanguage(value.language)) {
    return false;
  }
  if (!normalizeIntent(value.intent)) {
    return false;
  }
  if (!normalizeNextAction(value.next_action)) {
    return false;
  }
  if (
    normalizeMatchingDirection(
      value.matching_direction,
      normalizeIntent(value.intent),
      normalizeNextAction(value.next_action),
    ) === undefined
  ) {
    return false;
  }
  if (!toText(value.assistant_message)) {
    return false;
  }
  if (!isPlainObject(value.state_patch)) {
    return false;
  }
  if (!Array.isArray(value.facts)) {
    return false;
  }
  return true;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizeLanguage(value: unknown): RouterV2Language | null {
  const text = toText(value).toLowerCase();
  if (text === "ru" || text === "uk" || text === "en") {
    return text;
  }
  return null;
}

function normalizeIntent(value: unknown): RouterV2Intent | null {
  const text = toText(value).toLowerCase();
  if (
    text === "resume_upload" ||
    text === "job_upload" ||
    text === "prescreen_answer" ||
    text === "match_request" ||
    text === "match_request_jobs" ||
    text === "match_request_candidates" ||
    text === "status_request" ||
    text === "clarification" ||
    text === "smalltalk" ||
    text === "command" ||
    text === "other"
  ) {
    return text;
  }
  return null;
}

function normalizeMatchingDirection(
  value: unknown,
  intent: RouterV2Intent | null,
  nextAction: RouterV2NextAction | null,
): RouterV2MatchingDirection | undefined {
  const text = toText(value).toLowerCase();
  if (text === "candidate_to_jobs") {
    return "candidate_to_jobs";
  }
  if (text === "job_to_candidates") {
    return "job_to_candidates";
  }
  if (text === "" || text === "null" || value === null || typeof value === "undefined") {
    if (nextAction === "run_matching") {
      if (intent === "match_request_jobs") {
        return "candidate_to_jobs";
      }
      if (intent === "match_request_candidates") {
        return "job_to_candidates";
      }
      if (intent === "match_request") {
        return null;
      }
    }
    return null;
  }
  return undefined;
}

function normalizeNextAction(value: unknown): RouterV2NextAction | null {
  const text = toText(value).toLowerCase();
  if (
    text === "none" ||
    text === "extract_resume" ||
    text === "extract_job" ||
    text === "ask_next_question" ||
    text === "run_matching"
  ) {
    return text;
  }
  return null;
}

function normalizeFacts(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => toText(item))
    .filter(Boolean)
    .slice(0, 10);
}

function toText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
