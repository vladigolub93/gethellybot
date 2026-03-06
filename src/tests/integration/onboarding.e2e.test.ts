import assert from "node:assert/strict";
import { StateRouter } from "../../router/state.router";
import { StateService } from "../../state/state.service";
import { NormalizedUpdate, TelegramReplyMarkup } from "../../shared/types/telegram.types";
import { HellyAction } from "../../core/state/actions";
import { GatekeeperReason } from "../../core/state/gatekeeper/gatekeeper.types";

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

interface BuildRouterHarnessOptions {
  enableTypedRoleSelectionRouter?: boolean;
  enableTypedContactRouter?: boolean;
  enableTypedCvRouter?: boolean;
  enableTypedJdRouter?: boolean;
  enableTypedCandidateReviewRouter?: boolean;
  enableTypedManagerReviewRouter?: boolean;
  documentExtractedText?: string;
  voiceTranscriptionText?: string;
  actionRouterResult?: {
    action: HellyAction | null;
    confidence: number;
    message: string;
  };
  gatekeeperResult?: {
    accepted: boolean;
    reason: GatekeeperReason;
    action: HellyAction | null;
    message: string;
  };
}

function buildRouterHarness(): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
  actionRouterCalls: number;
  gatekeeperCalls: number;
} 
function buildRouterHarness(options: BuildRouterHarnessOptions): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
  actionRouterCalls: number;
  gatekeeperCalls: number;
}
function buildRouterHarness(options?: BuildRouterHarnessOptions): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
  actionRouterCalls: number;
  gatekeeperCalls: number;
} {
  const opts = options ?? {};
  const stateService = new StateService();
  const telegram = new TelegramClientMock();
  let actionRouterCalls = 0;
  let gatekeeperCalls = 0;
  const noopLogger = {
    debug() {},
    info() {},
    warn() {},
    error() {},
  };

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
        return (
          opts.documentExtractedText ??
          "Senior backend engineer with Node.js, TypeScript, PostgreSQL, AWS and production ownership."
        );
      },
      detectDocumentType() {
        return "pdf";
      },
    } as never,
    {
      async transcribeOgg() {
        return (
          opts.voiceTranscriptionText ??
          "This is my resume. I have six years of backend experience with Node.js and PostgreSQL in production."
        );
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
        return [];
      },
    } as never,
    {} as never,
    {} as never,
    {} as never,
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
        throw new Error("not used in onboarding test");
      },
      async submitAnswer() {
        throw new Error("not used in onboarding test");
      },
      async skipCurrentQuestion() {
        throw new Error("not used in onboarding test");
      },
    } as never,
    {
      async bootstrap() {
        throw new Error("not used in onboarding test");
      },
      async submitAnswer() {
        throw new Error("not used in onboarding test");
      },
      async skipCurrentQuestion() {
        throw new Error("not used in onboarding test");
      },
    } as never,
    noopLogger as never,
    false,
    undefined,
    false,
    undefined,
    undefined,
    undefined,
    undefined,
    opts.enableTypedRoleSelectionRouter ?? false,
    opts.enableTypedContactRouter ?? false,
    opts.enableTypedCvRouter ?? false,
    opts.enableTypedJdRouter ?? false,
    opts.enableTypedCandidateReviewRouter ?? false,
    opts.enableTypedManagerReviewRouter ?? false,
    {
      async classify() {
        actionRouterCalls += 1;
        return (
          opts.actionRouterResult ?? {
            action: null,
            confidence: 0,
            message: "Please continue.",
          }
        );
      },
    } as never,
    {
      evaluate(input: {
        action: HellyAction | null;
        confidence: number;
        message: string;
      }) {
        gatekeeperCalls += 1;
        return (
          opts.gatekeeperResult ?? {
            accepted: false,
            reason: "NO_ACTION",
            action: input.action,
            message: input.message,
          }
        );
      },
    } as never,
  );

  return {
    router,
    stateService,
    telegram,
    get actionRouterCalls() {
      return actionRouterCalls;
    },
    get gatekeeperCalls() {
      return gatekeeperCalls;
    },
  };
}

async function testOnboardingSkipRoleAndRestart(): Promise<void> {
  const { router, stateService, telegram } = buildRouterHarness();
  const userId = 91001;
  const chatId = 91001;

  await router.route(textUpdate(1, userId, chatId, "/start"));
  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(telegram.sent.length, 2);
  assert.equal(Boolean(telegram.sent[1]?.replyMarkup), true);
  assert.equal(hasReplyKeyboardButton(telegram.sent[1]?.replyMarkup, "Share my contact"), true);
  assert.equal(hasReplyKeyboardButton(telegram.sent[1]?.replyMarkup, "Skip for now"), true);

  await router.route(textUpdate(2, userId, chatId, "Skip for now"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, false);
  assert.equal(telegram.sent.some((item) => item.text.includes("Choose your role to begin.")), true);
  const rolePrompt = telegram.sent.find((item) => item.text.includes("Choose your role to begin."));
  assert.equal(Boolean(rolePrompt?.replyMarkup), true);
  assert.equal(hasReplyKeyboardButton(rolePrompt?.replyMarkup, "I am a Candidate"), true);
  assert.equal(hasReplyKeyboardButton(rolePrompt?.replyMarkup, "I am Hiring"), true);

  await router.route(textUpdate(3, userId, chatId, "I am a Candidate"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "candidate");
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.onboardingCompleted, true);

  await router.route(textUpdate(4, userId, chatId, "/start"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
}

async function testOnboardingContactThenRole(): Promise<void> {
  const { router, stateService } = buildRouterHarness();
  const userId = 91002;
  const chatId = 91002;

  await router.route(textUpdate(11, userId, chatId, "/start"));
  await router.route(contactUpdate(12, userId, chatId, "+380991112233", "Dmytro"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, false);
  assert.equal(session?.contactPhoneNumber, "+380991112233");

  await router.route(textUpdate(13, userId, chatId, "I am Hiring"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "manager");
  assert.equal(session?.state, "waiting_job");
}

async function testOnboardingSkipAliasAndRepeatStart(): Promise<void> {
  const { router, stateService, telegram } = buildRouterHarness();
  const userId = 91003;
  const chatId = 91003;

  await router.route(textUpdate(21, userId, chatId, "/start"));
  await router.route(textUpdate(22, userId, chatId, "skip"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, false);
  assert.equal(session?.state, "role_selection");
  assert.equal(
    telegram.sent.some((item) => item.text.includes("No problem, you can continue now.")),
    true,
  );

  await router.route(textUpdate(23, userId, chatId, "/start"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
}

async function testDeleteAllDataResetsToStart(): Promise<void> {
  const { router, stateService, telegram } = buildRouterHarness();
  const userId = 91004;
  const chatId = 91004;

  await router.route(textUpdate(31, userId, chatId, "/start"));
  await router.route(textUpdate(32, userId, chatId, "Skip for now"));
  await router.route(textUpdate(33, userId, chatId, "I am a Candidate"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");

  await router.route(textUpdate(34, userId, chatId, "Delete all my data"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.pendingDataDeletionConfirmation, true);
  assert.equal(
    telegram.sent.some((item) => item.text.includes("This action permanently deletes your stored data and resets your session.")),
    true,
  );

  await router.route(textUpdate(35, userId, chatId, "Delete everything"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(session?.pendingDataDeletionConfirmation, false);
  assert.equal(
    telegram.sent.some((item) => item.text.includes("Before we begin, please share your Telegram contact.")),
    true,
  );
}

async function testDeleteTypoResetsToStart(): Promise<void> {
  const { router, stateService } = buildRouterHarness();
  const userId = 91005;
  const chatId = 91005;

  await router.route(textUpdate(41, userId, chatId, "/start"));
  await router.route(textUpdate(42, userId, chatId, "Skip for now"));
  await router.route(textUpdate(43, userId, chatId, "I am a Candidate"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");

  await router.route(textUpdate(44, userId, chatId, "delet my data"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.pendingDataDeletionConfirmation, true);

  await router.route(textUpdate(45, userId, chatId, "everything"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(session?.pendingDataDeletionConfirmation, false);
}

async function testDeleteConfirmationEverythingResetsToStart(): Promise<void> {
  const { router, stateService } = buildRouterHarness();
  const userId = 91006;
  const chatId = 91006;

  await router.route(textUpdate(51, userId, chatId, "/start"));
  await router.route(textUpdate(52, userId, chatId, "Skip for now"));
  await router.route(textUpdate(53, userId, chatId, "I am a Candidate"));

  await router.route(textUpdate(54, userId, chatId, "delete my data"));
  await router.route(textUpdate(55, userId, chatId, "cancel"));
  const session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.pendingDataDeletionConfirmation, false);
}

async function testTypedRoleSelectionFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedRoleSelectionRouter: false,
    actionRouterResult: {
      action: "SELECT_ROLE_MANAGER",
      confidence: 0.99,
      message: "Selecting manager role.",
    },
  });
  const userId = 91007;
  const chatId = 91007;

  await harness.router.route(textUpdate(61, userId, chatId, "/start"));
  await harness.router.route(textUpdate(62, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(63, userId, chatId, "I am a Candidate"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "candidate");
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedRoleSelectionCandidateWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedRoleSelectionRouter: true,
    actionRouterResult: {
      action: "SELECT_ROLE_CANDIDATE",
      confidence: 0.95,
      message: "I can set candidate role.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SELECT_ROLE_CANDIDATE",
      message: "I can set candidate role.",
    },
  });
  const userId = 91008;
  const chatId = 91008;

  await harness.router.route(textUpdate(71, userId, chatId, "/start"));
  await harness.router.route(textUpdate(72, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(73, userId, chatId, "I am a Candidate"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "candidate");
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedRoleSelectionManagerWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedRoleSelectionRouter: true,
    actionRouterResult: {
      action: "SELECT_ROLE_MANAGER",
      confidence: 0.92,
      message: "I can set manager role.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SELECT_ROLE_MANAGER",
      message: "I can set manager role.",
    },
  });
  const userId = 91009;
  const chatId = 91009;

  await harness.router.route(textUpdate(81, userId, chatId, "/start"));
  await harness.router.route(textUpdate(82, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(83, userId, chatId, "I am Hiring"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "manager");
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedRoleSelectionRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedRoleSelectionRouter: true,
    actionRouterResult: {
      action: "SELECT_ROLE_MANAGER",
      confidence: 0.2,
      message: "Maybe manager role.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "SELECT_ROLE_MANAGER",
      message: "Maybe manager role.",
    },
  });
  const userId = 91010;
  const chatId = 91010;

  await harness.router.route(textUpdate(91, userId, chatId, "/start"));
  await harness.router.route(textUpdate(92, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(93, userId, chatId, "I am a Candidate"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.role, "candidate");
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedContactFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedContactRouter: false,
    actionRouterResult: {
      action: "SHARE_CONTACT",
      confidence: 0.99,
      message: "Please share contact.",
    },
  });
  const userId = 91011;
  const chatId = 91011;

  await harness.router.route(textUpdate(101, userId, chatId, "/start"));
  await harness.router.route(textUpdate(102, userId, chatId, "+380991234567"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, false);
  assert.equal(session?.contactPhoneNumber, "+380991234567");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedContactShareIntentWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedContactRouter: true,
    actionRouterResult: {
      action: "SHARE_CONTACT",
      confidence: 0.9,
      message: "Please share your contact.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SHARE_CONTACT",
      message: "Please share your contact.",
    },
  });
  const userId = 91012;
  const chatId = 91012;

  await harness.router.route(textUpdate(111, userId, chatId, "/start"));
  await harness.router.route(textUpdate(112, userId, chatId, "share my contact"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
  assert.equal(
    harness.telegram.sent.some((item) =>
      item.text.includes("Please send your phone number in one message."),
    ),
    true,
  );
}

async function testTypedContactPhoneTextWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedContactRouter: true,
    actionRouterResult: {
      action: "SHARE_PHONE_TEXT",
      confidence: 0.88,
      message: "Phone number detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SHARE_PHONE_TEXT",
      message: "Phone number detected.",
    },
  });
  const userId = 91013;
  const chatId = 91013;

  await harness.router.route(textUpdate(121, userId, chatId, "/start"));
  await harness.router.route(textUpdate(122, userId, chatId, "+380992345678"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, false);
  assert.equal(session?.contactPhoneNumber, "+380992345678");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedContactRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedContactRouter: true,
    actionRouterResult: {
      action: "SHARE_CONTACT",
      confidence: 0.2,
      message: "Please share your contact.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "SHARE_CONTACT",
      message: "Please share your contact.",
    },
  });
  const userId = 91014;
  const chatId = 91014;

  await harness.router.route(textUpdate(131, userId, chatId, "/start"));
  await harness.router.route(textUpdate(132, userId, chatId, "share my contact"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
  assert.equal(
    harness.telegram.sent.some((item) =>
      item.text.includes("Please send your phone number in one message."),
    ),
    true,
  );
}

async function testTypedCvFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCvRouter: false,
    actionRouterResult: {
      action: "SUBMIT_CV",
      confidence: 0.99,
      message: "CV detected.",
    },
  });
  const userId = 91015;
  const chatId = 91015;

  await harness.router.route(textUpdate(141, userId, chatId, "/start"));
  await harness.router.route(textUpdate(142, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(143, userId, chatId, "I am a Candidate"));
  await harness.router.route(
    textUpdate(
      144,
      userId,
      chatId,
      "This is my resume. I built backend services in Node.js and PostgreSQL, improved reliability, and led release processes.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedCvTextWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCvRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.9,
      message: "Resume text detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_TEXT",
      message: "Resume text detected.",
    },
  });
  const userId = 91016;
  const chatId = 91016;

  await harness.router.route(textUpdate(151, userId, chatId, "/start"));
  await harness.router.route(textUpdate(152, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(153, userId, chatId, "I am a Candidate"));
  await harness.router.route(
    textUpdate(
      154,
      userId,
      chatId,
      "This is my resume. I built backend services in Node.js and PostgreSQL, improved reliability, and led release processes.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCvFileWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCvRouter: true,
    actionRouterResult: {
      action: "SUBMIT_FILE",
      confidence: 0.92,
      message: "Resume file detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_FILE",
      message: "Resume file detected.",
    },
  });
  const userId = 91017;
  const chatId = 91017;

  await harness.router.route(textUpdate(161, userId, chatId, "/start"));
  await harness.router.route(textUpdate(162, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(163, userId, chatId, "I am a Candidate"));
  await harness.router.route(documentUpdate(164, userId, chatId, "resume.pdf", "application/pdf", "file-1"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCvVoiceWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCvRouter: true,
    actionRouterResult: {
      action: "SUBMIT_VOICE",
      confidence: 0.86,
      message: "Voice resume detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_VOICE",
      message: "Voice resume detected.",
    },
  });
  const userId = 91018;
  const chatId = 91018;

  await harness.router.route(textUpdate(171, userId, chatId, "/start"));
  await harness.router.route(textUpdate(172, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(173, userId, chatId, "I am a Candidate"));
  await harness.router.route(voiceUpdate(174, userId, chatId, "voice-file-1", 12));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls > 0, true);
  assert.equal(harness.gatekeeperCalls > 0, true);
}

async function testTypedCvRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCvRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.2,
      message: "Maybe resume.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "SUBMIT_TEXT",
      message: "Maybe resume.",
    },
  });
  const userId = 91019;
  const chatId = 91019;

  await harness.router.route(textUpdate(181, userId, chatId, "/start"));
  await harness.router.route(textUpdate(182, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(183, userId, chatId, "I am a Candidate"));
  await harness.router.route(
    textUpdate(
      184,
      userId,
      chatId,
      "This is my resume. I have backend experience with Node.js, TypeScript, PostgreSQL and cloud deployment.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedJdFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedJdRouter: false,
    actionRouterResult: {
      action: "SUBMIT_JD",
      confidence: 0.99,
      message: "JD detected.",
    },
  });
  const userId = 91020;
  const chatId = 91020;

  await harness.router.route(textUpdate(191, userId, chatId, "/start"));
  await harness.router.route(textUpdate(192, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(193, userId, chatId, "I am Hiring"));
  await harness.router.route(
    textUpdate(
      194,
      userId,
      chatId,
      "We need a backend engineer for payments platform with Node.js, TypeScript, PostgreSQL and cloud operations.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedJdTextWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedJdRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.91,
      message: "JD text detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_TEXT",
      message: "JD text detected.",
    },
  });
  const userId = 91021;
  const chatId = 91021;

  await harness.router.route(textUpdate(201, userId, chatId, "/start"));
  await harness.router.route(textUpdate(202, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(203, userId, chatId, "I am Hiring"));
  await harness.router.route(
    textUpdate(
      204,
      userId,
      chatId,
      "This is the job description. We are hiring a backend engineer to build APIs, improve reliability and own production operations.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedJdFileWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedJdRouter: true,
    actionRouterResult: {
      action: "SUBMIT_FILE",
      confidence: 0.93,
      message: "JD file detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_FILE",
      message: "JD file detected.",
    },
  });
  const userId = 91022;
  const chatId = 91022;

  await harness.router.route(textUpdate(211, userId, chatId, "/start"));
  await harness.router.route(textUpdate(212, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(213, userId, chatId, "I am Hiring"));
  await harness.router.route(documentUpdate(214, userId, chatId, "jd.pdf", "application/pdf", "file-2"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedJdVoiceWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedJdRouter: true,
    voiceTranscriptionText: "Need a backend engineer with Node.js and PostgreSQL.",
    actionRouterResult: {
      action: "SUBMIT_VOICE",
      confidence: 0.87,
      message: "JD voice detected.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_VOICE",
      message: "JD voice detected.",
    },
  });
  const userId = 91023;
  const chatId = 91023;

  await harness.router.route(textUpdate(221, userId, chatId, "/start"));
  await harness.router.route(textUpdate(222, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(223, userId, chatId, "I am Hiring"));
  await harness.router.route(voiceUpdate(224, userId, chatId, "voice-file-2", 10));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls > 0, true);
  assert.equal(harness.gatekeeperCalls > 0, true);
}

async function testTypedJdRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedJdRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.2,
      message: "Maybe JD.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "SUBMIT_TEXT",
      message: "Maybe JD.",
    },
  });
  const userId = 91024;
  const chatId = 91024;

  await harness.router.route(textUpdate(231, userId, chatId, "/start"));
  await harness.router.route(textUpdate(232, userId, chatId, "Skip for now"));
  await harness.router.route(textUpdate(233, userId, chatId, "I am Hiring"));
  await harness.router.route(
    textUpdate(
      234,
      userId,
      chatId,
      "This is the job description. Hiring backend engineer for Node.js APIs and data pipelines.",
    ),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCandidateReviewFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCandidateReviewRouter: false,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.98,
      message: "Summary approved.",
    },
  });
  const userId = 91025;
  const chatId = 91025;
  seedCandidateSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(241, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedCandidateReviewApproveWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCandidateReviewRouter: true,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.95,
      message: "Summary approved.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "APPROVE",
      message: "Summary approved.",
    },
  });
  const userId = 91026;
  const chatId = 91026;
  seedCandidateSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(251, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCandidateReviewEditWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCandidateReviewRouter: true,
    actionRouterResult: {
      action: "EDIT",
      confidence: 0.93,
      message: "Summary edit requested.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "EDIT",
      message: "Summary edit requested.",
    },
  });
  const userId = 91027;
  const chatId = 91027;
  seedCandidateSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(261, userId, chatId, "edit"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCandidateReviewFreeTextWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCandidateReviewRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.91,
      message: "Summary correction provided.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_TEXT",
      message: "Summary correction provided.",
    },
  });
  const userId = 91028;
  const chatId = 91028;
  seedCandidateSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(
    textUpdate(271, userId, chatId, "Please update summary: 6 years backend, not 4, and add AWS migration project."),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedCandidateReviewRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedCandidateReviewRouter: true,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.2,
      message: "Maybe approve.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "APPROVE",
      message: "Maybe approve.",
    },
  });
  const userId = 91029;
  const chatId = 91029;
  seedCandidateSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(281, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedManagerReviewFlagOffKeepsLegacyPath(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedManagerReviewRouter: false,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.96,
      message: "Vacancy summary approved.",
    },
  });
  const userId = 91030;
  const chatId = 91030;
  seedManagerSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(291, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(harness.actionRouterCalls, 0);
  assert.equal(harness.gatekeeperCalls, 0);
}

async function testTypedManagerReviewApproveWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedManagerReviewRouter: true,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.94,
      message: "Vacancy summary approved.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "APPROVE",
      message: "Vacancy summary approved.",
    },
  });
  const userId = 91031;
  const chatId = 91031;
  seedManagerSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(301, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedManagerReviewEditWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedManagerReviewRouter: true,
    actionRouterResult: {
      action: "EDIT",
      confidence: 0.93,
      message: "Vacancy summary edit requested.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "EDIT",
      message: "Vacancy summary edit requested.",
    },
  });
  const userId = 91032;
  const chatId = 91032;
  seedManagerSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(311, userId, chatId, "edit"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedManagerReviewFreeTextWhenEnabled(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedManagerReviewRouter: true,
    actionRouterResult: {
      action: "SUBMIT_TEXT",
      confidence: 0.9,
      message: "Vacancy summary corrections provided.",
    },
    gatekeeperResult: {
      accepted: true,
      reason: "ACCEPTED",
      action: "SUBMIT_TEXT",
      message: "Vacancy summary corrections provided.",
    },
  });
  const userId = 91033;
  const chatId = 91033;
  seedManagerSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(
    textUpdate(321, userId, chatId, "Please update summary: remote-first team, payment domain, and Node.js microservices."),
  );

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

async function testTypedManagerReviewRejectedFallsBackToLegacy(): Promise<void> {
  const harness = buildRouterHarness({
    enableTypedManagerReviewRouter: true,
    actionRouterResult: {
      action: "APPROVE",
      confidence: 0.2,
      message: "Maybe approve.",
    },
    gatekeeperResult: {
      accepted: false,
      reason: "LOW_CONFIDENCE",
      action: "APPROVE",
      message: "Maybe approve.",
    },
  });
  const userId = 91034;
  const chatId = 91034;
  seedManagerSummaryReviewSession(harness.stateService, userId, chatId);

  await harness.router.route(textUpdate(331, userId, chatId, "approve"));

  const session = harness.stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(harness.actionRouterCalls, 1);
  assert.equal(harness.gatekeeperCalls, 1);
}

function seedCandidateSummaryReviewSession(
  stateService: StateService,
  userId: number,
  chatId: number,
): void {
  const session = stateService.getOrCreate(userId, chatId);
  session.role = "candidate";
  session.state = "interviewing_candidate";
  session.interviewPlan = {
    summary: "Candidate intake",
    questions: [
      {
        id: "q1",
        question: "Please confirm your profile summary is correct.",
        goal: "summary confirmation",
        gapToClarify: "profile fit",
      },
    ],
  };
  session.currentQuestionIndex = 0;
  session.pendingFollowUp = undefined;
  session.answers = [];
}

function seedManagerSummaryReviewSession(
  stateService: StateService,
  userId: number,
  chatId: number,
): void {
  const session = stateService.getOrCreate(userId, chatId);
  session.role = "manager";
  session.state = "interviewing_manager";
  session.interviewPlan = {
    summary: "Manager intake",
    questions: [
      {
        id: "q1",
        question: "Please confirm your vacancy summary is correct.",
        goal: "summary confirmation",
        gapToClarify: "vacancy fit",
      },
    ],
  };
  session.currentQuestionIndex = 0;
  session.pendingFollowUp = undefined;
  session.answers = [];
}

function textUpdate(
  updateId: number,
  userId: number,
  chatId: number,
  text: string,
): NormalizedUpdate {
  return {
    kind: "text",
    updateId,
    chatId,
    userId,
    text,
  };
}

function contactUpdate(
  updateId: number,
  userId: number,
  chatId: number,
  phoneNumber: string,
  firstName: string,
): NormalizedUpdate {
  return {
    kind: "contact",
    updateId,
    chatId,
    userId,
    phoneNumber,
    firstName,
  };
}

function documentUpdate(
  updateId: number,
  userId: number,
  chatId: number,
  fileName: string,
  mimeType: string,
  fileId: string,
): NormalizedUpdate {
  return {
    kind: "document",
    updateId,
    chatId,
    userId,
    fileName,
    mimeType,
    fileId,
  };
}

function voiceUpdate(
  updateId: number,
  userId: number,
  chatId: number,
  fileId: string,
  durationSec: number,
): NormalizedUpdate {
  return {
    kind: "voice",
    updateId,
    chatId,
    userId,
    fileId,
    durationSec,
  };
}

async function run(): Promise<void> {
  await testOnboardingSkipRoleAndRestart();
  await testOnboardingContactThenRole();
  await testOnboardingSkipAliasAndRepeatStart();
  await testDeleteAllDataResetsToStart();
  await testDeleteTypoResetsToStart();
  await testDeleteConfirmationEverythingResetsToStart();
  await testTypedRoleSelectionFlagOffKeepsLegacyPath();
  await testTypedRoleSelectionCandidateWhenEnabled();
  await testTypedRoleSelectionManagerWhenEnabled();
  await testTypedRoleSelectionRejectedFallsBackToLegacy();
  await testTypedContactFlagOffKeepsLegacyPath();
  await testTypedContactShareIntentWhenEnabled();
  await testTypedContactPhoneTextWhenEnabled();
  await testTypedContactRejectedFallsBackToLegacy();
  await testTypedCvFlagOffKeepsLegacyPath();
  await testTypedCvTextWhenEnabled();
  await testTypedCvFileWhenEnabled();
  await testTypedCvVoiceWhenEnabled();
  await testTypedCvRejectedFallsBackToLegacy();
  await testTypedJdFlagOffKeepsLegacyPath();
  await testTypedJdTextWhenEnabled();
  await testTypedJdFileWhenEnabled();
  await testTypedJdVoiceWhenEnabled();
  await testTypedJdRejectedFallsBackToLegacy();
  await testTypedCandidateReviewFlagOffKeepsLegacyPath();
  await testTypedCandidateReviewApproveWhenEnabled();
  await testTypedCandidateReviewEditWhenEnabled();
  await testTypedCandidateReviewFreeTextWhenEnabled();
  await testTypedCandidateReviewRejectedFallsBackToLegacy();
  await testTypedManagerReviewFlagOffKeepsLegacyPath();
  await testTypedManagerReviewApproveWhenEnabled();
  await testTypedManagerReviewEditWhenEnabled();
  await testTypedManagerReviewFreeTextWhenEnabled();
  await testTypedManagerReviewRejectedFallsBackToLegacy();
  process.stdout.write("Onboarding e2e tests passed.\n");
}

void run();

function hasReplyKeyboardButton(
  replyMarkup: TelegramReplyMarkup | undefined,
  buttonText: string,
): boolean {
  if (!replyMarkup || !("keyboard" in replyMarkup) || !Array.isArray(replyMarkup.keyboard)) {
    return false;
  }
  return replyMarkup.keyboard.some((row) =>
    Array.isArray(row) && row.some((button) => button.text === buttonText),
  );
}
