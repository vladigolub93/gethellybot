import { Logger } from "../config/logger";
import { ContactExchangeService } from "../decisions/contact-exchange.service";
import { DecisionService } from "../decisions/decision.service";
import { LlmClient } from "../ai/llm.client";
import { JobsRepository } from "../db/repositories/jobs.repo";
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
import { MatchingEngine } from "../matching/matching.engine";
import { NotificationEngine } from "../notifications/notification.engine";
import { ProfileSummaryService } from "../profiles/profile-summary.service";
import { UserSessionState } from "../shared/types/state.types";
import { NormalizedUpdate } from "../shared/types/telegram.types";
import { MatchStorageService } from "../storage/match-storage.service";
import { StateService } from "../state/state.service";
import { StatePersistenceService } from "../state/state-persistence.service";
import { TelegramClient } from "../telegram/telegram.client";
import { JobTechnicalSummaryV2 } from "../shared/types/job-profile.types";
import { getShortEmpathyLine } from "../shared/utils/empathy.util";
import {
  candidateInterviewPreparationMessage,
  documentUploadNotAllowedMessage,
  interviewAlreadyStartedMessage,
  interviewLanguageSupportMessage,
  managerInterviewPreparationMessage,
  missingInterviewContextMessage,
  processingDocumentMessage,
  quickFollowUpMessage,
  questionMessage,
  textOnlyReplyMessage,
  transcriptionFailedMessage,
  transcribingVoiceMessage,
  voiceTooLongMessage,
} from "../telegram/ui/messages";
import { maybeReact } from "../telegram/reactions/reaction.service";
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
    private readonly decisionService: DecisionService,
    private readonly contactExchangeService: ContactExchangeService,
    private readonly profileSummaryService: ProfileSummaryService,
    private readonly guardrailsService: HiringScopeGuardrailsService,
    private readonly dataDeletionService: DataDeletionService,
    private readonly jobsRepository: JobsRepository,
    private readonly llmClient: LlmClient,
    private readonly interviewIntentRouterService: InterviewIntentRouterService,
    private readonly normalizationService: NormalizationService,
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

    if (this.stateService.isDuplicateUpdate(session.userId, update.updateId)) {
      this.logger.debug("Duplicate update ignored", {
        userId: session.userId,
        updateId: update.updateId,
      });
      return;
    }

    switch (update.kind) {
      case "text":
        this.stateService.recordPreferredLanguageSample(
          session.userId,
          toPreferredLanguage(detectLanguageQuick(update.text)),
        );
        if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
          if (shouldRouteInterviewTextToGeneralFlow(update.text)) {
            await this.messageRouter.route(update, session);
            break;
          }
          await this.handleInterviewAnswer(
            {
              answerText: update.text,
              inputType: "text",
            },
            session,
            update.messageId,
          );
          break;
        }
        await this.messageRouter.route(
          {
            ...update,
            text: await this.normalizeGeneralText(update.text),
          },
          session,
        );
        break;
      case "callback":
        await this.callbackRouter.route(update, session);
        break;
      case "document":
        await this.handleDocumentUpdate(update);
        break;
      case "voice":
        await this.handleVoiceUpdate(update, session);
        break;
      case "unsupported_message":
        if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
          await this.telegramClient.sendMessage(update.chatId, textOnlyReplyMessage());
          break;
        }
        await this.telegramClient.sendMessage(update.chatId, "Unsupported message type. Use text input.");
        break;
      default:
        this.logger.warn("Unhandled update type");
    }

    this.stateService.markUpdateProcessed(session.userId, update.updateId);
    const latestSession = this.stateService.getSession(session.userId);
    if (latestSession) {
      await this.statePersistenceService.persistSession(latestSession);
    }
  }

  private async handleDocumentUpdate(
    update: Extract<NormalizedUpdate, { kind: "document" }>,
  ): Promise<void> {
    const session = this.stateService.getOrCreate(update.userId, update.chatId, update.username);

    if (isInterviewingState(session.state)) {
      await this.telegramClient.sendMessage(update.chatId, interviewAlreadyStartedMessage());
      return;
    }

    if (!isDocumentUploadAllowedState(session.state)) {
      await this.telegramClient.sendMessage(update.chatId, documentUploadNotAllowedMessage());
      return;
    }

    try {
      evaluateInterviewBootstrap(session);
    } catch (error) {
      await this.telegramClient.sendMessage(
        update.chatId,
        error instanceof Error ? error.message : "Cannot start interview from the current state.",
      );
      return;
    }

    await this.telegramClient.sendMessage(update.chatId, processingDocumentMessage());

    try {
      const fileBuffer = await this.telegramFileService.downloadFile(update.fileId);
      const extractedText = await this.documentService.extractText(
        fileBuffer,
        update.fileName,
        update.mimeType,
      );

      const bootstrap = await this.interviewEngine.bootstrapInterview(session, extractedText);
      if (bootstrap.nextState === "interviewing_candidate") {
        await this.telegramClient.sendMessage(update.chatId, candidateInterviewPreparationMessage());
      } else {
        await this.telegramClient.sendMessage(update.chatId, managerInterviewPreparationMessage());
      }
      if (bootstrap.answerInstruction) {
        await this.telegramClient.sendMessage(update.chatId, bootstrap.answerInstruction);
      }
      await this.telegramClient.sendMessage(update.chatId, interviewLanguageSupportMessage());
      await this.telegramClient.sendMessage(update.chatId, questionMessage(0, bootstrap.firstQuestion));
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

      await this.telegramClient.sendMessage(
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
      await this.telegramClient.sendMessage(session.chatId, missingInterviewContextMessage());
      return;
    }

    if (!session.interviewPlan) {
      await this.telegramClient.sendMessage(session.chatId, missingInterviewContextMessage());
      return;
    }

    const originalText = input.answerText.trim();
    const normalized = await this.normalizeInterviewInput(originalText);
    this.stateService.recordPreferredLanguageSample(
      session.userId,
      toPreferredLanguage(normalized.detected_language),
    );

    const currentQuestionText = resolveCurrentInterviewQuestionText(session);
    if (!currentQuestionText) {
      await this.telegramClient.sendMessage(session.chatId, missingInterviewContextMessage());
      return;
    }

    const intentDecision = await this.interviewIntentRouterService.classify({
      currentState: session.state,
      currentQuestionText,
      userMessage: normalized.english_text,
    });

    if (intentDecision.intent === "META" || intentDecision.intent === "CONTROL") {
      await this.telegramClient.sendMessage(
        session.chatId,
        this.buildInterviewMetaReply(
          intentDecision.meta_type,
          intentDecision.control_type,
          session,
          intentDecision.suggested_reply,
        ),
      );
      return;
    }

    if (intentDecision.intent === "OFFTOPIC") {
      const reply =
        session.preferredLanguage === "ru"
          ? "Давайте держаться темы интервью по найму. Ответьте на текущий вопрос, и я продолжу."
          : session.preferredLanguage === "uk"
            ? "Давайте триматися теми інтерв'ю з найму. Відповідайте на поточне питання, і я продовжу."
          : intentDecision.suggested_reply ||
            "Let us keep this focused on your interview. Please answer the current question to continue.";
      await this.telegramClient.sendMessage(session.chatId, reply);
      return;
    }

    if (!intentDecision.should_advance_interview) {
      await this.telegramClient.sendMessage(
        session.chatId,
        this.buildInterviewMetaReply(
          intentDecision.meta_type,
          intentDecision.control_type,
          session,
          intentDecision.suggested_reply,
        ),
      );
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
        await this.maybeSendInterviewReaction(session, originalText, sourceMessageId);
        await this.maybeSendCandidateEmpathyLine(session);
        await this.telegramClient.sendMessage(
          session.chatId,
          result.isFollowUp
            ? quickFollowUpMessage(result.questionText)
            : questionMessage(result.questionIndex, result.questionText),
        );
        return;
      }

      this.stateService.transition(session.userId, result.completedState);
      await this.telegramClient.sendMessage(session.chatId, result.completionMessage);
      if (result.followupMessage) {
        await this.telegramClient.sendMessage(session.chatId, result.followupMessage);
      }
      if (result.completedState === "job_profile_ready") {
        await this.publishManagerMatches(session.userId);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to process answer.";
      await this.telegramClient.sendMessage(session.chatId, message);
    }
  }

  private async handleInterviewVoice(
    update: Extract<NormalizedUpdate, { kind: "voice" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (update.durationSec > this.voiceMaxDurationSec) {
      await this.telegramClient.sendMessage(update.chatId, voiceTooLongMessage(this.voiceMaxDurationSec));
      return;
    }

    await this.telegramClient.sendMessage(update.chatId, transcribingVoiceMessage());

    try {
      const buffer = await this.telegramFileService.downloadFile(update.fileId);
      const transcription = await this.transcriptionClient.transcribeOgg(buffer);
      await this.handleInterviewAnswer(
        {
          answerText: transcription,
          inputType: "voice",
          telegramVoiceFileId: update.fileId,
          voiceDurationSec: update.durationSec,
          transcriptionStatus: "success",
        },
        session,
        update.messageId,
      );
    } catch (error) {
      this.logger.error("Voice transcription failed", {
        userId: update.userId,
        durationSec: update.durationSec,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.telegramClient.sendMessage(update.chatId, transcriptionFailedMessage());
    }
  }

  private async handleVoiceUpdate(
    update: Extract<NormalizedUpdate, { kind: "voice" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
      await this.handleInterviewVoice(update, session);
      return;
    }

    if (update.durationSec > this.voiceMaxDurationSec) {
      await this.telegramClient.sendMessage(update.chatId, voiceTooLongMessage(this.voiceMaxDurationSec));
      return;
    }

    await this.telegramClient.sendMessage(update.chatId, transcribingVoiceMessage());

    try {
      const buffer = await this.telegramFileService.downloadFile(update.fileId);
      const transcription = await this.transcriptionClient.transcribeOgg(buffer);
      const normalized = await this.normalizeInterviewInput(transcription);
      this.stateService.recordPreferredLanguageSample(update.userId, toPreferredLanguage(normalized.detected_language));
      await this.messageRouter.route(
        {
          kind: "text",
          updateId: update.updateId,
          messageId: update.messageId,
          chatId: update.chatId,
          userId: update.userId,
          username: update.username,
          text: normalized.english_text,
        },
        session,
      );
    } catch (error) {
      this.logger.error("Voice transcription failed outside interview", {
        userId: update.userId,
        durationSec: update.durationSec,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.telegramClient.sendMessage(update.chatId, transcriptionFailedMessage());
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
    await this.telegramClient.sendMessage(session.chatId, line);
    this.stateService.setLastEmpathyLine(session.userId, line);
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
      const normalized = await this.normalizationService.normalizeUserTextToEnglish(originalText);
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
      const normalized = await this.normalizationService.normalizeUserTextToEnglish(trimmed);
      const englishText = normalized.english_text.trim();
      return englishText || text;
    } catch {
      return text;
    }
  }

  private buildInterviewMetaReply(
    metaType: "timing" | "language" | "format" | "privacy" | "other" | null,
    controlType: "pause" | "resume" | "restart" | "help" | "stop" | null,
    session: UserSessionState,
    suggestedReply: string,
  ): string {
    if (session.preferredLanguage === "ru") {
      if (metaType === "timing") {
        return "Обычно это занимает пару минут. Я отправлю следующий вопрос сразу после обработки текста. Вам ничего дополнительно делать не нужно.";
      }
      if (metaType === "language") {
        return "Да, можно отвечать голосом на русском или украинском. Я расшифрую и продолжу. Пожалуйста, отвечайте подробно и с реальными примерами.";
      }
      if (metaType === "format") {
        return "Можно отвечать текстом или голосом. Подробные ответы помогают собрать точный профиль.";
      }
      if (metaType === "privacy") {
        return "Ваш профиль передается менеджеру только после вашего отклика, а контакты только после взаимного согласия.";
      }
      if (controlType === "restart") {
        return "Чтобы начать заново, используйте /start.";
      }
      if (controlType === "pause" || controlType === "stop") {
        return "Сейчас пауза вручную не нужна. Можете ответить на текущий вопрос или использовать /start.";
      }
      return "Сейчас идет интервью. Ответьте на текущий вопрос подробно текстом или голосом.";
    }
    if (session.preferredLanguage === "uk") {
      if (metaType === "timing") {
        return "Зазвичай це займає кілька хвилин. Я надішлю наступне питання одразу після обробки тексту. Вам нічого додатково робити не потрібно.";
      }
      if (metaType === "language") {
        return "Так, можна відповідати голосом російською або українською. Я розшифрую і продовжу. Будь ласка, відповідайте детально та з реальними прикладами.";
      }
      if (metaType === "format") {
        return "Можна відповідати текстом або голосом. Детальні відповіді допомагають зібрати точний профіль.";
      }
      if (metaType === "privacy") {
        return "Ваш профіль передається менеджеру тільки після вашого відгуку, а контакти тільки після взаємного підтвердження.";
      }
      if (controlType === "restart") {
        return "Щоб почати заново, використайте /start.";
      }
      if (controlType === "pause" || controlType === "stop") {
        return "Зараз пауза вручну не потрібна. Можете відповісти на поточне питання або використати /start.";
      }
      return "Зараз триває інтерв'ю. Відповідайте на поточне питання детально текстом або голосом.";
    }

    if (metaType === "timing") {
      return "Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.";
    }
    if (metaType === "language") {
      return "Yes, you can answer by voice in Russian or Ukrainian. I will transcribe it and continue. Please be detailed and use real examples.";
    }
    if (metaType === "privacy") {
      return "Your profile is only shared after you apply, and contacts are shared only after mutual approval.";
    }
    if (metaType === "format" || metaType === "other") {
      return "You can answer in text or voice. Detailed answers help me build an accurate profile.";
    }
    if (controlType === "restart") {
      return "Use /start to restart the flow.";
    }
    if (controlType === "pause" || controlType === "stop") {
      return "You can pause by returning later, or continue by answering the current question.";
    }
    return suggestedReply || "Please answer the current question so I can continue the interview.";
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

function shouldRouteInterviewTextToGeneralFlow(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  return (
    normalized === "/start" ||
    normalized.includes("delete my data") ||
    normalized.includes("remove my data") ||
    normalized.includes("delete account") ||
    normalized.includes("wipe my data")
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
