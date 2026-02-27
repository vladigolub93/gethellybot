import { Logger } from "../config/logger";
import { ContactExchangeService } from "../decisions/contact-exchange.service";
import { DecisionService } from "../decisions/decision.service";
import { LlmClient } from "../ai/llm.client";
import { JobsRepository } from "../db/repositories/jobs.repo";
import { HiringScopeGuardrailsService } from "../guardrails/hiring-scope-guardrails.service";
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
  interviewOngoingReminderMessage,
  managerInterviewPreparationMessage,
  missingInterviewContextMessage,
  processingDocumentMessage,
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
        if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
          if (shouldRouteInterviewTextToGeneralFlow(update.text)) {
            await this.messageRouter.route(update, session);
            break;
          }
          if (isLikelyInterviewInterruption(update.text)) {
            await this.telegramClient.sendMessage(update.chatId, interviewOngoingReminderMessage());
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
        await this.messageRouter.route(update, session);
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
      inputType: "text" | "voice";
      telegramVoiceFileId?: string;
      voiceDurationSec?: number;
      transcriptionStatus?: "success" | "failed";
    },
    session: UserSessionState,
    sourceMessageId?: number,
  ): Promise<void> {
    if (!session.interviewPlan) {
      await this.telegramClient.sendMessage(session.chatId, missingInterviewContextMessage());
      return;
    }

    try {
      const result = await this.interviewEngine.submitAnswer(session, input);

      if (result.kind === "next_question") {
        await this.maybeSendInterviewReaction(session, input.answerText, sourceMessageId);
        await this.maybeSendCandidateEmpathyLine(session);
        await this.telegramClient.sendMessage(
          session.chatId,
          questionMessage(result.questionIndex, result.questionText),
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
      await this.messageRouter.route(
        {
          kind: "text",
          updateId: update.updateId,
          messageId: update.messageId,
          chatId: update.chatId,
          userId: update.userId,
          username: update.username,
          text: transcription,
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

function isLikelyInterviewInterruption(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  const interruptionPhrases = [
    "what next",
    "what now",
    "help",
    "hello",
    "hi",
    "can i ask",
    "wait",
    "stop",
    "pause",
    "why",
  ];

  if (interruptionPhrases.some((phrase) => normalized.includes(phrase))) {
    return true;
  }

  return normalized.length <= 3 && normalized === "?";
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
