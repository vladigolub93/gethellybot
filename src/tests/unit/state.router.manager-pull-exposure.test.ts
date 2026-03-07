import assert from "node:assert/strict";
import { ManagerExposureService } from "../../core/matching/manager-exposure.service";
import { Logger } from "../../config/logger";
import { MatchRecord } from "../../decisions/match.types";
import {
  CALLBACK_MANAGER_ACCEPT_PREFIX,
  CALLBACK_MANAGER_REJECT_PREFIX,
  CALLBACK_MANAGER_ASK_PREFIX,
} from "../../shared/constants";
import { TelegramReplyMarkup } from "../../shared/types/telegram.types";
import { StateRouter } from "../../router/state.router";
import { StateService } from "../../state/state.service";
import { managerCandidateSuggestionMessage } from "../../telegram/ui/messages";

interface SentMessage {
  source: string;
  chatId: number;
  text: string;
  replyMarkup?: TelegramReplyMarkup;
}

class TelegramClientMock {
  public readonly sent: SentMessage[] = [];

  async sendUserMessage(input: {
    source: string;
    chatId: number;
    text: string;
    replyMarkup?: TelegramReplyMarkup;
  }): Promise<void> {
    this.sent.push({
      source: input.source,
      chatId: input.chatId,
      text: input.text,
      replyMarkup: input.replyMarkup,
    });
  }
}

class LoggerMock implements Logger {
  public readonly debugCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];
  public readonly warnCalls: Array<{ message: string; meta?: Record<string, unknown> }> = [];

  debug(message: string, meta?: Record<string, unknown>): void {
    this.debugCalls.push({ message, meta });
  }

  info(): void {
    return;
  }

  warn(message: string, meta?: Record<string, unknown>): void {
    this.warnCalls.push({ message, meta });
  }

  error(): void {
    return;
  }
}

class ManagerExposureServiceSpy {
  public calls = 0;
  public inputs: Array<Record<string, unknown>> = [];

  exposeCandidateToManager(input: Record<string, unknown>): {
    canonicalObserved: null;
    canonicalFrom: null;
    canonicalTo: null;
    partialCoverage: boolean;
  } {
    this.calls += 1;
    this.inputs.push(input);
    return {
      canonicalObserved: null,
      canonicalFrom: null,
      canonicalTo: null,
      partialCoverage: true,
    };
  }
}

class ThrowingManagerExposureService {
  exposeCandidateToManager(): never {
    throw new Error("forced pull path sidecar failure");
  }
}

function findDebug(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.debugCalls.filter((entry) => entry.message === message);
}

function findWarn(logger: LoggerMock, message: string): Array<{ message: string; meta?: Record<string, unknown> }> {
  return logger.warnCalls.filter((entry) => entry.message === message);
}

function makeMatch(overrides: Partial<MatchRecord> = {}): MatchRecord {
  return {
    id: "match_1",
    managerUserId: 5001,
    candidateUserId: 7001,
    jobSummary: "Senior backend role",
    jobTechnicalSummary: null,
    candidateSummary: "Strong backend engineer",
    candidateTechnicalSummary: null,
    score: 88,
    explanation: "Strong backend fit",
    candidateDecision: "applied",
    managerDecision: "pending",
    status: "candidate_applied",
    createdAt: "2026-03-06T12:00:00.000Z",
    updatedAt: "2026-03-06T12:00:00.000Z",
    ...overrides,
  };
}

function buildHarness(options?: {
  matches?: MatchRecord[];
  managerExposureService?: ManagerExposureService;
}): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
  logger: LoggerMock;
} {
  const logger = new LoggerMock();
  const stateService = new StateService();
  const telegram = new TelegramClientMock();

  const router = new StateRouter(
    stateService,
    {
      async hydrateSession() {
        return null;
      },
      async persistSession() {},
    } as never,
    telegram as never,
    {
      async downloadFile() {
        return Buffer.from("fake");
      },
    } as never,
    {
      async extractText() {
        return "text";
      },
      detectDocumentType() {
        return "pdf";
      },
    } as never,
    {
      async transcribeOgg() {
        return "text";
      },
    } as never,
    180,
    false,
    0.12,
    {
      async bootstrapInterview(session: { state: string }) {
        return {
          nextState:
            session.state === "waiting_resume"
              ? "interviewing_candidate"
              : "interviewing_manager",
          intakeOneLiner: "I reviewed your document and prepared the next step.",
          answerInstruction: "Please answer clearly.",
          firstQuestion: "Tell me about your recent experience.",
          candidatePlanV2: undefined,
          plan: {
            summary: "stub",
            questions: [
              {
                id: "q1",
                question: "Tell me about your recent experience.",
                goal: "experience check",
                gapToClarify: "details",
              },
            ],
          },
        };
      },
      async submitAnswer() {
        return {
          kind: "completed",
          completedState: "candidate_profile_ready",
          completionMessage: "Done.",
        };
      },
      async skipCurrentQuestion() {
        return {
          kind: "completed",
          completedState: "candidate_profile_ready",
          completionMessage: "Done.",
        };
      },
      async finishInterviewNow() {
        return {
          completedState: "candidate_profile_ready",
          message: "Done.",
        };
      },
    } as never,
    {} as never,
    {
      async listAll() {
        return options?.matches ?? [];
      },
    } as never,
    {} as never,
    {
      async getMandatoryFields() {
        return {
          country: "",
          city: "",
          workMode: null,
          salaryAmount: null,
          salaryCurrency: null,
          salaryPeriod: null,
          profileComplete: false,
        };
      },
      async saveLocation() {},
      async saveWorkMode() {},
      async saveSalary() {},
    } as never,
    {
      async getMandatoryFields() {
        return {
          workFormat: null,
          remoteCountries: [],
          remoteWorldwide: false,
          budgetMin: null,
          budgetMax: null,
          budgetCurrency: null,
          budgetPeriod: null,
          profileComplete: false,
        };
      },
      async saveWorkFormat() {},
      async saveCountries() {},
      async saveBudget() {},
    } as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    {
      async requestDeletion() {
        return { confirmationMessage: "Deletion request accepted." };
      },
    } as never,
    {
      async setContactShared() {},
      async saveContact() {},
      async setMatchingPreferences() {},
      async getUserFlags() {
        return null;
      },
      async upsertTelegramUser() {},
    } as never,
    {} as never,
    {} as never,
    { getModelName: () => "gpt-5.2" } as never,
    {
      async classify() {
        return {
          parseSuccess: true,
          decision: {
            language: "en",
            intent: "other",
            assistant_message: "Please continue.",
            next_action: "none",
            state_patch: {},
            facts: [],
          },
        };
      },
    } as never,
    {
      async classify() {
        return {
          route: "OTHER",
          conversation_intent: "OTHER",
          meta_type: null,
          control_type: null,
          matching_intent: null,
          reply: "Please continue.",
          should_advance: false,
          should_process_text_as_document: false,
        };
      },
    } as never,
    {
      async classify() {
        return {
          intent: "META",
          meta_type: "other",
          control_type: null,
          reply: "Please continue.",
          should_advance: false,
        };
      },
    } as never,
    {
      async normalizeToEnglish(inputText: string) {
        return {
          detected_language: "en",
          english_text: inputText,
        };
      },
    } as never,
    {} as never,
    {
      async buildRouterContext() {
        return { knownUserName: null, ragContext: "" };
      },
      async buildInterviewContext() {
        return { knownUserName: null, ragContext: "" };
      },
      invalidate() {},
    } as never,
    {} as never,
    false,
    false,
    {
      async bootstrap() {
        throw new Error("not used in this test");
      },
      async submitAnswer() {
        throw new Error("not used in this test");
      },
      async skipCurrentQuestion() {
        throw new Error("not used in this test");
      },
    } as never,
    {
      async bootstrap() {
        throw new Error("not used in this test");
      },
      async submitAnswer() {
        throw new Error("not used in this test");
      },
      async skipCurrentQuestion() {
        throw new Error("not used in this test");
      },
    } as never,
    logger,
    false,
    undefined,
    false,
    undefined,
    undefined,
    undefined,
    undefined,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    false,
    undefined,
    undefined,
    options?.managerExposureService,
  );

  return {
    router,
    stateService,
    telegram,
    logger,
  };
}

async function callManagerPullPath(
  router: StateRouter,
  stateService: StateService,
  userId: number,
  chatId: number,
): Promise<boolean> {
  const session = stateService.getOrCreate(userId, chatId);
  session.role = "manager";
  return (router as unknown as {
    showTopMatchesWithActions: (inputSession: typeof session, inputChatId: number) => Promise<boolean>;
  }).showTopMatchesWithActions(session, chatId);
}

function extractInlineCallbackData(replyMarkup?: TelegramReplyMarkup): string[] {
  if (!replyMarkup || !("inline_keyboard" in replyMarkup) || !Array.isArray(replyMarkup.inline_keyboard)) {
    return [];
  }
  return replyMarkup.inline_keyboard
    .flat()
    .map((button) => button.callback_data)
    .filter((value): value is string => typeof value === "string");
}

async function testManagerPullPathStillWorksAndInvokesExposureSidecar(): Promise<void> {
  const match = makeMatch();
  const exposureSpy = new ManagerExposureServiceSpy();
  const harness = buildHarness({
    matches: [match],
    managerExposureService: exposureSpy as unknown as ManagerExposureService,
  });

  const sent = await callManagerPullPath(harness.router, harness.stateService, match.managerUserId, 777001);

  assert.equal(sent, true);
  assert.equal(exposureSpy.calls, 1);
  assert.equal(exposureSpy.inputs[0]?.matchId, match.id);

  assert.equal(harness.telegram.sent.length, 1);
  const outbound = harness.telegram.sent[0];
  assert.equal(
    outbound.source.endsWith("state_router.show_matches.manager_card"),
    true,
  );

  const expectedMessage = managerCandidateSuggestionMessage({
    candidateUserId: match.candidateUserId,
    score: match.score,
    candidateSummary: match.candidateSummary,
    candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
    explanationMessage: match.explanation,
  });
  const normalizedExpected = expectedMessage.replace(/\s+/g, " ").trim();
  const normalizedActual = outbound.text.replace(/\s+/g, " ").trim();
  assert.equal(normalizedActual, normalizedExpected);

  const callbacks = extractInlineCallbackData(outbound.replyMarkup);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_ACCEPT_PREFIX}${match.id}`), true);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_REJECT_PREFIX}${match.id}`), true);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_ASK_PREFIX}${match.id}`), true);

  const routedLogs = findDebug(harness.logger, "manager_exposure.pull_path_routed");
  assert.equal(routedLogs.length, 1);
}

async function testPullExposureFailureFallsBackWithoutBreakingRendering(): Promise<void> {
  const match = makeMatch({ id: "match_fallback" });
  const harness = buildHarness({
    matches: [match],
    managerExposureService: new ThrowingManagerExposureService() as unknown as ManagerExposureService,
  });

  const sent = await callManagerPullPath(harness.router, harness.stateService, match.managerUserId, 777002);

  assert.equal(sent, true);
  assert.equal(harness.telegram.sent.length, 1);
  assert.equal(
    (harness.telegram.sent[0]?.source ?? "").endsWith("state_router.show_matches.manager_card"),
    true,
  );

  const callbacks = extractInlineCallbackData(harness.telegram.sent[0]?.replyMarkup);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_ACCEPT_PREFIX}${match.id}`), true);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_REJECT_PREFIX}${match.id}`), true);
  assert.equal(callbacks.includes(`${CALLBACK_MANAGER_ASK_PREFIX}${match.id}`), true);

  const fallbackLogs = findWarn(harness.logger, "manager_exposure.pull_path_fallback");
  assert.equal(fallbackLogs.length, 1);
  assert.equal(fallbackLogs[0]?.meta?.matchId, match.id);
}

async function run(): Promise<void> {
  await testManagerPullPathStillWorksAndInvokesExposureSidecar();
  await testPullExposureFailureFallsBackWithoutBreakingRendering();
  process.stdout.write("state.router.manager-pull-exposure tests passed.\n");
}

void run();
