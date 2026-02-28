import { TelegramClient } from "../telegram/telegram.client";
import { buildManagerDecisionKeyboard } from "../telegram/ui/keyboards";
import {
  contactsSharedToManagerMessage,
  managerCandidateAppliedMessage,
} from "../telegram/ui/messages";
import { CandidateTechnicalSummaryV1 } from "../shared/types/candidate-summary.types";

export class ManagerNotifier {
  constructor(private readonly telegramClient: TelegramClient) {}

  async notifyCandidateApplied(params: {
    chatId: number;
    matchId: string;
    candidateUserId: number;
    score: number;
    candidateSummary: string;
    candidateTechnicalSummary?: CandidateTechnicalSummaryV1 | null;
    explanationMessage: string;
  }): Promise<void> {
    await this.telegramClient.sendUserMessage({
      source: "manager_notifier.candidate_applied",
      chatId: params.chatId,
      text: managerCandidateAppliedMessage({
        candidateUserId: params.candidateUserId,
        score: params.score,
        candidateSummary: params.candidateSummary,
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
