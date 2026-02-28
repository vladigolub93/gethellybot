import assert from "node:assert/strict";
import { StateRouter } from "../../router/state.router";
import { StateService } from "../../state/state.service";
import { NormalizedUpdate, TelegramReplyMarkup } from "../../shared/types/telegram.types";

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

function buildRouterHarness(): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
} {
  const stateService = new StateService();
  const telegram = new TelegramClientMock();
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
    {} as never,
    {} as never,
    {} as never,
    180,
    false,
    0.12,
    {} as never,
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
          route: "OTHER",
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
    noopLogger as never,
  );

  return { router, stateService, telegram };
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
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
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
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
}

async function testDeleteConfirmationEverythingResetsToStart(): Promise<void> {
  const { router, stateService } = buildRouterHarness();
  const userId = 91006;
  const chatId = 91006;

  await router.route(textUpdate(51, userId, chatId, "/start"));
  await router.route(textUpdate(52, userId, chatId, "Skip for now"));
  await router.route(textUpdate(53, userId, chatId, "I am a Candidate"));

  stateService.setLastBotMessage(
    userId,
    "Tell me what you want deleted: messages, profile details, or everything. Once you confirm, I will delete it and stop the interview flow.",
  );

  await router.route(textUpdate(54, userId, chatId, "everything"));
  const session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
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

async function run(): Promise<void> {
  await testOnboardingSkipRoleAndRestart();
  await testOnboardingContactThenRole();
  await testOnboardingSkipAliasAndRepeatStart();
  await testDeleteAllDataResetsToStart();
  await testDeleteTypoResetsToStart();
  await testDeleteConfirmationEverythingResetsToStart();
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
