import { buildConversationReplyPrompt } from "../ai/prompts/conversation-reply.prompt";
import { buildRouterPrompt } from "../ai/prompts/router.prompt";
import { LlmClient } from "../ai/llm.client";
import { callJsonPromptSafe, callTextPromptSafe } from "../ai/llm.safe";
import { Logger } from "../config/logger";
import { HiringScopeGuardrailsService } from "../guardrails/hiring-scope-guardrails.service";
import { DataDeletionService } from "../privacy/data-deletion.service";
import { ProfileSummaryService } from "../profiles/profile-summary.service";
import { UserSessionState, UserState } from "../shared/types/state.types";
import { NormalizedUpdate } from "../shared/types/telegram.types";
import { parseRouterDecision, RouterDecision } from "./router-decision";
import { StateService } from "../state/state.service";
import { TelegramClient } from "../telegram/telegram.client";
import { buildContactRequestKeyboard, buildRoleSelectionKeyboard } from "../telegram/ui/keyboards";
import {
  contactRequestMessage,
  candidateOnboardingMessage,
  candidateInterviewCompletedMessage,
  candidateResumePrompt,
  managerOnboardingMessage,
  managerInterviewCompletedMessage,
  managerJobPrompt,
  profileUnavailableMessage,
  unsupportedInputMessage,
  welcomeMessage,
} from "../telegram/ui/messages";

export class MessageRouter {
  constructor(
    private readonly stateService: StateService,
    private readonly telegramClient: TelegramClient,
    private readonly profileSummaryService: ProfileSummaryService,
    private readonly guardrailsService: HiringScopeGuardrailsService,
    private readonly dataDeletionService: DataDeletionService,
    private readonly llmClient: LlmClient,
    private readonly logger: Logger,
  ) {}

  async route(update: Extract<NormalizedUpdate, { kind: "text" }>, session: UserSessionState): Promise<void> {
    const text = update.text.trim();

    if (isStartCommand(text)) {
      await this.restartFlow(update);
      return;
    }

    if (text === "/profile" || text.toLowerCase() === "show profile") {
      await this.sendProfileSummaryOrFallback(update, session);
      return;
    }

    const guardrailsBlocked = await this.applyGuardrails(update, session);
    if (guardrailsBlocked) {
      return;
    }

    const decision = await this.classifyTextUpdate(update, session);
    if (decision) {
      const handled = await this.applyRouterDecision(decision, update, session);
      if (handled) {
        return;
      }
    }

    if (session.state === "role_selection") {
      await this.telegramClient.sendMessage(update.chatId, welcomeMessage(), {
        replyMarkup: buildRoleSelectionKeyboard(),
      });
      return;
    }

    if (session.state === "waiting_resume") {
      if (isTimingQuestion(text)) {
        await this.telegramClient.sendMessage(
          update.chatId,
          "Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.",
        );
        return;
      }
      await this.telegramClient.sendMessage(update.chatId, candidateResumePrompt());
      return;
    }

    if (session.state === "waiting_job") {
      if (isTimingQuestion(text)) {
        await this.telegramClient.sendMessage(
          update.chatId,
          "Usually this takes a couple of minutes. I will send the next question as soon as the text is extracted. You do not need to do anything.",
        );
        return;
      }
      await this.telegramClient.sendMessage(update.chatId, managerJobPrompt());
      return;
    }

    if (session.state === "onboarding_candidate") {
      await this.telegramClient.sendMessage(update.chatId, candidateOnboardingMessage());
      return;
    }

    if (session.state === "onboarding_manager") {
      await this.telegramClient.sendMessage(update.chatId, managerOnboardingMessage());
      return;
    }

    if (session.state === "interviewing_candidate" || session.state === "interviewing_manager") {
      await this.telegramClient.sendMessage(
        update.chatId,
        "We are currently in the interview step.\nPlease answer the question above to continue.",
      );
      return;
    }

    if (session.state === "candidate_profile_ready") {
      await this.sendStateAwareReply(update, session);
      return;
    }

    if (session.state === "job_profile_ready") {
      await this.sendStateAwareReply(update, session);
      return;
    }

    if (
      session.state === "job_published" ||
      session.state === "waiting_candidate_decision" ||
      session.state === "waiting_manager_decision" ||
      session.state === "contact_shared"
    ) {
      await this.sendStateAwareReply(update, session);
      return;
    }

    await this.telegramClient.sendMessage(update.chatId, unsupportedInputMessage());
  }

  private async classifyTextUpdate(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<RouterDecision | null> {
    const currentQuestion = resolveCurrentQuestionContext(session);
    const askedCount = session.answers?.length ?? 0;
    const totalQuestions = session.interviewPlan?.questions.length ?? 0;
    const profileSnapshotSummary = this.buildProfileSnapshotSummary(session);

    const prompt = buildRouterPrompt({
      userRole: session.role ?? null,
      currentState: session.state,
      lastBotMessage: null,
      currentQuestionId: currentQuestion?.id ?? null,
      lastQuestionText: currentQuestion?.text ?? null,
      interviewProgress:
        totalQuestions > 0
          ? {
              askedCount,
              remainingCount: Math.max(totalQuestions - askedCount, 0),
            }
          : null,
      userMessageText: update.text.trim(),
      updateType: "text",
      callbackData: null,
      documentMeta: null,
      voiceMeta: null,
      profileSnapshotSummary,
    });

    try {
      const safe = await callJsonPromptSafe<Record<string, unknown>>({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 260,
        promptName: "router_decision",
        schemaHint:
          "Router decision JSON with intent, next_action, confidence, reason_short, needs_clarification, clarifying_question.",
      });
      if (!safe.ok) {
        throw new Error(`router_decision_failed:${safe.error_code}`);
      }
      const raw = JSON.stringify(safe.data);
      const parsed = parseRouterDecision(raw);
      this.logger.debug("Router decision produced", {
        userId: session.userId,
        state: session.state,
        intent: parsed.intent,
        nextAction: parsed.next_action,
        confidence: parsed.confidence,
      });
      return parsed;
    } catch (error) {
      this.logger.warn("Router decision failed, using deterministic fallback", {
        userId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      return null;
    }
  }

  private async applyRouterDecision(
    decision: RouterDecision,
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<boolean> {
    switch (decision.next_action) {
      case "restart_flow":
        await this.restartFlow(update);
        return true;
      case "show_profile_summary":
        await this.sendProfileSummaryOrFallback(update, session);
        return true;
      case "ask_clarifying_question":
        await this.telegramClient.sendMessage(
          update.chatId,
          decision.clarifying_question ?? "Could you clarify what you want to do next?",
        );
        return true;
      case "answer_brief_and_return":
      case "redirect_to_hiring_context":
      case "publish_job":
      case "run_matching":
        await this.sendStateAwareReply(update, session);
        return true;
      case "pause_flow":
        await this.telegramClient.sendMessage(
          update.chatId,
          "Pause is not available yet in this MVP. You can continue or use /start.",
        );
        return true;
      case "resume_flow":
        await this.telegramClient.sendMessage(
          update.chatId,
          "Resume is not needed right now. Continue the current flow or use /start.",
        );
        return true;
      case "ack_and_wait":
        await this.telegramClient.sendMessage(update.chatId, getStateFallbackMessage(session.state));
        return true;
      default:
        return false;
    }
  }

  private async restartFlow(update: Extract<NormalizedUpdate, { kind: "text" }>): Promise<void> {
    this.stateService.reset(update.userId, update.chatId, update.username);
    await this.telegramClient.sendMessage(update.chatId, welcomeMessage(), {
      replyMarkup: buildRoleSelectionKeyboard(),
    });
    await this.telegramClient.sendMessage(update.chatId, contactRequestMessage(), {
      replyMarkup: buildContactRequestKeyboard(),
    });
  }

  private async sendProfileSummaryOrFallback(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    if (session.role === "candidate" && session.candidateProfile) {
      await this.telegramClient.sendMessage(
        update.chatId,
        this.profileSummaryService.formatCandidateSummary(session.candidateProfile),
      );
      return;
    }
    if (session.role === "manager" && session.jobProfile) {
      await this.telegramClient.sendMessage(
        update.chatId,
        this.profileSummaryService.formatJobSummary(session.jobProfile),
      );
      return;
    }
    await this.telegramClient.sendMessage(update.chatId, profileUnavailableMessage());
  }

  private buildProfileSnapshotSummary(session: UserSessionState): string | null {
    if (session.role === "candidate" && session.candidateProfile) {
      return this.profileSummaryService.formatCandidateSummary(session.candidateProfile).slice(0, 700);
    }
    if (session.role === "manager" && session.jobProfile) {
      return this.profileSummaryService.formatJobSummary(session.jobProfile).slice(0, 700);
    }
    return null;
  }

  private async sendStateAwareReply(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<void> {
    const fallback = getStateFallbackMessage(session.state);
    const nextStep = getStateNextStep(session.state);
    const prompt = buildConversationReplyPrompt({
      role: session.role,
      state: session.state,
      userText: update.text.trim(),
      nextStep,
      profileReady: Boolean(session.candidateProfile || session.jobProfile),
    });

    try {
      const safe = await callTextPromptSafe({
        llmClient: this.llmClient,
        logger: this.logger,
        prompt,
        maxTokens: 180,
        promptName: "conversation_reply",
      });
      const reply = safe.ok ? safe.text : fallback;
      await this.telegramClient.sendMessage(update.chatId, reply || fallback);
    } catch (error) {
      this.logger.warn("State-aware chat reply failed, fallback used", {
        userId: session.userId,
        state: session.state,
        error: error instanceof Error ? error.message : "Unknown error",
      });
      await this.telegramClient.sendMessage(update.chatId, fallback);
    }
  }

  private async applyGuardrails(
    update: Extract<NormalizedUpdate, { kind: "text" }>,
    session: UserSessionState,
  ): Promise<boolean> {
    const decision = await this.guardrailsService.evaluate({
      userMessage: update.text.trim(),
      userRole: session.role,
      currentState: session.state,
      userId: session.userId,
    });

    if (decision.action === "data_deletion_request") {
      const result = await this.dataDeletionService.requestDeletion({
        telegramUserId: session.userId,
        telegramUsername: session.username,
        reason: update.text.trim().slice(0, 160),
      });
      const reply = [decision.safe_reply, result.confirmationMessage]
        .filter(Boolean)
        .join("\n");
      await this.telegramClient.sendMessage(update.chatId, reply);
      return true;
    }

    if (decision.action === "privacy_block") {
      await this.telegramClient.sendMessage(update.chatId, decision.safe_reply);
      return true;
    }

    if (!decision.allowed || decision.response_style === "redirect" || decision.response_style === "refuse") {
      await this.telegramClient.sendMessage(update.chatId, decision.safe_reply);
      return true;
    }

    return false;
  }
}

function isStartCommand(text: string): boolean {
  return /^\/start(?:\s|$)/i.test(text.trim());
}

function resolveCurrentQuestionContext(
  session: UserSessionState,
): { id: string; text: string } | null {
  const plan = session.interviewPlan;
  const index = session.currentQuestionIndex;
  if (!plan || typeof index !== "number" || index < 0 || index >= plan.questions.length) {
    return null;
  }
  const question = plan.questions[index];
  return { id: question.id, text: question.question };
}

function getStateFallbackMessage(state: UserState): string {
  if (state === "onboarding_candidate") {
    return candidateOnboardingMessage();
  }
  if (state === "onboarding_manager") {
    return managerOnboardingMessage();
  }
  if (state === "waiting_resume") {
    return candidateResumePrompt();
  }
  if (state === "waiting_job") {
    return managerJobPrompt();
  }
  if (state === "candidate_profile_ready") {
    return candidateInterviewCompletedMessage();
  }
  if (state === "job_profile_ready") {
    return managerInterviewCompletedMessage();
  }
  if (state === "job_published") {
    return "Your job is published. You can wait for candidate actions or use /start for a new flow.";
  }
  if (state === "waiting_candidate_decision") {
    return "You have a pending opportunity decision. Use the buttons on the latest card.";
  }
  if (state === "waiting_manager_decision") {
    return "You have a pending candidate decision. Use the buttons on the latest card.";
  }
  if (state === "contact_shared") {
    return "Contacts were already shared. Use /start to begin another interview.";
  }
  return unsupportedInputMessage();
}

function getStateNextStep(state: UserState): string {
  if (state === "onboarding_candidate") {
    return "Ask user to send resume as PDF or DOCX, or paste full text.";
  }
  if (state === "onboarding_manager") {
    return "Ask user to send job description as PDF or DOCX, or paste full text.";
  }
  if (state === "waiting_resume") {
    return "Ask user to upload resume as PDF or DOCX now.";
  }
  if (state === "waiting_job") {
    return "Ask user to upload job description as PDF or DOCX now.";
  }
  if (state === "candidate_profile_ready") {
    return "Tell user interview is complete and they can use /start for a new interview.";
  }
  if (state === "job_profile_ready") {
    return "Tell user intake is complete and they can use /start for a new interview.";
  }
  if (state === "job_published") {
    return "Tell user job is published and to wait for candidate actions.";
  }
  if (state === "waiting_candidate_decision") {
    return "Tell user to choose Apply or Reject on the latest opportunity card.";
  }
  if (state === "waiting_manager_decision") {
    return "Tell user to choose Accept or Reject on the latest candidate card.";
  }
  if (state === "contact_shared") {
    return "Tell user contacts are shared and /start can begin a new flow.";
  }
  return "Guide user to use /start.";
}

function isTimingQuestion(text: string): boolean {
  const normalized = text.trim().toLowerCase();
  if (!normalized) {
    return false;
  }
  return (
    normalized.includes("how long") ||
    normalized.includes("when") ||
    normalized.includes("сколько") ||
    normalized.includes("когда")
  );
}
