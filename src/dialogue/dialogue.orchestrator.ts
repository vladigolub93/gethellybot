/**
 * Conversation state redesign v2 — single entry point for dialogue.
 * handleUserMessage(ctx) -> { replyText, reaction?, buttons?, nextStatePatch }
 * Integrates Stage 8 prompts v3, max 10 questions, repeat loop prevention, intents.
 */

import { Logger } from "../config/logger";
import type { UserSessionState } from "../shared/types/state.types";
import type {
  DialoguePhase,
  PrescreenStateV2,
  PrescreenCurrentQuestionV2,
} from "../shared/types/state.types";
import type { IntentRouterV2Schema } from "./intent-router-v2.service";
import { IntentRouterV2Service } from "./intent-router-v2.service";
import { dialogueRepeatLoopSkipHintMessage } from "../telegram/ui/messages";

export type DialogueLanguage = "en" | "ru" | "uk";

export interface DialogueContext {
  userId: number;
  chatId: number;
  session: UserSessionState;
  userMessage: string;
  language?: DialogueLanguage;
}

/** Stage 10: one match card to send (text + matchId for Apply/Reject or Accept/Reject buttons). */
export interface MatchCardOut {
  text: string;
  matchId: string;
  isCandidateCard: boolean;
}

export interface DialogueResult {
  replyText: string;
  reaction?: string | null;
  buttons?: Array<{ text: string; data: string }>;
  nextStatePatch: Partial<UserSessionState>;
  /** Stage 10: match cards to send (intro line in replyText, then each card with its buttons). */
  matchCards?: MatchCardOut[];
  /** Stage 10: text-based apply/reject — state router will call decisionService + notification. */
  matchAction?: { type: "candidate_apply" | "candidate_reject" | "manager_accept" | "manager_reject"; matchId: string };
  /** For telemetry */
  intent?: string;
  phaseTransition?: { from: string; to: string };
  questionsAskedCount?: number;
  mandatoryMissing?: Record<string, boolean>;
  promptName?: string;
  parseSuccess?: boolean;
}

const MAX_QUESTIONS = 10;
const MATCH_CARDS_MAX = 3;

export class DialogueOrchestratorV2 {
  constructor(
    private readonly intentRouter: IntentRouterV2Service,
    private readonly replyComposer: (input: {
      userRole: "candidate" | "manager";
      userLanguage: DialogueLanguage;
      currentState: string;
      lastUserMessage: string;
      nextQuestionText?: string | null;
      userFrustrated?: boolean;
    }) => Promise<string | null>,
    private readonly logger: Logger,
    private readonly matchingEngine?: import("../matching/matching.engine").MatchingEngine,
    private readonly matchCardComposer?: import("../matching/match-card-composer.service").MatchCardComposerService,
  ) {}

  async handleUserMessage(ctx: DialogueContext): Promise<DialogueResult> {
    const { session, userMessage } = ctx;
    const phase = session.dialoguePhase ?? inferPhaseFromState(session.state);
    const role = session.role ?? "candidate";
    let language = (ctx.language ?? resolveLanguage(session)) as DialogueLanguage;
    // Keep replying in user's preferred language; short replies like "qa" must not switch to English
    if (session.preferredLanguage === "ru" || session.preferredLanguage === "uk") {
      language = session.preferredLanguage;
    }
    const switchToEnglish = wantsEnglishOnly(userMessage);
    if (switchToEnglish) {
      language = "en";
    }

    const intentResult = await this.intentRouter.detect({
      userMessage,
      role,
      phase,
      currentQuestionText: getCurrentQuestionText(session),
    });

    this.logger.info("dialogue.orchestrator_v2.intent", {
      userId: ctx.userId,
      phase,
      intent: intentResult.intent,
      language: intentResult.language,
      confidence: intentResult.confidence,
    });

    if (switchToEnglish) {
      const reply = await this.replyComposer({
        userRole: role,
        userLanguage: "en",
        currentState: "switch_language",
        lastUserMessage: userMessage,
      });
      return {
        replyText: reply ?? "Switching to English.",
        nextStatePatch: { preferredLanguage: "en" as UserSessionState["preferredLanguage"] },
        intent: "switch_language",
      };
    }

    if (intentResult.intent === "restart") {
      return this.handleRestart(ctx, language);
    }

    if (intentResult.intent === "switch_role") {
      return this.handleSwitchRole(ctx, language);
    }

    if (intentResult.intent === "match_apply" || intentResult.intent === "match_reject") {
      return this.handleMatchAction(ctx, language, intentResult.intent);
    }

    if (intentResult.intent === "request_matching") {
      return this.handleRequestMatching(ctx, language, intentResult);
    }

    if (intentResult.intent === "skip" || intentResult.intent === "pause") {
      return this.handleSkipOrPause(ctx, language, intentResult.intent);
    }

    if (intentResult.intent === "clarify_question") {
      return this.handleClarifyQuestion(ctx, language, intentResult);
    }

    if (intentResult.intent === "smalltalk") {
      return this.handleSmalltalk(ctx, language);
    }

    if (phase === "prescreen_active" && intentResult.intent === "answer") {
      return this.handlePrescreenAnswer(ctx, language, intentResult);
    }

    if (phase === "onboarding_contact" || phase === "onboarding_role" || phase === "collecting_document") {
      return this.handleOnboardingOrCollecting(ctx, language, intentResult);
    }

    return this.handleOther(ctx, language, intentResult);
  }

  /**
   * When same outbound would be sent twice (repeat loop), return skip-hint message and stable state.
   */
  buildRepeatLoopReply(language: DialogueLanguage): DialogueResult {
    return {
      replyText: dialogueRepeatLoopSkipHintMessage(language),
      reaction: null,
      buttons: [],
      nextStatePatch: {},
      intent: "repeat_loop_prevented",
    };
  }

  private async handleRestart(ctx: DialogueContext, language: DialogueLanguage): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: "restart",
      lastUserMessage: ctx.userMessage,
      userFrustrated: false,
    });
    return {
      replyText: reply ?? "Restarting. Use /start to begin.",
      nextStatePatch: { state: "role_selection" as UserSessionState["state"], dialoguePhase: "onboarding_role" },
      intent: "restart",
      phaseTransition: { from: ctx.session.dialoguePhase ?? "", to: "onboarding_role" },
    };
  }

  private async handleSwitchRole(ctx: DialogueContext, language: DialogueLanguage): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: "switch_role",
      lastUserMessage: ctx.userMessage,
    });
    return {
      replyText: reply ?? "You can restart with /start and choose the other role.",
      nextStatePatch: { state: "role_selection" as UserSessionState["state"], dialoguePhase: "onboarding_role" },
      intent: "switch_role",
    };
  }

  private async handleRequestMatching(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intentResult: IntentRouterV2Schema,
  ): Promise<DialogueResult> {
    const role = ctx.session.role ?? "candidate";
    const patch: Partial<UserSessionState> = { dialoguePhase: "matching_idle" as const };

    if (!this.matchingEngine || !this.matchCardComposer) {
      const reply = await this.replyComposer({
        userRole: role,
        userLanguage: language,
        currentState: "request_matching",
        lastUserMessage: ctx.userMessage,
      });
      return {
        replyText: reply ?? "I'll look for matches. (Matching service not configured.)",
        nextStatePatch: patch,
        intent: "request_matching",
      };
    }

    if (role === "candidate") {
      const readiness = await this.matchingEngine.checkCandidateMatchingReadiness(ctx.userId);
      if (!readiness.ready) {
        const askOne = this.askOneMissingCandidate(readiness.reasons, language);
        return {
          replyText: askOne,
          nextStatePatch: {},
          intent: "request_matching",
          mandatoryMissing: { location: true, workFormat: true, salary: true },
        };
      }
      const records = await this.matchingEngine.getMatchRecordsForCandidate(ctx.userId, MATCH_CARDS_MAX);
      if (records.length === 0) {
        const reply = await this.replyComposer({
          userRole: "candidate",
          userLanguage: language,
          currentState: "request_matching_no_results",
          lastUserMessage: ctx.userMessage,
        });
        return {
          replyText: reply ?? "No matching roles found right now. Try again later.",
          nextStatePatch: patch,
          intent: "request_matching",
        };
      }
      const matchCards: MatchCardOut[] = [];
      for (const record of records) {
        const composed = await this.matchCardComposer.composeForCandidate(record, language);
        matchCards.push({
          text: composed.text,
          matchId: record.id,
          isCandidateCard: true,
        });
      }
      const ids = matchCards.map((c) => c.matchId);
      patch.matching = {
        lastShownMatchIds: ids,
        lastActionableMatchId: ids[ids.length - 1] ?? null,
      };
      const intro =
        language === "ru"
          ? `Вот ${records.length} подходящих вакансий.`
          : language === "uk"
            ? `Ось ${records.length} підходящих вакансій.`
            : `Here are ${records.length} matching roles.`;
      return {
        replyText: intro,
        nextStatePatch: patch,
        matchCards,
        intent: "request_matching",
      };
    }

    const managerUserId = ctx.userId;
    const jobId = ctx.session.lastActiveJobId ?? undefined;
    const readiness = await this.matchingEngine.checkManagerMatchingReadiness(managerUserId);
    if (!readiness.ready) {
      const askOne = this.askOneMissingManager(readiness.reasons, language);
      return {
        replyText: askOne,
        nextStatePatch: {},
        intent: "request_matching",
        mandatoryMissing: { workFormat: true, allowedCountries: true, budget: true },
      };
    }
    const records = await this.matchingEngine.getMatchRecordsForManager(managerUserId, jobId, MATCH_CARDS_MAX);
    if (records.length === 0) {
      const reply = await this.replyComposer({
        userRole: "manager",
        userLanguage: language,
        currentState: "request_matching_no_results",
        lastUserMessage: ctx.userMessage,
      });
      return {
        replyText: reply ?? "No suitable candidates found yet.",
        nextStatePatch: patch,
        intent: "request_matching",
      };
    }
    const matchCards: MatchCardOut[] = [];
    for (const record of records) {
      const composed = await this.matchCardComposer.composeForManager(record, language);
      matchCards.push({
        text: composed.text,
        matchId: record.id,
        isCandidateCard: false,
      });
    }
    const ids = matchCards.map((c) => c.matchId);
    patch.matching = {
      lastShownMatchIds: ids,
      lastActionableMatchId: ids[ids.length - 1] ?? null,
    };
    const intro =
      language === "ru"
        ? `Вот ${records.length} подходящих кандидатов.`
        : language === "uk"
          ? `Ось ${records.length} підходящих кандидатів.`
          : `Here are ${records.length} matching candidates.`;
    return {
      replyText: intro,
      nextStatePatch: patch,
      matchCards,
      intent: "request_matching",
    };
  }

  private handleMatchAction(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intent: "match_apply" | "match_reject",
  ): Promise<DialogueResult> {
    const matchId = ctx.session.matching?.lastActionableMatchId;
    if (!matchId) {
      return this.handleOther(ctx, language, { intent: "other", language, confidence: 0.5, userQuestion: null });
    }
    const role = ctx.session.role ?? "candidate";
    const type: "candidate_apply" | "candidate_reject" | "manager_accept" | "manager_reject" =
      intent === "match_apply"
        ? role === "candidate"
          ? "candidate_apply"
          : "manager_accept"
        : role === "candidate"
          ? "candidate_reject"
          : "manager_reject";
    let replyText: string;
    if (intent === "match_apply") {
      replyText =
        role === "candidate"
          ? language === "ru"
            ? "Заявка отправлена."
            : language === "uk"
              ? "Заявку надіслано."
              : "Application sent."
          : language === "ru"
            ? "Принято. Спросим контакт у кандидата."
            : language === "uk"
              ? "Прийнято. Запитаємо контакт у кандидата."
              : "Accepted. We'll ask the candidate for contact.";
    } else {
      replyText =
        language === "ru" ? "Пропущено." : language === "uk" ? "Пропущено." : "Skipped.";
    }
    return Promise.resolve({
      replyText,
      nextStatePatch: {},
      matchAction: { type, matchId },
      intent: intent,
    });
  }

  private askOneMissingCandidate(reasons: string[], language: DialogueLanguage): string {
    if (reasons.includes("candidate_mandatory_incomplete") || reasons.includes("candidate_profile_text_missing")) {
      return language === "ru"
        ? "Чтобы подобрать вакансии, укажите, пожалуйста: локацию, формат работы или зарплатные ожидания."
        : language === "uk"
          ? "Щоб підібрати вакансії, вкажіть, будь ласка: локацію, формат роботи або зарплатні очікування."
          : "To find matching roles, please share your location, work format, or salary expectations.";
    }
    return language === "ru"
      ? "Завершите профиль (резюме и несколько ответов), после этого смогу подобрать вакансии."
      : language === "uk"
        ? "Завершіть профіль (резюме та кілька відповідей), після цього зможу підібрати вакансії."
        : "Complete your profile (resume and a few answers), then I can find matching roles.";
  }

  private askOneMissingManager(reasons: string[], language: DialogueLanguage): string {
    if (reasons.includes("job_profile_missing") || reasons.includes("job_mandatory_incomplete")) {
      return language === "ru"
        ? "Чтобы подобрать кандидатов, укажите формат работы, допустимые страны и бюджет."
        : language === "uk"
          ? "Щоб підібрати кандидатів, вкажіть формат роботи, допустимі країни та бюджет."
          : "To find candidates, please share work format, allowed countries, and budget.";
    }
    return language === "ru"
      ? "Завершите описание вакансии, после этого смогу подобрать кандидатов."
      : language === "uk"
        ? "Завершіть опис вакансії, після цього зможу підібрати кандидатів."
        : "Complete your job profile, then I can find matching candidates.";
  }

  private async handleSkipOrPause(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intent: "skip" | "pause",
  ): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: intent,
      lastUserMessage: ctx.userMessage,
      userFrustrated: true,
    });
    const phase = ctx.session.dialoguePhase;
    const prescreen = ctx.session.prescreenV2;
    const patch: Partial<UserSessionState> = {};

    if (intent === "pause" && phase === "prescreen_active") {
      patch.dialoguePhase = "prescreen_paused";
    }

    if (intent === "skip" && phase === "prescreen_active" && prescreen?.currentQuestion) {
      const askedIds = [...(prescreen.askedQuestionIds ?? []), prescreen.currentQuestion.id];
      const totalAsked = (prescreen.totalQuestionsAsked ?? 0) + 1;
      const nextQuestion =
        totalAsked >= (prescreen.maxQuestions ?? MAX_QUESTIONS)
          ? null
          : prescreen.currentQuestion;
      patch.prescreenV2 = {
        ...prescreen,
        totalQuestionsAsked: totalAsked,
        askedQuestionIds: askedIds,
        currentQuestion: nextQuestion,
        followUpUsedForQuestionIds: prescreen.followUpUsedForQuestionIds ?? [],
        lastMicroConfirmationAt: prescreen.lastMicroConfirmationAt ?? null,
        mandatory: prescreen.mandatory ?? {},
        lastIntent: "skip",
      };
      if (totalAsked >= (prescreen.maxQuestions ?? MAX_QUESTIONS)) {
        patch.dialoguePhase = "profile_ready";
      }
    }

    return {
      replyText: reply ?? (intent === "skip" ? "Skipped. Moving on." : "Paused. Say when to continue."),
      nextStatePatch: patch,
      intent,
    };
  }

  private async handleClarifyQuestion(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intentResult: IntentRouterV2Schema,
  ): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: "clarify_question",
      lastUserMessage: intentResult.userQuestion ?? ctx.userMessage,
      nextQuestionText: getCurrentQuestionText(ctx.session),
    });
    const patch: Partial<UserSessionState> = {};
    if (ctx.session.prescreenV2) {
      patch.prescreenV2 = { ...ctx.session.prescreenV2, lastIntent: intentResult.intent };
    }
    return {
      replyText: reply ?? "I'll keep that in mind. Here's the next question.",
      nextStatePatch: patch,
      intent: "clarify_question",
    };
  }

  private async handleSmalltalk(ctx: DialogueContext, language: DialogueLanguage): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: "smalltalk",
      lastUserMessage: ctx.userMessage,
    });
    return {
      replyText: reply ?? "Hi! Let's continue with your profile when you're ready.",
      nextStatePatch: {},
      intent: "smalltalk",
    };
  }

  private async handlePrescreenAnswer(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intentResult: IntentRouterV2Schema,
  ): Promise<DialogueResult> {
    const prescreen = ctx.session.prescreenV2;
    if (!prescreen?.currentQuestion) {
      return this.handleOther(ctx, language, intentResult);
    }

    const totalAsked = (prescreen.totalQuestionsAsked ?? 0) + 1;
    const askedIds = [...(prescreen.askedQuestionIds ?? []), prescreen.currentQuestion.id];
    const atCap = totalAsked >= (prescreen.maxQuestions ?? MAX_QUESTIONS);

    const patch: Partial<UserSessionState> = {
      prescreenV2: {
        ...prescreen,
        totalQuestionsAsked: totalAsked,
        askedQuestionIds: askedIds,
        currentQuestion: atCap ? null : prescreen.currentQuestion,
        lastMicroConfirmationAt: new Date().toISOString(),
        lastIntent: "answer",
      },
    };
    if (atCap) {
      patch.dialoguePhase = "profile_ready";
    }

    const microConfirm =
      language === "ru"
        ? "Понял, записал."
        : language === "uk"
          ? "Зрозуміло, записав."
          : "Got it, I noted that.";
    const nextQ = atCap ? null : getCurrentQuestionText(ctx.session);
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: "prescreen_answer",
      lastUserMessage: ctx.userMessage,
      nextQuestionText: nextQ,
    });

    const replyText = reply
      ? `${microConfirm} ${reply}`
      : atCap
        ? language === "ru"
          ? `${microConfirm} Профиль готов. Можете попросить подобрать вакансии в любой момент.`
          : language === "uk"
            ? `${microConfirm} Профіль готовий. Можете попросити підібрати вакансії в будь-який момент.`
            : `${microConfirm} Profile ready. You can ask me to find jobs anytime.`
        : language === "ru"
          ? `${microConfirm} Следующий вопрос.`
          : language === "uk"
            ? `${microConfirm} Наступне питання.`
            : `${microConfirm} Next question.`;

    return {
      replyText,
      nextStatePatch: patch,
      intent: "answer",
      questionsAskedCount: totalAsked,
      mandatoryMissing: prescreen.mandatory as Record<string, boolean> | undefined,
      phaseTransition: atCap ? { from: "prescreen_active", to: "profile_ready" } : undefined,
    };
  }

  private async handleOnboardingOrCollecting(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intentResult: IntentRouterV2Schema,
  ): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: ctx.session.dialoguePhase ?? ctx.session.state,
      lastUserMessage: ctx.userMessage,
    });
    const patch: Partial<UserSessionState> = {};
    if (ctx.session.prescreenV2) {
      patch.prescreenV2 = { ...ctx.session.prescreenV2, lastIntent: intentResult.intent };
    }
    return {
      replyText: reply ?? "Please continue with the current step.",
      nextStatePatch: patch,
      intent: intentResult.intent,
    };
  }

  private async handleOther(
    ctx: DialogueContext,
    language: DialogueLanguage,
    intentResult: IntentRouterV2Schema,
  ): Promise<DialogueResult> {
    const reply = await this.replyComposer({
      userRole: ctx.session.role ?? "candidate",
      userLanguage: language,
      currentState: ctx.session.dialoguePhase ?? ctx.session.state,
      lastUserMessage: ctx.userMessage,
    });
    const patch: Partial<UserSessionState> = {};
    if (ctx.session.prescreenV2) {
      patch.prescreenV2 = { ...ctx.session.prescreenV2, lastIntent: intentResult.intent };
    }
    return {
      replyText: reply ?? "I didn't get that. You can say 'skip' to move on or ask a short question.",
      nextStatePatch: patch,
      intent: intentResult.intent,
    };
  }
}

function inferPhaseFromState(state: string): DialoguePhase {
  if (state === "role_selection") return "onboarding_role";
  if (state === "waiting_resume" || state === "waiting_job" || state === "extracting_resume" || state === "extracting_job") {
    return "collecting_document";
  }
  if (state === "interviewing_candidate" || state === "interviewing_manager") return "prescreen_active";
  if (state === "candidate_profile_ready" || state === "job_profile_ready") return "profile_ready";
  if (state === "job_published" || state === "candidate_mandatory_fields" || state === "manager_mandatory_fields") {
    return "profile_ready";
  }
  return "onboarding_contact";
}

function getCurrentQuestionText(session: UserSessionState): string | null {
  const q = session.prescreenV2?.currentQuestion;
  if (q && typeof (q as PrescreenCurrentQuestionV2).text === "string") {
    return (q as PrescreenCurrentQuestionV2).text;
  }
  return null;
}

function resolveLanguage(session: UserSessionState): DialogueLanguage {
  const p = session.preferredLanguage;
  if (p === "en" || p === "ru" || p === "uk") return p;
  return "en";
}

function wantsEnglishOnly(message: string): boolean {
  const t = message.trim().toLowerCase();
  if (/english\s+please|switch\s+to\s+english|in\s+english/i.test(t)) return true;
  if (/i\s+don'?t\s+understand\s+(russian|ukrainian)|не\s+понимаю\s+по-русски|не\s+розумію\s+українськ/i.test(t)) return true;
  return false;
}
