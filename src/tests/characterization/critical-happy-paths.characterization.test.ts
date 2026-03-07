import assert from "node:assert/strict";
import { StateRouter } from "../../router/state.router";
import { StateService } from "../../state/state.service";
import { NormalizedUpdate, TelegramReplyMarkup } from "../../shared/types/telegram.types";
import { CandidateSalaryCurrency, CandidateSalaryPeriod, CandidateWorkMode, JobBudgetCurrency, JobBudgetPeriod, JobWorkFormat } from "../../shared/types/state.types";

interface SentMessage {
  source: string;
  chatId: number;
  text: string;
  replyMarkup?: TelegramReplyMarkup;
  kind?: "primary" | "secondary";
}

interface CandidateMandatoryRecord {
  country: string;
  city: string;
  workMode: CandidateWorkMode | null;
  salaryAmount: number | null;
  salaryCurrency: CandidateSalaryCurrency | null;
  salaryPeriod: CandidateSalaryPeriod | null;
}

interface ManagerMandatoryRecord {
  workFormat: JobWorkFormat | null;
  remoteCountries: string[];
  remoteWorldwide: boolean;
  budgetMin: number | null;
  budgetMax: number | null;
  budgetCurrency: JobBudgetCurrency | null;
  budgetPeriod: JobBudgetPeriod | null;
}

interface UserFlagsRecord {
  contactShared: boolean;
  autoMatchingEnabled: boolean;
  autoNotifyEnabled: boolean;
  matchingPaused: boolean;
}

class TelegramClientMock {
  public readonly sent: SentMessage[] = [];

  async sendUserMessage(input: {
    source: string;
    chatId: number;
    text: string;
    replyMarkup?: TelegramReplyMarkup;
    kind?: "primary" | "secondary";
  }): Promise<void> {
    this.sent.push({
      source: input.source,
      chatId: input.chatId,
      text: input.text,
      replyMarkup: input.replyMarkup,
      kind: input.kind,
    });
  }

  async answerCallbackQuery(): Promise<void> {}
}

function buildRouterHarness(): {
  router: StateRouter;
  stateService: StateService;
  telegram: TelegramClientMock;
  dataDeletionCalls: Array<{ telegramUserId: number; reason: string }>;
} {
  const stateService = new StateService();
  const telegram = new TelegramClientMock();

  const candidateMandatoryByUser = new Map<number, CandidateMandatoryRecord>();
  const managerMandatoryByUser = new Map<number, ManagerMandatoryRecord>();
  const userFlagsByUser = new Map<number, UserFlagsRecord>();
  const dataDeletionCalls: Array<{ telegramUserId: number; reason: string }> = [];

  const persistedSessions = new Map<number, ReturnType<StateService["getSession"]>>();

  const noopLogger = {
    debug() {},
    info() {},
    warn() {},
    error() {},
  };

  const router = new StateRouter(
    stateService,
    {
      async hydrateSession(userId: number) {
        return (persistedSessions.get(userId) as never) ?? null;
      },
      async persistSession(session: unknown) {
        const typed = session as { userId: number };
        persistedSessions.set(typed.userId, session as never);
      },
    } as never,
    telegram as never,
    {
      async downloadFile() {
        throw new Error("not used in characterization tests");
      },
    } as never,
    {
      extractText: async () => {
        throw new Error("not used in characterization tests");
      },
      detectDocumentType: () => "unknown",
    } as never,
    {
      async transcribeOgg() {
        throw new Error("not used in characterization tests");
      },
    } as never,
    180,
    false,
    0,
    {
      async bootstrapInterview(session: { state: string }) {
        if (session.state === "waiting_resume") {
          return {
            nextState: "interviewing_candidate",
            intakeOneLiner: "I reviewed your resume and drafted a short summary.",
            answerInstruction: "Reply approve to continue, or send corrections.",
            firstQuestion: "Please confirm your profile summary is correct.",
            candidatePlanV2: undefined,
            plan: {
              summary: "Candidate intake",
              questions: [
                {
                  id: "cand_q1",
                  question: "Please confirm your profile summary is correct.",
                  goal: "summary confirmation",
                  gapToClarify: "profile fit",
                },
              ],
            },
          };
        }
        return {
          nextState: "interviewing_manager",
          intakeOneLiner: "I reviewed your job description and drafted a vacancy summary.",
          answerInstruction: "Reply approve to continue, or send corrections.",
          firstQuestion: "Please confirm your vacancy summary is correct.",
          candidatePlanV2: undefined,
          plan: {
            summary: "Manager intake",
            questions: [
              {
                id: "mgr_q1",
                question: "Please confirm your vacancy summary is correct.",
                goal: "summary confirmation",
                gapToClarify: "vacancy fit",
              },
            ],
          },
        };
      },
      async submitAnswer(session: { state: string }) {
        if (session.state === "interviewing_candidate") {
          return {
            kind: "completed",
            completedState: "candidate_profile_ready",
            completionMessage: "Candidate summary accepted.",
          };
        }
        return {
          kind: "completed",
          completedState: "job_profile_ready",
          completionMessage: "Vacancy summary accepted.",
        };
      },
      async skipCurrentQuestion(session: { state: string }) {
        if (session.state === "interviewing_candidate") {
          return {
            kind: "completed",
            completedState: "candidate_profile_ready",
            completionMessage: "Interview completed.",
          };
        }
        return {
          kind: "completed",
          completedState: "job_profile_ready",
          completionMessage: "Interview completed.",
        };
      },
      async finishInterviewNow(session: { state: string }) {
        if (session.state === "interviewing_candidate") {
          return {
            completedState: "candidate_profile_ready",
            message: "Interview completed.",
          };
        }
        return {
          completedState: "job_profile_ready",
          message: "Interview completed.",
        };
      },
    } as never,
    {
      async runForCandidate() {
        return { message: "No matches" };
      },
      async runForManager() {
        return { message: "No matches" };
      },
      async checkCandidateMatchingReadiness() {
        return { ready: true };
      },
      async checkManagerMatchingReadiness() {
        return { ready: true };
      },
    } as never,
    {
      async listAll() {
        return [];
      },
      async saveMany() {},
      async clearAll() {},
    } as never,
    {
      async notifyCandidateMatch() {},
      async notifyManagerMatch() {},
      async notifyContactShared() {},
    } as never,
    {
      async getMandatoryFields(userId: number) {
        const existing = candidateMandatoryByUser.get(userId);
        return {
          country: existing?.country ?? "",
          city: existing?.city ?? "",
          workMode: existing?.workMode ?? null,
          salaryAmount: existing?.salaryAmount ?? null,
          salaryCurrency: existing?.salaryCurrency ?? null,
          salaryPeriod: existing?.salaryPeriod ?? null,
          profileComplete: Boolean(
            existing?.country &&
              existing?.city &&
              existing?.workMode &&
              typeof existing?.salaryAmount === "number" &&
              existing.salaryAmount > 0 &&
              existing.salaryCurrency &&
              existing.salaryPeriod,
          ),
        };
      },
      async saveLocation(userId: number, input: { country: string; city: string }) {
        const current = candidateMandatoryByUser.get(userId) ?? {
          country: "",
          city: "",
          workMode: null,
          salaryAmount: null,
          salaryCurrency: null,
          salaryPeriod: null,
        };
        candidateMandatoryByUser.set(userId, {
          ...current,
          country: input.country,
          city: input.city,
        });
      },
      async saveWorkMode(userId: number, workMode: CandidateWorkMode) {
        const current = candidateMandatoryByUser.get(userId) ?? {
          country: "",
          city: "",
          workMode: null,
          salaryAmount: null,
          salaryCurrency: null,
          salaryPeriod: null,
        };
        candidateMandatoryByUser.set(userId, {
          ...current,
          workMode,
        });
      },
      async saveSalary(
        userId: number,
        salary: { amount: number; currency: CandidateSalaryCurrency; period: CandidateSalaryPeriod },
      ) {
        const current = candidateMandatoryByUser.get(userId) ?? {
          country: "",
          city: "",
          workMode: null,
          salaryAmount: null,
          salaryCurrency: null,
          salaryPeriod: null,
        };
        candidateMandatoryByUser.set(userId, {
          ...current,
          salaryAmount: salary.amount,
          salaryCurrency: salary.currency,
          salaryPeriod: salary.period,
        });
      },
    } as never,
    {
      async getMandatoryFields(userId: number) {
        const existing = managerMandatoryByUser.get(userId);
        return {
          workFormat: existing?.workFormat ?? null,
          remoteCountries: existing?.remoteCountries ?? [],
          remoteWorldwide: existing?.remoteWorldwide ?? false,
          budgetMin: existing?.budgetMin ?? null,
          budgetMax: existing?.budgetMax ?? null,
          budgetCurrency: existing?.budgetCurrency ?? null,
          budgetPeriod: existing?.budgetPeriod ?? null,
          profileComplete: Boolean(
            existing?.workFormat &&
              (existing.workFormat !== "remote" || existing.remoteWorldwide || existing.remoteCountries.length > 0) &&
              typeof existing?.budgetMin === "number" &&
              typeof existing?.budgetMax === "number" &&
              existing.budgetMin > 0 &&
              existing.budgetMax >= existing.budgetMin &&
              existing.budgetCurrency &&
              existing.budgetPeriod,
          ),
        };
      },
      async saveWorkFormat(userId: number, workFormat: JobWorkFormat) {
        const current = managerMandatoryByUser.get(userId) ?? {
          workFormat: null,
          remoteCountries: [],
          remoteWorldwide: false,
          budgetMin: null,
          budgetMax: null,
          budgetCurrency: null,
          budgetPeriod: null,
        };
        managerMandatoryByUser.set(userId, {
          ...current,
          workFormat,
          ...(workFormat === "remote"
            ? {}
            : { remoteWorldwide: false, remoteCountries: [] }),
        });
      },
      async saveCountries(userId: number, input: { worldwide: boolean; countries: string[] }) {
        const current = managerMandatoryByUser.get(userId) ?? {
          workFormat: null,
          remoteCountries: [],
          remoteWorldwide: false,
          budgetMin: null,
          budgetMax: null,
          budgetCurrency: null,
          budgetPeriod: null,
        };
        managerMandatoryByUser.set(userId, {
          ...current,
          remoteWorldwide: input.worldwide,
          remoteCountries: input.countries,
        });
      },
      async saveBudget(
        userId: number,
        input: { min: number; max: number; currency: JobBudgetCurrency; period: JobBudgetPeriod },
      ) {
        const current = managerMandatoryByUser.get(userId) ?? {
          workFormat: null,
          remoteCountries: [],
          remoteWorldwide: false,
          budgetMin: null,
          budgetMax: null,
          budgetCurrency: null,
          budgetPeriod: null,
        };
        managerMandatoryByUser.set(userId, {
          ...current,
          budgetMin: input.min,
          budgetMax: input.max,
          budgetCurrency: input.currency,
          budgetPeriod: input.period,
        });
      },
    } as never,
    {} as never,
    {} as never,
    {} as never,
    {} as never,
    {
      async requestDeletion(input: { telegramUserId: number; reason: string }) {
        dataDeletionCalls.push({ telegramUserId: input.telegramUserId, reason: input.reason });
        return { confirmationMessage: "Deletion request accepted." };
      },
    } as never,
    {
      async setContactShared(userId: number, contactShared: boolean) {
        const current = userFlagsByUser.get(userId) ?? {
          contactShared: false,
          autoMatchingEnabled: true,
          autoNotifyEnabled: true,
          matchingPaused: false,
        };
        userFlagsByUser.set(userId, {
          ...current,
          contactShared,
        });
      },
      async saveContact(input: { telegramUserId: number }) {
        const current = userFlagsByUser.get(input.telegramUserId) ?? {
          contactShared: false,
          autoMatchingEnabled: true,
          autoNotifyEnabled: true,
          matchingPaused: false,
        };
        userFlagsByUser.set(input.telegramUserId, {
          ...current,
          contactShared: true,
        });
      },
      async setMatchingPreferences(input: {
        telegramUserId: number;
        autoMatchingEnabled: boolean;
        autoNotifyEnabled: boolean;
        matchingPaused: boolean;
      }) {
        userFlagsByUser.set(input.telegramUserId, {
          contactShared: userFlagsByUser.get(input.telegramUserId)?.contactShared ?? false,
          autoMatchingEnabled: input.autoMatchingEnabled,
          autoNotifyEnabled: input.autoNotifyEnabled,
          matchingPaused: input.matchingPaused,
        });
      },
      async getUserFlags(userId: number) {
        return (
          userFlagsByUser.get(userId) ?? {
            contactShared: false,
            autoMatchingEnabled: true,
            autoNotifyEnabled: true,
            matchingPaused: false,
          }
        );
      },
      async upsertTelegramUser() {},
      async getCandidateMandatoryFields() {
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
    } as never,
    {
      async saveJobIntakeSource() {},
      async getJobMandatoryFields() {
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
    } as never,
    {
      async saveCandidateResumeIntakeSource() {},
      async getCandidatePrescreenVersion() {
        return "v1";
      },
      async getJobPrescreenVersion() {
        return "v1";
      },
    } as never,
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
            matching_direction: null,
            state_patch: {},
            facts: [],
          },
        };
      },
    } as never,
    {
      async classify(input: {
        currentState: string;
      }) {
        if (input.currentState === "waiting_resume") {
          return {
            route: "RESUME_TEXT",
            conversation_intent: "OTHER",
            meta_type: null,
            control_type: null,
            matching_intent: null,
            reply: "Resume text received. Processing now.",
            should_advance: false,
            should_process_text_as_document: true,
          };
        }
        if (input.currentState === "waiting_job") {
          return {
            route: "JD_TEXT",
            conversation_intent: "OTHER",
            meta_type: null,
            control_type: null,
            matching_intent: null,
            reply: "Job description received. Processing now.",
            should_advance: false,
            should_process_text_as_document: true,
          };
        }
        if (input.currentState === "interviewing_candidate" || input.currentState === "interviewing_manager") {
          return {
            route: "INTERVIEW_ANSWER",
            conversation_intent: "ANSWER",
            meta_type: null,
            control_type: null,
            matching_intent: null,
            reply: "Thanks, processing your answer.",
            should_advance: true,
            should_process_text_as_document: false,
          };
        }
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
          intent: "ANSWER",
          meta_type: null,
          control_type: null,
          reply: "Answer recorded.",
          should_advance: true,
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
    {
      async shouldAskForConfirm() {
        return false;
      },
      async registerAnswer() {
        return { shouldConfirm: false };
      },
    } as never,
    {
      async buildRouterContext() {
        return { knownUserName: null, ragContext: "" };
      },
      async buildInterviewContext() {
        return { knownUserName: null, ragContext: "" };
      },
      invalidate() {},
    } as never,
    {
      async extractFromResume() {
        return null;
      },
    } as never,
    false,
    false,
    {
      async bootstrap() {
        throw new Error("candidate prescreen v2 is disabled in this test harness");
      },
      async submitAnswer() {
        throw new Error("candidate prescreen v2 is disabled in this test harness");
      },
      async skipCurrentQuestion() {
        throw new Error("candidate prescreen v2 is disabled in this test harness");
      },
    } as never,
    {
      async bootstrap() {
        throw new Error("job prescreen v2 is disabled in this test harness");
      },
      async submitAnswer() {
        throw new Error("job prescreen v2 is disabled in this test harness");
      },
      async skipCurrentQuestion() {
        throw new Error("job prescreen v2 is disabled in this test harness");
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
  );

  return {
    router,
    stateService,
    telegram,
    dataDeletionCalls,
  };
}

function createUpdateFactory(userId: number, chatId: number): {
  text: (text: string) => NormalizedUpdate;
  contact: (phoneNumber: string, firstName: string) => NormalizedUpdate;
} {
  let nextUpdateId = 1;
  let nextMessageId = 1;

  return {
    text: (text: string): NormalizedUpdate => ({
      kind: "text",
      updateId: nextUpdateId++,
      messageId: nextMessageId++,
      userId,
      chatId,
      text,
    }),
    contact: (phoneNumber: string, firstName: string): NormalizedUpdate => ({
      kind: "contact",
      updateId: nextUpdateId++,
      messageId: nextMessageId++,
      userId,
      chatId,
      phoneNumber,
      firstName,
      contactUserId: userId,
    }),
  };
}

function countMessagesContaining(telegram: TelegramClientMock, needle: string): number {
  return telegram.sent.filter((item) => item.text.includes(needle)).length;
}

async function testCandidateOnboardingHappyPathCurrentBehavior(): Promise<void> {
  const { router, stateService, telegram } = buildRouterHarness();
  const userId = 92001;
  const chatId = 92001;
  const updates = createUpdateFactory(userId, chatId);

  await router.route(updates.text("/start"));
  await router.route(updates.contact("+380991112233", "Dmytro"));
  await router.route(updates.text("I am a Candidate"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.role, "candidate");

  await router.route(
    updates.text(
      "Senior backend engineer. 7 years Node.js/TypeScript, PostgreSQL, AWS, Docker, mentoring, architecture ownership.",
    ),
  );

  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_candidate");
  assert.equal(
    telegram.sent.some((item) => item.text.includes("Document received. Processing now")),
    true,
  );
  assert.equal(
    telegram.sent.some((item) => item.text.includes("drafted a short summary")),
    true,
  );

  await router.route(updates.text("approve"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "candidate_mandatory_fields");
  assert.equal(session?.candidateMandatoryStep, "location");

  await router.route(updates.text("Kyiv, Ukraine"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "candidate_mandatory_fields");
  assert.equal(session?.candidateMandatoryStep, "work_mode");

  await router.route(updates.text("remote"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "candidate_mandatory_fields");
  assert.equal(session?.candidateMandatoryStep, "salary");

  await router.route(updates.text("5000 USD per month"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "candidate_profile_ready");
  assert.equal(session?.candidateProfileComplete, true);
  assert.equal(session?.candidateCountry, "Ukraine");
  assert.equal(session?.candidateCity, "Kyiv");
  assert.equal(session?.candidateWorkMode, "remote");
  assert.equal(session?.candidateSalaryAmount, 5000);
  assert.equal(session?.candidateSalaryCurrency, "USD");
  assert.equal(session?.candidateSalaryPeriod, "month");
}

async function testManagerVacancyCreationHappyPathCurrentBehavior(): Promise<void> {
  const { router, stateService, telegram } = buildRouterHarness();
  const userId = 92002;
  const chatId = 92002;
  const updates = createUpdateFactory(userId, chatId);

  await router.route(updates.text("/start"));
  await router.route(updates.contact("+380992223344", "Olha"));
  await router.route(updates.text("I am Hiring"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_job");
  assert.equal(session?.role, "manager");

  await router.route(
    updates.text(
      "Need senior Node.js engineer for B2B SaaS platform. Stack: TypeScript, NestJS, PostgreSQL, AWS. Product team, remote-first.",
    ),
  );

  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "interviewing_manager");
  assert.equal(
    telegram.sent.some((item) => item.text.includes("Document received. Processing now")),
    true,
  );
  assert.equal(
    telegram.sent.some((item) => item.text.includes("vacancy summary")),
    true,
  );

  await router.route(updates.text("approve"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "manager_mandatory_fields");
  assert.equal(session?.managerMandatoryStep, "work_format");

  await router.route(updates.text("remote"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "manager_mandatory_fields");
  assert.equal(session?.managerMandatoryStep, "countries");

  await router.route(updates.text("worldwide"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "manager_mandatory_fields");
  assert.equal(session?.managerMandatoryStep, "budget");

  await router.route(updates.text("7000 - 9000 USD per month"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "job_profile_ready");
  assert.equal(session?.jobProfileComplete, true);
  assert.equal(session?.jobWorkFormat, "remote");
  assert.equal(session?.jobRemoteWorldwide, true);
  assert.deepEqual(session?.jobRemoteCountries ?? [], []);
  assert.equal(session?.jobBudgetMin, 7000);
  assert.equal(session?.jobBudgetMax, 9000);
  assert.equal(session?.jobBudgetCurrency, "USD");
  assert.equal(session?.jobBudgetPeriod, "month");
}

async function testCandidateProfileDeletionConfirmationFlow(): Promise<void> {
  const { router, stateService, telegram, dataDeletionCalls } = buildRouterHarness();
  const userId = 92003;
  const chatId = 92003;
  const updates = createUpdateFactory(userId, chatId);

  await router.route(updates.text("/start"));
  await router.route(updates.contact("+380993334455", "Nadia"));
  await router.route(updates.text("I am a Candidate"));

  let session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");

  await router.route(updates.text("Delete all my data"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.pendingDataDeletionConfirmation, true);
  assert.equal(
    countMessagesContaining(telegram, "This action permanently deletes your stored data and resets your session."),
    1,
  );

  const sentBeforeAmbiguousReply = telegram.sent.length;
  await router.route(updates.text("not sure"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.pendingDataDeletionConfirmation, true);
  assert.equal(telegram.sent.length > sentBeforeAmbiguousReply, true);
  assert.equal(dataDeletionCalls.length, 0);

  await router.route(updates.text("cancel"));
  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "waiting_resume");
  assert.equal(session?.pendingDataDeletionConfirmation, false);
  assert.equal(dataDeletionCalls.length, 0);

  await router.route(updates.text("delete my data"));
  await router.route(updates.text("Delete everything"));

  session = stateService.getSession(userId);
  assert(session);
  assert.equal(session?.state, "role_selection");
  assert.equal(session?.awaitingContactChoice, true);
  assert.equal(session?.pendingDataDeletionConfirmation, false);
  assert.equal(dataDeletionCalls.length, 1);
  assert.equal(dataDeletionCalls[0]?.telegramUserId, userId);
  assert.equal(dataDeletionCalls[0]?.reason, "user_text_command");
  assert.equal(session?.contactPhoneNumber, undefined);
  assert.equal(
    telegram.sent.some((item) => item.text.includes("Deletion request accepted.")),
    true,
  );
}

async function run(): Promise<void> {
  await testCandidateOnboardingHappyPathCurrentBehavior();
  await testManagerVacancyCreationHappyPathCurrentBehavior();
  await testCandidateProfileDeletionConfirmationFlow();
  process.stdout.write("Characterization happy-path tests passed.\n");
}

void run();
