import { logContext, Logger } from "../config/logger";
import { ContactExchangeService } from "../decisions/contact-exchange.service";
import { DecisionService } from "../decisions/decision.service";
import { LlmClient } from "../ai/llm.client";
import { UsersRepository } from "../db/repositories/users.repo";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { ProfilesRepository } from "../db/repositories/profiles.repo";
import { HiringScopeGuardrailsService } from "../guardrails/hiring-scope-guardrails.service";
import { NormalizationService, detectLanguageQuick, toPreferredLanguage } from "../i18n/normalization.service";
import { DataDeletionService } from "../privacy/data-deletion.service";
import { TranscriptionClient } from "../ai/transcription.client";
import { DocumentService } from "../documents/document.service";
import { TelegramFileService } from "../documents/storage/telegram-file.service";
import {
  evaluateInterviewBootstrap,
  isDocumentUploadAllowedState,
  isInterviewingState,
} from "../interviews/interview-bootstrap.guard";
import { InterviewEngine } from "../interviews/interview.engine";
import { InterviewIntentRouterService } from "../interviews/interview-intent-router.service";
import { JobMandatoryFieldsService } from "../jobs/job-mandatory-fields.service";
import { parseBudget } from "../jobs/parsers/budget.parser";
import { parseCountries } from "../jobs/parsers/countries.parser";
import { MatchingEngine } from "../matching/matching.engine";
import { NotificationEngine } from "../notifications/notification.engine";
import { CandidateMandatoryFieldsService } from "../profiles/candidate-mandatory-fields.service";
import { parseCountryCity } from "../profiles/parsers/location.parser";
import { parseSalary } from "../profiles/parsers/salary.parser";
import { ProfileSummaryService } from "../profiles/profile-summary.service";
import {
  CandidateMandatoryStep,
  CandidateSalaryCurrency,
  CandidateSalaryPeriod,
  CandidateWorkMode,
  JobBudgetCurrency,
  JobBudgetPeriod,
  JobWorkFormat,
  ManagerMandatoryStep,
  UserSessionState,
} from "../shared/types/state.types";
import {
  CALLBACK_MANAGER_WORK_FORMAT_HYBRID,
  CALLBACK_MANAGER_WORK_FORMAT_ONSITE,
  CALLBACK_MANAGER_WORK_FORMAT_REMOTE,
} from "../shared/constants";
import { NormalizedUpdate } from "../shared/types/telegram.types";
import { AlwaysOnRouterDecision } from "../shared/types/always-on-router.types";
import { MatchStorageService } from "../storage/match-storage.service";
import { StateService } from "../state/state.service";
import { StatePersistenceService } from "../state/state-persistence.service";
import { TelegramClient } from "../telegram/telegram.client";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { getShortEmpathyLine } from "../shared/utils/empathy.util";
import { checkAndConsumeUserRateLimit } from "../shared/utils/rate-limit";
import {
  buildCandidateDecisionKeyboard,
  buildCandidateMatchingActionsKeyboard,
  buildContactRequestKeyboard,
  buildCandidateMandatoryLocationKeyboard,
  buildCandidateWorkModeKeyboard,
  buildManagerDecisionKeyboard,
  buildManagerMatchingActionsKeyboard,
  buildManagerWorkFormatKeyboard,
  buildRemoveReplyKeyboard,
  buildRoleSelectionKeyboard,
} from "../telegram/ui/keyboards";
import {
  candidateMatchingActionsReadyMessage,
  candidateMandatoryCompletedMessage,
  candidateMandatoryIntroMessage,
  candidateMandatoryLocationPinReceivedMessage,
  candidateMandatoryLocationQuestionMessage,
  candidateMandatoryLocationRetryMessage,
  candidateMandatorySalaryCurrencyConfirmMessage,
  candidateMandatorySalaryQuestionMessage,
  candidateMandatorySalaryRetryMessage,
  candidateMandatoryWorkModeQuestionMessage,
  candidateMandatoryWorkModeRetryMessage,
  candidateMatchingBlockedByMandatoryMessage,
  candidateOpportunityMessage,
  candidateInterviewPreparationMessage,
  contactRequestMessage,
  contactSavedMessage,
  contactSkippedMessage,
  documentUploadNotAllowedMessage,
  interviewAlreadyStartedMessage,
  interviewLanguageSupportMessage,
  managerMandatoryBudgetCurrencyConfirmMessage,
  managerMandatoryBudgetCurrencyRetryMessage,
  managerMandatoryBudgetPeriodRetryMessage,
  managerMandatoryBudgetQuestionMessage,
  managerMandatoryBudgetRetryMessage,
  managerMandatoryCompletedMessage,
  managerMandatoryCountriesQuestionMessage,
  managerMandatoryCountriesRetryMessage,
  managerMandatoryIntroMessage,
  managerMandatoryWorkFormatQuestionMessage,
  managerMatchingActionsReadyMessage,
  managerMatchingBlockedByMandatoryMessage,
  managerCandidateSuggestionMessage,
  managerInterviewPreparationMessage,
  ownContactRequiredMessage,
  missingInterviewContextMessage,
  processingDocumentMessage,
  questionMessage,
  welcomeMessage,
  textOnlyReplyMessage,
  transcriptionFailedMessage,
  transcribingVoiceMessage,
  voiceTooLongMessage,
} from "../telegram/ui/messages";
import { maybeReact } from "../telegram/reactions/reaction.service";
import { InterviewConfirmationService } from "../confirmations/interview-confirmation.service";
import { AlwaysOnRouterService } from "./always-on-router.service";
import { CallbackRouter } from "./callback.router";
import { MessageRouter } from "./message.router";

export class StateRouter {
  private readonly messageRouter: MessageRouter;
  private readonly callbackRouter: CallbackRouter;

  constructor(
    private readonly stateService: StateService,
    private readonly statePersistenceService: StatePersistenceService,
    private readonly telegramClient: TelegramClient,
    private readonly telegramFileService: TelegramFileService,
    private readonly documentService: DocumentService,
    private readonly transcriptionClient: TranscriptionClient,
    private readonly voiceMaxDurationSec: number,
    private readonly telegramReactionsEnabled: boolean,
    private readonly telegramReactionsProbability: number,
    private readonly interviewEngine: InterviewEngine,
    private readonly matchingEngine: MatchingEngine,
    private readonly matchStorageService: MatchStorageService,
    private readonly notificationEngine: NotificationEngine,
    private readonly candidateMandatoryFieldsService: CandidateMandatoryFieldsService,
    private readonly jobMandatoryFieldsService: JobMandatoryFieldsService,
    private readonly decisionService: DecisionService,
    private readonly contactExchangeService: ContactExchangeService,
    private readonly profileSummaryService: ProfileSummaryService,
    private readonly guardrailsService: HiringScopeGuardrailsService,
    private readonly dataDeletionService: DataDeletionService,
    private readonly usersRepository: UsersRepository,
    private readonly jobsRepository: JobsRepository,
    private readonly profilesRepository: ProfilesRepository,
    private readonly llmClient: LlmClient,
    private readonly alwaysOnRouterService: AlwaysOnRouterService,
    private readonly interviewIntentRouterService: InterviewIntentRouterService,
    private readonly normalizationService: NormalizationService,
    private readonly interviewConfirmationService: InterviewConfirmationService,
    private readonly logger: Logger,
  ) {
    this.messageRouter = new MessageRouter(
      this.stateService,
      this.telegramClient,
      this.profileSummaryService,
      this.guardrailsService,
      this.dataDeletionService,
      this.llmClient,
      this.logger,
    );
    this.callbackRouter = new CallbackRouter(
      this.stateService,
      this.statePersistenceService,
      this.telegramClient,
      this.decisionService,
      this.notificationEngine,
      this.contactExchangeService,
    );
  }

  async route(update: NormalizedUpdate): Promise<void> {
    let session = this.stateService.getSession(update.userId);
    if (!session) {
      const restored = await this.statePersistenceService.hydrateSession(
        update.userId,
        update.chatId,
        update.username,
      );
      if (restored) {
        this.stateService.setSession(restored);
      }
      session = this.stateService.getOrCreate(update.userId, update.chatId, update.username);
    } else if (update.username && session.username !== update.username) {
      session.username = update.username;
    }

    session = await this.ensureInterviewContext(session, update);

    const rateLimitDecision = checkAndConsumeUserRateLimit(session.userId);
    if (!rateLimitDecision.allowed) {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "Too many messages at once. Please wait a few seconds and try again.",
      );
      this.logger.warn("User update rate limit triggered", {
        updateId: update.updateId,
        telegramUserId: session.userId,
        retryAfterSeconds: rateLimitDecision.retryAfterSeconds,
      });
      return;
    }

    if (this.stateService.isDuplicateUpdate(session.userId, update.updateId)) {
      this.logger.debug("Duplicate update ignored", {
        userId: session.userId,
        updateId: update.updateId,
      });
      return;
    }

    logContext(
      this.logger,
      "info",
      "update.received",
      {
        update_id: update.updateId,
        telegram_user_id: session.userId,
        role: session.role ?? "unknown",
        current_state: session.state,
      },
      {
        kind: update.kind,
      },
    );

    const routed = await this.classifyAlwaysOnForUpdate(update, session);
    if (!routed) {
      this.stateService.markUpdateProcessed(session.userId, update.updateId);
      const latestAfterFailure = this.stateService.getSession(session.userId);
      if (latestAfterFailure) {
        await this.statePersistenceService.persistSession(latestAfterFailure);
      }
      return;
    }

    this.logger.debug("dispatch route: X", {
      updateId: update.updateId,
      telegramUserId: session.userId,
      currentState: session.state,
      route: routed.decision.route,
    });

    switch (update.kind) {
      case "text":
        await this.dispatchTextRoute(
          update,
          session,
          routed.decision,
          routed.textEnglish ?? update.text,
          routed.detectedLanguage ?? detectLanguageQuick(update.text),
        );
        break;
      case "document":
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          routed.decision.reply,
        );
        await this.handleDocumentUpdate(update);
        break;
      case "voice":
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          routed.decision.reply,
        );
        await this.handleVoiceUpdate(update, session);
        break;
      case "callback":
        if (session.state === "manager_mandatory_fields" && isManagerWorkFormatCallback(update.data)) {
          await this.handleManagerWorkFormatCallback(update, session);
        } else {
          await this.callbackRouter.route(update, session);
        }
        break;
      case "contact":
        await this.handleContactUpdate(update, session);
        break;
      case "location":
        await this.handleLocationUpdate(update, session);
        break;
      case "unsupported_message":
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          routed.decision.reply || textOnlyReplyMessage(),
        );
        break;
      default:
        this.logger.warn("Unhandled update type");
    }

    logContext(
      this.logger,
      "info",
      "update.dispatched",
      {
        update_id: update.updateId,
        telegram_user_id: session.userId,
        role: session.role ?? "unknown",
        current_state: session.state,
        route: routed.decision.route,
        action: mapRouteToActionLabel(routed.decision.route),
        ok: true,
      },
    );

    this.stateService.markUpdateProcessed(session.userId, update.updateId);
    const latestSession = this.stateService.getSession(session.userId);
    if (latestSession) {
      await this.statePersistenceService.persistSession(latestSession);
    }
  }

  private async ensureInterviewContext(
    session: UserSessionState,
    update: NormalizedUpdate,
  ): Promise<UserSessionState> {
    if (!isInterviewingState(session.state)) {
      return session;
    }

    if (session.interviewPlan) {
      if (!resolveCurrentInterviewQuestionText(session)) {
        const recoveredIndex = resolveMissingQuestionIndexFromPlan(session);
        if (recoveredIndex !== null) {
          this.stateService.setCurrentQuestionIndex(session.userId, recoveredIndex);
          this.logger.info("Recovered missing current question index", {
            updateId: update.updateId,
            telegramUserId: session.userId,
            recoveredQuestionIndex: recoveredIndex,
          });
        }
      }
      return this.stateService.getSession(session.userId) ?? session;
    }

    const restored = await this.statePersistenceService.hydrateSession(
      session.userId,
      session.chatId,
      session.username,
    );
    if (restored?.interviewPlan) {
      if (!resolveCurrentInterviewQuestionText(restored)) {
        const recoveredIndex = resolveMissingQuestionIndexFromPlan(restored);
        if (recoveredIndex !== null) {
          restored.currentQuestionIndex = recoveredIndex;
        }
      }
      this.stateService.setSession(restored);
      this.logger.info("Interview context recovered from persistence", {
        updateId: update.updateId,
        telegramUserId: session.userId,
        state: restored.state,
      });
      return restored;
    }

    await this.sendBotMessage(
      session.userId,
      update.chatId,
      "I could not restore your interview context. Please use /start and upload your file or text again.",
    );
    return session;
  }

  private async classifyAlwaysOnForUpdate(
    update: NormalizedUpdate,
    session: UserSessionState,
    overrideEnglishText?: string | null,
  ): Promise<{
    decision: AlwaysOnRouterDecision;
    textEnglish: string | null;
    detectedLanguage?: "en" | "ru" | "uk" | "other";
  } | null> {
    let textEnglish: string | null = null;
    let detectedLanguage: "en" | "ru" | "uk" | "other" | undefined;

    if (update.kind === "text") {
      detectedLanguage = detectLanguageQuick(update.text);
      this.stateService.recordPreferredLanguageSample(
        session.userId,
        toPreferredLanguage(detectedLanguage),
      );
      textEnglish = typeof overrideEnglishText === "string"
        ? overrideEnglishText
        : await this.normalizeGeneralText(update.text);
    } else if (update.kind === "callback") {
      textEnglish = update.data;
    } else if (typeof overrideEnglishText === "string") {
      textEnglish = overrideEnglishText;
    }

    const currentQuestion = resolveCurrentInterviewQuestionText(session);

    try {
      const decision = await this.alwaysOnRouterService.classify({
        updateId: update.updateId,
        telegramUserId: update.userId,
        currentState: session.state,
        userRole: session.role,
        hasText: Boolean(textEnglish && textEnglish.trim()),
        textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
        hasDocument: update.kind === "document",
        hasVoice: update.kind === "voice",
        currentQuestion,
        lastBotMessage: session.lastBotMessage ?? null,
      });
      return {
        decision,
        textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
        detectedLanguage,
      };
    } catch (error) {
      this.logger.warn("always-on router failed, sending safe fallback", {
        updateId: update.updateId,
        telegramUserId: update.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      const deterministicFallback = this.buildDeterministicRouteFallback(update);
      if (deterministicFallback) {
        return {
          decision: deterministicFallback,
          textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
          detectedLanguage,
        };
      }
      await this.sendRouterReplyWithLoopGuard(
        session,
        update.chatId,
        "I had trouble understanding that message. Please try again, or send the document text or file.",
      );
      return null;
    }
  }

  private async handleSkipContact(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    this.stateService.clearContactInfo(session.userId);
    await this.usersRepository.setContactShared(session.userId, false);
    await this.sendBotMessage(session.userId, update.chatId, contactSkippedMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
    if (session.state === "role_selection") {
      await this.sendBotMessage(session.userId, update.chatId, "Choose your role to begin.", {
        replyMarkup: buildRoleSelectionKeyboard(),
      });
    }
  }

  private async dispatchTextRoute(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
    decision: AlwaysOnRouterDecision,
    normalizedEnglishText: string,
    detectedLanguage: "en" | "ru" | "uk" | "other",
  ): Promise<void> {
    const rawText = update.text.trim();
    const normalizedLower = normalizedEnglishText.trim().toLowerCase();
    const mandatoryUpdateCommand = detectCandidateMandatoryUpdateCommand(normalizedLower);
    const managerMandatoryUpdateCommand = detectManagerMandatoryUpdateCommand(normalizedLower);

    if (isStartCommand(rawText) || decision.control_type === "restart") {
      await this.restartFlow(update);
      return;
    }

    if (isSkipContactForNow(rawText)) {
      await this.handleSkipContact(update, session);
      return;
    }

    if (isDataDeletionCommand(rawText, normalizedEnglishText)) {
      const result = await this.dataDeletionService.requestDeletion({
        telegramUserId: session.userId,
        telegramUsername: session.username,
        reason: "user_text_command",
      });
      this.stateService.clearContactInfo(session.userId);
      await this.sendBotMessage(session.userId, update.chatId, result.confirmationMessage, {
        replyMarkup: buildRemoveReplyKeyboard(),
      });
      return;
    }

    if (
      session.role === "candidate" &&
      mandatoryUpdateCommand &&
      session.state !== "interviewing_candidate" &&
      session.state !== "interviewing_manager"
    ) {
      await this.startCandidateMandatoryFieldsFlow(session, update.chatId, {
        forcedStep: mandatoryUpdateCommand,
        showIntro: false,
      });
      return;
    }

    if (
      session.role === "manager" &&
      managerMandatoryUpdateCommand &&
      session.state !== "interviewing_candidate" &&
      session.state !== "interviewing_manager"
    ) {
      await this.startManagerMandatoryFieldsFlow(session, update.chatId, {
        forcedStep: managerMandatoryUpdateCommand,
        showIntro: false,
      });
      return;
    }

    if (session.state === "candidate_mandatory_fields") {
      await this.handleCandidateMandatoryTextInput(session, update.chatId, rawText, normalizedEnglishText);
      return;
    }

    if (session.state === "manager_mandatory_fields") {
      await this.handleManagerMandatoryTextInput(session, update.chatId, normalizedEnglishText);
      return;
    }

    if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
      if (isInterviewSkipCommand(normalizedEnglishText)) {
        const skipResult = await this.interviewEngine.skipCurrentQuestion(session);
        this.stateService.resetInterviewNoAnswerCounter(session.userId);
        if (skipResult.kind === "next_question") {
          await this.sendBotMessage(
            session.userId,
            session.chatId,
            questionMessage(skipResult.questionIndex, skipResult.questionText),
          );
          return;
        }

        this.stateService.transition(session.userId, skipResult.completedState);
        await this.sendBotMessage(session.userId, session.chatId, skipResult.completionMessage);
        if (skipResult.followupMessage) {
          await this.sendBotMessage(session.userId, session.chatId, skipResult.followupMessage);
        }
        if (skipResult.completedState === "candidate_profile_ready") {
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          await this.startCandidateMandatoryFieldsFlow(latestSession, session.chatId, {
            showIntro: true,
          });
        }
        if (skipResult.completedState === "job_profile_ready") {
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          await this.startManagerMandatoryFieldsFlow(latestSession, session.chatId, {
            showIntro: true,
            runMatchingAfterComplete: true,
          });
        }
        return;
      }

      const currentQuestion = resolveCurrentInterviewQuestionText(session);
      if (!currentQuestion) {
        await this.sendBotMessage(session.userId, update.chatId, missingInterviewContextMessage());
        return;
      }

      const intentDecision = await this.interviewIntentRouterService.classify({
        currentState: session.state,
        userRole: session.state === "interviewing_candidate" ? "candidate" : "manager",
        currentQuestion,
        userMessageEnglish: normalizedEnglishText,
        lastBotMessage: session.lastBotMessage ?? null,
      });

      if (intentDecision.intent === "ANSWER" && intentDecision.should_advance) {
        this.stateService.resetInterviewNoAnswerCounter(session.userId);
        await this.handleInterviewAnswer(
          {
            answerText: normalizedEnglishText,
            originalText: rawText,
            detectedLanguage,
            inputType: "text",
          },
          session,
          update.messageId,
        );
        return;
      }

      const noAnswerQuestionIndex = resolveCurrentQuestionIndexValue(session);
      if (noAnswerQuestionIndex !== null) {
        const counterSession = this.stateService.incrementInterviewNoAnswerCounter(
          session.userId,
          noAnswerQuestionIndex,
        );
        if ((counterSession.interviewMessageWithoutAnswerCount ?? 0) >= 5) {
          await this.sendBotMessage(
            session.userId,
            update.chatId,
            "You can answer by voice, or type skip to move on.",
          );
          this.stateService.resetInterviewNoAnswerCounter(session.userId);
          return;
        }
      }

      if (intentDecision.intent === "CONTROL") {
        if (intentDecision.control_type === "restart") {
          await this.restartFlow(update);
          return;
        }
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          localizeInterviewMetaReply(intentDecision.reply, intentDecision.meta_type, detectedLanguage),
        );
        return;
      }

      await this.sendRouterReplyWithLoopGuard(
        session,
        update.chatId,
        localizeInterviewMetaReply(intentDecision.reply, intentDecision.meta_type, detectedLanguage),
      );
      return;
    }

    if (session.state === "waiting_job") {
      if (isJdIntakeMetaFormatQuestion(rawText, normalizedEnglishText)) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Yes. You can paste the job description text here, or send or forward a PDF or DOCX file. Both work.",
        );
        return;
      }

      const jdHeuristic = detectLikelyJobDescriptionText(normalizedEnglishText);
      const looksLikeExplicitJd =
        normalizedLower.includes("this is the job description") ||
        normalizedLower.includes("job description below");

      if (jdHeuristic.isLikely || looksLikeExplicitJd) {
        this.stateService.clearWaitingShortTextCounter(session.userId);
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Got it. I will process this job description now.",
        );
        await this.handlePastedDocumentText(update, {
          sourceTextOriginal: rawText,
          sourceTextEnglish: normalizedEnglishText,
        });
        return;
      }

      if (isClearlyTooShortForJd(normalizedEnglishText)) {
        const counterSession = this.stateService.incrementWaitingShortTextCounter(
          session.userId,
          "waiting_job",
        );
        if ((counterSession.waitingShortTextCount ?? 0) >= 3) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "Please send the full job description. Example: role overview, responsibilities, requirements, tech stack, and domain context.",
          );
          return;
        }
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Please paste the full job description text, or send a PDF or DOCX file.",
        );
        return;
      }
    }

    if (session.state === "waiting_resume") {
      if (isResumeIntakeMetaFormatQuestion(rawText, normalizedEnglishText)) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Yes. You can paste your resume text here, or send or forward a PDF or DOCX file. Both work.",
        );
        return;
      }

      if (isResumeIntakeLanguageQuestion(rawText, normalizedEnglishText)) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Yes. You can answer interview questions by voice in Russian or Ukrainian. I will transcribe and understand.",
        );
        return;
      }

      const resumeHeuristic = detectLikelyResumeText(normalizedEnglishText);
      const looksLikeExplicitResume =
        normalizedLower.includes("this is my resume") ||
        normalizedLower.includes("resume below");

      if (resumeHeuristic.isLikely || looksLikeExplicitResume) {
        this.stateService.clearWaitingShortTextCounter(session.userId);
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Got it. I will process your resume now.",
        );
        await this.handlePastedDocumentText(update, {
          sourceTextOriginal: rawText,
          sourceTextEnglish: normalizedEnglishText,
        });
        return;
      }

      if (isClearlyTooShortForResume(normalizedEnglishText)) {
        const counterSession = this.stateService.incrementWaitingShortTextCounter(
          session.userId,
          "waiting_resume",
        );
        if ((counterSession.waitingShortTextCount ?? 0) >= 3) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "Please send the full resume text. Example: experience, skills, projects, education, and links.",
          );
          return;
        }
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          "Please paste the full resume text, or send a PDF or DOCX file.",
        );
        return;
      }
    }

    if (decision.route === "MATCHING_COMMAND") {
      await this.handleMatchingIntentRoute({
        session,
        chatId: update.chatId,
        matchingIntent: decision.matching_intent,
        reply: decision.reply,
      });
      return;
    }

    if (decision.route === "CONTROL") {
      await this.handleControlRoute({
        update,
        session,
        decision,
      });
      return;
    }

    if (decision.route === "JD_TEXT" || decision.route === "RESUME_TEXT") {
      if (decision.should_process_text_as_document) {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
        await this.handlePastedDocumentText(update, {
          sourceTextOriginal: rawText,
          sourceTextEnglish: normalizedEnglishText,
        });
      } else {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      }
      return;
    }

    if (decision.route === "INTERVIEW_ANSWER") {
      await this.handleInterviewAnswer(
        {
          answerText: normalizedEnglishText,
          originalText: rawText,
          detectedLanguage,
          inputType: "text",
        },
        session,
        update.messageId,
      );
      return;
    }

    if (decision.route === "OFFTOPIC" || decision.route === "META" || decision.route === "OTHER") {
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      return;
    }

    await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
  }

  private async handleControlRoute(input: {
    update: Extract<NormalizedUpdate, { kind: "text" }>;
    session: UserSessionState;
    decision: AlwaysOnRouterDecision;
  }): Promise<void> {
    const { update, session, decision } = input;

    if (decision.control_type === "help") {
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      return;
    }

    if (decision.control_type === "pause") {
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      return;
    }

    if (decision.control_type === "resume") {
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      return;
    }

    if (decision.control_type === "stop") {
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
      return;
    }

    await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
  }

  private async handleMatchingIntentRoute(input: {
    session: UserSessionState;
    chatId: number;
    matchingIntent: AlwaysOnRouterDecision["matching_intent"];
    reply: string;
  }): Promise<void> {
    const { session, chatId, matchingIntent, reply } = input;
    const interviewActive = session.state === "interviewing_candidate" || session.state === "interviewing_manager";

    if (matchingIntent !== "pause" && matchingIntent !== "help" && interviewActive) {
      await this.sendRouterReplyWithLoopGuard(
        session,
        chatId,
        "We are in the interview step. If you want, you can type pause matching. Otherwise please answer the question above.",
      );
      return;
    }

    if (matchingIntent === "help") {
      await this.sendRouterReplyWithLoopGuard(session, chatId, matchingHelpMessage());
      return;
    }

    if (matchingIntent === "pause") {
      await this.usersRepository.setMatchingPreferences({
        telegramUserId: session.userId,
        autoMatchingEnabled: false,
        autoNotifyEnabled: false,
        matchingPaused: true,
      });
      await this.sendRouterReplyWithLoopGuard(
        session,
        chatId,
        "Matching is paused. Type resume matching if you want me to search again.",
      );
      return;
    }

    if (matchingIntent === "resume") {
      await this.usersRepository.setMatchingPreferences({
        telegramUserId: session.userId,
        autoMatchingEnabled: true,
        autoNotifyEnabled: true,
        matchingPaused: false,
      });
      await this.sendRouterReplyWithLoopGuard(
        session,
        chatId,
        "Matching is resumed. I can search again when you ask.",
      );
      return;
    }

    if (matchingIntent === "show") {
      const sentCards = await this.showTopMatchesWithActions(session, chatId);
      if (!sentCards) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          await this.formatStoredMatchesMessage(session),
        );
      }
      return;
    }

    if (matchingIntent === "run") {
      if (!session.role) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          "Please choose your role with /start first, then I can run matching.",
        );
        return;
      }

      if (session.role === "candidate") {
        const isComplete = await this.isCandidateMandatoryComplete(session);
        if (!isComplete) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            chatId,
            candidateMatchingBlockedByMandatoryMessage(),
          );
          await this.startCandidateMandatoryFieldsFlow(session, chatId, {
            showIntro: true,
          });
          return;
        }
      }
      if (session.role === "manager") {
        const isComplete = await this.isManagerMandatoryComplete(session);
        if (!isComplete) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            chatId,
            managerMatchingBlockedByMandatoryMessage(),
          );
          await this.startManagerMandatoryFieldsFlow(session, chatId, {
            showIntro: true,
          });
          return;
        }
      }

      const flags = await this.usersRepository.getUserFlags(session.userId);
      if (flags.matchingPaused || !flags.autoMatchingEnabled) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          "Matching is paused. Type resume matching if you want me to search again.",
        );
        return;
      }

      const run =
        session.role === "candidate"
          ? await this.matchingEngine.runForCandidate(String(session.userId))
          : await this.matchingEngine.runForManager(String(session.userId));
      await this.sendRouterReplyWithLoopGuard(session, chatId, run.message);
      return;
    }

    await this.sendRouterReplyWithLoopGuard(session, chatId, reply);
  }

  private async restartFlow(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
  ): Promise<void> {
    const session = this.stateService.reset(update.userId, update.chatId, update.username);
    await this.sendBotMessage(session.userId, update.chatId, welcomeMessage(), {
      replyMarkup: buildRoleSelectionKeyboard(),
    });
    await this.sendBotMessage(session.userId, update.chatId, contactRequestMessage(), {
      replyMarkup: buildContactRequestKeyboard(),
    });
  }

  private buildDeterministicRouteFallback(update: NormalizedUpdate): AlwaysOnRouterDecision | null {
    if (update.kind === "document") {
      return {
        route: "DOC",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: "Document received. I will process it now.",
        should_advance: false,
        should_process_text_as_document: false,
      };
    }
    if (update.kind === "voice") {
      return {
        route: "VOICE",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: "Voice message received. I will transcribe it now.",
        should_advance: false,
        should_process_text_as_document: false,
      };
    }
    if (update.kind === "text" && isStartCommand(update.text.trim())) {
      return {
        route: "CONTROL",
        meta_type: null,
        control_type: "restart",
        matching_intent: null,
        reply: "Restarting.",
        should_advance: false,
        should_process_text_as_document: false,
      };
    }
    return null;
  }

  private async handlePastedDocumentText(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    input: {
      sourceTextOriginal: string;
      sourceTextEnglish: string;
    },
  ): Promise<void> {
    const session = this.stateService.getOrCreate(update.userId, update.chatId, update.username);

    if (isInterviewingState(session.state)) {
      await this.sendBotMessage(session.userId, update.chatId, interviewAlreadyStartedMessage());
      return;
    }

    if (!isDocumentUploadAllowedState(session.state)) {
      await this.sendBotMessage(session.userId, update.chatId, documentUploadNotAllowedMessage());
      return;
    }

    try {
      evaluateInterviewBootstrap(session);
    } catch (error) {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        error instanceof Error ? error.message : "Cannot start interview from the current state.",
      );
      return;
    }

    await this.sendBotMessage(session.userId, update.chatId, processingDocumentMessage());

    try {
      this.stateService.clearWaitingShortTextCounter(update.userId);
      if (session.state === "waiting_job") {
        await this.jobsRepository.saveJobIntakeSource({
          managerTelegramUserId: update.userId,
          sourceType: "text",
          sourceTextOriginal: input.sourceTextOriginal,
          sourceTextEnglish: input.sourceTextEnglish,
          telegramFileId: null,
        });
      }
      if (session.state === "waiting_resume") {
        await this.profilesRepository.saveCandidateResumeIntakeSource({
          telegramUserId: update.userId,
          sourceType: "text",
          sourceTextOriginal: input.sourceTextOriginal,
          sourceTextEnglish: input.sourceTextEnglish,
          telegramFileId: null,
        });
      }

      const bootstrap = await this.interviewEngine.bootstrapInterview(session, input.sourceTextEnglish);
      if (bootstrap.intakeOneLiner) {
        await this.sendBotMessage(session.userId, update.chatId, bootstrap.intakeOneLiner);
      }
      if (bootstrap.nextState === "interviewing_candidate") {
        await this.sendBotMessage(session.userId, update.chatId, candidateInterviewPreparationMessage());
      } else {
        await this.sendBotMessage(session.userId, update.chatId, managerInterviewPreparationMessage());
      }
      if (bootstrap.answerInstruction) {
        await this.sendBotMessage(session.userId, update.chatId, bootstrap.answerInstruction);
      }
      await this.sendBotMessage(session.userId, update.chatId, interviewLanguageSupportMessage());
      await this.sendBotMessage(session.userId, update.chatId, questionMessage(0, bootstrap.firstQuestion));
      this.stateService.setInterviewPlan(update.userId, bootstrap.plan);
      if (bootstrap.candidatePlanV2) {
        this.stateService.setCandidateInterviewPlanV2(update.userId, bootstrap.candidatePlanV2);
      }
      this.stateService.setCurrentQuestionIndex(update.userId, 0);
      this.stateService.markInterviewStarted(update.userId, "unknown", new Date().toISOString());
      this.stateService.transition(update.userId, bootstrap.nextState);
    } catch (error) {
      this.logger.error("Failed to process pasted document text", {
        userId: update.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        error instanceof Error ? error.message : "Failed to process text.",
      );
    }
  }

  private async sendRouterReplyWithLoopGuard(
    session: UserSessionState,
    chatId: number,
    reply: string,
  ): Promise<void> {
    const trimmed = reply.trim();
    const previous = session.lastBotMessage?.trim();
    const finalReply =
      trimmed && previous && trimmed === previous
        ? "Please send a PDF or DOCX file, or paste the full text here."
        : trimmed || "Please continue with your hiring flow.";
    await this.sendBotMessage(session.userId, chatId, finalReply);
  }

  private async sendBotMessage(
    userId: number,
    chatId: number,
    text: string,
    options?: Parameters<TelegramClient["sendMessage"]>[2],
  ): Promise<void> {
    await this.telegramClient.sendMessage(chatId, text, options);
    this.stateService.setLastBotMessage(userId, text);
  }

  private async handleContactUpdate(
    update: Extract<NormalizedUpdate, { kind: "contact" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (typeof update.contactUserId === "number" && update.contactUserId !== update.userId) {
      await this.sendBotMessage(session.userId, update.chatId, ownContactRequiredMessage(), {
        replyMarkup: buildContactRequestKeyboard(),
      });
      return;
    }

    const sharedAt = new Date().toISOString();
    this.stateService.setContactInfo({
      userId: update.userId,
      phoneNumber: update.phoneNumber,
      firstName: update.firstName,
      lastName: update.lastName,
      sharedAt,
    });
    await this.usersRepository.saveContact({
      telegramUserId: update.userId,
      telegramUsername: update.username,
      phoneNumber: update.phoneNumber,
      firstName: update.firstName,
      lastName: update.lastName,
      contactSharedAt: sharedAt,
    });

    await this.sendBotMessage(session.userId, update.chatId, contactSavedMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
    if (session.state === "role_selection") {
      await this.sendBotMessage(session.userId, update.chatId, "Choose your role to begin.", {
        replyMarkup: buildRoleSelectionKeyboard(),
      });
    }
  }

  private async handleLocationUpdate(
    update: Extract<NormalizedUpdate, { kind: "location" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (session.state !== "candidate_mandatory_fields") {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "Location received. If you want to update profile location, type update location.",
      );
      return;
    }

    await this.sendBotMessage(
      session.userId,
      update.chatId,
      candidateMandatoryLocationPinReceivedMessage(),
      { replyMarkup: buildCandidateMandatoryLocationKeyboard() },
    );
  }

  private async startCandidateMandatoryFieldsFlow(
    session: UserSessionState,
    chatId: number,
    options?: {
      forcedStep?: CandidateMandatoryStep;
      showIntro?: boolean;
    },
  ): Promise<void> {
    if (session.role !== "candidate") {
      return;
    }

    const mandatory = await this.getCandidateMandatorySnapshot(session);
    if (mandatory.profileComplete) {
      this.stateService.setCandidateProfileComplete(session.userId, true);
      this.stateService.setCandidateMandatoryStep(session.userId, undefined);
      this.stateService.setCandidatePendingSalary(session.userId, undefined);
      if (session.state === "candidate_mandatory_fields") {
        this.stateService.transition(session.userId, "candidate_profile_ready");
      }
      return;
    }

    if (session.state !== "candidate_mandatory_fields") {
      try {
        this.stateService.transition(session.userId, "candidate_mandatory_fields");
      } catch {
        return;
      }
    }
    this.stateService.setCandidateProfileComplete(session.userId, false);

    const nextStep = options?.forcedStep ?? resolveMissingMandatoryStep(mandatory);
    if (!nextStep) {
      this.stateService.setCandidateProfileComplete(session.userId, true);
      this.stateService.setCandidateMandatoryStep(session.userId, undefined);
      this.stateService.setCandidatePendingSalary(session.userId, undefined);
      if (session.state === "candidate_mandatory_fields") {
        this.stateService.transition(session.userId, "candidate_profile_ready");
      }
      await this.sendBotMessage(session.userId, chatId, candidateMandatoryCompletedMessage(), {
        replyMarkup: buildCandidateMatchingActionsKeyboard(),
      });
      await this.sendBotMessage(session.userId, chatId, candidateMatchingActionsReadyMessage());
      return;
    }

    this.stateService.setCandidateMandatoryStep(session.userId, nextStep);
    this.stateService.setCandidatePendingSalary(session.userId, undefined);
    if (options?.showIntro) {
      await this.sendBotMessage(session.userId, chatId, candidateMandatoryIntroMessage());
    }
    await this.askCandidateMandatoryQuestion(session.userId, chatId, nextStep);
  }

  private async handleCandidateMandatoryTextInput(
    session: UserSessionState,
    chatId: number,
    originalText: string,
    normalizedEnglishText: string,
  ): Promise<void> {
    const step = session.candidateMandatoryStep ?? "location";

    if (step === "location") {
      const parsed = parseCountryCity(normalizedEnglishText);
      if (!parsed.isValid) {
        await this.sendBotMessage(
          session.userId,
          chatId,
          candidateMandatoryLocationRetryMessage(),
          { replyMarkup: buildCandidateMandatoryLocationKeyboard() },
        );
        return;
      }

      this.stateService.setCandidateLocation(session.userId, {
        country: parsed.country,
        city: parsed.city,
      });
      await this.candidateMandatoryFieldsService.saveLocation(session.userId, {
        country: parsed.country,
        city: parsed.city,
      });
      await this.startCandidateMandatoryFieldsFlow(session, chatId);
      return;
    }

    if (step === "work_mode") {
      const workMode = parseCandidateWorkMode(normalizedEnglishText);
      if (!workMode) {
        await this.sendBotMessage(
          session.userId,
          chatId,
          candidateMandatoryWorkModeRetryMessage(),
          { replyMarkup: buildCandidateWorkModeKeyboard() },
        );
        return;
      }

      this.stateService.setCandidateWorkMode(session.userId, workMode);
      await this.candidateMandatoryFieldsService.saveWorkMode(session.userId, workMode);
      await this.startCandidateMandatoryFieldsFlow(session, chatId);
      return;
    }

    const pendingSalary = session.candidatePendingSalary;
    if (pendingSalary?.needsCurrencyConfirmation) {
      if (isYesConfirmation(normalizedEnglishText)) {
        this.stateService.setCandidateSalary(session.userId, {
          amount: pendingSalary.amount,
          currency: pendingSalary.currency,
          period: pendingSalary.period,
        });
        this.stateService.setCandidatePendingSalary(session.userId, undefined);
        await this.candidateMandatoryFieldsService.saveSalary(session.userId, {
          amount: pendingSalary.amount,
          currency: pendingSalary.currency,
          period: pendingSalary.period,
        });
        await this.startCandidateMandatoryFieldsFlow(session, chatId);
        return;
      }
    }

    const salary = parseSalary(normalizedEnglishText);
    if (!salary.isValid || salary.amount === null || salary.period === null || salary.currency === null) {
      await this.sendBotMessage(
        session.userId,
        chatId,
        candidateMandatorySalaryRetryMessage(),
      );
      return;
    }

    if (salary.currencyMissing) {
      this.stateService.setCandidatePendingSalary(session.userId, {
        amount: salary.amount,
        currency: salary.currency,
        period: salary.period,
        needsCurrencyConfirmation: true,
      });
      await this.sendBotMessage(
        session.userId,
        chatId,
        candidateMandatorySalaryCurrencyConfirmMessage({
          amount: salary.amount,
          period: salary.period,
        }),
      );
      return;
    }

    this.stateService.setCandidateSalary(session.userId, {
      amount: salary.amount,
      currency: salary.currency,
      period: salary.period,
    });
    this.stateService.setCandidatePendingSalary(session.userId, undefined);
    await this.candidateMandatoryFieldsService.saveSalary(session.userId, {
      amount: salary.amount,
      currency: salary.currency,
      period: salary.period,
    });
    await this.startCandidateMandatoryFieldsFlow(session, chatId);
  }

  private async askCandidateMandatoryQuestion(
    userId: number,
    chatId: number,
    step: CandidateMandatoryStep,
  ): Promise<void> {
    if (step === "location") {
      await this.sendBotMessage(userId, chatId, candidateMandatoryLocationQuestionMessage(), {
        replyMarkup: buildCandidateMandatoryLocationKeyboard(),
      });
      return;
    }
    if (step === "work_mode") {
      await this.sendBotMessage(userId, chatId, candidateMandatoryWorkModeQuestionMessage(), {
        replyMarkup: buildCandidateWorkModeKeyboard(),
      });
      return;
    }
    await this.sendBotMessage(userId, chatId, candidateMandatorySalaryQuestionMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
  }

  private async getCandidateMandatorySnapshot(session: UserSessionState): Promise<{
    country: string;
    city: string;
    workMode: CandidateWorkMode | null;
    salaryAmount: number | null;
    salaryCurrency: CandidateSalaryCurrency | null;
    salaryPeriod: CandidateSalaryPeriod | null;
    profileComplete: boolean;
  }> {
    const fromDb = await this.candidateMandatoryFieldsService.getMandatoryFields(session.userId);
    if (fromDb.country) {
      this.stateService.setCandidateLocation(session.userId, {
        country: fromDb.country,
        city: fromDb.city,
      });
    }
    if (fromDb.workMode) {
      this.stateService.setCandidateWorkMode(session.userId, fromDb.workMode);
    }
    if (
      typeof fromDb.salaryAmount === "number" &&
      fromDb.salaryCurrency &&
      fromDb.salaryPeriod
    ) {
      this.stateService.setCandidateSalary(session.userId, {
        amount: fromDb.salaryAmount,
        currency: fromDb.salaryCurrency,
        period: fromDb.salaryPeriod,
      });
    }

    const country = (fromDb.country || session.candidateCountry || "").trim();
    const city = (fromDb.city || session.candidateCity || "").trim();
    const workMode = fromDb.workMode ?? session.candidateWorkMode ?? null;
    const salaryAmount =
      typeof fromDb.salaryAmount === "number"
        ? fromDb.salaryAmount
        : typeof session.candidateSalaryAmount === "number"
          ? session.candidateSalaryAmount
          : null;
    const salaryCurrency = fromDb.salaryCurrency ?? session.candidateSalaryCurrency ?? null;
    const salaryPeriod = fromDb.salaryPeriod ?? session.candidateSalaryPeriod ?? null;
    const profileComplete = Boolean(
      country &&
      city &&
      workMode &&
      typeof salaryAmount === "number" &&
      salaryAmount > 0 &&
      salaryCurrency &&
      salaryPeriod,
    );

    this.stateService.setCandidateProfileComplete(session.userId, profileComplete);
    return {
      country,
      city,
      workMode,
      salaryAmount,
      salaryCurrency,
      salaryPeriod,
      profileComplete,
    };
  }

  private async isCandidateMandatoryComplete(session: UserSessionState): Promise<boolean> {
    const snapshot = await this.getCandidateMandatorySnapshot(session);
    return snapshot.profileComplete;
  }

  private async handleManagerWorkFormatCallback(
    update: Extract<NormalizedUpdate, { kind: "callback" }>,
    session: UserSessionState,
  ): Promise<void> {
    const workFormat = parseManagerWorkFormatCallback(update.data);
    if (!workFormat) {
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Invalid work format");
      return;
    }
    await this.telegramClient.answerCallbackQuery(update.callbackQueryId, `Saved: ${workFormat}`);

    this.stateService.setJobWorkFormat(session.userId, workFormat);
    this.stateService.setManagerMandatoryStep(session.userId, "work_format");
    this.stateService.setManagerPendingBudget(session.userId, undefined);
    if (workFormat !== "remote") {
      this.stateService.setJobRemotePolicy(session.userId, { worldwide: false, countries: [] });
    }
    await this.jobMandatoryFieldsService.saveWorkFormat(session.userId, workFormat);
    if (workFormat !== "remote") {
      await this.jobMandatoryFieldsService.saveCountries(session.userId, {
        worldwide: false,
        countries: [],
      });
    }

    await this.startManagerMandatoryFieldsFlow(session, update.chatId);
  }

  private async startManagerMandatoryFieldsFlow(
    session: UserSessionState,
    chatId: number,
    options?: {
      forcedStep?: ManagerMandatoryStep;
      showIntro?: boolean;
      runMatchingAfterComplete?: boolean;
    },
  ): Promise<void> {
    if (session.role !== "manager") {
      return;
    }

    const mandatory = await this.getManagerMandatorySnapshot(session);
    if (mandatory.profileComplete) {
      this.stateService.setJobProfileComplete(session.userId, true);
      this.stateService.setManagerMandatoryStep(session.userId, undefined);
      this.stateService.setManagerPendingBudget(session.userId, undefined);
      if (session.state === "manager_mandatory_fields") {
        this.stateService.transition(session.userId, "job_profile_ready");
      }
      if (options?.runMatchingAfterComplete) {
        await this.publishManagerMatches(session.userId);
      }
      return;
    }

    if (session.state !== "manager_mandatory_fields") {
      try {
        this.stateService.transition(session.userId, "manager_mandatory_fields");
      } catch {
        return;
      }
    }
    this.stateService.setJobProfileComplete(session.userId, false);
    const nextStep = options?.forcedStep ?? resolveMissingManagerMandatoryStep(mandatory);
    if (!nextStep) {
      this.stateService.setJobProfileComplete(session.userId, true);
      this.stateService.setManagerMandatoryStep(session.userId, undefined);
      this.stateService.setManagerPendingBudget(session.userId, undefined);
      this.stateService.transition(session.userId, "job_profile_ready");
      await this.sendBotMessage(session.userId, chatId, managerMandatoryCompletedMessage(), {
        replyMarkup: buildManagerMatchingActionsKeyboard(),
      });
      await this.sendBotMessage(session.userId, chatId, managerMatchingActionsReadyMessage());
      if (options?.runMatchingAfterComplete) {
        await this.publishManagerMatches(session.userId);
      }
      return;
    }

    this.stateService.setManagerMandatoryStep(session.userId, nextStep);
    this.stateService.setManagerPendingBudget(session.userId, undefined);
    if (options?.showIntro) {
      await this.sendBotMessage(session.userId, chatId, managerMandatoryIntroMessage());
    }
    await this.askManagerMandatoryQuestion(session.userId, chatId, nextStep);
  }

  private async handleManagerMandatoryTextInput(
    session: UserSessionState,
    chatId: number,
    normalizedEnglishText: string,
  ): Promise<void> {
    const step = session.managerMandatoryStep ?? "work_format";
    if (step === "work_format") {
      const workFormat = parseJobWorkFormat(normalizedEnglishText);
      if (!workFormat) {
        await this.sendBotMessage(
          session.userId,
          chatId,
          managerMandatoryWorkFormatQuestionMessage(),
          { replyMarkup: buildManagerWorkFormatKeyboard() },
        );
        return;
      }
      this.stateService.setJobWorkFormat(session.userId, workFormat);
      if (workFormat !== "remote") {
        this.stateService.setJobRemotePolicy(session.userId, { worldwide: false, countries: [] });
      }
      await this.jobMandatoryFieldsService.saveWorkFormat(session.userId, workFormat);
      if (workFormat !== "remote") {
        await this.jobMandatoryFieldsService.saveCountries(session.userId, {
          worldwide: false,
          countries: [],
        });
      }
      await this.startManagerMandatoryFieldsFlow(session, chatId);
      return;
    }

    if (step === "countries") {
      const parsed = parseCountries(normalizedEnglishText);
      if (!parsed.isValid) {
        await this.sendBotMessage(
          session.userId,
          chatId,
          managerMandatoryCountriesRetryMessage(),
        );
        return;
      }
      this.stateService.setJobRemotePolicy(session.userId, {
        worldwide: parsed.worldwide,
        countries: parsed.countries,
      });
      await this.jobMandatoryFieldsService.saveCountries(session.userId, {
        worldwide: parsed.worldwide,
        countries: parsed.countries,
      });
      await this.startManagerMandatoryFieldsFlow(session, chatId);
      return;
    }

    const pending = session.managerPendingBudget;
    if (pending?.needsCurrencyConfirmation && isYesConfirmation(normalizedEnglishText)) {
      this.stateService.setJobBudget(session.userId, {
        min: pending.min,
        max: pending.max,
        currency: pending.currency,
        period: pending.period,
      });
      this.stateService.setManagerPendingBudget(session.userId, undefined);
      await this.jobMandatoryFieldsService.saveBudget(session.userId, {
        min: pending.min,
        max: pending.max,
        currency: pending.currency,
        period: pending.period,
      });
      await this.startManagerMandatoryFieldsFlow(session, chatId);
      return;
    }

    const budget = parseBudget(normalizedEnglishText);
    if (!budget.isValid || budget.min === null || budget.max === null || budget.currency === null || budget.period === null) {
      if (budget.currencyMissing) {
        await this.sendBotMessage(session.userId, chatId, managerMandatoryBudgetCurrencyRetryMessage());
      } else if (budget.periodMissing) {
        await this.sendBotMessage(session.userId, chatId, managerMandatoryBudgetPeriodRetryMessage());
      } else {
        await this.sendBotMessage(session.userId, chatId, managerMandatoryBudgetRetryMessage());
      }
      return;
    }

    if (budget.currencyMissing) {
      this.stateService.setManagerPendingBudget(session.userId, {
        min: budget.min,
        max: budget.max,
        currency: budget.currency,
        period: budget.period,
        needsCurrencyConfirmation: true,
      });
      await this.sendBotMessage(
        session.userId,
        chatId,
        managerMandatoryBudgetCurrencyConfirmMessage({
          min: budget.min,
          max: budget.max,
          period: budget.period,
        }),
      );
      return;
    }

    this.stateService.setJobBudget(session.userId, {
      min: budget.min,
      max: budget.max,
      currency: budget.currency,
      period: budget.period,
    });
    this.stateService.setManagerPendingBudget(session.userId, undefined);
    await this.jobMandatoryFieldsService.saveBudget(session.userId, {
      min: budget.min,
      max: budget.max,
      currency: budget.currency,
      period: budget.period,
    });
    await this.startManagerMandatoryFieldsFlow(session, chatId);
  }

  private async askManagerMandatoryQuestion(
    userId: number,
    chatId: number,
    step: ManagerMandatoryStep,
  ): Promise<void> {
    if (step === "work_format") {
      await this.sendBotMessage(userId, chatId, managerMandatoryWorkFormatQuestionMessage(), {
        replyMarkup: buildManagerWorkFormatKeyboard(),
      });
      return;
    }
    if (step === "countries") {
      await this.sendBotMessage(userId, chatId, managerMandatoryCountriesQuestionMessage(), {
        replyMarkup: buildRemoveReplyKeyboard(),
      });
      return;
    }
    await this.sendBotMessage(userId, chatId, managerMandatoryBudgetQuestionMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
  }

  private async getManagerMandatorySnapshot(session: UserSessionState): Promise<{
    workFormat: JobWorkFormat | null;
    remoteCountries: string[];
    remoteWorldwide: boolean;
    budgetMin: number | null;
    budgetMax: number | null;
    budgetCurrency: JobBudgetCurrency | null;
    budgetPeriod: JobBudgetPeriod | null;
    profileComplete: boolean;
  }> {
    const fromDb = await this.jobMandatoryFieldsService.getMandatoryFields(session.userId);
    if (fromDb.workFormat) {
      this.stateService.setJobWorkFormat(session.userId, fromDb.workFormat);
    }
    this.stateService.setJobRemotePolicy(session.userId, {
      worldwide: fromDb.remoteWorldwide,
      countries: fromDb.remoteCountries,
    });
    if (
      typeof fromDb.budgetMin === "number" &&
      typeof fromDb.budgetMax === "number" &&
      fromDb.budgetCurrency &&
      fromDb.budgetPeriod
    ) {
      this.stateService.setJobBudget(session.userId, {
        min: fromDb.budgetMin,
        max: fromDb.budgetMax,
        currency: fromDb.budgetCurrency,
        period: fromDb.budgetPeriod,
      });
    }

    const workFormat = fromDb.workFormat ?? session.jobWorkFormat ?? null;
    const remoteCountries = fromDb.remoteCountries.length > 0 ? fromDb.remoteCountries : (session.jobRemoteCountries ?? []);
    const remoteWorldwide = fromDb.remoteWorldwide || Boolean(session.jobRemoteWorldwide);
    const budgetMin = typeof fromDb.budgetMin === "number" ? fromDb.budgetMin : (session.jobBudgetMin ?? null);
    const budgetMax = typeof fromDb.budgetMax === "number" ? fromDb.budgetMax : (session.jobBudgetMax ?? null);
    const budgetCurrency = fromDb.budgetCurrency ?? session.jobBudgetCurrency ?? null;
    const budgetPeriod = fromDb.budgetPeriod ?? session.jobBudgetPeriod ?? null;
    const profileComplete = Boolean(
      workFormat &&
      (workFormat !== "remote" || remoteWorldwide || remoteCountries.length > 0) &&
      typeof budgetMin === "number" &&
      typeof budgetMax === "number" &&
      budgetMin > 0 &&
      budgetMax >= budgetMin &&
      budgetCurrency &&
      budgetPeriod,
    );
    this.stateService.setJobProfileComplete(session.userId, profileComplete);
    return {
      workFormat,
      remoteCountries,
      remoteWorldwide,
      budgetMin,
      budgetMax,
      budgetCurrency,
      budgetPeriod,
      profileComplete,
    };
  }

  private async isManagerMandatoryComplete(session: UserSessionState): Promise<boolean> {
    const snapshot = await this.getManagerMandatorySnapshot(session);
    return snapshot.profileComplete;
  }

  private async handleDocumentUpdate(
    update: Extract<NormalizedUpdate, { kind: "document" }>,
  ): Promise<void> {
    const session = this.stateService.getOrCreate(update.userId, update.chatId, update.username);

    if (isInterviewingState(session.state)) {
      await this.sendBotMessage(session.userId, update.chatId, interviewAlreadyStartedMessage());
      return;
    }

    if (!isDocumentUploadAllowedState(session.state)) {
      await this.sendBotMessage(session.userId, update.chatId, documentUploadNotAllowedMessage());
      return;
    }

    try {
      evaluateInterviewBootstrap(session);
    } catch (error) {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        error instanceof Error ? error.message : "Cannot start interview from the current state.",
      );
      return;
    }

    await this.sendBotMessage(session.userId, update.chatId, processingDocumentMessage());

    try {
      this.stateService.clearWaitingShortTextCounter(update.userId);
      const isManagerJdIntake = session.state === "waiting_job";
      const isCandidateResumeIntake = session.state === "waiting_resume";
      const fileBuffer = await this.telegramFileService.downloadFile(update.fileId);
      const extractedText = await this.documentService.extractText(
        fileBuffer,
        update.fileName,
        update.mimeType,
      );
      const normalizedExtractedText = await this.normalizeGeneralText(extractedText);

      if (isManagerJdIntake) {
        await this.jobsRepository.saveJobIntakeSource({
          managerTelegramUserId: update.userId,
          sourceType: "file",
          sourceTextOriginal: extractedText,
          sourceTextEnglish: normalizedExtractedText,
          telegramFileId: update.fileId,
        });
      }
      if (isCandidateResumeIntake) {
        await this.profilesRepository.saveCandidateResumeIntakeSource({
          telegramUserId: update.userId,
          sourceType: "file",
          sourceTextOriginal: extractedText,
          sourceTextEnglish: normalizedExtractedText,
          telegramFileId: update.fileId,
        });
      }

      const bootstrap = await this.interviewEngine.bootstrapInterview(session, normalizedExtractedText);
      if (bootstrap.intakeOneLiner) {
        await this.sendBotMessage(session.userId, update.chatId, bootstrap.intakeOneLiner);
      }
      if (bootstrap.nextState === "interviewing_candidate") {
        await this.sendBotMessage(session.userId, update.chatId, candidateInterviewPreparationMessage());
      } else {
        await this.sendBotMessage(session.userId, update.chatId, managerInterviewPreparationMessage());
      }
      if (bootstrap.answerInstruction) {
        await this.sendBotMessage(session.userId, update.chatId, bootstrap.answerInstruction);
      }
      await this.sendBotMessage(session.userId, update.chatId, interviewLanguageSupportMessage());
      await this.sendBotMessage(session.userId, update.chatId, questionMessage(0, bootstrap.firstQuestion));
      this.stateService.setInterviewPlan(update.userId, bootstrap.plan);
      if (bootstrap.candidatePlanV2) {
        this.stateService.setCandidateInterviewPlanV2(update.userId, bootstrap.candidatePlanV2);
      }
      this.stateService.setCurrentQuestionIndex(update.userId, 0);
      this.stateService.markInterviewStarted(
        update.userId,
        this.documentService.detectDocumentType(update.fileName, update.mimeType),
        new Date().toISOString(),
      );
      this.stateService.transition(update.userId, bootstrap.nextState);
    } catch (error) {
      this.logger.error("Failed to process document", {
        userId: update.userId,
        fileName: update.fileName,
        mimeType: update.mimeType,
        error: error instanceof Error ? error.message : "Unknown error",
      });

      await this.sendBotMessage(
        session.userId,
        update.chatId,
        error instanceof Error ? error.message : "Failed to process document.",
      );
    }
  }

  private async handleInterviewAnswer(
    input: {
      answerText: string;
      originalText?: string;
      detectedLanguage?: "en" | "ru" | "uk" | "other";
      inputType: "text" | "voice";
      telegramVoiceFileId?: string;
      voiceDurationSec?: number;
      transcriptionStatus?: "success" | "failed";
    },
    session: UserSessionState,
    sourceMessageId?: number,
  ): Promise<void> {
    if (session.state !== "interviewing_candidate" && session.state !== "interviewing_manager") {
      await this.sendBotMessage(session.userId, session.chatId, missingInterviewContextMessage());
      return;
    }

    if (!session.interviewPlan) {
      await this.sendBotMessage(session.userId, session.chatId, missingInterviewContextMessage());
      return;
    }

    const originalText = (input.originalText ?? input.answerText).trim();
    const normalized = await this.normalizeInterviewInput(input.answerText.trim());
    this.stateService.recordPreferredLanguageSample(
      session.userId,
      toPreferredLanguage(normalized.detected_language),
    );

    const currentQuestionText = resolveCurrentInterviewQuestionText(session);
    if (!currentQuestionText) {
      await this.sendBotMessage(session.userId, session.chatId, missingInterviewContextMessage());
      return;
    }

    try {
      const normalizedInput = {
        ...input,
        answerText: normalized.english_text,
        originalText,
        detectedLanguage: normalized.detected_language,
      };
      const result = await this.interviewEngine.submitAnswer(session, normalizedInput);

      if (result.kind === "next_question") {
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        const shouldSendProgressConfirmation = this.shouldSendProgressConfirmation(
          latestSession,
          normalizedInput.answerText,
        );
        if (shouldSendProgressConfirmation) {
          const confirmation = await this.generateInterviewProgressConfirmation(latestSession);
          if (confirmation) {
            await this.sendBotMessage(session.userId, session.chatId, confirmation);
            this.stateService.resetAnswersSinceConfirm(session.userId);
          }
        }

        await this.maybeSendInterviewReaction(session, originalText, sourceMessageId);
        await this.maybeSendCandidateEmpathyLine(session);
        await this.sendBotMessage(
          session.userId,
          session.chatId,
          result.isFollowUp
            ? result.questionText
            : questionMessage(result.questionIndex, result.questionText),
        );
        return;
      }

      this.stateService.transition(session.userId, result.completedState);
      this.stateService.resetAnswersSinceConfirm(session.userId);
      await this.sendBotMessage(session.userId, session.chatId, result.completionMessage);
      if (result.followupMessage) {
        await this.sendBotMessage(session.userId, session.chatId, result.followupMessage);
      }
      if (result.completedState === "candidate_profile_ready") {
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        await this.startCandidateMandatoryFieldsFlow(latestSession, session.chatId, {
          showIntro: true,
        });
      }
      if (result.completedState === "job_profile_ready") {
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        await this.startManagerMandatoryFieldsFlow(latestSession, session.chatId, {
          showIntro: true,
          runMatchingAfterComplete: true,
        });
      }
    } catch (error) {
      this.logger.warn("Interview answer processing failed", {
        userId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.sendBotMessage(
        session.userId,
        session.chatId,
        "I had trouble processing that. Please resend your last message, text or voice.",
      );
    }
  }

  private async handleVoiceUpdate(
    update: Extract<NormalizedUpdate, { kind: "voice" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (update.durationSec > this.voiceMaxDurationSec) {
      await this.sendBotMessage(session.userId, update.chatId, voiceTooLongMessage(this.voiceMaxDurationSec));
      return;
    }

    await this.sendBotMessage(session.userId, update.chatId, transcribingVoiceMessage());

    try {
      const buffer = await this.telegramFileService.downloadFile(update.fileId);
      const transcription = await this.transcriptionClient.transcribeOgg(buffer);
      const normalized = await this.normalizeInterviewInput(transcription);
      this.stateService.recordPreferredLanguageSample(update.userId, toPreferredLanguage(normalized.detected_language));
      const latestSession = this.stateService.getSession(update.userId) ?? session;
      const syntheticTextUpdate: Extract<NormalizedUpdate, { kind: "text" }> = {
        kind: "text",
        updateId: update.updateId,
        messageId: update.messageId,
        chatId: update.chatId,
        userId: update.userId,
        username: update.username,
        text: transcription,
      };
      const routed = await this.classifyAlwaysOnForUpdate(
        syntheticTextUpdate,
        latestSession,
        normalized.english_text,
      );
      if (!routed) {
        return;
      }
      this.logger.debug("dispatch route: X", {
        updateId: update.updateId,
        telegramUserId: update.userId,
        currentState: latestSession.state,
        route: routed.decision.route,
        source: "voice_transcription",
      });
      await this.dispatchTextRoute(
        syntheticTextUpdate,
        latestSession,
        routed.decision,
        routed.textEnglish ?? normalized.english_text,
        routed.detectedLanguage ?? normalized.detected_language,
      );
    } catch (error) {
      this.logger.error("Voice transcription failed outside interview", {
        userId: update.userId,
        durationSec: update.durationSec,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.sendBotMessage(session.userId, update.chatId, transcriptionFailedMessage());
    }
  }

  private async maybeSendInterviewReaction(
    session: UserSessionState,
    answerText: string,
    messageId?: number,
  ): Promise<void> {
    const reactionResult = await maybeReact(
      {
        telegramClient: this.telegramClient,
        logger: this.logger,
        userId: session.userId,
        chatId: session.chatId,
        messageId,
        state: session.state,
        answerText,
      },
      {
        enabled: this.telegramReactionsEnabled,
        probability: this.telegramReactionsProbability,
        reactionMessagesSinceLast: session.reactionMessagesSinceLast,
        lastReactionEmoji: session.lastReactionEmoji,
        answerQualityHint: estimateAnswerQuality(answerText),
      },
    );

    this.stateService.setReactionState({
      userId: session.userId,
      reactionMessagesSinceLast: reactionResult.nextMessagesSinceLast,
      lastReactionAt: reactionResult.lastReactionAt ?? session.lastReactionAt,
      lastReactionEmoji: reactionResult.reactionEmoji ?? session.lastReactionEmoji,
    });
  }

  private async maybeSendCandidateEmpathyLine(session: UserSessionState): Promise<void> {
    if (session.state !== "interviewing_candidate") {
      return;
    }
    if (Math.random() > 0.4) {
      return;
    }

    const line = getShortEmpathyLine(session.lastEmpathyLine);
    await this.sendBotMessage(session.userId, session.chatId, line);
    this.stateService.setLastEmpathyLine(session.userId, line);
  }

  private shouldSendProgressConfirmation(
    session: UserSessionState,
    normalizedAnswerText: string,
  ): boolean {
    const counterSession = this.stateService.incrementAnswersSinceConfirm(session.userId);
    const count = counterSession.answersSinceConfirm ?? 0;
    return count >= 2 || isSignificantAnswer(normalizedAnswerText);
  }

  private async generateInterviewProgressConfirmation(
    session: UserSessionState,
  ): Promise<string | null> {
    if (session.state !== "interviewing_candidate" && session.state !== "interviewing_manager") {
      return null;
    }

    const role = session.state === "interviewing_candidate" ? "candidate" : "manager";
    const lastAnswers = this.stateService
      .getAnswers(session.userId)
      .slice(-2)
      .map((item) => item.answerText.trim())
      .filter(Boolean);
    if (lastAnswers.length === 0) {
      return null;
    }

    const currentProfileJson =
      role === "candidate"
        ? session.candidateProfile ?? {}
        : session.managerJobProfileV2 ?? session.jobProfile ?? {};

    return this.interviewConfirmationService.generateInterviewProgressOneLiner({
      telegramUserId: session.userId,
      role,
      lastAnswersEnglish: lastAnswers,
      currentProfileJson,
    });
  }

  private async publishManagerMatches(managerUserId: number): Promise<void> {
    const managerSession = this.stateService.getSession(managerUserId);
    if (!managerSession) {
      return;
    }

    try {
      this.stateService.transition(managerUserId, "job_published");
      if (managerSession.jobProfile) {
        await this.jobsRepository.upsertManagerJob({
          managerTelegramUserId: managerUserId,
          status: "active",
          jobSummary: managerSession.jobProfile.searchableText,
          jobProfile: managerSession.jobProfile,
        });
      }
    } catch {
      // Keep current state if transition is not available.
    }

    try {
      const run = await this.matchingEngine.runForManager(managerUserId);
      if (!run || run.matches.length === 0) {
        await this.telegramClient.sendMessage(
          managerSession.chatId,
          "No suitable candidates found yet.",
        );
        return;
      }

      await this.telegramClient.sendMessage(
        managerSession.chatId,
        "Matching run completed. Candidate notifications were sent where eligible.",
      );

      const jobTechnicalSummary = await this.jobsRepository.getJobTechnicalSummary(managerUserId);
      const candidateJobSummary = formatCandidateJobSummary(
        jobTechnicalSummary,
        run.jobSummary,
      );

      const records = await this.matchStorageService.createForJob(
        managerUserId,
        candidateJobSummary,
        run.matches.map((match) => ({
          candidateUserId: match.candidateUserId,
          jobId: null,
          candidateId: null,
          candidateSummary: match.candidateSummary,
          jobTechnicalSummary: match.jobTechnicalSummary ?? null,
          candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
          score: match.score,
          breakdown: match.breakdown,
          reasons: match.reasons,
          explanationJson: match.explanationJson,
          matchingDecision: match.decision,
          explanation: match.explanation,
        })),
      );

      for (const record of records) {
        await this.notificationEngine.notifyCandidateOpportunity(record);
      }
    } catch (error) {
      this.logger.error("Failed to publish manager matches", {
        managerUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.telegramClient.sendMessage(
        managerSession.chatId,
        "Matching is temporarily unavailable.",
      );
    }
  }

  private async normalizeInterviewInput(
    originalText: string,
  ): Promise<{ detected_language: "en" | "ru" | "uk" | "other"; english_text: string }> {
    try {
      const normalized = await this.normalizationService.normalizeToEnglish(originalText);
      const englishText = normalized.english_text.trim();
      if (!englishText) {
        return {
          detected_language: normalized.detected_language,
          english_text: originalText,
        };
      }
      return {
        detected_language: normalized.detected_language,
        english_text: englishText,
      };
    } catch (error) {
      this.logger.warn("Interview input normalization failed, using original text", {
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return {
        detected_language: detectLanguageQuick(originalText),
        english_text: originalText,
      };
    }
  }

  private async normalizeGeneralText(text: string): Promise<string> {
    const trimmed = text.trim();
    if (!trimmed || trimmed.startsWith("/")) {
      return text;
    }

    const detected = detectLanguageQuick(trimmed);
    if (detected === "en" || detected === "other") {
      return text;
    }

    try {
      const normalized = await this.normalizationService.normalizeToEnglish(trimmed);
      const englishText = normalized.english_text.trim();
      return englishText || text;
    } catch {
      return text;
    }
  }

  private async showTopMatchesWithActions(session: UserSessionState, chatId: number): Promise<boolean> {
    const all = await this.matchStorageService.listAll();
    if (session.role === "manager") {
      const managerMatches = all
        .filter((item) => item.managerUserId === session.userId)
        .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
        .slice(0, 3);
      if (managerMatches.length === 0) {
        return false;
      }

      for (const match of managerMatches) {
        await this.telegramClient.sendMessage(
          chatId,
          managerCandidateSuggestionMessage({
            candidateUserId: match.candidateUserId,
            score: match.score,
            candidateSummary: match.candidateSummary,
            candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
            explanationMessage:
              match.explanationJson?.message_for_manager ?? match.explanation,
          }),
          { replyMarkup: buildManagerDecisionKeyboard(match.id) },
        );
      }
      return true;
    }

    const candidateMatches = all
      .filter((item) => item.candidateUserId === session.userId)
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .slice(0, 3);
    if (candidateMatches.length === 0) {
      return false;
    }

    for (const match of candidateMatches) {
      await this.telegramClient.sendMessage(
        chatId,
        candidateOpportunityMessage({
          score: match.score,
          jobSummary: match.jobSummary,
          explanationMessage:
            match.explanationJson?.message_for_candidate ?? match.explanation,
          jobTechnicalSummary: match.jobTechnicalSummary ?? null,
        }),
        { replyMarkup: buildCandidateDecisionKeyboard(match.id) },
      );
    }
    return true;
  }

  private async formatStoredMatchesMessage(session: UserSessionState): Promise<string> {
    const all = await this.matchStorageService.listAll();
    if (session.role === "manager") {
      const managerMatches = all
        .filter((item) => item.managerUserId === session.userId)
        .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
        .slice(0, 10);
      if (managerMatches.length === 0) {
        return "No matches found yet. Type find candidates to run matching.";
      }
      const lines = ["Latest candidate matches:", ""];
      for (const [index, match] of managerMatches.entries()) {
        lines.push(`${index + 1}) Candidate #${match.candidateUserId} | score ${Math.round(match.score)}%`);
        lines.push(`   Status: ${match.status}`);
      }
      return lines.join("\n");
    }

    const candidateMatches = all
      .filter((item) => item.candidateUserId === session.userId)
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .slice(0, 10);
    if (candidateMatches.length === 0) {
      return "No role matches found yet. Type find me roles to run matching.";
    }
    const lines = ["Latest role matches:", ""];
    for (const [index, match] of candidateMatches.entries()) {
      lines.push(`${index + 1}) Score ${Math.round(match.score)}%`);
      lines.push(`   ${match.jobSummary.slice(0, 220)}`);
      lines.push(`   Status: ${match.status}`);
    }
    return lines.join("\n");
  }
}

function formatCandidateJobSummary(
  summary: JobTechnicalSummaryV2 | null,
  fallback: string,
): string {
  if (!summary) {
    return fallback;
  }

  const tasks = summary.current_tasks.slice(0, 2).join(", ") || "unknown";
  const coreTech = summary.core_tech.join(", ") || "unknown";
  const keyRequirements = summary.key_requirements.slice(0, 3).join(", ") || "unknown";

  return [
    summary.headline || "Role summary",
    `Product: ${summary.product_context || "unknown"}`,
    `Tasks: ${tasks}`,
    `Core tech: ${coreTech}`,
    `Key requirements: ${keyRequirements}`,
    `Domain need: ${summary.domain_need}`,
    `Ownership: ${summary.ownership_expectation}`,
  ].join(" | ");
}

function isSkipContactForNow(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  return normalized === "skip for now";
}

function isStartCommand(text: string): boolean {
  return /^\/start(?:\s|$)/i.test(text.trim());
}

function isDataDeletionCommand(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("delete my data") ||
    english.includes("remove my contact") ||
    english.includes("delete my contact") ||
    english === "delete data" ||
    english === "delete contact" ||
    raw.includes("удали мои данные") ||
    raw.includes("удали мой контакт") ||
    raw.includes("видали мої дані") ||
    raw.includes("видали мій контакт")
  );
}

function resolveCurrentInterviewQuestionText(session: UserSessionState): string | null {
  if (!session.interviewPlan) {
    return null;
  }

  const followUp = session.pendingFollowUp;
  if (followUp?.questionText?.trim()) {
    return followUp.questionText.trim();
  }

  const index = session.currentQuestionIndex;
  if (
    typeof index !== "number" ||
    index < 0 ||
    index >= session.interviewPlan.questions.length
  ) {
    return null;
  }

  const question = session.interviewPlan.questions[index];
  const text = question?.question?.trim();
  return text || null;
}

function resolveCurrentQuestionIndexValue(session: UserSessionState): number | null {
  if (session.pendingFollowUp && typeof session.pendingFollowUp.questionIndex === "number") {
    return session.pendingFollowUp.questionIndex;
  }
  if (typeof session.currentQuestionIndex === "number") {
    return session.currentQuestionIndex;
  }
  return null;
}

function resolveMissingQuestionIndexFromPlan(session: UserSessionState): number | null {
  const plan = session.interviewPlan;
  if (!plan) {
    return null;
  }
  const answered = new Set((session.answers ?? []).map((item) => item.questionIndex));
  const skipped = new Set(session.skippedQuestionIndexes ?? []);
  for (let index = 0; index < plan.questions.length; index += 1) {
    if (!answered.has(index) && !skipped.has(index)) {
      return index;
    }
  }
  return null;
}

function isInterviewSkipCommand(textEnglish: string): boolean {
  const normalized = textEnglish.trim().toLowerCase();
  return normalized === "skip" || normalized === "skip question" || normalized === "pass";
}

function estimateAnswerQuality(answerText: string): "low" | "medium" | "high" {
  const words = answerText
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (words.length >= 35 || /\d/.test(answerText)) {
    return "high";
  }
  if (words.length >= 12) {
    return "medium";
  }
  return "low";
}

function isSignificantAnswer(answerText: string): boolean {
  const trimmed = answerText.trim();
  if (!trimmed) {
    return false;
  }
  const wordCount = trimmed.split(/\s+/).filter(Boolean).length;
  if (wordCount >= 40) {
    return true;
  }
  const hasMetrics = /\d/.test(trimmed);
  const hasDepthSignals =
    /\b(architecture|trade-off|tradeoff|latency|throughput|incident|scalability|ownership|domain)\b/i.test(
      trimmed,
    );
  return wordCount >= 20 && (hasMetrics || hasDepthSignals);
}

function matchingHelpMessage(): string {
  return [
    "Matching commands you can use:",
    "find me roles",
    "find jobs",
    "find candidates",
    "show matches",
    "pause matching",
    "resume matching",
  ].join("\n");
}

function mapRouteToActionLabel(route: AlwaysOnRouterDecision["route"]): string {
  if (route === "DOC") {
    return "process_document";
  }
  if (route === "VOICE") {
    return "transcribe_voice";
  }
  if (route === "JD_TEXT" || route === "RESUME_TEXT") {
    return "process_pasted_text";
  }
  if (route === "INTERVIEW_ANSWER") {
    return "process_interview_answer";
  }
  if (route === "MATCHING_COMMAND") {
    return "matching_command";
  }
  if (route === "CONTROL") {
    return "control";
  }
  if (route === "META") {
    return "meta_reply";
  }
  if (route === "OFFTOPIC") {
    return "redirect_offtopic";
  }
  return "generic_reply";
}

function parseCandidateWorkMode(textEnglish: string): CandidateWorkMode | null {
  const normalized = textEnglish.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes("remote")) {
    return "remote";
  }
  if (normalized.includes("hybrid")) {
    return "hybrid";
  }
  if (normalized.includes("onsite") || normalized.includes("on site") || normalized.includes("office")) {
    return "onsite";
  }
  if (normalized.includes("flexible")) {
    return "flexible";
  }
  return null;
}

function detectCandidateMandatoryUpdateCommand(
  normalizedEnglishText: string,
): CandidateMandatoryStep | null {
  if (normalizedEnglishText.includes("update location")) {
    return "location";
  }
  if (normalizedEnglishText.includes("update salary")) {
    return "salary";
  }
  if (normalizedEnglishText.includes("update work mode")) {
    return "work_mode";
  }
  return null;
}

function detectManagerMandatoryUpdateCommand(
  normalizedEnglishText: string,
): ManagerMandatoryStep | null {
  if (normalizedEnglishText.includes("update budget")) {
    return "budget";
  }
  if (normalizedEnglishText.includes("update work format")) {
    return "work_format";
  }
  if (normalizedEnglishText.includes("update countries")) {
    return "countries";
  }
  return null;
}

function resolveMissingMandatoryStep(input: {
  country: string;
  city: string;
  workMode: CandidateWorkMode | null;
  salaryAmount: number | null;
  salaryCurrency: CandidateSalaryCurrency | null;
  salaryPeriod: CandidateSalaryPeriod | null;
}): CandidateMandatoryStep | null {
  if (!input.country.trim() || !input.city.trim()) {
    return "location";
  }
  if (!input.workMode) {
    return "work_mode";
  }
  if (
    typeof input.salaryAmount !== "number" ||
    input.salaryAmount <= 0 ||
    !input.salaryCurrency ||
    !input.salaryPeriod
  ) {
    return "salary";
  }
  return null;
}

function resolveMissingManagerMandatoryStep(input: {
  workFormat: JobWorkFormat | null;
  remoteCountries: string[];
  remoteWorldwide: boolean;
  budgetMin: number | null;
  budgetMax: number | null;
  budgetCurrency: JobBudgetCurrency | null;
  budgetPeriod: JobBudgetPeriod | null;
}): ManagerMandatoryStep | null {
  if (!input.workFormat) {
    return "work_format";
  }
  if (input.workFormat === "remote" && !input.remoteWorldwide && input.remoteCountries.length === 0) {
    return "countries";
  }
  if (
    typeof input.budgetMin !== "number" ||
    typeof input.budgetMax !== "number" ||
    input.budgetMin <= 0 ||
    input.budgetMax < input.budgetMin ||
    !input.budgetCurrency ||
    !input.budgetPeriod
  ) {
    return "budget";
  }
  return null;
}

function parseJobWorkFormat(textEnglish: string): JobWorkFormat | null {
  const normalized = textEnglish.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes("remote")) {
    return "remote";
  }
  if (normalized.includes("hybrid")) {
    return "hybrid";
  }
  if (normalized.includes("onsite") || normalized.includes("on site") || normalized.includes("office")) {
    return "onsite";
  }
  return null;
}

function isManagerWorkFormatCallback(callbackData: string): boolean {
  return (
    callbackData === CALLBACK_MANAGER_WORK_FORMAT_REMOTE ||
    callbackData === CALLBACK_MANAGER_WORK_FORMAT_HYBRID ||
    callbackData === CALLBACK_MANAGER_WORK_FORMAT_ONSITE
  );
}

function parseManagerWorkFormatCallback(callbackData: string): JobWorkFormat | null {
  if (callbackData === CALLBACK_MANAGER_WORK_FORMAT_REMOTE) {
    return "remote";
  }
  if (callbackData === CALLBACK_MANAGER_WORK_FORMAT_HYBRID) {
    return "hybrid";
  }
  if (callbackData === CALLBACK_MANAGER_WORK_FORMAT_ONSITE) {
    return "onsite";
  }
  return null;
}

function isYesConfirmation(textEnglish: string): boolean {
  const normalized = textEnglish.trim().toLowerCase();
  return normalized === "yes" || normalized === "y" || normalized === "confirm" || normalized === "ok";
}

function localizeInterviewMetaReply(
  defaultReply: string,
  metaType: "timing" | "language" | "format" | "privacy" | "other" | null,
  detectedLanguage: "en" | "ru" | "uk" | "other",
): string {
  if (detectedLanguage === "ru") {
    if (metaType === "timing") {
      return "Обычно это занимает пару минут. Я продолжу сразу после вашего ответа.";
    }
    if (metaType === "language") {
      return "Да, можно отвечать голосом на русском или украинском. Я расшифрую и продолжу.";
    }
    if (metaType === "format") {
      return "Можно ответить текстом или голосом. Нужен конкретный пример из практики.";
    }
    if (metaType === "privacy") {
      return "Профиль виден менеджеру только после вашего отклика, контакты только после взаимного согласия.";
    }
  }

  if (detectedLanguage === "uk") {
    if (metaType === "timing") {
      return "Зазвичай це займає кілька хвилин. Я продовжу одразу після вашої відповіді.";
    }
    if (metaType === "language") {
      return "Так, можна відповідати голосом російською або українською. Я розшифрую і продовжу.";
    }
    if (metaType === "format") {
      return "Можна відповісти текстом або голосом. Потрібен конкретний приклад з практики.";
    }
    if (metaType === "privacy") {
      return "Профіль видно менеджеру лише після вашого відгуку, контакти лише після взаємної згоди.";
    }
  }

  return defaultReply;
}

function isJdIntakeMetaFormatQuestion(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  if (!raw && !english) {
    return false;
  }

  const englishSignals = [
    "can i paste",
    "can i send text",
    "can i forward",
    "forward a file",
    "paste it as text",
    "can i paste text",
  ];
  if (englishSignals.some((signal) => english.includes(signal))) {
    return true;
  }

  return (
    raw.includes("можно текстом") ||
    raw.includes("можно переслать файл") ||
    raw.includes("можно вставить текст") ||
    raw.includes("можна текстом") ||
    raw.includes("можна переслати файл") ||
    raw.includes("можна вставити текст")
  );
}

function detectLikelyJobDescriptionText(textEnglish: string): { isLikely: boolean } {
  const text = textEnglish.trim();
  if (!text) {
    return { isLikely: false };
  }

  if (text.length >= 400) {
    return { isLikely: true };
  }

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const signalPatterns = [
    /responsibilities/i,
    /requirements/i,
    /tech stack/i,
    /we are hiring/i,
    /^role\b/i,
    /must have/i,
    /nice to have/i,
  ];
  let matchedSignals = 0;
  for (const pattern of signalPatterns) {
    if (pattern.test(text)) {
      matchedSignals += 1;
    }
  }

  const bulletLikeLines = lines.filter((line) => /^[-*•]\s+/.test(line)).length;

  if (lines.length >= 5 && matchedSignals >= 2) {
    return { isLikely: true };
  }
  if (bulletLikeLines >= 4) {
    return { isLikely: true };
  }

  return { isLikely: false };
}

function isClearlyTooShortForJd(textEnglish: string): boolean {
  const words = textEnglish
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return words.length > 0 && words.length < 8;
}

function isResumeIntakeMetaFormatQuestion(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  if (!raw && !english) {
    return false;
  }

  const englishSignals = [
    "can i paste",
    "can i send text",
    "can i forward",
    "forward a file",
    "paste it as text",
    "can i paste text",
  ];
  if (englishSignals.some((signal) => english.includes(signal))) {
    return true;
  }

  return (
    raw.includes("можно текстом") ||
    raw.includes("можно переслать файл") ||
    raw.includes("можно вставить текст") ||
    raw.includes("можна текстом") ||
    raw.includes("можна переслати файл") ||
    raw.includes("можна вставити текст")
  );
}

function isResumeIntakeLanguageQuestion(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();

  return (
    english.includes("can i answer in russian") ||
    english.includes("can i answer in ukrainian") ||
    english.includes("can i answer by voice") ||
    english.includes("voice language") ||
    raw.includes("можно на русском") ||
    raw.includes("можно на украинском") ||
    raw.includes("можно голосом") ||
    raw.includes("можна російською") ||
    raw.includes("можна українською") ||
    raw.includes("можна голосом")
  );
}

function detectLikelyResumeText(textEnglish: string): { isLikely: boolean } {
  const text = textEnglish.trim();
  if (!text) {
    return { isLikely: false };
  }

  if (text.length >= 400) {
    return { isLikely: true };
  }

  const resumeSignals = [
    /experience/i,
    /work experience/i,
    /skills/i,
    /projects/i,
    /education/i,
    /summary/i,
    /linkedin/i,
    /github/i,
  ];

  let matchedSignals = 0;
  for (const pattern of resumeSignals) {
    if (pattern.test(text)) {
      matchedSignals += 1;
    }
  }
  if (matchedSignals >= 2) {
    return { isLikely: true };
  }

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const yearLikeLines = lines.filter((line) => /\b(19|20)\d{2}\b/.test(line)).length;
  const roleLikeLines = lines.filter((line) =>
    /\b(engineer|developer|architect|manager|lead|intern|specialist)\b/i.test(line),
  ).length;
  const companyHints = lines.filter((line) => /\b(inc|llc|ltd|corp|company)\b/i.test(line)).length;

  if (lines.length >= 6 && yearLikeLines >= 2 && (roleLikeLines >= 2 || companyHints >= 2)) {
    return { isLikely: true };
  }

  return { isLikely: false };
}

function isClearlyTooShortForResume(textEnglish: string): boolean {
  const words = textEnglish
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return words.length > 0 && words.length < 8;
}
