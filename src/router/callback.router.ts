import {
  CALLBACK_CANDIDATE_APPLY_PREFIX,
  CALLBACK_CANDIDATE_ASK_PREFIX,
  CALLBACK_CANDIDATE_REJECT_PREFIX,
  CALLBACK_MANAGER_ACCEPT_PREFIX,
  CALLBACK_MANAGER_ASK_PREFIX,
  CALLBACK_MANAGER_REJECT_PREFIX,
  CALLBACK_ROLE_BACK,
  CALLBACK_ROLE_CANDIDATE,
  CALLBACK_ROLE_LEARN_MORE,
  CALLBACK_ROLE_MANAGER,
} from "../shared/constants";
import { ContactExchangeService } from "../decisions/contact-exchange.service";
import { DecisionService } from "../decisions/decision.service";
import { NotificationEngine } from "../notifications/notification.engine";
import { UserSessionState } from "../shared/types/state.types";
import { NormalizedUpdate } from "../shared/types/telegram.types";
import { StateService } from "../state/state.service";
import { StatePersistenceService } from "../state/state-persistence.service";
import { TelegramClient } from "../telegram/telegram.client";
import {
  buildRoleLearnMoreKeyboard,
  buildRoleSelectionKeyboard,
} from "../telegram/ui/keyboards";
import {
  askQuestionNotImplementedMessage,
  candidateOnboardingMessage,
  candidateAppliedAcknowledgement,
  candidateRejectedAcknowledgement,
  onboardingLearnHowItWorksMessage,
  onboardingPrivacyNoteMessage,
  welcomeMessage,
  managerAcceptedAcknowledgement,
  managerOnboardingMessage,
  managerRejectedAcknowledgement,
  candidateResumePrompt,
  managerJobPrompt,
} from "../telegram/ui/messages";

export class CallbackRouter {
  constructor(
    private readonly stateService: StateService,
    private readonly statePersistenceService: StatePersistenceService,
    private readonly telegramClient: TelegramClient,
    private readonly decisionService: DecisionService,
    private readonly notificationEngine: NotificationEngine,
    private readonly contactExchangeService: ContactExchangeService,
  ) {}

  async route(
    update: Extract<NormalizedUpdate, { kind: "callback" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (update.data.startsWith(CALLBACK_CANDIDATE_APPLY_PREFIX)) {
      await this.handleCandidateApply(update);
      return;
    }

    if (update.data.startsWith(CALLBACK_CANDIDATE_REJECT_PREFIX)) {
      await this.handleCandidateReject(update);
      return;
    }

    if (update.data.startsWith(CALLBACK_CANDIDATE_ASK_PREFIX)) {
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Not implemented yet");
      await this.telegramClient.sendMessage(update.chatId, askQuestionNotImplementedMessage());
      return;
    }

    if (update.data.startsWith(CALLBACK_MANAGER_ACCEPT_PREFIX)) {
      await this.handleManagerAccept(update);
      return;
    }

    if (update.data.startsWith(CALLBACK_MANAGER_REJECT_PREFIX)) {
      await this.handleManagerReject(update);
      return;
    }

    if (update.data.startsWith(CALLBACK_MANAGER_ASK_PREFIX)) {
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Not implemented yet");
      await this.telegramClient.sendMessage(update.chatId, askQuestionNotImplementedMessage());
      return;
    }

    if (update.data === CALLBACK_ROLE_CANDIDATE) {
      if (session.state !== "role_selection") {
        await this.telegramClient.answerCallbackQuery(
          update.callbackQueryId,
          "Please use /start to begin a new flow.",
        );
        return;
      }
      this.stateService.setRole(update.userId, "candidate");
      this.stateService.transition(update.userId, "onboarding_candidate");
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Candidate flow selected");
      await this.telegramClient.sendMessage(update.chatId, candidateOnboardingMessage());
      await this.telegramClient.sendMessage(update.chatId, onboardingPrivacyNoteMessage());
      this.stateService.transition(update.userId, "waiting_resume");
      this.stateService.setOnboardingCompleted(update.userId, true);
      await this.telegramClient.sendMessage(update.chatId, candidateResumePrompt());
      return;
    }

    if (update.data === CALLBACK_ROLE_MANAGER) {
      if (session.state !== "role_selection") {
        await this.telegramClient.answerCallbackQuery(
          update.callbackQueryId,
          "Please use /start to begin a new flow.",
        );
        return;
      }
      this.stateService.setRole(update.userId, "manager");
      this.stateService.transition(update.userId, "onboarding_manager");
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Hiring flow selected");
      await this.telegramClient.sendMessage(update.chatId, managerOnboardingMessage());
      await this.telegramClient.sendMessage(update.chatId, onboardingPrivacyNoteMessage());
      this.stateService.transition(update.userId, "waiting_job");
      this.stateService.setOnboardingCompleted(update.userId, true);
      await this.telegramClient.sendMessage(update.chatId, managerJobPrompt());
      return;
    }

    if (update.data === CALLBACK_ROLE_LEARN_MORE) {
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Overview");
      await this.telegramClient.sendMessage(update.chatId, onboardingLearnHowItWorksMessage(), {
        replyMarkup: buildRoleLearnMoreKeyboard(),
      });
      return;
    }

    if (update.data === CALLBACK_ROLE_BACK) {
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Back");
      await this.telegramClient.sendMessage(update.chatId, welcomeMessage(), {
        replyMarkup: buildRoleSelectionKeyboard(),
      });
      return;
    }

    await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Unsupported action");
  }

  private async handleCandidateApply(update: Extract<NormalizedUpdate, { kind: "callback" }>): Promise<void> {
    const matchId = update.data.slice(CALLBACK_CANDIDATE_APPLY_PREFIX.length);
    try {
      const match = await this.decisionService.candidateApply(matchId, update.userId);
      await this.notificationEngine.notifyManagerCandidateApplied(match);
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Applied");
      await this.telegramClient.sendMessage(update.chatId, candidateAppliedAcknowledgement());
    } catch (error) {
      await this.telegramClient.answerCallbackQuery(
        update.callbackQueryId,
        error instanceof Error ? error.message : "Failed",
      );
    }
  }

  private async handleCandidateReject(update: Extract<NormalizedUpdate, { kind: "callback" }>): Promise<void> {
    const matchId = update.data.slice(CALLBACK_CANDIDATE_REJECT_PREFIX.length);
    try {
      await this.decisionService.candidateReject(matchId, update.userId);
      await this.safeTransitionToProfileReady(update.userId);
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Rejected");
      await this.telegramClient.sendMessage(update.chatId, candidateRejectedAcknowledgement());
    } catch (error) {
      await this.telegramClient.answerCallbackQuery(
        update.callbackQueryId,
        error instanceof Error ? error.message : "Failed",
      );
    }
  }

  private async handleManagerAccept(update: Extract<NormalizedUpdate, { kind: "callback" }>): Promise<void> {
    const matchId = update.data.slice(CALLBACK_MANAGER_ACCEPT_PREFIX.length);
    try {
      const match = await this.decisionService.managerAccept(matchId, update.userId);
      const contacts = await this.contactExchangeService.prepareExchange(match);
      if (!contacts.ready) {
        await this.telegramClient.answerCallbackQuery(
          update.callbackQueryId,
          "Contact sharing is pending",
        );
        return;
      }
      await this.notificationEngine.notifyContactsShared(
        match,
        contacts.managerContact,
        contacts.candidateContact,
      );
      await this.decisionService.markContactShared(match.id, update.userId);
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Accepted");
      await this.telegramClient.sendMessage(update.chatId, managerAcceptedAcknowledgement());
    } catch (error) {
      await this.telegramClient.answerCallbackQuery(
        update.callbackQueryId,
        error instanceof Error ? error.message : "Failed",
      );
    }
  }

  private async handleManagerReject(update: Extract<NormalizedUpdate, { kind: "callback" }>): Promise<void> {
    const matchId = update.data.slice(CALLBACK_MANAGER_REJECT_PREFIX.length);
    try {
      const match = await this.decisionService.managerReject(matchId, update.userId);
      await this.notificationEngine.notifyManagerRejected(match);
      await this.safeTransitionManagerAfterReject(update.userId);
      await this.telegramClient.answerCallbackQuery(update.callbackQueryId, "Rejected");
      await this.telegramClient.sendMessage(update.chatId, managerRejectedAcknowledgement());
    } catch (error) {
      await this.telegramClient.answerCallbackQuery(
        update.callbackQueryId,
        error instanceof Error ? error.message : "Failed",
      );
    }
  }

  private async safeTransitionToProfileReady(userId: number): Promise<void> {
    const session = this.stateService.getSession(userId);
    if (!session || session.state === "candidate_profile_ready") {
      return;
    }
    try {
      this.stateService.transition(userId, "candidate_profile_ready");
      const latest = this.stateService.getSession(userId);
      if (latest) {
        await this.statePersistenceService.persistSession(latest);
      }
    } catch {
      return;
    }
  }

  private async safeTransitionManagerAfterReject(userId: number): Promise<void> {
    const session = this.stateService.getSession(userId);
    if (!session || session.state === "job_published") {
      return;
    }
    try {
      this.stateService.transition(userId, "job_published");
      const latest = this.stateService.getSession(userId);
      if (latest) {
        await this.statePersistenceService.persistSession(latest);
      }
    } catch {
      return;
    }
  }
}
