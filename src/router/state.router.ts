import { recordFailure, recordLastRoute } from "../admin/admin-debug.store";
import { safeNotifyAdmin } from "../admin/admin-notifier";
import { logContext, Logger } from "../config/logger";
import { createHash } from "node:crypto";
import { RouterV2Decision, RouterV2Service } from "../ai/router.v2";
import { ActionRouterService } from "../ai/action-router/action-router.service";
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
import { CandidatePrescreenEngine } from "../interviews/prescreen/candidate-prescreen.engine";
import { JobPrescreenEngine } from "../interviews/prescreen/job-prescreen.engine";
import { CandidateNameExtractorService } from "../interviews/candidate-name-extractor.service";
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
  CandidatePrescreenVersion,
  JobPrescreenVersion,
  CandidateWorkMode,
  JobBudgetCurrency,
  JobBudgetPeriod,
  JobWorkFormat,
  ManagerMandatoryStep,
  UserRole,
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
import { TelegramReplyMarkup } from "../shared/types/telegram.types";
import {
  buildCandidateDecisionKeyboard,
  buildCandidateMatchingActionsKeyboard,
  buildCandidateMandatoryLocationKeyboard,
  buildCandidateWorkModeKeyboard,
  buildContactRequestKeyboard,
  buildDataDeletionConfirmKeyboard,
  buildManagerDecisionKeyboard,
  buildManagerMatchingActionsKeyboard,
  buildManagerWorkFormatKeyboard,
  buildRemoveReplyKeyboard,
  buildRoleSelectionKeyboard,
} from "../telegram/ui/keyboards";
import {
  candidateOnboardingMessage,
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
  dataDeletionCanceledMessage,
  dataDeletionConfirmPromptMessage,
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
  managerOnboardingMessage,
  managerMatchingActionsReadyMessage,
  managerMatchingBlockedByMandatoryMessage,
  managerCandidateSuggestionMessage,
  managerInterviewPreparationMessage,
  onboardingLearnHowItWorksMessage,
  ownContactRequiredMessage,
  missingInterviewContextMessage,
  processingDocumentMessage,
  stillProcessingDocumentMessage,
  stillProcessingAnswerMessage,
  questionMessage,
  candidateResumePrompt,
  managerJobPrompt,
  roleSelectionMessage,
  welcomeMessage,
  textOnlyReplyMessage,
  transcriptionFailedMessage,
  transcribingVoiceMessage,
  voiceTooLongMessage,
  dialogueLlmFallbackMessage,
  dialogueSkipAndMoveOnMessage,
} from "../telegram/ui/messages";
import { maybeReact } from "../telegram/reactions/reaction.service";
import { InterviewConfirmationService } from "../confirmations/interview-confirmation.service";
import { AlwaysOnRouterService } from "./always-on-router.service";
import { CallbackRouter } from "./callback.router";
import { UserRagContextService } from "./context/user-rag-context.service";
import type { DialogueOrchestrator } from "./dialogue/dialogue.orchestrator";
import type { LanguageService } from "./dialogue/language.service";
import type { ReplyComposerV2 } from "./dialogue/reply.composer";
import type { DialogueOrchestratorV2 } from "../dialogue/dialogue.orchestrator";
import { resolveRouterDispatchAction } from "./intent-action.dispatcher";
import { GatekeeperService } from "../core/state/gatekeeper/gatekeeper.service";
import { HELLY_ACTIONS } from "../core/state/actions";
import { TypedOnboardingCoordinator } from "./typed-onboarding.coordinator";

export class StateRouter {
  private readonly callbackRouter: CallbackRouter;
  private readonly typedOnboardingCoordinator: TypedOnboardingCoordinator;
  private readonly answerProcessingStatusAt = new Map<number, number>();

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
    private readonly routerV2Service: RouterV2Service,
    private readonly alwaysOnRouterService: AlwaysOnRouterService,
    private readonly interviewIntentRouterService: InterviewIntentRouterService,
    private readonly normalizationService: NormalizationService,
    private readonly interviewConfirmationService: InterviewConfirmationService,
    private readonly userRagContextService: UserRagContextService,
    private readonly candidateNameExtractorService: CandidateNameExtractorService,
    private readonly prescreenV2Enabled: boolean,
    private readonly jobPrescreenV2Enabled: boolean,
    private readonly candidatePrescreenEngine: CandidatePrescreenEngine,
    private readonly jobPrescreenEngine: JobPrescreenEngine,
    private readonly logger: Logger,
    private readonly conversationStateV2Enabled: boolean,
    private readonly dialogueOrchestratorV2: DialogueOrchestratorV2 | undefined,
    private readonly dialogueV2Enabled: boolean,
    private readonly replyComposerV2?: ReplyComposerV2,
    private readonly languageService?: LanguageService,
    private readonly dialogueOrchestrator?: DialogueOrchestrator,
    private readonly adminUserIds?: number[],
    private readonly enableTypedRoleSelectionRouter = false,
    private readonly enableTypedContactRouter = false,
    private readonly enableTypedCvRouter = false,
    private readonly enableTypedJdRouter = false,
    private readonly enableTypedCandidateMandatoryRouter = false,
    private readonly enableTypedManagerMandatoryRouter = false,
    private readonly enableTypedCandidateDecisionRouter = false,
    private readonly enableTypedManagerDecisionRouter = false,
    private readonly enableTypedCandidateReviewRouter = false,
    private readonly enableTypedManagerReviewRouter = false,
    private readonly actionRouterService?: ActionRouterService,
    private readonly gatekeeperService?: GatekeeperService,
  ) {
    this.callbackRouter = new CallbackRouter(
      this.stateService,
      this.statePersistenceService,
      this.telegramClient,
      this.decisionService,
      this.notificationEngine,
      this.contactExchangeService,
    );
    this.typedOnboardingCoordinator = new TypedOnboardingCoordinator(
      {
        enableTypedRoleSelectionRouter: this.enableTypedRoleSelectionRouter,
        enableTypedContactRouter: this.enableTypedContactRouter,
        enableTypedCvRouter: this.enableTypedCvRouter,
        enableTypedJdRouter: this.enableTypedJdRouter,
        enableTypedCandidateMandatoryRouter: this.enableTypedCandidateMandatoryRouter,
        enableTypedManagerMandatoryRouter: this.enableTypedManagerMandatoryRouter,
        enableTypedCandidateDecisionRouter: this.enableTypedCandidateDecisionRouter,
        enableTypedManagerDecisionRouter: this.enableTypedManagerDecisionRouter,
        enableTypedCandidateReviewRouter: this.enableTypedCandidateReviewRouter,
        enableTypedManagerReviewRouter: this.enableTypedManagerReviewRouter,
      },
      this.actionRouterService,
      this.gatekeeperService,
      this.logger,
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
      conversationIntent: routed.decision.conversation_intent,
      action: resolveRouterDispatchAction(routed.decision, session),
    });

    if (update.kind === "text") {
      this.stateService.setTurnContext(update.userId, {
        lastUserMessage: update.text,
        language:
          routed.detectedLanguage === "ru" || routed.detectedLanguage === "uk"
            ? routed.detectedLanguage
            : "en",
      });
    }

    switch (update.kind) {
      case "text":
        {
          if (this.adminUserIds?.length && this.adminUserIds.includes(session.userId)) {
            const trimmed = update.text.trim();
            const match = trimmed.match(/^\/(debug_\w+)(?:\s+(\d+))?$/);
            if (match) {
              const cmd = match[1] as
                | "debug_chat_id"
                | "debug_state"
                | "debug_profile"
                | "debug_last_route"
                | "debug_matches"
                | "debug_active_job"
                | "debug_failures";
              const optionalUserId = match[2] ? parseInt(match[2], 10) : undefined;
              await this.handleAdminDebugCommand(update, session, cmd, optionalUserId);
              break;
            }
          }
          const lang =
            routed.detectedLanguage === "ru" || routed.detectedLanguage === "uk"
              ? routed.detectedLanguage
              : "en";
          if (
            this.conversationStateV2Enabled &&
            this.dialogueOrchestratorV2 &&
            isPrescreenOrOnboardingState(session)
          ) {
            const ctx = {
              userId: update.userId,
              chatId: update.chatId,
              session,
              userMessage: update.text,
              language: lang as "en" | "ru" | "uk",
            };
            let result: Awaited<ReturnType<NonNullable<typeof this.dialogueOrchestratorV2>["handleUserMessage"]>>;
            try {
              result = await this.dialogueOrchestratorV2.handleUserMessage(ctx);
            } catch (err) {
              recordFailure(session.userId, "llm_fail", {
                source: "dialogue_orchestrator",
                detail: err instanceof Error ? err.message : String(err),
              });
              safeNotifyAdmin("error", "Dialogue orchestrator failed", undefined, {
                userId: session.userId,
                chatId: session.chatId,
                state: session.state,
                phase: session.dialoguePhase,
                updateId: update.updateId,
                errorStack: err instanceof Error ? err.stack : undefined,
              });
              await this.sendBotMessage(
                session.userId,
                update.chatId,
                dialogueLlmFallbackMessage(lang as "en" | "ru" | "uk"),
                { source: "state_router.dialogue_v2.fallback" },
              );
              break;
            }
            const replyHash = hashMessageText(result.replyText);
            if (session.lastBotMessageHash && replyHash === session.lastBotMessageHash) {
              result = this.dialogueOrchestratorV2.buildRepeatLoopReply(lang);
            }
            const updated = { ...session, ...result.nextStatePatch };
            this.stateService.setSession(updated);
            this.logger.info("dialogue.orchestrator_v2.result", {
              userId: update.userId,
              intent: result.intent,
              phaseTransition: result.phaseTransition,
              questionsAskedCount: result.questionsAskedCount,
              promptName: result.promptName,
              parseSuccess: result.parseSuccess,
              matchCardsCount: result.matchCards?.length ?? 0,
            });
            if (result.matchAction) {
              try {
                await this.callbackRouter.executeMatchAction(
                  update.userId,
                  update.chatId,
                  result.matchAction,
                );
                await this.sendBotMessage(update.userId, update.chatId, result.replyText, {
                  source: "state_router.dialogue_v2.match_action",
                });
              } catch (err) {
                this.logger.warn("dialogue_v2.match_action failed", {
                  userId: update.userId,
                  matchAction: result.matchAction,
                  error: err instanceof Error ? err.message : String(err),
                });
                await this.sendBotMessage(update.userId, update.chatId, result.replyText, {
                  source: "state_router.dialogue_v2.match_action_fallback",
                });
              }
            } else if (result.matchCards && result.matchCards.length > 0) {
              await this.sendBotMessage(update.userId, update.chatId, result.replyText, {
                source: "state_router.dialogue_v2.matching_intro",
              });
              for (const card of result.matchCards) {
                const replyMarkup = card.isCandidateCard
                  ? buildCandidateDecisionKeyboard(card.matchId)
                  : buildManagerDecisionKeyboard(card.matchId);
                await this.sendBotMessage(update.userId, update.chatId, card.text, {
                  source: "state_router.dialogue_v2.match_card",
                  replyMarkup,
                });
              }
            } else {
              await this.sendBotMessage(update.userId, update.chatId, result.replyText, {
                source: "state_router.dialogue_v2",
              });
            }
            break;
          }
          const throughRouterV2 = await this.routeTextThroughRouterV2({
            update,
            session,
            decision: routed.decision,
            textEnglish: routed.textEnglish ?? update.text,
            detectedLanguage: routed.detectedLanguage ?? detectLanguageQuick(update.text),
          });
          if (!throughRouterV2) {
            break;
          }
          await this.dispatchTextByIntentAction({
            update,
            session,
            decision: throughRouterV2.decision,
            textEnglish: throughRouterV2.textEnglish,
            detectedLanguage: throughRouterV2.detectedLanguage,
            routerV2Decision: throughRouterV2.routerV2Decision,
          });
        }
        break;
      case "document":
        await this.handleDocumentUpdate(update);
        break;
      case "voice":
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
        action: resolveRouterDispatchAction(routed.decision, session),
        conversation_intent: routed.decision.conversation_intent,
        prompt_name: "always_on_router_v1",
        model_name: this.llmClient.getModelName(),
        did_call_llm_router: true,
        did_call_task_prompt: didRouteLikelyCallTaskPrompt(routed.decision.route),
        ok: true,
      },
    );

    this.stateService.markUpdateProcessed(session.userId, update.updateId);
    this.stateService.clearTurnContext(update.userId);
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
    knownUserName?: string | null;
    ragContext?: string | null;
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
    const rag = await this.userRagContextService.buildRouterContext(session);

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
        knownUserName: rag.knownUserName,
        userRagContext: rag.ragContext,
      });
      return {
        decision,
        textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
        detectedLanguage,
        knownUserName: rag.knownUserName,
        ragContext: rag.ragContext,
      };
    } catch (error) {
      recordFailure(session.userId, "llm_fail", {
        source: "always_on_router",
        detail: error instanceof Error ? error.message : String(error),
      });
      safeNotifyAdmin("error", "LLM classify failed", undefined, {
        userId: session.userId,
        chatId: session.chatId,
        state: session.state,
        updateId: update.updateId,
        promptName: "always_on_router",
        errorStack: error instanceof Error ? error.stack : undefined,
      });
      this.logger.warn("always-on router failed, sending safe fallback", {
        updateId: update.updateId,
        telegramUserId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      const deterministicFallback = this.buildDeterministicRouteFallback(update);
      if (deterministicFallback) {
        return {
          decision: deterministicFallback,
          textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
          detectedLanguage,
          knownUserName: rag.knownUserName,
          ragContext: rag.ragContext,
        };
      }
      if (update.kind === "text" || update.kind === "callback") {
        const fallbackLang =
          detectedLanguage === "ru" || detectedLanguage === "uk" ? detectedLanguage : "en";
        return {
          decision: {
            route: "OTHER",
            conversation_intent: "OTHER",
            meta_type: null,
            control_type: null,
            matching_intent: null,
            reply: dialogueLlmFallbackMessage(fallbackLang),
            should_advance: false,
            should_process_text_as_document: false,
          },
          textEnglish: textEnglish?.trim() ? textEnglish.trim() : null,
          detectedLanguage,
          knownUserName: rag.knownUserName,
          ragContext: rag.ragContext,
        };
      }
      await this.sendRouterReplyWithLoopGuard(
        session,
        update.chatId,
        dialogueLlmFallbackMessage("en"),
      );
      return null;
    }
  }

  private async handleSkipContact(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    this.stateService.clearContactInfo(session.userId);
    this.stateService.setAwaitingContactChoice(session.userId, false);
    await this.usersRepository.setContactShared(session.userId, false);
    await this.sendBotMessage(session.userId, update.chatId, contactSkippedMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
    if (session.state === "role_selection") {
      await this.sendBotMessage(session.userId, update.chatId, roleSelectionMessage(), {
        replyMarkup: buildRoleSelectionKeyboard(),
        kind: "secondary",
      });
    }
  }

  private async dispatchTextByIntentAction(input: {
    update: Extract<NormalizedUpdate, { kind: "text" }>;
    session: UserSessionState;
    decision: AlwaysOnRouterDecision;
    textEnglish: string;
    detectedLanguage: "en" | "ru" | "uk" | "other";
    routerV2Decision?: RouterV2Decision;
  }): Promise<void> {
    const { update, session, decision, textEnglish, detectedLanguage, routerV2Decision } = input;
    void resolveRouterDispatchAction(decision, session);
    // Global intent→action dispatch layer. Interview safety checks still run inside dispatchTextRoute.
    await this.dispatchTextRoute(
      update,
      session,
      decision,
      textEnglish,
      detectedLanguage,
      routerV2Decision,
    );
  }

  private async routeTextThroughRouterV2(input: {
    update: Extract<NormalizedUpdate, { kind: "text" }>;
    session: UserSessionState;
    decision: AlwaysOnRouterDecision;
    textEnglish: string;
    detectedLanguage: "en" | "ru" | "uk" | "other";
  }): Promise<{
    decision: AlwaysOnRouterDecision;
    textEnglish: string;
    detectedLanguage: "en" | "ru" | "uk" | "other";
    routerV2Decision: RouterV2Decision;
  } | null> {
    const { update, session } = input;
    const routerV2 = await this.routerV2Service.classify({
      userMessage: update.text,
      currentState: session.state,
      partialProfile: buildRouterV2PartialProfile(session),
      lastMessages: buildRouterV2LastMessages(session, update.text),
      role: resolveRouterV2Role(session),
    });

    this.logger.debug("router.v2.intent", {
      updateId: update.updateId,
      telegramUserId: session.userId,
      parseSuccess: routerV2.parseSuccess,
      intent: routerV2.decision.intent,
      nextAction: routerV2.decision.next_action,
    });

    if (!routerV2.parseSuccess) {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        routerV2.decision.assistant_message,
        { source: "state_router.system.router_v2_fallback" },
      );
      return null;
    }

    const decision = this.applyRouterV2NextAction(
      input.decision,
      routerV2.decision,
      session,
    );

    return {
      decision,
      textEnglish: input.textEnglish,
      detectedLanguage: input.detectedLanguage,
      routerV2Decision: routerV2.decision,
    };
  }

  private applyRouterV2NextAction(
    decision: AlwaysOnRouterDecision,
    routerV2Decision: RouterV2Decision,
    session: UserSessionState,
  ): AlwaysOnRouterDecision {
    const nextAction = routerV2Decision.next_action;
    const assistantMessage = routerV2Decision.assistant_message;
    const safeReply = assistantMessage.trim() || decision.reply;
    if (routerV2Decision.intent === "status_request") {
      return {
        ...decision,
        route: "OTHER",
        conversation_intent: "OTHER",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: safeReply,
        should_advance: false,
        should_process_text_as_document: false,
      };
    }
    if (nextAction === "extract_resume") {
      return {
        ...decision,
        route: "RESUME_TEXT",
        conversation_intent: "OTHER",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: safeReply,
        should_advance: false,
        should_process_text_as_document: true,
      };
    }
    if (nextAction === "extract_job") {
      return {
        ...decision,
        route: "JD_TEXT",
        conversation_intent: "OTHER",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: safeReply,
        should_advance: false,
        should_process_text_as_document: true,
      };
    }
    if (nextAction === "ask_next_question" && isInterviewingState(session.state)) {
      return {
        ...decision,
        route: "INTERVIEW_ANSWER",
        conversation_intent: "ANSWER",
        meta_type: null,
        control_type: null,
        matching_intent: null,
        reply: safeReply,
        should_advance: true,
        should_process_text_as_document: false,
      };
    }
    if (nextAction === "run_matching") {
      return {
        ...decision,
        route: "MATCHING_COMMAND",
        conversation_intent: "MATCHING",
        meta_type: null,
        control_type: null,
        matching_intent: "run",
        reply: safeReply,
        should_advance: false,
        should_process_text_as_document: false,
      };
    }
    return decision;
  }

  private async dispatchTextRoute(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
    decision: AlwaysOnRouterDecision,
    normalizedEnglishText: string,
    detectedLanguage: "en" | "ru" | "uk" | "other",
    routerV2Decision?: RouterV2Decision,
  ): Promise<void> {
    const rawText = update.text.trim();
    const normalizedLower = normalizedEnglishText.trim().toLowerCase();
    const mandatoryUpdateCommand = detectCandidateMandatoryUpdateCommand(normalizedLower);
    const managerMandatoryUpdateCommand = detectManagerMandatoryUpdateCommand(normalizedLower);
    const explicitMatchingIntent = detectExplicitMatchingIntent(rawText, normalizedLower, session.role ?? null);

    if (routerV2Decision?.intent === "status_request") {
      await this.sendRouterReplyWithLoopGuard(
        session,
        update.chatId,
        await this.buildStatusReplyForUser(session),
      );
      return;
    }

    if (isStartCommand(rawText) || decision.control_type === "restart") {
      await this.restartFlow(update);
      return;
    }

    if (session.pendingDataDeletionConfirmation) {
      await this.handlePendingDataDeletionConfirmation(update, session, rawText, normalizedEnglishText);
      return;
    }

    if (explicitMatchingIntent && decision.route !== "MATCHING_COMMAND") {
      await this.handleMatchingIntentRoute({
        session,
        chatId: update.chatId,
        matchingIntent: explicitMatchingIntent,
        reply: decision.reply,
      });
      return;
    }

    if (isSkipContactForNow(rawText)) {
      await this.handleSkipContact(update, session);
      return;
    }

    const explicitContactIntent = isContactShareTextIntent(rawText, normalizedEnglishText);
    const extractedPhone = extractPhoneNumber(rawText);
    if (isAwaitingContactChoice(session)) {
      const typedContactResult = await this.typedOnboardingCoordinator.attemptContactIdentity({
        session,
        userMessage: normalizedEnglishText,
        awaitingContactChoice: session.awaitingContactChoice === true,
      });
      if (typedContactResult.accepted) {
        if (extractedPhone && canAcceptTextContactByState(session.state)) {
          await this.saveTextContact(session, update.chatId, extractedPhone);
          return;
        }
        this.logger.debug("typed_contact.path", {
          userId: session.userId,
          path: "typed",
          action: typedContactResult.action,
          outcome: "request_phone_text",
        });
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          "Please send your phone number in one message. Example, +380991112233. Or type Skip for now.",
          { replyMarkup: buildContactRequestKeyboard() },
        );
        return;
      }
    }
    if (extractedPhone && canAcceptTextContactByState(session.state)) {
      await this.saveTextContact(session, update.chatId, extractedPhone);
      return;
    }
    if (explicitContactIntent && !extractedPhone) {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "Please send your phone number in one message. Example, +380991112233. Or type Skip for now.",
        { replyMarkup: buildContactRequestKeyboard() },
      );
      return;
    }

    if (isDataDeletionCommand(rawText, normalizedEnglishText)) {
      await this.requestDataDeletionConfirmation(update, session);
      return;
    }

    if (session.state === "role_selection") {
      if (isAwaitingContactChoice(session)) {
        const reminder = contactRequestMessage();
        if ((session.lastBotMessage ?? "").trim() !== reminder.trim()) {
          await this.sendBotMessage(
            session.userId,
            update.chatId,
            reminder,
            { replyMarkup: buildContactRequestKeyboard() },
          );
        }
        return;
      }
      if (isRoleLearnHowItWorksText(rawText, normalizedEnglishText)) {
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          onboardingLearnHowItWorksMessage(),
          { replyMarkup: buildRoleSelectionKeyboard() },
        );
        return;
      }
      const typedRoleResult = await this.typedOnboardingCoordinator.attemptRoleSelection({
        session,
        userMessage: normalizedEnglishText,
      });
      if (typedRoleResult.accepted && typedRoleResult.action === HELLY_ACTIONS.SELECT_ROLE_CANDIDATE) {
        await this.startRoleFlowFromText(session, update.chatId, "candidate");
        return;
      }

      if (typedRoleResult.accepted && typedRoleResult.action === HELLY_ACTIONS.SELECT_ROLE_MANAGER) {
        await this.startRoleFlowFromText(session, update.chatId, "manager");
        return;
      }
      const selectedRole = detectRoleSelectionFromText(rawText, normalizedEnglishText);
      if (selectedRole) {
        await this.startRoleFlowFromText(session, update.chatId, selectedRole);
        return;
      }
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "Please choose your role first, I am a Candidate or I am Hiring.",
        { replyMarkup: buildRoleSelectionKeyboard() },
      );
      return;
    }

    if (session.state === "extracting_resume" || session.state === "extracting_job") {
      if (decision.route === "CONTROL") {
        await this.handleControlRoute({
          update,
          session,
          decision,
        });
        return;
      }
      const statusReply = getExtractingStatusReply(session.state, decision.meta_type);
      await this.sendRouterReplyWithLoopGuard(session, update.chatId, statusReply);
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
      await this.maybeRunTypedCandidateMandatoryRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
      await this.handleCandidateMandatoryTextInput(session, update.chatId, rawText, normalizedEnglishText);
      return;
    }

    if (session.state === "manager_mandatory_fields") {
      await this.maybeRunTypedManagerMandatoryRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
      await this.handleManagerMandatoryTextInput(session, update.chatId, normalizedEnglishText);
      return;
    }

    if (session.state === "waiting_candidate_decision") {
      await this.maybeRunTypedCandidateDecisionRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
    }

    if (session.state === "waiting_manager_decision") {
      await this.maybeRunTypedManagerDecisionRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
    }

    if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
      const isCandidatePrescreenV2 = this.isCandidatePrescreenV2Session(session);
      const isManagerPrescreenV2 = this.isManagerPrescreenV2Session(session);
      const isAnyPrescreenV2 = isCandidatePrescreenV2 || isManagerPrescreenV2;

      if (isEnglishPreferenceSignal(rawText, normalizedEnglishText)) {
        this.stateService.setPreferredLanguage(session.userId, "en");
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          "Got it, we will continue in English. Please answer the current question, text or voice is fine.",
          { source: "state_router.system.interview_language_pref" },
        );
        return;
      }

      if (isInterviewFinishCommand(rawText, normalizedEnglishText)) {
        const completion = await this.interviewEngine.finishInterviewNow(session);
        if (isAnyPrescreenV2) {
          this.stateService.transition(session.userId, completion.completedState);
          this.stateService.clearCurrentQuestionIndex(session.userId);
          if (isCandidatePrescreenV2) {
            this.stateService.clearPrescreenQuestionIndex(session.userId);
          }
          if (isManagerPrescreenV2) {
            this.stateService.clearJobPrescreenQuestionIndex(session.userId);
          }
          await this.sendBotMessage(
            session.userId,
            update.chatId,
            isCandidatePrescreenV2
              ? "Okay, we can stop here. I saved your partial profile. You can ask me to find jobs anytime."
              : "Okay, we can stop here. I saved your partial job profile. You can ask me to find candidates anytime.",
            {
              source: isCandidatePrescreenV2
                ? "state_router.system.prescreen_v2_stop"
                : "state_router.system.job_prescreen_v2_stop",
            },
          );
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          if (isCandidatePrescreenV2) {
            await this.startCandidateMandatoryFieldsFlow(latestSession, update.chatId, {
              showIntro: true,
            });
          } else {
            await this.startManagerMandatoryFieldsFlow(latestSession, update.chatId, {
              showIntro: true,
              runMatchingAfterComplete: true,
            });
          }
        } else {
          await this.handleInterviewCompletedState(session, update.chatId, completion);
        }
        return;
      }

      if (isInterviewSkipCommand(normalizedEnglishText)) {
        const skipResult = isCandidatePrescreenV2
          ? await this.candidatePrescreenEngine.skipCurrentQuestion(session)
          : isManagerPrescreenV2
          ? await this.jobPrescreenEngine.skipCurrentQuestion(session)
          : await this.interviewEngine.skipCurrentQuestion(session);
        this.stateService.resetInterviewNoAnswerCounter(session.userId);
        if (skipResult.kind === "next_question") {
          const nextQuestionText = await this.formatInterviewQuestionForDelivery(
            session,
            skipResult.questionText,
            skipResult.questionIndex,
            false,
          );
          await this.sendBotMessage(
            session.userId,
            session.chatId,
            skipResult.isFollowUp
              ? nextQuestionText
              : questionMessage(skipResult.questionIndex, nextQuestionText),
          );
          return;
        }
        if (skipResult.kind === "reanswer_required") {
          await this.sendBotMessage(session.userId, session.chatId, skipResult.message);
          return;
        }
        if (isAnyPrescreenV2) {
          const completion = await this.interviewEngine.finishInterviewNow(session);
          this.stateService.transition(session.userId, completion.completedState);
          this.stateService.clearCurrentQuestionIndex(session.userId);
          if (isCandidatePrescreenV2) {
            this.stateService.clearPrescreenQuestionIndex(session.userId);
          }
          if (isManagerPrescreenV2) {
            this.stateService.clearJobPrescreenQuestionIndex(session.userId);
          }
          await this.sendBotMessage(
            session.userId,
            session.chatId,
            skipResult.completionMessage,
            {
              source: isCandidatePrescreenV2
                ? "state_router.system.prescreen_v2_completed"
                : "state_router.system.job_prescreen_v2_completed",
            },
          );
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          if (isCandidatePrescreenV2) {
            await this.startCandidateMandatoryFieldsFlow(latestSession, session.chatId, {
              showIntro: true,
            });
          } else {
            await this.startManagerMandatoryFieldsFlow(latestSession, session.chatId, {
              showIntro: true,
              runMatchingAfterComplete: true,
            });
          }
        } else {
          const completion =
            skipResult as Extract<
              Awaited<ReturnType<InterviewEngine["skipCurrentQuestion"]>>,
              { kind: "completed" }
            >;
          await this.handleInterviewCompletedState(session, session.chatId, completion);
        }
        return;
      }

      const currentQuestion = resolveCurrentInterviewQuestionText(session);
      if (!currentQuestion) {
        await this.sendBotMessage(session.userId, update.chatId, missingInterviewContextMessage());
        return;
      }
      if (session.state === "interviewing_candidate") {
        await this.maybeRunTypedCandidateReviewRouter({
          session,
          userMessage: normalizedEnglishText,
          currentQuestion,
        });
      }
      if (session.state === "interviewing_manager") {
        await this.maybeRunTypedManagerReviewRouter({
          session,
          userMessage: normalizedEnglishText,
          currentQuestion,
        });
      }
      const interviewRag = await this.userRagContextService.buildInterviewContext(
        session,
        currentQuestion,
      );

      const intentDecision = await this.interviewIntentRouterService.classify({
        currentState: session.state,
        userRole: session.state === "interviewing_candidate" ? "candidate" : "manager",
        currentQuestion,
        userMessageEnglish: normalizedEnglishText,
        lastBotMessage: session.lastBotMessage ?? null,
        knownUserName: interviewRag.knownUserName,
        userRagContext: interviewRag.ragContext,
      });

      if (
        intentDecision.intent === "META" &&
        intentDecision.meta_type === "language" &&
        isAskBotQuestionInPreferredLanguage(rawText, normalizedEnglishText)
      ) {
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          buildAskBotQuestionInPreferredLanguageReply(detectedLanguage),
        );
        return;
      }

      if (isRemainingQuestionsMetaQuery(rawText, normalizedEnglishText)) {
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          buildInterviewRemainingQuestionsReply(session, detectedLanguage),
        );
        return;
      }

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
        if (intentDecision.control_type === "stop" || (isAnyPrescreenV2 && intentDecision.control_type === "pause")) {
          const completion = await this.interviewEngine.finishInterviewNow(session);
          if (isAnyPrescreenV2) {
            this.stateService.transition(session.userId, completion.completedState);
            this.stateService.clearCurrentQuestionIndex(session.userId);
            if (isCandidatePrescreenV2) {
              this.stateService.clearPrescreenQuestionIndex(session.userId);
            }
            if (isManagerPrescreenV2) {
              this.stateService.clearJobPrescreenQuestionIndex(session.userId);
            }
            await this.sendBotMessage(
              session.userId,
              update.chatId,
              isCandidatePrescreenV2
                ? "Okay, we can pause here. I saved your partial profile. You can ask me to find jobs anytime."
                : "Okay, we can pause here. I saved your partial job profile. You can ask me to find candidates anytime.",
              {
                source: isCandidatePrescreenV2
                  ? "state_router.system.prescreen_v2_pause"
                  : "state_router.system.job_prescreen_v2_pause",
              },
            );
            const latestSession = this.stateService.getSession(session.userId) ?? session;
            if (isCandidatePrescreenV2) {
              await this.startCandidateMandatoryFieldsFlow(latestSession, update.chatId, {
                showIntro: true,
              });
            } else {
              await this.startManagerMandatoryFieldsFlow(latestSession, update.chatId, {
                showIntro: true,
                runMatchingAfterComplete: true,
              });
            }
          } else {
            await this.handleInterviewCompletedState(session, update.chatId, completion);
          }
          return;
        }
        await this.sendRouterReplyWithLoopGuard(
          session,
          update.chatId,
          isAnyPrescreenV2
            ? localizePrescreenMetaReply(intentDecision.reply, detectedLanguage)
            : localizeInterviewMetaReply(intentDecision.reply, intentDecision.meta_type, detectedLanguage),
        );
        return;
      }

      await this.sendRouterReplyWithLoopGuard(
        session,
        update.chatId,
        isAnyPrescreenV2
          ? localizePrescreenMetaReply(intentDecision.reply, detectedLanguage)
          : localizeInterviewMetaReply(intentDecision.reply, intentDecision.meta_type, detectedLanguage),
      );
      return;
    }

    if (session.state === "waiting_job") {
      await this.maybeRunTypedJdRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
      // Short messages are never treated as job description — insist on full JD or file
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

      if (session.jobDescriptionText?.trim()) {
        if (isRetryProcessingSignal(rawText, normalizedEnglishText)) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "I already have your job description. Restarting processing now.",
          );
          await this.handlePastedDocumentText(update, {
            sourceTextOriginal: session.jobDescriptionText,
            sourceTextEnglish: session.jobDescriptionText,
          });
          return;
        }
        if (decision.meta_type === "timing") {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "I already have your job description. If the interview did not start, type retry processing and I will continue without reupload.",
          );
          return;
        }
      }

      if (decision.route === "CONTROL") {
        await this.handleControlRoute({
          update,
          session,
          decision,
        });
        return;
      }

      if (decision.route === "META") {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
        return;
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

      if (decision.route === "JD_TEXT" && decision.should_process_text_as_document) {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
        await this.handlePastedDocumentText(update, {
          sourceTextOriginal: rawText,
          sourceTextEnglish: normalizedEnglishText,
        });
        return;
      }

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
    }

    if (session.state === "waiting_resume") {
      await this.maybeRunTypedCvRouter({
        session,
        userMessage: normalizedEnglishText,
        source: "text",
      });
      // Short messages are never treated as resume — insist on full paste or file
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

      if (session.candidateResumeText?.trim()) {
        if (isRetryProcessingSignal(rawText, normalizedEnglishText)) {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "I already have your resume. Restarting processing now.",
          );
          await this.handlePastedDocumentText(update, {
            sourceTextOriginal: session.candidateResumeText,
            sourceTextEnglish: session.candidateResumeText,
          });
          return;
        }
        if (decision.meta_type === "timing") {
          await this.sendRouterReplyWithLoopGuard(
            session,
            update.chatId,
            "I already have your resume. If the interview did not start, type retry processing and I will continue without reupload.",
          );
          return;
        }
      }

      if (decision.route === "CONTROL") {
        await this.handleControlRoute({
          update,
          session,
          decision,
        });
        return;
      }

      if (decision.route === "META") {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
        return;
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

      if (decision.route === "RESUME_TEXT" && decision.should_process_text_as_document) {
        await this.sendRouterReplyWithLoopGuard(session, update.chatId, decision.reply);
        await this.handlePastedDocumentText(update, {
          sourceTextOriginal: rawText,
          sourceTextEnglish: normalizedEnglishText,
        });
        return;
      }

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

  private async handleInterviewCompletedState(
    session: UserSessionState,
    chatId: number,
    result: Extract<Awaited<ReturnType<InterviewEngine["skipCurrentQuestion"]>>, { kind: "completed" }>,
  ): Promise<void> {
    this.stateService.transition(session.userId, result.completedState);
    this.stateService.resetAnswersSinceConfirm(session.userId);
    await this.sendBotMessage(session.userId, chatId, result.completionMessage, {
      source: "state_router.system.interview_completed",
    });

    const needsMandatoryFlow =
      result.completedState === "candidate_profile_ready" ||
      result.completedState === "job_profile_ready";
    if (result.followupMessage && !needsMandatoryFlow) {
      await this.sendBotMessage(session.userId, chatId, result.followupMessage, {
        kind: "secondary",
        source: "state_router.system.interview_completed_followup",
      });
    }
    if (result.completedState === "candidate_profile_ready") {
      const latestSession = this.stateService.getSession(session.userId) ?? session;
      await this.startCandidateMandatoryFieldsFlow(latestSession, chatId, {
        showIntro: true,
      });
      return;
    }
    if (result.completedState === "job_profile_ready") {
      const latestSession = this.stateService.getSession(session.userId) ?? session;
      await this.startManagerMandatoryFieldsFlow(latestSession, chatId, {
        showIntro: true,
        runMatchingAfterComplete: true,
      });
    }
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
      const userFlags = await this.usersRepository.getUserFlags(session.userId);
      if (!userFlags.contactShared) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          "Before I can match you, please share your Telegram contact.",
        );
        await this.sendBotMessage(session.userId, chatId, contactRequestMessage(), {
          source: "state_router.system.matching_contact_required",
          replyMarkup: buildContactRequestKeyboard(),
          kind: "secondary",
        });
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

      if (userFlags.matchingPaused || !userFlags.autoMatchingEnabled) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          "Matching is paused. Type resume matching if you want me to search again.",
        );
        return;
      }
      const readiness =
        session.role === "candidate"
          ? await this.matchingEngine.checkCandidateMatchingReadiness(session.userId)
          : await this.matchingEngine.checkManagerMatchingReadiness(session.userId);
      if (!readiness.ready) {
        await this.sendRouterReplyWithLoopGuard(
          session,
          chatId,
          "I need your resume and a few quick answers first. Send your resume file or type your key experience.",
        );
        return;
      }

      const run =
        session.role === "candidate"
          ? await this.matchingEngine.runForCandidate(String(session.userId))
          : await this.matchingEngine.runForManager(String(session.userId));
      const sentCards = await this.showTopMatchesWithActions(session, chatId);
      if (!sentCards) {
        await this.sendRouterReplyWithLoopGuard(session, chatId, run.message);
      }
      return;
    }

    await this.sendRouterReplyWithLoopGuard(session, chatId, reply);
  }

  private async maybeRunTypedCandidateReviewRouter(input: {
    session: UserSessionState;
    userMessage: string;
    currentQuestion: string;
  }): Promise<void> {
    const currentQuestionIndex = resolveCurrentQuestionIndexValue(input.session);
    const hasFinalAnswers = (input.session.answers ?? []).some((item) => item.status !== "draft");
    await this.typedOnboardingCoordinator.attemptCandidateReview({
      session: input.session,
      userMessage: input.userMessage,
      currentQuestion: input.currentQuestion,
      currentQuestionIndex,
      hasFinalAnswers,
    });
  }

  private async maybeRunTypedCandidateMandatoryRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "location";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptCandidateMandatory({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async maybeRunTypedManagerMandatoryRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptManagerMandatory({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async maybeRunTypedCandidateDecisionRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptCandidateDecision({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async maybeRunTypedManagerDecisionRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptManagerDecision({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async maybeRunTypedManagerReviewRouter(input: {
    session: UserSessionState;
    userMessage: string;
    currentQuestion: string;
  }): Promise<void> {
    const currentQuestionIndex = resolveCurrentQuestionIndexValue(input.session);
    const hasFinalAnswers = (input.session.answers ?? []).some((item) => item.status !== "draft");
    await this.typedOnboardingCoordinator.attemptManagerReview({
      session: input.session,
      userMessage: input.userMessage,
      currentQuestion: input.currentQuestion,
      currentQuestionIndex,
      hasFinalAnswers,
    });
  }

  private async maybeRunTypedCvRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "document" | "voice";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptCandidateCvIntake({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async maybeRunTypedJdRouter(input: {
    session: UserSessionState;
    userMessage: string;
    source: "text" | "document" | "voice";
  }): Promise<void> {
    await this.typedOnboardingCoordinator.attemptManagerJdIntake({
      session: input.session,
      userMessage: input.userMessage,
      source: input.source,
    });
  }

  private async restartFlow(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    options?: { includeWelcome?: boolean },
  ): Promise<void> {
    const session = this.stateService.reset(update.userId, update.chatId, update.username);
    this.stateService.setAwaitingContactChoice(session.userId, true);
    if (options?.includeWelcome !== false) {
      await this.sendBotMessage(session.userId, update.chatId, welcomeMessage());
    }
    await this.sendBotMessage(session.userId, update.chatId, contactRequestMessage(), {
      replyMarkup: buildContactRequestKeyboard(),
      kind: "secondary",
    });
  }

  private async requestDataDeletionConfirmation(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    this.stateService.setPendingDataDeletionConfirmation(session.userId, true);
    await this.sendBotMessage(session.userId, update.chatId, dataDeletionConfirmPromptMessage(), {
      source: "state_router.system.data_deletion_confirm",
      replyMarkup: buildDataDeletionConfirmKeyboard(),
    });
  }

  private async handlePendingDataDeletionConfirmation(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
    rawText: string,
    normalizedEnglishText: string,
  ): Promise<void> {
    if (isDataDeletionConfirmIntent(rawText, normalizedEnglishText)) {
      await this.handleDataDeletionAndRestart(update, session);
      return;
    }

    if (isDataDeletionCancelIntent(rawText, normalizedEnglishText)) {
      this.stateService.setPendingDataDeletionConfirmation(session.userId, false);
      await this.sendBotMessage(session.userId, update.chatId, dataDeletionCanceledMessage(), {
        source: "state_router.system.data_deletion_cancel",
        replyMarkup: buildRemoveReplyKeyboard(),
      });
      return;
    }

    await this.sendBotMessage(session.userId, update.chatId, dataDeletionConfirmPromptMessage(), {
      source: "state_router.system.data_deletion_confirm_repeat",
      replyMarkup: buildDataDeletionConfirmKeyboard(),
    });
  }

  private async handleDataDeletionAndRestart(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    const result = await this.dataDeletionService.requestDeletion({
      telegramUserId: session.userId,
      telegramUsername: session.username,
      reason: "user_text_command",
    });

    this.stateService.setPendingDataDeletionConfirmation(session.userId, false);
    this.stateService.clearContactInfo(session.userId);
    await this.sendBotMessage(session.userId, update.chatId, result.confirmationMessage, {
      replyMarkup: buildRemoveReplyKeyboard(),
      source: "state_router.system.data_deletion",
    });
    await this.restartFlow(update, { includeWelcome: false });
  }

  private buildDeterministicRouteFallback(update: NormalizedUpdate): AlwaysOnRouterDecision | null {
    if (update.kind === "document") {
      return {
        route: "DOC",
        conversation_intent: "OTHER",
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
        conversation_intent: "OTHER",
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
        conversation_intent: "COMMAND",
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

    const intakeState = session.state;
    const extractingState = intakeState === "waiting_resume" ? "extracting_resume" : "extracting_job";
    this.stateService.transition(update.userId, extractingState);

    await this.sendBotMessage(session.userId, update.chatId, processingDocumentMessage(), {
      kind: "secondary",
    });
    const stillProcessingTimer = setTimeout(() => {
      void this.sendBotMessage(
        session.userId,
        update.chatId,
        stillProcessingDocumentMessage(),
        { source: "state_router.progress.document", kind: "secondary" },
      );
    }, 10_000);

    try {
      this.stateService.clearWaitingShortTextCounter(update.userId);
      if (intakeState === "waiting_resume") {
        this.stateService.setCandidateResumeText(update.userId, input.sourceTextEnglish);
      }
      if (intakeState === "waiting_job") {
        this.stateService.setJobDescriptionText(update.userId, input.sourceTextEnglish);
      }
      this.logger.info("document.extracted", {
        userId: update.userId,
        sourceType: "text",
        extractedChars: input.sourceTextOriginal.length,
        normalizedChars: input.sourceTextEnglish.length,
      });
      if (intakeState === "waiting_resume") {
        await this.persistCandidateNameFromResumeText(update.userId, input.sourceTextEnglish);
      }
      if (intakeState === "waiting_job") {
        await this.jobsRepository.saveJobIntakeSource({
          managerTelegramUserId: update.userId,
          sourceType: "text",
          sourceTextOriginal: input.sourceTextOriginal,
          sourceTextEnglish: input.sourceTextEnglish,
          telegramFileId: null,
        });
      }
      if (intakeState === "waiting_resume") {
        await this.profilesRepository.saveCandidateResumeIntakeSource({
          telegramUserId: update.userId,
          sourceType: "text",
          sourceTextOriginal: input.sourceTextOriginal,
          sourceTextEnglish: input.sourceTextEnglish,
          telegramFileId: null,
        });
      }

      const useCandidatePrescreenV2 =
        intakeState === "waiting_resume" && (await this.shouldUseCandidatePrescreenV2(session));
      const useJobPrescreenV2 =
        intakeState === "waiting_job" && (await this.shouldUseJobPrescreenV2(session));
      if (useCandidatePrescreenV2) {
        await this.bootstrapCandidatePrescreenV2({
          session,
          chatId: update.chatId,
          resumeText: input.sourceTextEnglish,
          sourceType: "text",
          documentType: "unknown",
        });
      } else if (useJobPrescreenV2) {
        await this.bootstrapJobPrescreenV2({
          session,
          chatId: update.chatId,
          jdText: input.sourceTextEnglish,
          sourceType: "text",
          documentType: "unknown",
        });
      } else {
        const bootstrapSession: UserSessionState = {
          ...session,
          state: intakeState,
        };
        const bootstrap = await this.interviewEngine.bootstrapInterview(bootstrapSession, input.sourceTextEnglish);
        this.logger.info("interview.bootstrap.completed", {
          userId: update.userId,
          sourceType: "text",
          nextState: bootstrap.nextState,
          questions: bootstrap.plan.questions.length,
          hasOneLiner: Boolean(bootstrap.intakeOneLiner),
        });
        const firstQuestionText = await this.formatInterviewQuestionForDelivery(
          session,
          bootstrap.firstQuestion,
          0,
          false,
        );
        const interviewState =
          bootstrap.nextState === "interviewing_candidate"
            ? "interviewing_candidate"
            : "interviewing_manager";
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          this.buildInterviewBootstrapDeliveryMessage({
            nextState: interviewState,
            intakeOneLiner: bootstrap.intakeOneLiner,
            answerInstruction: bootstrap.answerInstruction,
            firstQuestionText,
            firstQuestionIndex: 0,
          }),
        );
        this.stateService.setInterviewPlan(update.userId, bootstrap.plan);
        if (bootstrap.candidatePlanV2) {
          this.stateService.setCandidateInterviewPlanV2(update.userId, bootstrap.candidatePlanV2);
        }
        this.stateService.setCurrentQuestionIndex(update.userId, 0);
        this.stateService.markInterviewStarted(update.userId, "unknown", new Date().toISOString());
        this.stateService.transition(update.userId, bootstrap.nextState);
      }
    } catch (error) {
      const latestSession = this.stateService.getSession(update.userId);
      if (latestSession?.state === extractingState) {
        this.stateService.transition(update.userId, intakeState);
      }
      this.logger.error("Failed to process pasted document text", {
        userId: update.userId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        mapDocumentProcessingErrorToUserMessage(
          error,
          intakeState === "waiting_job" ? "waiting_job" : "waiting_resume",
        ),
      );
    } finally {
      clearTimeout(stillProcessingTimer);
    }
  }

  private async sendRouterReplyWithLoopGuard(
    session: UserSessionState,
    chatId: number,
    reply: string,
  ): Promise<void> {
    const trimmed = reply.trim();
    const previous = session.lastBotMessage?.trim();
    const isRepeat = Boolean(trimmed && previous && trimmed === previous);
    const turnContext = this.stateService.getTurnContext(session.userId);
    const lang = turnContext?.language ?? "en";

    let finalReply: string;
    if (
      this.dialogueV2Enabled &&
      this.replyComposerV2 &&
      turnContext?.lastUserMessage
    ) {
      if (isRepeat) {
        finalReply = dialogueSkipAndMoveOnMessage(lang);
      } else {
        const composed = await this.replyComposerV2.compose({
          userRole: session.role ?? "candidate",
          userLanguage: lang,
          currentState: session.state,
          lastUserMessage: turnContext.lastUserMessage,
          profileSummaryFacts: [],
          lastBotMessage: session.lastBotMessage,
          avoidPhrase: session.lastBotMessage ?? undefined,
        });
        finalReply =
          (composed?.message?.trim() ?? trimmed) || "Please continue with your hiring flow.";
      }
    } else {
      finalReply =
        isRepeat
          ? getSecondaryFallbackByState(session.state)
          : trimmed || "Please continue with your hiring flow.";
    }
    await this.sendBotMessage(session.userId, chatId, finalReply);
  }

  private async persistCandidateNameFromResumeText(
    telegramUserId: number,
    resumeTextEnglish: string,
  ): Promise<void> {
    try {
      const extracted = await this.candidateNameExtractorService.extractFromResume(resumeTextEnglish);
      if (!extracted?.firstName || extracted.confidence < 0.55) {
        return;
      }
      await this.usersRepository.upsertTelegramUser({
        telegramUserId,
        firstName: extracted.firstName,
        lastName: extracted.lastName ?? null,
      });
      this.userRagContextService.invalidate(telegramUserId);
      this.logger.info("candidate.name.persisted", {
        telegramUserId,
        confidence: extracted.confidence,
      });
    } catch (error) {
      this.logger.debug("candidate.name.persist_failed", {
        telegramUserId,
        error: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  private async formatInterviewQuestionForDelivery(
    session: UserSessionState,
    questionText: string,
    marker: number,
    isFollowUp: boolean,
  ): Promise<string> {
    const baseText = questionText.trim();
    if (!baseText) {
      return questionText;
    }
    if (isFollowUp || session.role !== "candidate") {
      return baseText;
    }
    if (!shouldUsePersonalName(session.userId, marker)) {
      return baseText;
    }
    const knownName = await this.resolveKnownUserName(session);
    if (!knownName) {
      return baseText;
    }
    return `${knownName}, ${baseText}`;
  }

  private buildInterviewBootstrapDeliveryMessage(input: {
    nextState: "interviewing_candidate" | "interviewing_manager";
    intakeOneLiner?: string | null;
    answerInstruction?: string | null;
    firstQuestionText: string;
    firstQuestionIndex: number;
  }): string {
    const parts: string[] = [];
    if (input.intakeOneLiner?.trim()) {
      parts.push(input.intakeOneLiner.trim());
    }
    parts.push(
      input.nextState === "interviewing_candidate"
        ? candidateInterviewPreparationMessage()
        : managerInterviewPreparationMessage(),
    );
    if (input.answerInstruction?.trim()) {
      parts.push(input.answerInstruction.trim());
    }
    parts.push(interviewLanguageSupportMessage());
    parts.push(questionMessage(input.firstQuestionIndex, input.firstQuestionText));
    return parts.join("\n\n");
  }

  private isCandidatePrescreenV2Session(session: UserSessionState): boolean {
    return (
      session.state === "interviewing_candidate" &&
      session.prescreenVersion === "v2" &&
      Boolean(session.prescreenPlan?.length)
    );
  }

  private isManagerPrescreenV2Session(session: UserSessionState): boolean {
    return (
      session.state === "interviewing_manager" &&
      session.jobPrescreenVersion === "v2" &&
      Boolean(session.jobPrescreenPlan?.length)
    );
  }

  private async shouldUseCandidatePrescreenV2(session: UserSessionState): Promise<boolean> {
    if (!this.prescreenV2Enabled || session.role !== "candidate") {
      return false;
    }

    if (session.prescreenVersion === "v1") {
      return false;
    }
    if (session.prescreenVersion === "v2") {
      return true;
    }

    const persistedVersion = await this.profilesRepository.getCandidatePrescreenVersion(
      session.userId,
    );
    const resolvedVersion: CandidatePrescreenVersion = persistedVersion ?? "v2";
    this.stateService.setPrescreenVersion(session.userId, resolvedVersion);
    return resolvedVersion === "v2";
  }

  private async shouldUseJobPrescreenV2(session: UserSessionState): Promise<boolean> {
    if (!this.jobPrescreenV2Enabled || session.role !== "manager") {
      return false;
    }

    if (session.jobPrescreenVersion === "v1") {
      return false;
    }
    if (session.jobPrescreenVersion === "v2") {
      return true;
    }

    const persistedVersion = await this.profilesRepository.getJobPrescreenVersion(
      session.userId,
    );
    const resolvedVersion: JobPrescreenVersion = persistedVersion ?? "v2";
    this.stateService.setJobPrescreenVersion(session.userId, resolvedVersion);
    return resolvedVersion === "v2";
  }

  private async bootstrapCandidatePrescreenV2(input: {
    session: UserSessionState;
    chatId: number;
    resumeText: string;
    sourceType: "file" | "text";
    documentType: "pdf" | "docx" | "unknown";
  }): Promise<void> {
    const detectedFromResume = detectLanguageQuick(input.resumeText.slice(0, 1500));
    const language = resolvePrescreenBootstrapLanguage(
      input.session.preferredLanguage,
      detectedFromResume === "ru" || detectedFromResume === "uk" ? detectedFromResume : undefined,
    );
    const result = await this.candidatePrescreenEngine.bootstrap(
      input.session,
      input.resumeText,
      language,
    );

    this.logger.info("candidate.prescreen_v2.bootstrap.completed", {
      userId: input.session.userId,
      sourceType: input.sourceType,
      questions: result.questionsGenerated,
      language,
    });

    this.stateService.setInterviewPlan(input.session.userId, result.plan);
    this.stateService.setPrescreenVersion(input.session.userId, "v2");
    this.stateService.setCurrentQuestionIndex(input.session.userId, 0);
    this.stateService.setPrescreenQuestionIndex(input.session.userId, 0);
    this.stateService.markInterviewStarted(
      input.session.userId,
      input.documentType,
      new Date().toISOString(),
    );
    this.stateService.transition(input.session.userId, "interviewing_candidate");

    const firstQuestionText = await this.formatInterviewQuestionForDelivery(
      input.session,
      result.firstQuestion,
      0,
      false,
    );
    await this.sendBotMessage(
      input.session.userId,
      input.chatId,
      `${result.summarySentence}\n\n${questionMessage(0, firstQuestionText)}`,
      { source: "state_router.system.prescreen_v2_bootstrap" },
    );
  }

  private async bootstrapJobPrescreenV2(input: {
    session: UserSessionState;
    chatId: number;
    jdText: string;
    sourceType: "file" | "text";
    documentType: "pdf" | "docx" | "unknown";
  }): Promise<void> {
    const detectedFromJd = detectLanguageQuick(input.jdText.slice(0, 1500));
    const language = resolvePrescreenBootstrapLanguage(
      input.session.preferredLanguage,
      detectedFromJd === "ru" || detectedFromJd === "uk" ? detectedFromJd : undefined,
    );
    const result = await this.jobPrescreenEngine.bootstrap(
      input.session,
      input.jdText,
      language,
    );

    this.logger.info("job.prescreen_v2.bootstrap.completed", {
      userId: input.session.userId,
      sourceType: input.sourceType,
      questions: result.questionsGenerated,
      language,
    });

    this.stateService.setInterviewPlan(input.session.userId, result.plan);
    this.stateService.setJobPrescreenVersion(input.session.userId, "v2");
    this.stateService.setCurrentQuestionIndex(input.session.userId, 0);
    this.stateService.setJobPrescreenQuestionIndex(input.session.userId, 0);
    this.stateService.markInterviewStarted(
      input.session.userId,
      input.documentType,
      new Date().toISOString(),
    );
    this.stateService.transition(input.session.userId, "interviewing_manager");

    const firstQuestionText = await this.formatInterviewQuestionForDelivery(
      input.session,
      result.firstQuestion,
      0,
      false,
    );
    await this.sendBotMessage(
      input.session.userId,
      input.chatId,
      `${result.summarySentence}\n\n${questionMessage(0, firstQuestionText)}`,
      { source: "state_router.system.job_prescreen_v2_bootstrap" },
    );
  }

  private async resolveKnownUserName(session: UserSessionState): Promise<string | null> {
    if (session.contactFirstName?.trim()) {
      return sanitizeUserName(session.contactFirstName);
    }
    const rag = await this.userRagContextService.buildRouterContext(session);
    return sanitizeUserName(rag.knownUserName);
  }

  private async handleAdminDebugCommand(
    update: NormalizedUpdate & { kind: "text" },
    session: UserSessionState,
    command:
      | "debug_chat_id"
      | "debug_state"
      | "debug_profile"
      | "debug_last_route"
      | "debug_matches"
      | "debug_active_job"
      | "debug_failures",
    optionalUserId?: number,
  ): Promise<void> {
    const targetUserId = optionalUserId ?? session.userId;
    const targetSession = optionalUserId ? this.stateService.getSession(optionalUserId) : session;

    if (command === "debug_chat_id") {
      await this.sendBotMessage(
        update.userId,
        update.chatId,
        `chat_id: ${update.chatId}\n(Use Bot API getUpdates to see chat.type)`,
        { source: "state_router.admin.debug_chat_id" },
      );
      return;
    }

    if (command === "debug_state") {
      const s = targetSession ?? { state: "no_session", userId: targetUserId };
      const phase = (s as UserSessionState).dialoguePhase ?? "—";
      const role = (s as UserSessionState).role ?? "—";
      const lang = (s as UserSessionState).preferredLanguage ?? "—";
      const prescreen = (s as UserSessionState).prescreenV2;
      const asked = prescreen?.totalQuestionsAsked ?? 0;
      const mandatory = prescreen?.mandatory
        ? JSON.stringify(prescreen.mandatory).slice(0, 80)
        : "—";
      const lastIntent = prescreen?.lastIntent ?? "—";
      const text = [
        `user=${targetUserId}`,
        `phase=${phase}`,
        `state=${(s as UserSessionState).state}`,
        `role=${role}`,
        `lang=${lang}`,
        `asked=${asked}`,
        `mandatory=${mandatory}`,
        `lastIntent=${lastIntent}`,
      ].join("\n");
      await this.sendBotMessage(update.userId, update.chatId, text, {
        source: "state_router.admin.debug_state",
      });
      return;
    }

    if (command === "debug_profile") {
      const s = targetSession as UserSessionState | undefined;
      if (!s) {
        await this.sendBotMessage(update.userId, update.chatId, `No session for user ${targetUserId}`, {
          source: "state_router.admin.debug_profile",
        });
        return;
      }
      const cand = s.candidateTechnicalSummary;
      const job = s.managerTechnicalSummary ?? s.managerJobProfileV2;
      const lines: string[] = [];
      if (cand) {
        lines.push("Candidate:", cand.headline?.slice(0, 120) ?? "—", cand.technical_depth_summary?.slice(0, 120) ?? "—");
      }
      if (job && typeof job === "object") {
        const j = job as { role_title?: string; headline?: string };
        lines.push("Job:", (j.role_title ?? j.headline ?? "—").slice(0, 120));
      }
      if (lines.length === 0) lines.push("No profile snapshot in session.");
      await this.sendBotMessage(update.userId, update.chatId, lines.join("\n").slice(0, 500), {
        source: "state_router.admin.debug_profile",
      });
      return;
    }

    if (command === "debug_last_route") {
      const { getLastRoute } = await import("../admin/admin-debug.store");
      const route = getLastRoute(targetUserId);
      const text = route
        ? `handler=${route.handler}\nsource=${route.source}\nat=${route.at}`
        : `No last route for user ${targetUserId}.`;
      await this.sendBotMessage(update.userId, update.chatId, text, {
        source: "state_router.admin.debug_last_route",
      });
      return;
    }

    if (command === "debug_failures") {
      const { getLastFailures } = await import("../admin/admin-debug.store");
      const failures = getLastFailures(targetUserId, 5);
      const lines =
        failures.length > 0
          ? failures.map((f, i) => `${i + 1}) ${f.kind} ${f.promptName ?? ""} ${f.source ?? ""} ${f.at}`)
          : [`No failures recorded for user ${targetUserId}.`];
      await this.sendBotMessage(update.userId, update.chatId, ["debug_failures (last 5):", ""].concat(lines).join("\n"), {
        source: "state_router.admin.debug_failures",
      });
      return;
    }

    if (command === "debug_matches") {
      const all = await this.matchStorageService.listAll();
      const forUser = all.filter(
        (m) => m.candidateUserId === targetUserId || m.managerUserId === targetUserId,
      );
      const sorted = forUser.sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      );
      const top5 = sorted.slice(0, 5);
      const lines = top5.length
        ? top5.map(
            (m, i) =>
              `${i + 1}) ${m.id.slice(0, 30)}… | c=${m.candidateUserId} m=${m.managerUserId} | ${m.status}`,
          )
        : [`No matches for user ${targetUserId}.`];
      await this.sendBotMessage(update.userId, update.chatId, ["debug_matches (last 5):", ""].concat(lines).join("\n"), {
        source: "state_router.admin.debug_matches",
      });
      return;
    }

    if (command === "debug_active_job") {
      const s = targetSession as UserSessionState | undefined;
      const activeJobId = s?.lastActiveJobId ?? "not set";
      await this.sendBotMessage(
        update.userId,
        update.chatId,
        `debug_active_job (user=${targetUserId}): ${activeJobId}`,
        { source: "state_router.admin.debug_active_job" },
      );
    }
  }

  private async sendBotMessage(
    userId: number,
    chatId: number,
    text: string,
    options?: {
      source?: string;
      replyMarkup?: TelegramReplyMarkup;
      kind?: "primary" | "secondary";
    },
  ): Promise<void> {
    const baseSource = options?.source ?? "state_router.dialogue";
    const source = resolveMessageSource(baseSource, text, options?.replyMarkup);
    let sanitizedText = sanitizeUserFacingText(text);
    const latestSession = this.stateService.getSession(userId);
    const previousText = latestSession?.lastBotMessage?.trim();
    const previousAt = latestSession?.lastBotMessageAt;
    const nowIso = new Date().toISOString();
    const nowMs = Date.now();
    const previousMs = previousAt ? Date.parse(previousAt) : Number.NaN;
    const isSameWithinWindow =
      Boolean(previousText) &&
      previousText === sanitizedText.trim() &&
      Number.isFinite(previousMs) &&
      nowMs - previousMs <= 60_000;

    if (isSameWithinWindow) {
      const stateForFallback = latestSession?.state ?? "role_selection";
      const replacement = getNonRepeatingFallbackByState(stateForFallback);
      sanitizedText =
        replacement.trim() === sanitizedText.trim()
          ? getSecondaryFallbackByState(stateForFallback)
          : replacement;
      const prevHash = latestSession?.lastBotMessageHash;
      const nextHash = hashMessageText(sanitizedText);
      recordFailure(userId, "repeat_loop", { source });
      this.logger.warn("repeat_loop_prevented", {
        telegram_user_id: userId,
        chat_id: chatId,
        source,
        previousHash: prevHash,
        nextHash,
      });
      safeNotifyAdmin("warn", "repeat_loop_prevented", undefined, {
        userId,
        chatId,
        state: stateForFallback,
        source,
        lastOutboundHashes: [prevHash, nextHash].filter(Boolean) as string[],
      });
    }

    recordLastRoute(userId, "send", source);
    this.logger.debug("user.reply.sent", {
      telegram_user_id: userId,
      chat_id: chatId,
      source,
      kind: options?.kind ?? "primary",
      reply_sent: true,
    });
    await this.telegramClient.sendUserMessage({
      source,
      chatId,
      text: sanitizedText,
      replyMarkup: options?.replyMarkup,
      kind: options?.kind ?? "primary",
    });
    this.stateService.setLastBotMessage(userId, sanitizedText, {
      hash: hashMessageText(sanitizedText),
      at: nowIso,
    });
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

    this.stateService.setAwaitingContactChoice(update.userId, false);
    await this.sendBotMessage(session.userId, update.chatId, contactSavedMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });
    if (session.state === "role_selection") {
      await this.sendBotMessage(session.userId, update.chatId, roleSelectionMessage(), {
        replyMarkup: buildRoleSelectionKeyboard(),
        kind: "secondary",
      });
    }
  }

  private async saveTextContact(
    session: UserSessionState,
    chatId: number,
    phoneNumber: string,
  ): Promise<void> {
    const firstName =
      session.contactFirstName?.trim() ||
      session.username?.trim() ||
      `user_${session.userId}`;
    const lastName = session.contactLastName?.trim() || undefined;
    const sharedAt = new Date().toISOString();

    this.stateService.setContactInfo({
      userId: session.userId,
      phoneNumber,
      firstName,
      lastName,
      sharedAt,
    });
    await this.usersRepository.saveContact({
      telegramUserId: session.userId,
      telegramUsername: session.username,
      phoneNumber,
      firstName,
      lastName,
      contactSharedAt: sharedAt,
    });

    this.stateService.setAwaitingContactChoice(session.userId, false);
    await this.sendBotMessage(session.userId, chatId, contactSavedMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
    });

    if (session.state === "role_selection") {
      await this.sendBotMessage(session.userId, chatId, roleSelectionMessage(), {
        replyMarkup: buildRoleSelectionKeyboard(),
        kind: "secondary",
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

    await this.maybeRunTypedCandidateMandatoryRouter({
      session,
      userMessage: `location ${update.latitude},${update.longitude}`,
      source: "location",
    });

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
      await this.sendBotMessage(session.userId, chatId, candidateMatchingActionsReadyMessage(), {
        kind: "secondary",
      });
      return;
    }

    this.stateService.setCandidateMandatoryStep(session.userId, nextStep);
    this.stateService.setCandidatePendingSalary(session.userId, undefined);
    if (options?.showIntro) {
      await this.sendBotMessage(session.userId, chatId, candidateMandatoryIntroMessage());
    }
    await this.askCandidateMandatoryQuestion(
      session.userId,
      chatId,
      nextStep,
      options?.showIntro ? "secondary" : "primary",
    );
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
    kind: "primary" | "secondary" = "primary",
  ): Promise<void> {
    if (step === "location") {
      await this.sendBotMessage(userId, chatId, candidateMandatoryLocationQuestionMessage(), {
        replyMarkup: buildCandidateMandatoryLocationKeyboard(),
        kind,
      });
      return;
    }
    if (step === "work_mode") {
      await this.sendBotMessage(userId, chatId, candidateMandatoryWorkModeQuestionMessage(), {
        replyMarkup: buildCandidateWorkModeKeyboard(),
        kind,
      });
      return;
    }
    await this.sendBotMessage(userId, chatId, candidateMandatorySalaryQuestionMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
      kind,
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
      await this.sendBotMessage(session.userId, chatId, managerMatchingActionsReadyMessage(), {
        kind: "secondary",
      });
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
    await this.askManagerMandatoryQuestion(
      session.userId,
      chatId,
      nextStep,
      options?.showIntro ? "secondary" : "primary",
    );
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
    kind: "primary" | "secondary" = "primary",
  ): Promise<void> {
    if (step === "work_format") {
      await this.sendBotMessage(userId, chatId, managerMandatoryWorkFormatQuestionMessage(), {
        replyMarkup: buildManagerWorkFormatKeyboard(),
        kind,
      });
      return;
    }
    if (step === "countries") {
      await this.sendBotMessage(userId, chatId, managerMandatoryCountriesQuestionMessage(), {
        replyMarkup: buildRemoveReplyKeyboard(),
        kind,
      });
      return;
    }
    await this.sendBotMessage(userId, chatId, managerMandatoryBudgetQuestionMessage(), {
      replyMarkup: buildRemoveReplyKeyboard(),
      kind,
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

    if (session.state === "extracting_resume" || session.state === "extracting_job") {
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "I already received your document and processing is in progress. I will send the next step shortly.",
      );
      return;
    }

    if (isInterviewingState(session.state)) {
      await this.sendBotMessage(session.userId, update.chatId, interviewAlreadyStartedMessage());
      return;
    }

    if (session.state === "role_selection") {
      if (isAwaitingContactChoice(session)) {
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          "Please share your contact first, or type Skip for now.",
          { replyMarkup: buildContactRequestKeyboard() },
        );
        return;
      }
      await this.sendBotMessage(
        session.userId,
        update.chatId,
        "Please choose your role first, then send your file.",
        { replyMarkup: buildRoleSelectionKeyboard() },
      );
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

    const intakeState = session.state;
    if (intakeState === "waiting_resume") {
      const typedCvRawMessage = `resume file ${update.fileName ?? ""} ${update.mimeType ?? ""}`.trim();
      try {
        const normalizedTypedCvMessage = await this.normalizeGeneralText(typedCvRawMessage);
        await this.maybeRunTypedCvRouter({
          session: { ...session, state: intakeState },
          userMessage: normalizedTypedCvMessage,
          source: "document",
        });
      } catch (error) {
        this.logger.warn("typed_cv.failed_legacy_fallback", {
          userId: session.userId,
          source: "document",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }
    if (intakeState === "waiting_job") {
      const typedJdRawMessage = `job description file ${update.fileName ?? ""} ${update.mimeType ?? ""}`.trim();
      try {
        const normalizedTypedJdMessage = await this.normalizeGeneralText(typedJdRawMessage);
        await this.maybeRunTypedJdRouter({
          session: { ...session, state: intakeState },
          userMessage: normalizedTypedJdMessage,
          source: "document",
        });
      } catch (error) {
        this.logger.warn("typed_jd.failed_legacy_fallback", {
          userId: session.userId,
          source: "document",
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }
    const extractingState = intakeState === "waiting_resume" ? "extracting_resume" : "extracting_job";
    this.stateService.transition(update.userId, extractingState);

    await this.sendBotMessage(session.userId, update.chatId, processingDocumentMessage(), {
      kind: "secondary",
    });
    const stillProcessingTimer = setTimeout(() => {
      void this.sendBotMessage(
        session.userId,
        update.chatId,
        stillProcessingDocumentMessage(),
        { source: "state_router.progress.document", kind: "secondary" },
      );
    }, 10_000);

    try {
      this.stateService.clearWaitingShortTextCounter(update.userId);
      const isManagerJdIntake = intakeState === "waiting_job";
      const isCandidateResumeIntake = intakeState === "waiting_resume";
      const fileBuffer = await this.telegramFileService.downloadFile(update.fileId);
      const extractedText = await this.documentService.extractText(
        fileBuffer,
        update.fileName,
        update.mimeType,
      );
      const normalizedExtractedText = await this.normalizeGeneralText(extractedText);
      if (isCandidateResumeIntake) {
        this.stateService.setCandidateResumeText(update.userId, normalizedExtractedText);
      }
      if (isManagerJdIntake) {
        this.stateService.setJobDescriptionText(update.userId, normalizedExtractedText);
      }
      if (isCandidateResumeIntake) {
        await this.persistCandidateNameFromResumeText(update.userId, normalizedExtractedText);
      }
      this.logger.info("document.extracted", {
        userId: update.userId,
        sourceType: "file",
        fileName: update.fileName ?? null,
        mimeType: update.mimeType ?? null,
        extractedChars: extractedText.length,
        normalizedChars: normalizedExtractedText.length,
      });

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

      const useCandidatePrescreenV2 =
        intakeState === "waiting_resume" && (await this.shouldUseCandidatePrescreenV2(session));
      const useJobPrescreenV2 =
        intakeState === "waiting_job" && (await this.shouldUseJobPrescreenV2(session));
      if (useCandidatePrescreenV2) {
        await this.bootstrapCandidatePrescreenV2({
          session,
          chatId: update.chatId,
          resumeText: normalizedExtractedText,
          sourceType: "file",
          documentType: this.documentService.detectDocumentType(update.fileName, update.mimeType),
        });
      } else if (useJobPrescreenV2) {
        await this.bootstrapJobPrescreenV2({
          session,
          chatId: update.chatId,
          jdText: normalizedExtractedText,
          sourceType: "file",
          documentType: this.documentService.detectDocumentType(update.fileName, update.mimeType),
        });
      } else {
        const bootstrapSession: UserSessionState = {
          ...session,
          state: intakeState,
        };
        const bootstrap = await this.interviewEngine.bootstrapInterview(bootstrapSession, normalizedExtractedText);
        this.logger.info("interview.bootstrap.completed", {
          userId: update.userId,
          sourceType: "file",
          nextState: bootstrap.nextState,
          questions: bootstrap.plan.questions.length,
          hasOneLiner: Boolean(bootstrap.intakeOneLiner),
        });
        const firstQuestionText = await this.formatInterviewQuestionForDelivery(
          session,
          bootstrap.firstQuestion,
          0,
          false,
        );
        const interviewState =
          bootstrap.nextState === "interviewing_candidate"
            ? "interviewing_candidate"
            : "interviewing_manager";
        await this.sendBotMessage(
          session.userId,
          update.chatId,
          this.buildInterviewBootstrapDeliveryMessage({
            nextState: interviewState,
            intakeOneLiner: bootstrap.intakeOneLiner,
            answerInstruction: bootstrap.answerInstruction,
            firstQuestionText,
            firstQuestionIndex: 0,
          }),
        );
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
      }
    } catch (error) {
      const latestSession = this.stateService.getSession(update.userId);
      if (latestSession?.state === extractingState) {
        this.stateService.transition(update.userId, intakeState);
      }
      this.logger.error("Failed to process document", {
        userId: update.userId,
        fileName: update.fileName,
        mimeType: update.mimeType,
        error: error instanceof Error ? error.message : "Unknown error",
      });

      await this.sendBotMessage(
        session.userId,
        update.chatId,
        mapDocumentProcessingErrorToUserMessage(
          error,
          intakeState === "waiting_job" ? "waiting_job" : "waiting_resume",
        ),
      );
    } finally {
      clearTimeout(stillProcessingTimer);
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

    const stillProcessingTimer = setTimeout(() => {
      const nowMs = Date.now();
      const lastSentMs = this.answerProcessingStatusAt.get(session.userId) ?? 0;
      if (nowMs - lastSentMs < 30_000) {
        return;
      }
      this.answerProcessingStatusAt.set(session.userId, nowMs);
      void this.sendBotMessage(
        session.userId,
        session.chatId,
        stillProcessingAnswerMessage(),
        { source: "state_router.progress.answer", kind: "secondary" },
      );
    }, 12_000);

    try {
      const normalizedInput = {
        ...input,
        answerText: normalized.english_text,
        originalText,
        detectedLanguage: normalized.detected_language,
      };
      const isCandidatePrescreenV2 = this.isCandidatePrescreenV2Session(session);
      const isManagerPrescreenV2 = this.isManagerPrescreenV2Session(session);
      if (isCandidatePrescreenV2) {
        const prescreenResult = await this.candidatePrescreenEngine.submitAnswer(session, normalizedInput);
        if (prescreenResult.kind === "reanswer_required") {
          await this.sendBotMessage(session.userId, session.chatId, prescreenResult.message, {
            source: "state_router.system.prescreen_v2_reanswer",
          });
          return;
        }

        if (prescreenResult.kind === "next_question") {
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          const nextQuestionText = await this.formatInterviewQuestionForDelivery(
            latestSession,
            prescreenResult.questionText,
            prescreenResult.questionIndex,
            Boolean(prescreenResult.isFollowUp),
          );
          const questionBlock = prescreenResult.isFollowUp
            ? nextQuestionText
            : questionMessage(prescreenResult.questionIndex, nextQuestionText);
          const outbound = prescreenResult.preQuestionMessage?.trim()
            ? `${prescreenResult.preQuestionMessage.trim()}\n\n${questionBlock}`
            : questionBlock;
          await this.sendBotMessage(session.userId, session.chatId, outbound, {
            source: "state_router.system.prescreen_v2_next_question",
          });
          return;
        }

        const completion = await this.interviewEngine.finishInterviewNow(session);
        this.stateService.transition(session.userId, completion.completedState);
        this.stateService.resetAnswersSinceConfirm(session.userId);
        this.stateService.clearPrescreenQuestionIndex(session.userId);
        await this.sendBotMessage(
          session.userId,
          session.chatId,
          prescreenResult.completionMessage,
          { source: "state_router.system.prescreen_v2_completed" },
        );
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        await this.startCandidateMandatoryFieldsFlow(latestSession, session.chatId, {
          showIntro: true,
        });
        return;
      }
      if (isManagerPrescreenV2) {
        const prescreenResult = await this.jobPrescreenEngine.submitAnswer(session, normalizedInput);
        if (prescreenResult.kind === "reanswer_required") {
          await this.sendBotMessage(session.userId, session.chatId, prescreenResult.message, {
            source: "state_router.system.job_prescreen_v2_reanswer",
          });
          return;
        }

        if (prescreenResult.kind === "next_question") {
          const latestSession = this.stateService.getSession(session.userId) ?? session;
          const nextQuestionText = await this.formatInterviewQuestionForDelivery(
            latestSession,
            prescreenResult.questionText,
            prescreenResult.questionIndex,
            Boolean(prescreenResult.isFollowUp),
          );
          const questionBlock = prescreenResult.isFollowUp
            ? nextQuestionText
            : questionMessage(prescreenResult.questionIndex, nextQuestionText);
          const outbound = prescreenResult.preQuestionMessage?.trim()
            ? `${prescreenResult.preQuestionMessage.trim()}\n\n${questionBlock}`
            : questionBlock;
          await this.sendBotMessage(session.userId, session.chatId, outbound, {
            source: "state_router.system.job_prescreen_v2_next_question",
          });
          return;
        }

        const completion = await this.interviewEngine.finishInterviewNow(session);
        this.stateService.transition(session.userId, completion.completedState);
        this.stateService.resetAnswersSinceConfirm(session.userId);
        this.stateService.clearJobPrescreenQuestionIndex(session.userId);
        await this.sendBotMessage(
          session.userId,
          session.chatId,
          prescreenResult.completionMessage,
          { source: "state_router.system.job_prescreen_v2_completed" },
        );
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        await this.startManagerMandatoryFieldsFlow(latestSession, session.chatId, {
          showIntro: true,
          runMatchingAfterComplete: true,
        });
        return;
      }

      const result = await this.interviewEngine.submitAnswer(session, normalizedInput);

      if (result.kind === "reanswer_required") {
        await this.sendBotMessage(session.userId, session.chatId, result.message, {
          source: "state_router.system.interview_reanswer",
        });
        return;
      }

      if (result.kind === "next_question") {
        const latestSession = this.stateService.getSession(session.userId) ?? session;
        let secondaryMessage: string | null = result.preQuestionMessage?.trim() || null;
        const shouldSendProgressConfirmation = !result.isFollowUp && this.shouldSendProgressConfirmation(
          latestSession,
          normalizedInput.answerText,
        );
        if (!secondaryMessage && shouldSendProgressConfirmation) {
          const confirmation = await this.generateInterviewProgressConfirmation(latestSession);
          if (confirmation) {
            secondaryMessage = confirmation;
            this.stateService.resetAnswersSinceConfirm(session.userId);
          }
        }

        await this.maybeSendInterviewReaction(session, originalText, sourceMessageId);
        if (!secondaryMessage && !result.isFollowUp) {
          secondaryMessage = await this.getCandidateEmpathyLine(latestSession);
        }
        const nextQuestionText = await this.formatInterviewQuestionForDelivery(
          latestSession,
          result.questionText,
          result.questionIndex,
          Boolean(result.isFollowUp),
        );
        const questionBlock = result.isFollowUp
          ? nextQuestionText
          : questionMessage(result.questionIndex, nextQuestionText);
        const outbound = secondaryMessage
          ? `${secondaryMessage}\n\n${questionBlock}`
          : questionBlock;
        await this.sendBotMessage(
          session.userId,
          session.chatId,
          outbound,
        );
        return;
      }

      this.stateService.transition(session.userId, result.completedState);
      this.stateService.resetAnswersSinceConfirm(session.userId);
      await this.sendBotMessage(session.userId, session.chatId, result.completionMessage);
      const needsMandatoryFlow =
        result.completedState === "candidate_profile_ready" ||
        result.completedState === "job_profile_ready";
      if (result.followupMessage && !needsMandatoryFlow) {
        await this.sendBotMessage(session.userId, session.chatId, result.followupMessage, {
          kind: "secondary",
        });
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
    } finally {
      clearTimeout(stillProcessingTimer);
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

    await this.sendBotMessage(session.userId, update.chatId, transcribingVoiceMessage(), {
      kind: "secondary",
    });

    try {
      const buffer = await this.telegramFileService.downloadFile(update.fileId);
      const transcription = await this.transcriptionClient.transcribeOgg(buffer);
      const normalized = await this.normalizeInterviewInput(transcription);
      this.stateService.recordPreferredLanguageSample(update.userId, toPreferredLanguage(normalized.detected_language));
      const latestSession = this.stateService.getSession(update.userId) ?? session;
      if (latestSession.state === "waiting_resume") {
        await this.maybeRunTypedCvRouter({
          session: latestSession,
          userMessage: normalized.english_text,
          source: "voice",
        });
      }
      if (latestSession.state === "waiting_job") {
        await this.maybeRunTypedJdRouter({
          session: latestSession,
          userMessage: normalized.english_text,
          source: "voice",
        });
      }
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

  private async getCandidateEmpathyLine(session: UserSessionState): Promise<string | null> {
    if (session.state !== "interviewing_candidate") {
      return null;
    }
    if (Math.random() > 0.4) {
      return null;
    }

    const line = getShortEmpathyLine(session.lastEmpathyLine);
    this.stateService.setLastEmpathyLine(session.userId, line);
    return line;
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
        await this.sendBotMessage(
          managerSession.userId,
          managerSession.chatId,
          "No suitable candidates found yet.",
          { source: "state_router.publish_manager_matches.empty" },
        );
        return;
      }

      await this.sendBotMessage(
        managerSession.userId,
        managerSession.chatId,
        "Matching run completed. Candidate notifications were sent where eligible.",
        { source: "state_router.publish_manager_matches.done" },
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
      await this.sendBotMessage(
        managerSession.userId,
        managerSession.chatId,
        "Matching is temporarily unavailable.",
        { source: "state_router.publish_manager_matches.error" },
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

  private async startRoleFlowFromText(
    session: UserSessionState,
    chatId: number,
    role: UserRole,
  ): Promise<void> {
    this.stateService.setRole(session.userId, role);
    if (role === "candidate") {
      this.stateService.transition(session.userId, "onboarding_candidate");
      await this.sendBotMessage(session.userId, chatId, candidateOnboardingMessage());
      this.stateService.transition(session.userId, "waiting_resume");
      this.stateService.setOnboardingCompleted(session.userId, true);
      await this.sendBotMessage(session.userId, chatId, candidateResumePrompt(), {
        replyMarkup: buildRemoveReplyKeyboard(),
        kind: "secondary",
      });
      return;
    }

    this.stateService.transition(session.userId, "onboarding_manager");
    await this.sendBotMessage(session.userId, chatId, managerOnboardingMessage());
    this.stateService.transition(session.userId, "waiting_job");
    this.stateService.setOnboardingCompleted(session.userId, true);
    await this.sendBotMessage(session.userId, chatId, managerJobPrompt(), {
      replyMarkup: buildRemoveReplyKeyboard(),
      kind: "secondary",
    });
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

      const match = managerMatches[0];
      const message = managerCandidateSuggestionMessage({
        candidateUserId: match.candidateUserId,
        score: match.score,
        candidateSummary: match.candidateSummary,
        candidateTechnicalSummary: match.candidateTechnicalSummary ?? null,
        explanationMessage:
          match.explanationJson?.message_for_manager ?? match.explanation,
      });
      const withHint =
        managerMatches.length > 1
          ? `${message}\n\nShowing the strongest match first. Type show matches again for the next one.`
          : message;
      await this.sendBotMessage(
        session.userId,
        chatId,
        withHint,
        {
          source: "state_router.show_matches.manager_card",
          replyMarkup: buildManagerDecisionKeyboard(match.id),
        },
      );
      return true;
    }

    const candidateMatches = all
      .filter((item) => item.candidateUserId === session.userId)
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .slice(0, 3);
    if (candidateMatches.length === 0) {
      return false;
    }

    const match = candidateMatches[0];
    const message = candidateOpportunityMessage({
      score: match.score,
      jobSummary: match.jobSummary,
      explanationMessage:
        match.explanationJson?.message_for_candidate ?? match.explanation,
      jobTechnicalSummary: match.jobTechnicalSummary ?? null,
    });
    const withHint =
      candidateMatches.length > 1
        ? `${message}\n\nShowing the strongest role first. Type show matches again for the next one.`
        : message;
    await this.sendBotMessage(
      session.userId,
      chatId,
      withHint,
      {
        source: "state_router.show_matches.candidate_card",
        replyMarkup: buildCandidateDecisionKeyboard(match.id),
      },
    );
    return true;
  }

  private async buildStatusReplyForUser(session: UserSessionState): Promise<string> {
    if (session.role === "candidate") {
      const canonical = await this.profilesRepository.getCanonicalCandidateProfileV2(session.userId);
      const mandatory = await this.usersRepository.getCandidateMandatoryFields(session.userId);
      const flags = await this.usersRepository.getUserFlags(session.userId);
      const profileReady = canonical.profileText.trim().length > 0 ? "ready" : "not ready";
      const mandatoryReady = mandatory.profileComplete ? "complete" : "incomplete";
      const contact = flags.contactShared ? "shared" : "missing";
      return [
        "Current candidate status:",
        `Profile: ${profileReady}.`,
        `Mandatory fields: ${mandatoryReady}.`,
        `Contact: ${contact}.`,
        session.state === "interviewing_candidate"
          ? "Interview: in progress."
          : `Current step: ${session.state}.`,
      ].join("\n");
    }

    if (session.role === "manager") {
      const canonical = await this.profilesRepository.getCanonicalJobProfileV2(session.userId);
      const mandatory = await this.jobsRepository.getJobMandatoryFields(session.userId);
      const flags = await this.usersRepository.getUserFlags(session.userId);
      const profileReady = canonical.profileText.trim().length > 0 ? "ready" : "not ready";
      const mandatoryReady = mandatory.profileComplete ? "complete" : "incomplete";
      const contact = flags.contactShared ? "shared" : "missing";
      return [
        "Current manager status:",
        `Job profile: ${profileReady}.`,
        `Mandatory fields: ${mandatoryReady}.`,
        `Contact: ${contact}.`,
        session.state === "interviewing_manager"
          ? "Interview: in progress."
          : `Current step: ${session.state}.`,
      ].join("\n");
    }

    return "I can show your profile status after you pick a role, candidate or manager.";
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
  const compact = normalized.replace(/[^\p{L}\p{N}+]+/gu, " ").trim();
  return (
    normalized === "skip" ||
    normalized === "skip for now" ||
    normalized === "skip now" ||
    normalized === "not now" ||
    normalized === "later" ||
    normalized === "пропустить" ||
    normalized === "скип" ||
    normalized === "пропуск" ||
    normalized === "пропустити" ||
    normalized === "пропускати" ||
    normalized.includes("не хочу отправлять номер") ||
    normalized.includes("не хочу отправлять контакт") ||
    normalized.includes("не сейчас") ||
    normalized.includes("позже") ||
    normalized.includes("не хочу поки") ||
    normalized.includes("поки не хочу") ||
    normalized.includes("не хочу надсилати") ||
    normalized.includes("пізніше") ||
    compact === "skip" ||
    compact === "skip for now" ||
    compact === "пропустить" ||
    compact === "скип"
  );
}

function isAwaitingContactChoice(session: UserSessionState): boolean {
  return session.state === "role_selection" && session.awaitingContactChoice === true;
}

function isRemainingQuestionsMetaQuery(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("how many questions") ||
    english.includes("questions left") ||
    english.includes("how many left") ||
    english.includes("remaining questions") ||
    raw.includes("сколько вопросов") ||
    raw.includes("много еще вопросов") ||
    raw.includes("сколько еще") ||
    raw.includes("скільки питань") ||
    raw.includes("багато ще питань")
  );
}

function buildInterviewRemainingQuestionsReply(
  session: UserSessionState,
  detectedLanguage: "en" | "ru" | "uk" | "other",
): string {
  const plan = session.interviewPlan;
  if (!plan) {
    if (detectedLanguage === "ru") {
      return "Сейчас не вижу план интервью. Отправьте ответ на текущий вопрос, и я продолжу.";
    }
    if (detectedLanguage === "uk") {
      return "Зараз не бачу план інтерв'ю. Надішліть відповідь на поточне питання, і я продовжу.";
    }
    return "I do not see the interview plan right now. Please answer the current question and I will continue.";
  }

  const answered = new Set(
    (session.answers ?? [])
      .filter((item) => item.status !== "draft")
      .map((item) => item.questionIndex),
  );
  const skipped = new Set(session.skippedQuestionIndexes ?? []);
  let remaining = 0;
  for (let index = 0; index < plan.questions.length; index += 1) {
    if (!answered.has(index) && !skipped.has(index)) {
      remaining += 1;
    }
  }

  if (detectedLanguage === "ru") {
    if (remaining <= 1) {
      return "Остался последний вопрос. После вашего ответа завершим интервью.";
    }
    return `Осталось ${remaining} вопросов, включая текущий. После каждого ответа я сразу продолжу.`;
  }
  if (detectedLanguage === "uk") {
    if (remaining <= 1) {
      return "Залишилося останнє питання. Після вашої відповіді завершимо інтерв'ю.";
    }
    return `Залишилося ${remaining} питань, включно з поточним. Після кожної відповіді я одразу продовжу.`;
  }
  if (remaining <= 1) {
    return "One final question is left. After your answer, we will complete the interview.";
  }
  return `${remaining} questions are left, including the current one. After each answer I will continue immediately.`;
}

function mapDocumentProcessingErrorToUserMessage(
  error: unknown,
  intakeState: "waiting_resume" | "waiting_job",
): string {
  const message = error instanceof Error ? error.message.toLowerCase() : "";

  if (message.includes("timeout")) {
    if (intakeState === "waiting_resume") {
      return "I could not finish resume analysis in time. Please send the same PDF or DOCX once more, or paste your resume text.";
    }
    return "I could not finish job description analysis in time. Please send the same PDF or DOCX once more, or paste the full text.";
  }

  if (message.includes("outside helly scope")) {
    return "This looks outside technical hiring scope. Please send a technical resume or technical job description.";
  }

  if (intakeState === "waiting_resume") {
    return "I could not process this resume. Please try another PDF or DOCX, or paste the full resume text.";
  }
  return "I could not process this job description. Please try another PDF or DOCX, or paste the full text.";
}

function isContactShareTextIntent(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("share my contact") ||
    english.includes("share contact") ||
    english.includes("my phone number") ||
    english.includes("save my phone") ||
    raw.includes("поделиться контактом") ||
    raw.includes("мой номер") ||
    raw.includes("мій номер") ||
    raw.includes("поділитися контактом")
  );
}

function extractPhoneNumber(rawText: string): string | null {
  const match = rawText.match(/(\+?\d[\d\s\-()]{7,}\d)/);
  if (!match) {
    return null;
  }
  const normalized = match[1].replace(/[^\d+]/g, "");
  const digits = normalized.replace(/\D/g, "");
  if (digits.length < 9) {
    return null;
  }
  return normalized.startsWith("+") ? normalized : `+${digits}`;
}

function canAcceptTextContactByState(state: UserSessionState["state"]): boolean {
  return (
    state === "role_selection" ||
    state === "waiting_candidate_decision" ||
    state === "waiting_manager_decision" ||
    state === "contact_shared" ||
    state === "candidate_profile_ready" ||
    state === "job_profile_ready"
  );
}

function isStartCommand(text: string): boolean {
  return /^\/start(?:\s|$)/i.test(text.trim());
}

function isDataDeletionCommand(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  const compactEnglish = english.replace(/\s+/g, " ").trim();
  return (
    /\bdelet(e)?\s+(all\s+)?my\s+data\b/.test(compactEnglish) ||
    compactEnglish.includes("delete my data") ||
    compactEnglish.includes("delete all my data") ||
    compactEnglish.includes("remove all my data") ||
    compactEnglish.includes("erase all my data") ||
    compactEnglish.includes("wipe my data") ||
    compactEnglish.includes("remove my contact") ||
    compactEnglish.includes("delete my contact") ||
    compactEnglish === "delete data" ||
    compactEnglish === "delete contact" ||
    compactEnglish === "delete everything" ||
    raw.includes("удали мои данные") ||
    raw.includes("удали все мои данные") ||
    raw.includes("удали все данные") ||
    raw.includes("удали мой контакт") ||
    raw.includes("видали мої дані") ||
    raw.includes("видали всі мої дані") ||
    raw.includes("видали всі дані") ||
    raw.includes("видали мій контакт")
  );
}

function isDataDeletionConfirmIntent(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase().replace(/\s+/g, " ");
  return (
    english === "delete everything" ||
    english === "everything" ||
    english === "confirm delete" ||
    english === "yes delete" ||
    english === "yes, delete everything" ||
    english.includes("delete all my data") ||
    english.includes("delete everything now") ||
    raw === "все" ||
    raw === "всё" ||
    raw === "удали все" ||
    raw === "удали всё" ||
    raw === "видали все" ||
    raw === "видали все дані" ||
    raw === "да удалить"
  );
}

function isDataDeletionCancelIntent(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase().replace(/\s+/g, " ");
  return (
    english === "cancel" ||
    english === "keep data" ||
    english === "do not delete" ||
    english === "no" ||
    english === "keep it" ||
    raw === "отмена" ||
    raw === "скасувати" ||
    raw === "отменить" ||
    raw === "не удаляй" ||
    raw === "не видаляй" ||
    raw === "нет"
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
  const answered = new Set(
    (session.answers ?? [])
      .filter((item) => item.status !== "draft")
      .map((item) => item.questionIndex),
  );
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
  return (
    normalized === "skip" ||
    normalized === "skip question" ||
    normalized === "skip this question" ||
    normalized === "pass" ||
    normalized === "pass question" ||
    normalized === "пропустить" ||
    normalized === "пропустить вопрос" ||
    normalized === "пропусти вопрос" ||
    normalized === "пропустить этот вопрос" ||
    normalized === "пропусти этот вопрос" ||
    normalized === "пропустити" ||
    normalized === "пропустити питання" ||
    normalized === "pass this one"
  );
}

function isInterviewFinishCommand(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase().replace(/\s+/g, " ");
  const english = normalizedEnglishText.trim().toLowerCase().replace(/\s+/g, " ");
  return (
    english.includes("finish interview") ||
    english.includes("end interview") ||
    english.includes("stop interview") ||
    english.includes("i am done with interview") ||
    english.includes("i'm done with interview") ||
    english.includes("finish all questions") ||
    english.includes("skip all questions") ||
    english.includes("done, find roles") ||
    english.includes("stop questions") ||
    raw.includes("я закончил интервью") ||
    raw.includes("я завершил интервью") ||
    raw.includes("закончим интервью") ||
    raw.includes("заверши интервью") ||
    raw.includes("останови интервью") ||
    raw.includes("все вопросы пропусти") ||
    raw.includes("пропусти все вопросы") ||
    raw.includes("закінчити інтерв'ю") ||
    raw.includes("заверши співбесіду")
  );
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

function detectExplicitMatchingIntent(
  rawText: string,
  normalizedEnglishText: string,
  role: UserRole | null,
): AlwaysOnRouterDecision["matching_intent"] | null {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  if (raw === "/find_jobs" || english === "/find_jobs") {
    return role === "manager" ? null : "run";
  }
  if (raw === "/find_candidates" || english === "/find_candidates") {
    return role === "candidate" ? null : "run";
  }
  if (raw === "/show_matches" || english === "/show_matches") {
    return "show";
  }
  if (raw === "/pause_matching" || english === "/pause_matching") {
    return "pause";
  }
  if (raw === "/resume_matching" || english === "/resume_matching") {
    return "resume";
  }
  return null;
}

function didRouteLikelyCallTaskPrompt(route: AlwaysOnRouterDecision["route"]): boolean {
  return (
    route === "DOC" ||
    route === "VOICE" ||
    route === "JD_TEXT" ||
    route === "RESUME_TEXT" ||
    route === "INTERVIEW_ANSWER" ||
    route === "MATCHING_COMMAND"
  );
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

function isRetryProcessingSignal(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("retry processing") ||
    english.includes("retry") ||
    english.includes("already sent") ||
    english.includes("i already sent") ||
    english.includes("already uploaded") ||
    raw.includes("повтори обработку") ||
    raw.includes("перезапусти обработку") ||
    raw.includes("я уже прислал") ||
    raw.includes("я уже отправил") ||
    raw.includes("я уже надіслав") ||
    raw.includes("я вже надіслав") ||
    raw.includes("я уже скинул") ||
    raw.includes("я уже отправлял") ||
    raw.includes("вище")
  );
}

function detectRoleSelectionFromText(
  rawText: string,
  normalizedEnglishText: string,
): UserRole | null {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();

  if (/\b(candidate|job seeker|looking for a job)\b/.test(english)) {
    return "candidate";
  }
  if (/\b(hiring manager|recruiter|find candidates|i am hiring|manager)\b/.test(english)) {
    return "manager";
  }
  if (/кандидат|соискател|шукаю роботу|шукаю ваканс/.test(raw)) {
    return "candidate";
  }
  if (/нанима|ищу кандидат|роботодав|шукаю кандидат|підбираю/.test(raw)) {
    return "manager";
  }

  const candidateSignals = [
    "i am candidate",
    "candidate",
    "job seeker",
    "looking for a job",
    "find me roles",
    "я кандидат",
    "я соискатель",
    "ищу работу",
    "шукаю роботу",
    "я кандидатка",
  ];
  if (candidateSignals.some((signal) => raw.includes(signal) || english.includes(signal))) {
    return "candidate";
  }

  const managerSignals = [
    "i am hiring",
    "hiring manager",
    "find candidates",
    "recruiter",
    "manager",
    "я нанимаю",
    "я hiring manager",
    "ищу кандидатов",
    "шукаю кандидатів",
    "я роботодавець",
  ];
  if (managerSignals.some((signal) => raw.includes(signal) || english.includes(signal))) {
    return "manager";
  }

  return null;
}

function isRoleLearnHowItWorksText(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("learn how this works") ||
    english.includes("how this works") ||
    english.includes("how it works") ||
    raw.includes("learn how this works") ||
    raw.includes("как это работает") ||
    raw.includes("як це працює")
  );
}

function isEnglishPreferenceSignal(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("i don't understand russian") ||
    english.includes("i do not understand russian") ||
    english.includes("english please") ||
    english.includes("please use english") ||
    english.includes("speak english") ||
    raw.includes("по английски") ||
    raw.includes("английский пожалуйста")
  );
}

function localizeInterviewMetaReply(
  defaultReply: string,
  metaType: "timing" | "language" | "format" | "privacy" | "other" | null,
  detectedLanguage: "en" | "ru" | "uk" | "other",
): string {
  const trimmedReply = defaultReply.trim();
  if (detectedLanguage !== "ru" && detectedLanguage !== "uk") {
    return trimmedReply || defaultReply;
  }

  if (trimmedReply && !isGenericMetaReplyTemplate(trimmedReply, metaType)) {
    return trimmedReply;
  }

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

  return trimmedReply || defaultReply;
}

function localizePrescreenMetaReply(
  reply: string,
  detectedLanguage: "en" | "ru" | "uk" | "other",
): string {
  const trimmed = reply.trim();
  const normalized = trimmed.toLowerCase();
  if (
    normalized.includes("please answer the current interview question") ||
    normalized.includes("please answer the question you are on now")
  ) {
    if (detectedLanguage === "ru") {
      return "Когда будете готовы, ответьте на текущий вопрос в свободной форме. Можно текстом или голосом.";
    }
    if (detectedLanguage === "uk") {
      return "Коли будете готові, дайте відповідь на поточне питання у вільній формі. Можна текстом або голосом.";
    }
    return "When you are ready, answer the current question in your own words. Text or voice is fine.";
  }
  return trimmed || reply;
}

function isGenericMetaReplyTemplate(
  reply: string,
  metaType: "timing" | "language" | "format" | "privacy" | "other" | null,
): boolean {
  const normalized = reply.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  if (metaType === "timing") {
    return (
      normalized.includes("usually this takes a couple of minutes") ||
      normalized.includes("i will continue right after your answer")
    );
  }
  if (metaType === "language") {
    return (
      normalized.includes("you can answer by voice in russian or ukrainian") ||
      normalized.includes("i will transcribe") ||
      normalized.includes("i will understand")
    );
  }
  if (metaType === "format") {
    return (
      normalized.includes("you can answer in text or voice") ||
      normalized.includes("please answer the current interview question")
    );
  }
  if (metaType === "privacy") {
    return normalized.includes("contacts are shared only after mutual approval");
  }
  return false;
}

function isAskBotQuestionInPreferredLanguage(rawText: string, normalizedEnglishText: string): boolean {
  const raw = rawText.trim().toLowerCase();
  const english = normalizedEnglishText.trim().toLowerCase();
  return (
    english.includes("can you ask in russian") ||
    english.includes("can you ask in ukrainian") ||
    english.includes("ask the question in russian") ||
    english.includes("ask the question in ukrainian") ||
    raw.includes("можешь на русском написать вопрос") ||
    raw.includes("можешь на русском задать вопрос") ||
    raw.includes("можешь вопрос на русском") ||
    raw.includes("пиши вопрос на русском") ||
    raw.includes("можеш українською поставити питання") ||
    raw.includes("можеш українською задати питання") ||
    raw.includes("пиши питання українською")
  );
}

function buildAskBotQuestionInPreferredLanguageReply(
  detectedLanguage: "en" | "ru" | "uk" | "other",
): string {
  if (detectedLanguage === "ru") {
    return "Да, могу задавать вопросы на русском. Отвечайте на текущий вопрос, и дальше продолжу на русском.";
  }
  if (detectedLanguage === "uk") {
    return "Так, можу ставити питання українською. Дайте відповідь на поточне питання, і далі продовжу українською.";
  }
  return "Yes. I can ask questions in Russian or Ukrainian. Please answer the current question, and I will continue in your preferred language.";
}

function resolvePrescreenBootstrapLanguage(
  preferredLanguage: UserSessionState["preferredLanguage"],
  detectedFromText?: "ru" | "uk",
): "en" | "ru" | "uk" {
  if (preferredLanguage === "ru" || preferredLanguage === "uk") {
    return preferredLanguage;
  }
  if (detectedFromText === "ru" || detectedFromText === "uk") {
    return detectedFromText;
  }
  return "en";
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

function getExtractingStatusReply(
  state: UserSessionState["state"],
  metaType: "timing" | "language" | "format" | "privacy" | "other" | null,
): string {
  if (metaType === "timing") {
    return "Usually this takes a couple of minutes. I already received your document and processing is in progress.";
  }
  if (metaType === "format") {
    return "No action is needed now. I already received your document and I am processing it.";
  }
  if (metaType === "language") {
    return "Yes. You can answer in Russian or Ukrainian. I will normalize it to continue the interview.";
  }
  if (metaType === "privacy") {
    return "Your profile is only shared after you apply, and contacts are shared only after mutual approval.";
  }
  if (state === "extracting_job") {
    return "I already received your job description and I am processing it now. I will send the next step shortly.";
  }
  return "I already received your resume and I am processing it now. I will send the next step shortly.";
}

function getNonRepeatingFallbackByState(state: UserSessionState["state"]): string {
  if (state === "waiting_resume") {
    return "Please send a PDF or DOCX file, or paste the full resume text here.";
  }
  if (state === "waiting_job") {
    return "Please send a PDF or DOCX file, or paste the full job description text here.";
  }
  if (state === "extracting_resume" || state === "extracting_job") {
    return "I already received your document and processing is in progress.";
  }
  if (state === "interviewing_candidate" || state === "interviewing_manager") {
    return "Please answer the current interview question. You can reply in text or voice.";
  }
  if (state === "role_selection") {
    return "Please tell me your role by text or voice, candidate or hiring.";
  }
  return "Please continue with the current step.";
}

function getSecondaryFallbackByState(state: UserSessionState["state"]): string {
  if (state === "waiting_resume") {
    return "You can also forward a resume file from another chat, PDF or DOCX is supported.";
  }
  if (state === "waiting_job") {
    return "You can also forward a job description file from another chat, PDF or DOCX is supported.";
  }
  if (state === "extracting_resume" || state === "extracting_job") {
    return "Processing is still running. I will post the next step as soon as it is ready.";
  }
  if (state === "interviewing_candidate" || state === "interviewing_manager") {
    return "If you want to move on, type skip. You can also answer by voice.";
  }
  if (state === "role_selection") {
    return "Please choose role by text or button, candidate or hiring.";
  }
  return "Please continue with the next step.";
}

function resolveMessageSource(
  source: string,
  text: string,
  replyMarkup?: TelegramReplyMarkup,
): string {
  const normalized = source.trim().toLowerCase();
  if (normalized.startsWith("system_") || normalized.startsWith("state_router.system")) {
    return source;
  }
  if (replyMarkup) {
    return `state_router.system.keyboard.${source}`;
  }
  if (isHardSystemMessageText(text)) {
    return `state_router.system.control.${source}`;
  }
  return source;
}

function buildRouterV2PartialProfile(
  session: UserSessionState,
): Record<string, unknown> | null {
  if (session.role === "candidate") {
    return (session.candidateProfile as unknown as Record<string, unknown>) ?? null;
  }
  if (session.role === "manager") {
    return (
      (session.managerJobProfileV2 as unknown as Record<string, unknown>) ??
      (session.jobProfile as unknown as Record<string, unknown>) ??
      null
    );
  }
  return null;
}

function buildRouterV2LastMessages(session: UserSessionState, currentUserMessage: string): string[] {
  const previousBot = session.lastBotMessage?.trim();
  const recentAnswers = (session.answers ?? [])
    .slice(-4)
    .map((item) => item.answerText.trim())
    .filter(Boolean);
  const merged = [
    ...recentAnswers,
    previousBot ?? "",
    currentUserMessage.trim(),
  ].filter(Boolean);
  return merged.slice(-5);
}

function resolveRouterV2Role(session: UserSessionState): "candidate" | "manager" {
  if (session.role === "manager") {
    return "manager";
  }
  if (
    session.state === "onboarding_manager" ||
    session.state === "waiting_job" ||
    session.state === "extracting_job" ||
    session.state === "interviewing_manager" ||
    session.state === "job_profile_ready" ||
    session.state === "manager_mandatory_fields" ||
    session.state === "job_published"
  ) {
    return "manager";
  }
  return "candidate";
}

function isHardSystemMessageText(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return (
    normalized.includes("/start") ||
    normalized.includes("share my contact") ||
    normalized.includes("skip for now") ||
    normalized.includes("i am a candidate") ||
    normalized.includes("i am hiring") ||
    normalized.includes("pdf or docx") ||
    normalized.includes("choose your role")
  );
}

function hashMessageText(text: string): string {
  return createHash("sha256").update(text).digest("hex").slice(0, 16);
}

function isPrescreenOrOnboardingState(session: UserSessionState): boolean {
  const state = session.state;
  // role_selection: must use deterministic flow so "I am a Candidate" / "I am Hiring" actually transition to waiting_resume/waiting_job
  if (state === "role_selection") {
    return false;
  }
  // waiting_resume / waiting_job: only strict document intake (paste full text or file), no free chat
  if (state === "waiting_resume" || state === "waiting_job") {
    return false;
  }
  if (session.dialoguePhase) {
    return true;
  }
  return (
    state === "onboarding_candidate" ||
    state === "extracting_resume" ||
    state === "interviewing_candidate" ||
    state === "onboarding_manager" ||
    state === "extracting_job" ||
    state === "interviewing_manager" ||
    state === "candidate_profile_ready" ||
    state === "job_published" ||
    state === "waiting_candidate_decision" ||
    state === "waiting_manager_decision" ||
    state === "contact_shared"
  );
}

function shouldUsePersonalName(userId: number, marker: number): boolean {
  return Math.abs((userId * 31 + marker * 17) % 4) === 0;
}

function sanitizeUserName(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const firstToken = trimmed.split(/\s+/)[0];
  if (!firstToken) {
    return null;
  }
  return firstToken.slice(0, 24);
}

function sanitizeUserFacingText(text: string): string {
  return text
    .replace(/[—–]/g, ", ")
    .replace(/\s{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
