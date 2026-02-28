import assert from "node:assert/strict";
import { callJsonPromptSafe } from "../../ai/llm.safe";
import { InterviewIntentRouterService } from "../../interviews/interview-intent-router.service";
import { AlwaysOnRouterService } from "../../router/always-on-router.service";
import { checkAndConsumeUserRateLimit } from "../../shared/utils/rate-limit";
import { shouldProcessUpdate } from "../../shared/utils/telegram-idempotency";

const logger = {
  debug() {},
  info() {},
  warn() {},
  error() {},
};

async function testWebhookIdempotency(): Promise<void> {
  const updateId = Date.now() + Math.floor(Math.random() * 1000);
  const userId = 9001;
  const first = await shouldProcessUpdate(updateId, userId);
  const second = await shouldProcessUpdate(updateId, userId);
  assert.equal(first, true);
  assert.equal(second, false);
}

function testRateLimiter(): void {
  const userId = 8001 + Math.floor(Math.random() * 1000);
  let blocked = false;
  for (let i = 0; i < 11; i += 1) {
    const result = checkAndConsumeUserRateLimit(userId);
    if (!result.allowed) {
      blocked = true;
      break;
    }
  }
  assert.equal(blocked, true);
}

async function testAlwaysOnRouterIsCalled(): Promise<void> {
  let calls = 0;
  const llmMock = {
    getModelName(): string {
      return "gpt-5.2";
    },
    async generateStructuredJson(): Promise<string> {
      calls += 1;
      return JSON.stringify({
        route: "OTHER",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: "Please continue.",
        should_advance: false,
        should_process_text_as_document: false,
      });
    },
  };

  const router = new AlwaysOnRouterService(llmMock as never, logger);
  const decision = await router.classify({
    updateId: 123,
    telegramUserId: 456,
    currentState: "waiting_resume",
    userRole: "candidate",
    hasText: true,
    textEnglish: "hello",
    hasDocument: false,
    hasVoice: false,
    currentQuestion: null,
    lastBotMessage: null,
  });
  assert.equal(calls, 1);
  assert.equal(decision.route, "OTHER");
}

async function testInterviewIntentMetaDoesNotAdvance(): Promise<void> {
  const llmMock = {
    async generateStructuredJson(): Promise<string> {
      return JSON.stringify({
        intent: "META",
        meta_type: "timing",
        control_type: null,
        reply: "Usually this takes a couple of minutes.",
        should_advance: false,
      });
    },
  };

  const service = new InterviewIntentRouterService(llmMock as never, logger);
  const decision = await service.classify({
    currentState: "interviewing_candidate",
    userRole: "candidate",
    currentQuestion: "Tell me about your architecture decisions.",
    userMessageEnglish: "How long will this take?",
    lastBotMessage: null,
  });
  assert.equal(decision.intent, "META");
  assert.equal(decision.should_advance, false);
}

async function testJsonSafeFallbackPath(): Promise<void> {
  const result = await callJsonPromptSafe<Record<string, unknown>>({
    llmClient: {
      async generateStructuredJson(): Promise<string> {
        return "not a json";
      },
    },
    prompt: "irrelevant",
    maxTokens: 50,
    promptName: "json_safe_test",
    schemaHint: "object with field x",
  });

  assert.equal(result.ok, false);
}

async function run(): Promise<void> {
  await testWebhookIdempotency();
  testRateLimiter();
  await testAlwaysOnRouterIsCalled();
  await testInterviewIntentMetaDoesNotAdvance();
  await testJsonSafeFallbackPath();
  process.stdout.write("Integration smoke tests passed.\n");
}

void run();
