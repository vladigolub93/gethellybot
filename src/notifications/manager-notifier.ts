import { TelegramClient } from "../telegram/telegram.client";
import { buildManagerDecisionKeyboard } from "../telegram/ui/keyboards";
import {
  contactsSharedToManagerMessage,
  managerCandidateAppliedMessage,
} from "../telegram/ui/messages";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";
import { Logger } from "../config/logger";
import { buildManagerReviewReadModel } from "../core/matching/manager-review-read-model";
import {
  LegacyEvaluationInput,
  LegacyInterviewLifecycleInput,
  LegacyMatchLifecycleInput,
} from "../core/matching/lifecycle-normalizers";

export class ManagerNotifier {
  constructor(
    private readonly telegramClient: TelegramClient,
    private readonly logger?: Logger,
  ) {}

  async notifyCandidateApplied(params: {
    chatId: number;
    matchId: string;
    candidateUserId: number;
    score: number;
    candidateSummary: string;
    candidateTechnicalSummary?: CandidateTechnicalSummaryV1 | null;
    explanationMessage: string;
    matchLifecycle?: LegacyMatchLifecycleInput;
    interviewLifecycle?: LegacyInterviewLifecycleInput;
    evaluation?: LegacyEvaluationInput;
    verification?: {
      videoVerified?: boolean | null;
      contactShared?: boolean | null;
      identityVerified?: boolean | null;
      notes?: string[] | null;
    };
  }): Promise<void> {
    const managerReadModel = buildManagerReviewReadModel({
      candidate: {
        summary: params.candidateSummary,
        technicalSummary: params.candidateTechnicalSummary
          ? (params.candidateTechnicalSummary as unknown as Record<string, unknown>)
          : null,
      },
      match: {
        status: params.matchLifecycle?.status,
        candidateDecision: params.matchLifecycle?.candidateDecision,
        managerDecision: params.matchLifecycle?.managerDecision,
        contactShared: params.matchLifecycle?.contactShared,
        score: params.score,
        candidateSummary: params.candidateSummary,
        explanation: params.explanationMessage,
      },
      interview: params.interviewLifecycle,
      evaluation: params.evaluation,
      verification: params.verification,
    });

    this.logger?.debug("manager_package.normalized_built", {
      matchId: params.matchId,
      candidateUserId: params.candidateUserId,
      matchStatus: managerReadModel.matchStatus,
      interviewStatus: managerReadModel.interviewStatus,
      evaluationStatus: managerReadModel.evaluationStatus,
      isCandidateSentToManager: managerReadModel.isCandidateSentToManager,
    });

    if (managerReadModel.notes.length > 0) {
      this.logger?.debug("manager_package.normalization_notes", {
        matchId: params.matchId,
        candidateUserId: params.candidateUserId,
        notes: managerReadModel.notes,
        risks: managerReadModel.risks,
      });
    }

    await this.telegramClient.sendUserMessage({
      source: "manager_notifier.candidate_applied",
      chatId: params.chatId,
      text: managerCandidateAppliedMessage({
        candidateUserId: params.candidateUserId,
        score: params.score,
        candidateSummary: managerReadModel.candidateSummary || params.candidateSummary,
        candidateTechnicalSummary: params.candidateTechnicalSummary ?? null,
        explanationMessage: params.explanationMessage,
      }),
      replyMarkup: buildManagerDecisionKeyboard(params.matchId),
    });
  }

  async notifyContactsShared(chatId: number, candidateContact: string): Promise<void> {
    await this.telegramClient.sendUserMessage({
      source: "manager_notifier.contacts_shared",
      chatId,
      text: contactsSharedToManagerMessage(candidateContact),
    });
  }
}
